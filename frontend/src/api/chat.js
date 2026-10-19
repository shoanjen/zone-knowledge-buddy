import { fetchEventSource } from '@microsoft/fetch-event-source'
import http from './http'
import { TOKEN_KEY } from './http'

export async function listSessions() {
  const { data } = await http.get('/chat/sessions')
  return data // { items: [{ id, title, created_at }] }
}

export async function getSession(id) {
  const { data } = await http.get(`/chat/sessions/${id}`)
  return data // { id, messages: [{ id, role, content, citations, created_at }] }
}

/**
 * 规格§10.1 SSE 事件协议：meta / token / citations / done / error。
 * 返回 { controller, done }：controller 供 abort；done 在流结束（含出错终止）后 resolve。
 */
export function streamChat(body, handlers) {
  const controller = new AbortController()
  const dispatch = (event, payload) => {
    if (event === 'meta') handlers.meta?.(payload)
    else if (event === 'token') handlers.token?.(payload)
    else if (event === 'citations') handlers.citations?.(payload)
    else if (event === 'done') handlers.done?.(payload)
    else if (event === 'error') handlers.error?.(payload)
  }
  const done = fetchEventSource('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) || ''}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
    openWhenHidden: true,
    async onopen(response) {
      if (response.ok && (response.headers.get('content-type') || '').includes('text/event-stream')) {
        return
      }
      if (response.status === 401) {
        handlers.error?.({ code: 'AUTH_INVALID', message: '登录已失效，请重新登录' })
        throw new Error('unauthorized')
      }
      throw new Error(`连接失败：HTTP ${response.status}`)
    },
    onmessage(ev) {
      let payload = {}
      try {
        payload = JSON.parse(ev.data || '{}')
      } catch {
        payload = { raw: ev.data }
      }
      dispatch(ev.event || 'message', payload)
    },
    onerror(err) {
      // 主动 abort 不算错误；其余错误回调一次并抛出以阻止自动重连
      if (err?.name !== 'AbortError') {
        handlers.error?.({ code: 'SSE_ERROR', message: `连接中断：${err?.message || err}` })
        throw err
      }
    },
  }).catch(() => {})
  return { controller, done }
}

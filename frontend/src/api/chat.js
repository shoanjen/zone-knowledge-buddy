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

export async function deleteSession(id) {
  await http.delete(`/chat/sessions/${id}`)
}

export async function batchDeleteSessions(ids) {
  const { data } = await http.post('/chat/sessions/batch-delete', { ids })
  return data // { deleted: n }
}

/**
 * 规格§10.1 SSE 事件协议：meta / token / citations / done / error。
 * 返回 { controller, done }：controller 供 abort；done 在流结束（含出错终止）后 resolve。
 */
export function streamChat(body, handlers) {
  const controller = new AbortController()
  let sawDone = false
  let errored = false
  const dispatch = (event, payload) => {
    if (event === 'meta') handlers.meta?.(payload)
    else if (event === 'token') handlers.token?.(payload)
    else if (event === 'citations') handlers.citations?.(payload)
    else if (event === 'done') {
      sawDone = true
      handlers.done?.(payload)
    } else if (event === 'error') {
      errored = true
      handlers.error?.(payload)
    }
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
        errored = true
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem('kb_username')
        handlers.error?.({ code: 'AUTH_INVALID', message: '登录已失效，请重新登录' })
        if (!window.location.pathname.startsWith('/login')) window.location.href = '/login'
        throw new Error('unauthorized')
      }
      const detail = await response.text().catch(() => '')
      errored = true
      handlers.error?.({ code: 'SSE_HTTP', message: `连接失败：HTTP ${response.status}${detail ? ` ${detail.slice(0, 120)}` : ''}` })
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
    onclose() {
      // 服务端干净关闭但未发 done：视为断流，必须让用户看到错误态（§13.4）
      if (!controller.signal.aborted && !sawDone && !errored) {
        handlers.error?.({ code: 'SSE_CLOSED', message: '连接已断开，回答可能不完整' })
      }
    },
    onerror(err) {
      // 主动 abort 不算错误；其余错误回调一次并抛出以阻止自动重连
      if (err?.name !== 'AbortError') {
        errored = true
        handlers.error?.({ code: 'SSE_ERROR', message: `连接中断：${err?.message || err}` })
        throw err
      }
    },
  }).catch(() => {})
  return { controller, done }
}

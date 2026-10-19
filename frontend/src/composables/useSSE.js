import { getCurrentInstance, onUnmounted } from 'vue'
import { streamChat } from '../api/chat'

/**
 * SSE 生命周期封装（规格§13.4）：持有 AbortController，切会话/卸载即 abort。
 */
export function useSSE() {
  let handle = null
  const close = () => {
    if (handle) {
      handle.controller.abort()
      handle = null
    }
  }
  const open = (body, handlers) => {
    close()
    handle = streamChat(body, handlers)
    return handle
  }
  if (getCurrentInstance()) onUnmounted(close)
  return { open, close }
}

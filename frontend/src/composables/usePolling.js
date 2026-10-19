import { getCurrentInstance, onUnmounted } from 'vue'

/**
 * 通用轮询（规格§13.2：解析中/进行中任务 3s 轮询，无进行中项即停由调用方控制）。
 * 组件内使用时随组件卸载自动停止；store 内使用（无组件实例）时由调用方负责 stop。
 */
export function usePolling(fn, intervalMs = 3000) {
  let timer = null
  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }
  const start = () => {
    if (timer) return
    timer = setInterval(() => {
      try {
        const ret = fn()
        if (ret && typeof ret.catch === 'function') ret.catch(() => {})
      } catch {
        // 单次轮询失败不打断后续轮询
      }
    }, intervalMs)
  }
  if (getCurrentInstance()) onUnmounted(stop)
  return { start, stop }
}

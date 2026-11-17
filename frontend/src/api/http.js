// 规格§13.4：axios 实例 + 统一错误映射（§2.4 错误码表）
import axios from 'axios'
import { ElMessage } from 'element-plus'

export const TOKEN_KEY = 'kb_token'
export const USERNAME_KEY = 'kb_username'

const CODE_FALLBACK = {
  AUTH_INVALID: '登录已失效，请重新登录',
  FORBIDDEN: '无权访问',
  NOT_FOUND: '资源不存在',
  VALIDATION: '请求参数校验失败',
  UPLOAD_TOO_LARGE: '文件超出大小上限',
  UPLOAD_FORMAT: '不支持的文件格式',
  URL_INVALID: 'URL 不合法',
  PARSE_FAILED: '解析失败',
  PARSE_UNSUPPORTED: '暂不支持该格式',
  DOC_STATE: '文档当前状态不允许该操作',
  TASK_STATE: '任务当前状态不允许该操作',
  EMBEDDING_LOCKED: '向量模型已锁定，需清空全部文档后重建',
  PROVIDER_UNREACHABLE: '模型服务不可达',
  PROVIDER_CONFIG: '模型供应商配置不完整',
  LLM_JSON_INVALID: '模型输出异常，请重试或切换模型',
  INTERNAL: '服务内部错误',
}

const http = axios.create({ baseURL: '/api', timeout: 120000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error.response?.status
    let body = error.response?.data
    // blob 响应里的错误体也需要展示（报告下载/数据导出）
    if (body instanceof Blob) {
      try {
        body = JSON.parse(await body.text())
      } catch {
        body = null
      }
    }
    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USERNAME_KEY)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      } else {
        // 登录页内的 401 = 账号密码错误（AUTH_INVALID），必须提示；
        // 其他场景的会话过期提示由跳转后的登录页承担，避免重复弹窗。
        ElMessage.error(body?.message || CODE_FALLBACK[body?.code] || '用户名或密码错误')
      }
      return Promise.reject(error)
    }
    const message =
      body?.message || CODE_FALLBACK[body?.code] || `请求失败（${status ?? '网络错误'}）`
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default http

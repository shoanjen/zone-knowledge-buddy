import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { listSessions, getSession, batchDeleteSessions } from '../api/chat'
import { useSSE } from '../composables/useSSE'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [],
    currentSessionId: null,
    // { id, role, content, citations: [], streaming?: true }
    messages: [],
    streaming: false,
    // 回答阶段：retrieving 检索中 → thinking 思考中 → streaming 生成中；非流式为 null
    phase: null,
    provider: null,
    retrieved: [],
    error: null,
    sse: null,
    topK: 5,
    // 输入框草稿（放 store 里以便新会话时一并清空）
    draft: '',
    // 新会话重置序号：ChatStream 监听它来聚焦输入框
    sessionSeq: 0,
  }),
  actions: {
    async loadSessions() {
      const data = await listSessions()
      this.sessions = data.items
    },
    async loadSession(id) {
      this.abort()
      const data = await getSession(id)
      this.currentSessionId = id
      this.messages = data.messages.map((m) => ({ ...m, citations: m.citations || [] }))
    },
    newSession() {
      this.abort()
      this.currentSessionId = null
      this.messages = []
      this.error = null
      this.provider = null
      this.retrieved = []
      this.draft = ''
      this.sessionSeq += 1
      // 空态下点击毫无可见变化，会被误认为按钮失效，给显式反馈
      ElMessage.success('已开启新会话')
    },
    /**
     * 删除会话（单条传 [id]，批量传多个）。
     * 若包含当前会话：先中止流式并回到欢迎页。
     */
    async removeSessions(ids) {
      if (!ids.length) return 0
      const hitsCurrent = !!this.currentSessionId && ids.includes(this.currentSessionId)
      if (hitsCurrent) this.abort()
      await batchDeleteSessions(ids)
      if (hitsCurrent) {
        this.currentSessionId = null
        this.messages = []
        this.error = null
        this.provider = null
        this.retrieved = []
        this.draft = ''
      }
      this.loadSessions().catch(() => {})
      return ids.length
    },
    abort() {
      this.sse?.close()
      this.sse = null
      this.streaming = false
      this.phase = null
    },
    async send(text) {
      const message = (text || '').trim()
      if (!message || this.streaming) return
      this.streaming = true
      this.phase = 'retrieving'
      this.error = null
      this.retrieved = []
      const assistant = { id: '', role: 'assistant', content: '', citations: [] }
      this.messages.push({ id: '', role: 'user', content: message, citations: [] }, assistant)
      let finished = false
      const sse = useSSE()
      this.sse = sse
      const { done } = sse.open(
        { session_id: this.currentSessionId, message, top_k: this.topK },
        {
          meta: (p) => {
            this.currentSessionId = p.session_id
            this.provider = p.provider
            this.retrieved = p.retrieved || []
            this.phase = 'thinking'
          },
          token: (p) => {
            if (this.phase !== 'streaming') this.phase = 'streaming'
            assistant.content += p.delta || ''
          },
          citations: (p) => {
            assistant.citations = p.citations || []
          },
          done: () => {
            finished = true
            this.loadSessions().catch(() => {})
          },
          error: (p) => {
            if (finished) return
            finished = true
            this.error = p
            ElMessage.error(p?.message || '问答失败')
          },
        },
      )
      await done
      this.streaming = false
      this.phase = null
      this.sse = null
    },
  },
})

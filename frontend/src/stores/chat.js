import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { listSessions, getSession } from '../api/chat'
import { useSSE } from '../composables/useSSE'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [],
    currentSessionId: null,
    // { id, role, content, citations: [], streaming?: true }
    messages: [],
    streaming: false,
    provider: null,
    retrieved: [],
    error: null,
    sse: null,
    topK: 5,
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
    },
    abort() {
      this.sse?.close()
      this.sse = null
      this.streaming = false
    },
    async send(text) {
      const message = (text || '').trim()
      if (!message || this.streaming) return
      this.streaming = true
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
          },
          token: (p) => {
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
      this.sse = null
    },
  },
})

import { defineStore } from 'pinia'
import * as api from '../api/tasks'
import { usePolling } from '../composables/usePolling'

// paused 等待用户确认，不轮询（规格§13.2：进行中任务 3s 轮询）
const ACTIVE = ['pending', 'planning', 'running', 'reflecting']

export const useTasksStore = defineStore('tasks', {
  state: () => ({
    list: [],
    total: 0,
    page: 1,
    pageSize: 20,
    filterStatus: '',
    filterType: '',
    current: null,
    loading: false,
    poller: null,
  }),
  getters: {
    hasActive: (s) => s.list.some((t) => ACTIVE.includes(t.status)),
  },
  actions: {
    async fetchList(silent = false) {
      if (!silent) this.loading = true
      try {
        const data = await api.listTasks({
          page: this.page,
          page_size: this.pageSize,
          status: this.filterStatus || undefined,
          type: this.filterType || undefined,
        })
        this.list = data.items
        this.total = data.total
      } finally {
        if (!silent) this.loading = false
        this.ensurePolling()
      }
    },
    async fetchDetail(id) {
      this.current = await api.getTask(id)
    },
    async confirm(id, approve, contentMd = null) {
      const data = await api.confirmTask(id, approve, contentMd)
      await this.fetchDetail(id).catch(() => {})
      await this.fetchList(true)
      return data
    },
    async cancel(id) {
      const data = await api.cancelTask(id)
      await this.fetchDetail(id).catch(() => {})
      await this.fetchList(true)
      return data
    },
    ensurePolling() {
      if (this.poller) {
        if (!this.hasActive) {
          this.poller.stop()
          this.poller = null
        }
        return
      }
      if (this.hasActive) {
        this.poller = usePolling(() => this.fetchList(true), 3000)
        this.poller.start()
      }
    },
    stopPolling() {
      this.poller?.stop()
      this.poller = null
    },
  },
})

import { defineStore } from 'pinia'
import * as api from '../api/reports'

export const useReportsStore = defineStore('reports', {
  state: () => ({
    list: [],
    total: 0,
    page: 1,
    pageSize: 20,
    current: null,
    loading: false,
  }),
  actions: {
    async fetchList(silent = false) {
      if (!silent) this.loading = true
      try {
        const data = await api.listReports({
          page: this.page,
          page_size: this.pageSize,
        })
        this.list = data.items
        this.total = data.total
      } finally {
        if (!silent) this.loading = false
      }
    },
    async fetchDetail(id) {
      this.current = await api.getReport(id)
    },
    async generate(payload) {
      // payload: { doc_ids, intent, title? }
      return api.generateReport(payload) // { task_id }
    },
  },
})

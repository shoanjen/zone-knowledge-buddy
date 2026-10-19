import { defineStore } from 'pinia'
import * as api from '../api/documents'
import { usePolling } from '../composables/usePolling'

const IN_PROGRESS = ['pending', 'parsing']

export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    list: [],
    total: 0,
    page: 1,
    pageSize: 20,
    filterSourceType: '',
    keyword: '',
    current: null,
    loading: false,
    poller: null,
  }),
  getters: {
    hasInProgress: (s) => s.list.some((d) => IN_PROGRESS.includes(d.status)),
  },
  actions: {
    async fetchList(silent = false) {
      if (!silent) this.loading = true
      try {
        const data = await api.listDocuments({
          page: this.page,
          page_size: this.pageSize,
          source_type: this.filterSourceType || undefined,
          q: this.keyword || undefined,
        })
        this.list = data.items
        this.total = data.total
      } finally {
        if (!silent) this.loading = false
        this.ensurePolling()
      }
    },
    async fetchDetail(id) {
      this.current = await api.getDocument(id)
    },
    async upload(files) {
      const data = await api.uploadDocuments(files)
      this.ensurePolling()
      return data
    },
    async importUrl(url) {
      const data = await api.importUrl(url)
      this.ensurePolling()
      return data
    },
    async remove(id) {
      await api.deleteDocument(id)
      if (this.current?.id === id) this.current = null
      await this.fetchList(true)
    },
    async retry(id) {
      await api.retryDocument(id)
      await this.fetchList(true)
      this.ensurePolling()
    },
    // 解析中 3s 轮询；无进行中项即停（规格§13.2）
    ensurePolling() {
      if (this.poller) {
        if (!this.hasInProgress) {
          this.poller.stop()
          this.poller = null
        }
        return
      }
      if (this.hasInProgress) {
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

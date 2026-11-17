import { defineStore } from 'pinia'
import * as api from '../api/podcasts'

export const usePodcastsStore = defineStore('podcasts', {
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
        const data = await api.listPodcasts({
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
      this.current = await api.getPodcast(id)
      return this.current
    },
    async generate(payload) {
      // payload: { doc_ids, intent, title?, style?, voice_a?, voice_b? }
      return api.generatePodcast(payload) // { task_id }
    },
    async remove(id) {
      await api.deletePodcast(id)
      if (this.current?.id === id) this.current = null
      await this.fetchList(true).catch(() => {})
    },
  },
})

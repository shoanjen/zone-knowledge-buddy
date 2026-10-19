import { defineStore } from 'pinia'
import * as api from '../api/notes'

export const useNotesStore = defineStore('notes', {
  state: () => ({
    list: [],
    total: 0,
    page: 1,
    pageSize: 20,
    keyword: '',
    tag: '',
    current: null,
    loading: false,
  }),
  actions: {
    async fetchList(silent = false) {
      if (!silent) this.loading = true
      try {
        const data = await api.listNotes({
          page: this.page,
          page_size: this.pageSize,
          q: this.keyword || undefined,
          tag: this.tag || undefined,
        })
        this.list = data.items
        this.total = data.total
      } finally {
        if (!silent) this.loading = false
      }
    },
    async fetchDetail(id) {
      this.current = await api.getNote(id)
    },
    async update(id, payload) {
      this.current = await api.updateNote(id, payload)
      await this.fetchList(true)
    },
    async remove(id) {
      await api.deleteNote(id)
      if (this.current?.id === id) this.current = null
      await this.fetchList(true)
    },
    async generate(payload) {
      // payload: { doc_ids, intent, confirm_required }
      return api.generateNote(payload) // { task_id }
    },
  },
})

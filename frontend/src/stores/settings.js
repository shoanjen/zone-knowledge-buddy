import { defineStore } from 'pinia'
import {
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  testProvider,
  activateProvider,
  getSettings,
  putSettings,
} from '../api/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    providers: [],
    settings: {
      active_provider_id: null,
      generation_params: {},
      embedding: {},
      embedding_locked: false,
    },
    loaded: false,
  }),
  getters: {
    activeProvider: (s) =>
      s.providers.find((p) => p.id === s.settings.active_provider_id) || null,
  },
  actions: {
    async fetchAll() {
      await Promise.all([this.fetchProviders(), this.fetchSettings()])
      this.loaded = true
    },
    async fetchProviders() {
      this.providers = await listProviders()
    },
    async fetchSettings() {
      this.settings = await getSettings()
    },
    async createProvider(payload) {
      await createProvider(payload)
      await this.fetchProviders()
    },
    async updateProvider(id, payload) {
      await updateProvider(id, payload)
      await this.fetchProviders()
    },
    async removeProvider(id) {
      await deleteProvider(id)
      await this.fetchProviders()
    },
    async testProvider(id) {
      return testProvider(id) // { ok, latency_ms, models, error? }
    },
    async activateProvider(id) {
      await activateProvider(id)
      await this.fetchAll()
    },
    async saveSettings(patch) {
      this.settings = await putSettings(patch)
    },
  },
})

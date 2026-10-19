import { defineStore } from 'pinia'
import { login as apiLogin, me as apiMe } from '../api/auth'
import { TOKEN_KEY, USERNAME_KEY } from '../api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    username: localStorage.getItem(USERNAME_KEY) || '',
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
  },
  actions: {
    async login(username, password) {
      const data = await apiLogin({ username, password })
      this.token = data.token
      this.username = data.username
      localStorage.setItem(TOKEN_KEY, data.token)
      localStorage.setItem(USERNAME_KEY, data.username)
    },
    async restore() {
      if (!this.token) return false
      try {
        const data = await apiMe()
        this.username = data.username
        return true
      } catch {
        this.logout()
        return false
      }
    },
    logout() {
      this.token = ''
      this.username = ''
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USERNAME_KEY)
    },
  },
})

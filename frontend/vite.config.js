import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 规格§13.4：dev 代理 /api → 后端 8000
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})

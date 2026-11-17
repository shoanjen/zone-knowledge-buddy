import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 规格§13.4：dev 代理 /api → 后端（默认 8000；可用 KB_BACKEND_URL 覆盖，如本地 8000 被其他项目占用时）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5201,
    proxy: {
      '/api': process.env.KB_BACKEND_URL || 'http://localhost:8000',
    },
  },
})

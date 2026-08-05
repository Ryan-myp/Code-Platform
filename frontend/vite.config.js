import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // 仅代理 /api/ 前缀（带斜杠），避免 /api-platform、/api-docs 等 SPA 路由被误转发
      '/api/': 'http://localhost:8888'
    }
  }
})

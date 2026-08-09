import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    // 大依赖独立 chunk：与 lazy 页面配合，避免全部打进主 bundle（曾 1.1MB）
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/echarts')) return 'echarts'
          if (id.includes('node_modules/react-markdown') || id.includes('node_modules/remark-') || id.includes('node_modules/rehype-')) return 'markdown'
          if (id.includes('node_modules/mermaid') || id.includes('node_modules/d3-') || id.includes('node_modules/dagre')) return 'mermaid'
          if (id.includes('node_modules/lucide-react')) return 'icons'
          if (id.includes('node_modules/axios')) return 'http'
        },
      },
    },
  },
  server: {
    // 监听全部网卡（IPv4+IPv6），避免 macOS 上默认仅绑 IPv6 localhost 导致部分 浏览器连不上
    host: true,
    proxy: {
      // 仅代理 /api/ 前缀（带斜杠），避免 /api-platform、/api-docs 等 SPA 路由 被误转发
      // 后端监听 IPv4 *:8888，代理目标用 127.0.0.1 避免 localhost 解析到 ::1 连接失败
      '/api/': 'http://127.0.0.1:8888'
    }
  }
})

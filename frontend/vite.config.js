import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    // 大依赖独立 chunk：与 lazy 页面配合，避免全部打进主 bundle
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/echarts')) return 'echarts'
          if (id.includes('node_modules/react-markdown') || id.includes('node_modules/remark-') || id.includes('node_modules/rehype-')) return 'markdown'
          if (id.includes('node_modules/mermaid') || id.includes('node_modules/d3-') || id.includes('node_modules/dagre')) return 'mermaid'
          if (id.includes('node_modules/lucide-react')) return 'icons'
          if (id.includes('node_modules/axios')) return 'http'
          // 新增分包
          if (id.includes('node_modules/katex')) return 'katex'
          if (id.includes('node_modules/recharts')) return 'recharts'
          if (id.includes('node_modules/rich-text-editor') || id.includes('node_modules/quill')) return 'editor'
          if (id.includes('node_modules/@tiptap')) return 'tiptap'
          // 图表相关
          if (id.includes('node_modules/klinecharts')) return 'klinecharts'
          // 工具函数库
          if (id.includes('node_modules/dayjs') || id.includes('node_modules/date-fns')) return 'dateutils'
          if (id.includes('node_modules/lodash')) return 'lodash'
        },
        // 减小 chunk 大小警告阈值
        chunkSizeWarningLimit: 300,
      },
    },
    // 代码分割策略
    modulePreload: {
      polyfill: false,
    },
    // 压缩配置
    minify: 'esbuild',
    sourcemap: false,
  },
  server: {
    host: true,
    proxy: {
      '/api/': 'http://127.0.0.1:8888',
      '/uploads/': 'http://127.0.0.1:8888'
    }
  }
})

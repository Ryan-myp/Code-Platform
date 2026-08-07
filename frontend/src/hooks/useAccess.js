import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

/**
 * 内容可见性 Hook（v9.3）
 * - 拉取 /api/access/pages 获取当前用户可见的页面列表（后端已过滤不可见页面）
 * - 页面带 locked=true 表示可见但需要会员等级（requires）
 * - 请求失败时默认全部可见（不因网络波动锁死 UI）
 */

// 路由路径 → 页面注册表 id（与后端 permissions.PAGES 对齐）
const PAGE_PATH_TO_ID = {
  '/image-factory': 'image-factory',
  '/video-factory': 'video-factory',
  '/music-factory': 'music-factory',
  '/copywriting': 'copywriting',
  '/translation': 'translation',
  '/ppt-factory': 'ppt-factory',
  '/excel': 'excel',
  '/stock': 'stock',
  '/agents': 'agents',
  '/workflows': 'workflows',
  '/sandbox': 'sandbox',
  '/plugins': 'plugins',
  '/chat': 'chat',
  '/publish': 'publish',
  '/miniapp': 'miniapp',
  '/games': 'games',
  '/meme': 'meme',
  '/gallery': 'gallery',
  '/templates': 'templates',
  '/voice-dubbing': 'voice-dubbing',
  '/digital-human': 'digital-human',
  '/voice-chat': 'voice-chat',
  '/video-analyzer': 'video-analyzer',
  '/mindmap': 'mindmap',
  '/forecast': 'forecast',
  '/doc-qa': 'doc-qa',
  '/pdf-tools': 'pdf-tools',
  '/web-search': 'web-search',
  '/batch-process': 'batch-process',
  '/code-interpreter': 'code-interpreter',
  '/api-platform': 'api-platform',
  '/usage-analytics': 'usage-analytics',
  '/scheduler': 'scheduler',
  '/growth': 'growth',
  '/strategy': 'strategy',
  '/monitor': 'monitor',
  '/favorites': 'favorites',
  '/data-analyzer': 'data-analyzer',
}

export default function useAccess() {
  const [pages, setPages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/access/pages')
      setPages(res.data || [])
      setError(false)
    } catch {
      // 静默失败：默认全部可见
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  /**
   * 查询页面访问状态
   * @param {string} path 路由路径（如 /ppt-factory）
   * @returns {{visible: boolean, locked: boolean, requires?: string, loading: boolean}}
   */
  const getPageStatus = useCallback(
    (path) => {
      if (loading || error) return { visible: true, locked: false, loading }
      const pageId = PAGE_PATH_TO_ID[path]
      if (!pageId) return { visible: true, locked: false, loading: false }
      const page = pages.find((p) => p.id === pageId)
      // 加载完成后未出现在列表中 → 后端判定不可见
      if (!page) return { visible: false, locked: false, loading: false }
      return { visible: true, locked: !!page.locked, requires: page.requires, loading: false }
    },
    [pages, loading, error]
  )

  // 便捷方法：Sidebar 按 pageId 判断
  const getPageStatusById = useCallback(
    (pageId) => {
      if (loading || error) return { visible: true, locked: false, loading }
      const page = pages.find((p) => p.id === pageId)
      if (!page) return { visible: false, locked: false, loading: false }
      return { visible: true, locked: !!page.locked, requires: page.requires, loading: false }
    },
    [pages, loading, error]
  )

  return { pages, loading, error, refresh, getPageStatus, getPageStatusById }
}

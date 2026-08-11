import { useState, useEffect, useCallback } from 'react'

// v16「最近使用」：localStorage 追踪用户访问过的核心页面，首页一键直达（留存利器）
// 记录 {path, label, icon, ts}，同页面去重置顶，上限 10 条，仅收录映射表内页面
// v17-F：TOOL_META 同时供 App.jsx 路由级页面标题使用（单份数据源，两处消费）
export const TOOL_META = {
  '/workspace': { label: 'AI 工作台', icon: '⚡' },
  '/board': { label: '需求看板', icon: '📋' },
  '/projects': { label: '项目空间', icon: '📁' },
  '/artifacts': { label: '成果仓库', icon: '🗂️' },
  '/tasks': { label: '任务中心', icon: '✅' },
  '/chat': { label: '智能协作', icon: '💬' },
  '/agents': { label: 'Agent 列表', icon: '🤖' },
  '/workflows': { label: 'Workflow 管理', icon: '🔀' },
  '/knowledge-bases': { label: '知识库', icon: '📚' },
  '/digital-human': { label: 'AI 数字人', icon: '🎭' },
  '/meme': { label: '表情包工坊', icon: '😀' },
  '/music-factory': { label: '音乐工厂', icon: '🎵' },
  '/image-factory': { label: '图片工厂', icon: '🖼️' },
  '/video-factory': { label: '视频工厂', icon: '🎬' },
  '/games': { label: '小游戏工坊', icon: '🕹️' },
  '/miniapp': { label: '小程序工坊', icon: '📱' },
  '/drama': { label: '短剧工厂', icon: '🎞️' },
  '/voice-dubbing': { label: '配音工坊', icon: '🎙️' },
  '/voice-chat': { label: 'AI 语音对话', icon: '🎧' },
  '/copywriting': { label: '文案工厂', icon: '✍️' },
  '/translation': { label: '翻译中心', icon: '🌐' },
  '/ppt-factory': { label: 'PPT 工厂', icon: '📊' },
  '/excel': { label: 'Excel 助手', icon: '📈' },
  '/pdf-tools': { label: 'PDF 工具集', icon: '📄' },
  '/mindmap': { label: 'AI 思维导图', icon: '🧠' },
  '/doc-qa': { label: 'AI 文档问答', icon: '📚' },
  '/code-interpreter': { label: '代码解释器', icon: '💻' },
  '/sandbox': { label: '沙箱运行', icon: '🧪' },
  '/web-search': { label: '联网搜索', icon: '🔍' },
  '/batch-process': { label: '批量处理', icon: '📦' },
  '/tool-hub': { label: '工具中心', icon: '🧰' },
  '/seo': { label: 'SEO 分析', icon: '🚀' },
  '/data-analyzer': { label: '数据分析', icon: '📉' },
  '/forecast': { label: 'AI 数据预测', icon: '🔮' },
  '/stock': { label: '股票分析', icon: '💹' },
  '/monitor': { label: '竞品监控', icon: '🛰️' },
  '/strategy': { label: '内容策略', icon: '🗓️' },
  '/video-analyzer': { label: '视频理解', icon: '🎥' },
  '/ab-testing': { label: 'AB 测试', icon: '🧪' },
  '/scheduler': { label: '定时任务', icon: '⏰' },
  '/notifications': { label: '通知中心', icon: '🔔' },
  '/favorites': { label: '收藏中心', icon: '❤️' },
  '/usage-analytics': { label: '用量分析', icon: '📊' },
  '/api-platform': { label: 'API 开放平台', icon: '🔑' },
  '/gallery': { label: '作品广场', icon: '🏞️' },
  '/growth': { label: '增长工坊', icon: '🎯' },
  '/records': { label: '使用记录', icon: '🗒️' },
  '/profile': { label: '个人中心', icon: '👤' },
  '/dashboard': { label: '数据看板', icon: '📊' },
  '/pipelines': { label: '流水线', icon: '🔗' },
  '/publish': { label: '发布中心', icon: '🚀' },
  '/templates': { label: '模板市场', icon: '🗃️' },
  '/help': { label: '帮助中心', icon: '❓' },
}

const STORAGE_KEY = 'recent_tools_v1'
const MAX_ITEMS = 10
// 不追踪的通用页（首页/登录/分享/会员等非工具页）
const EXCLUDED = new Set(['/home', '/login', '/share', '/membership', '/not-found'])

function loadRecent() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

function saveRecent(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    /* localStorage 不可用时静默降级 */
  }
}

/** 路由访问追踪：同页面去重置顶，未收录/排除页不记录 */
export function trackVisit(pathname) {
  if (!pathname || EXCLUDED.has(pathname)) return
  const meta = TOOL_META[pathname]
  if (!meta) return
  const list = loadRecent().filter((it) => it.path !== pathname)
  list.unshift({ path: pathname, ...meta, ts: Date.now() })
  saveRecent(list.slice(0, MAX_ITEMS))
}

/** 清空最近使用记录 */
export function clearRecentTools() {
  localStorage.removeItem(STORAGE_KEY)
}

/** 最近使用 hook：recent 列表 + 刷新 + 清空 */
export default function useRecentTools() {
  const [recent, setRecent] = useState([])
  const refresh = useCallback(() => setRecent(loadRecent()), [])
  useEffect(() => {
    refresh()
  }, [refresh])
  return {
    recent,
    refresh,
    clear: () => {
      clearRecentTools()
      setRecent([])
    },
  }
}

/** 相对时间展示：刚刚 / N 分钟前 / N 小时前 / 昨天 / N 天前 / 月日 */
export function formatRecentTime(ts) {
  if (!ts) return ''
  const diff = Date.now() - ts
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} 小时前`
  const d = Math.floor(h / 24)
  if (d === 1) return '昨天'
  if (d < 7) return `${d} 天前`
  const dt = new Date(ts)
  return `${dt.getMonth() + 1}月${dt.getDate()}日`
}

/**
 * v17-F 路由级页面标题：浏览器标签页标题跟随路由变化。
 * TOOL_META 之外补充通用页/动态页映射，单份数据源供 App.jsx 使用。
 */
import { TOOL_META } from '../hooks/useRecentTools'

// 未收录在 TOOL_META 的通用页标题
const EXTRA_TITLES = {
  '/home': '首页',
  '/login': '登录',
  '/teams': '团队协作',
  '/config': '系统配置',
  '/skills': '技能库',
  '/mcp-servers': 'MCP 服务器',
  '/evolution': '平台演进',
  '/code-gen': 'AI 代码生成',
  '/code-review': 'AI 代码审查',
  '/plugins': '插件中心',
  '/membership': '会员中心',
  '/admin': '管理后台',
  '/api-docs': 'API 文档',
  '/tools': '工具中心',
  '/tool-hub': '工具中心',
  '/not-found': '页面不存在',
}

// 动态路径（/projects/:id 等）：按前缀回退到基础页面标题
const PREFIX_TITLES = {
  '/projects/': '项目空间',
  '/agents/': 'Agent 执行',
  '/workflows/': 'Workflow 编辑',
  '/tool/': 'AI 工具',
  '/share/': '分享',
}

export const SITE_NAME = '小团智能平台'

export function pageTitleFor(pathname) {
  if (!pathname) return SITE_NAME
  const direct = TOOL_META[pathname]?.label || EXTRA_TITLES[pathname]
  if (direct) return `${direct} - ${SITE_NAME}`
  for (const [prefix, label] of Object.entries(PREFIX_TITLES)) {
    if (pathname.startsWith(prefix)) return `${label} - ${SITE_NAME}`
  }
  return SITE_NAME
}

export default pageTitleFor

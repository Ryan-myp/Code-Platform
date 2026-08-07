/**
 * 通用格式化工具
 */

/** 格式化日期时间：2026-08-02 14:30 */
export function formatDateTime(value, fallback = '-') {
  if (!value) return fallback
  const d = new Date(value)
  if (isNaN(d.getTime())) return fallback
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 格式化日期：2026-08-02 */
export function formatDate(value, fallback = '-') {
  if (!value) return fallback
  const d = new Date(value)
  if (isNaN(d.getTime())) return fallback
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 相对时间：刚刚 / 5 分钟前 / 2 小时前 / 3 天前 */
export function formatRelativeTime(value, fallback = '-') {
  if (!value) return fallback
  const d = new Date(value)
  if (isNaN(d.getTime())) return fallback
  const diff = Date.now() - d.getTime()
  const sec = Math.floor(diff / 1000)
  const min = Math.floor(sec / 60)
  const hour = Math.floor(min / 60)
  const day = Math.floor(hour / 24)
  if (sec < 60) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  if (hour < 24) return `${hour} 小时前`
  if (day < 30) return `${day} 天前`
  return formatDate(value)
}

/** 文件大小格式化 */
export function formatBytes(bytes, fallback = '-') {
  if (bytes == null || isNaN(bytes)) return fallback
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** 通用状态 → 颜色/文本映射 */
const STATUS_MAP = {
  // 通用
  active: { text: '运行中', cls: 'bg-emerald-100 text-emerald-700' },
  inactive: { text: '已停用', cls: 'bg-gray-100 text-gray-600' },
  enabled: { text: '已启用', cls: 'bg-emerald-100 text-emerald-700' },
  disabled: { text: '已禁用', cls: 'bg-gray-100 text-gray-600' },
  running: { text: '运行中', cls: 'bg-blue-100 text-blue-700' },
  pending: { text: '待处理', cls: 'bg-amber-100 text-amber-700' },
  queued: { text: '排队中', cls: 'bg-amber-100 text-amber-700' },
  processing: { text: '处理中', cls: 'bg-blue-100 text-blue-700' },
  success: { text: '成功', cls: 'bg-emerald-100 text-emerald-700' },
  completed: { text: '已完成', cls: 'bg-emerald-100 text-emerald-700' },
  failed: { text: '失败', cls: 'bg-red-100 text-red-700' },
  error: { text: '异常', cls: 'bg-red-100 text-red-700' },
  stopped: { text: '已停止', cls: 'bg-gray-100 text-gray-600' },
  draft: { text: '草稿', cls: 'bg-gray-100 text-gray-600' },
  published: { text: '已发布', cls: 'bg-emerald-100 text-emerald-700' },
  archived: { text: '已归档', cls: 'bg-gray-100 text-gray-600' },
  // 需求/项目
  todo: { text: '待开始', cls: 'bg-gray-100 text-gray-600' },
  'in-progress': { text: '进行中', cls: 'bg-blue-100 text-blue-700' },
  'in_review': { text: '评审中', cls: 'bg-amber-100 text-amber-700' },
  'in-review': { text: '评审中', cls: 'bg-amber-100 text-amber-700' },
  done: { text: '已完成', cls: 'bg-emerald-100 text-emerald-700' },
  approved: { text: '已批准', cls: 'bg-emerald-100 text-emerald-700' },
  rejected: { text: '已拒绝', cls: 'bg-red-100 text-red-700' },
}

/** 获取状态展示信息 */
export function getStatusMeta(status, customMap = {}) {
  const s = String(status || '').toLowerCase()
  return customMap[status] || STATUS_MAP[s] || { text: status || '未知', cls: 'bg-gray-100 text-gray-600' }
}

/** 截断文本 */
export function truncate(text, len = 50) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '…' : text
}

/** 防抖 */
export function debounce(fn, delay = 300) {
  let timer
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

/** 复制到剪贴板 */
export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

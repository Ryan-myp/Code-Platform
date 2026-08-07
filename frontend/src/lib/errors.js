/**
 * 友好错误文案映射：把底层异常 / 原始错误串转成用户能看懂的提示。
 *
 * 用途：
 * - api.js 拦截器：axios 层错误（超时 / 网络 / 5xx）没有后端 detail 时兜底翻译
 * - 异步任务失败 error 字段（后端存的是原始异常串）展示前翻译
 * 规则：能精确匹配就翻译；否则返回原文（保留排查信息，截断超长）。
 */

const RULES = [
  { test: /timeout|timed ?out|ETIMEDOUT/i, msg: '服务响应超时，请稍后重试' },
  {
    test: /network error|fetch failed|ECONNREFUSED|ERR_CONNECTION|ENOTFOUND/i,
    msg: '网络连接失败，请检查网络后重试',
  },
  { test: /request failed with status code 5\d\d/i, msg: '服务开小差了，请稍后重试' },
  { test: /429|too many requests/i, msg: '操作太频繁了，请稍后再试' },
  { test: /api[_-]?key|apikey|密钥|credential/i, msg: 'AI 服务配置异常，请联系平台管理员' },
  { test: /balance|insufficient.*fund|欠费/i, msg: 'AI 服务余额不足，请联系平台管理员' },
  { test: /敏感|违规|sensitive|content policy/i, msg: '内容包含敏感信息，请修改后重试' },
]

export function friendlyError(msg) {
  if (!msg) return '操作失败，请稍后重试'
  const text = String(msg)
  for (const rule of RULES) {
    if (rule.test.test(text)) return rule.msg
  }
  return text.length > 200 ? `${text.slice(0, 200)}…` : text
}

export default friendlyError

// 轻量 HTML 消毒工具：富文本内容渲染前调用，防止 XSS（script/iframe/事件属性等）
// 采用白名单策略：仅保留安全标签与安全属性，其余全部剔除

const ALLOWED_TAGS = new Set([
  'p', 'br', 'hr', 'div', 'span', 'strong', 'b', 'em', 'i', 'u', 's', 'strike',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
  'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'sub', 'sup', 'small',
  'mark', 'del', 'ins', 'abbr', 'details', 'summary',
])

const ALLOWED_ATTRS = new Set([
  'href', 'title', 'target', 'rel', 'src', 'alt', 'width', 'height',
  'align', 'colspan', 'rowspan', 'style',
])

// 危险样式关键字（style 属性中出现即整体丢弃该属性）
const DANGEROUS_STYLE = /(expression|javascript:|url\(|@import|behavior|binding)/i

export function sanitizeHtml(html = '') {
  if (typeof DOMParser === 'undefined') return html
  const doc = new DOMParser().parseFromString(String(html), 'text/html')
  const walk = (node) => {
    Array.from(node.children || []).forEach((el) => {
      const tag = el.tagName ? el.tagName.toLowerCase() : ''
      if (!ALLOWED_TAGS.has(tag)) {
        // 危险/未知标签：保留其文本内容，移除标签本身
        const parent = el.parentNode
        while (el.firstChild) parent.insertBefore(el.firstChild, el)
        parent.removeChild(el)
        return
      }
      Array.from(el.attributes).forEach((attr) => {
        const name = attr.name.toLowerCase()
        const value = attr.value
        const isEvent = name.startsWith('on')
        const isJsUrl = (name === 'href' || name === 'src') && /^\s*javascript:/i.test(value)
        const isBadStyle = name === 'style' && DANGEROUS_STYLE.test(value)
        if (!ALLOWED_ATTRS.has(name) || isEvent || isJsUrl || isBadStyle) {
          el.removeAttribute(attr.name)
        } else if (name === 'href' || name === 'src') {
          // 仅允许 http(s)/相对/锚点链接，其余剔除
          if (!/^(https?:|\/|#|mailto:)/i.test(value)) el.removeAttribute(attr.name)
        } else if (name === 'target') {
          if (value !== '_blank') el.setAttribute('target', '_blank')
        } else if (name === 'rel') {
          el.setAttribute('rel', 'noopener noreferrer')
        }
      })
      walk(el)
    })
  }
  walk(doc.body || doc)
  return (doc.body || doc).innerHTML
}

export default sanitizeHtml

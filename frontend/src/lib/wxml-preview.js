/**
 * WXML → HTML 实时预览转换器
 *
 * 将微信小程序 WXML/WXSS/JS 文件转换为浏览器可直接渲染的 HTML，
 * 让非技术用户也能直观看到小程序页面的样子。
 */

// ── WXML → HTML 标签映射 ─────────────────────────────────
const TAG_MAP = {
  view: 'div',
  text: 'span',
  image: 'img',
  button: 'button',
  input: 'input',
  textarea: 'textarea',
  navigator: 'a',
  'scroll-view': 'div',
  icon: 'span',
  'rich-text': 'div',
  label: 'label',
  picker: 'select',
  'picker-view': 'div',
  switch: 'input',
  slider: 'input',
  progress: 'div',
  form: 'form',
  block: 'div',
  cover: 'div',
  'cover-view': 'div',
  'movable-view': 'div',
}

const IMAGE_PLACEHOLDER =
  'data:image/svg+xml,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" fill="#e5e7eb"><rect width="200" height="150"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#9ca3af" font-size="12">图片占位</text></svg>'
  )

// ── 工具函数 ─────────────────────────────────────────────

/** 从 Page({data:{...}}) 中提取 mock data */
function extractPageData(jsContent) {
  if (!jsContent) return {}
  // 匹配 Page({ ... data: { ... } ... })
  const match = jsContent.match(/Page\s*\(\s*\{([\s\S]*?)\}\s*\)/)
  if (!match) return {}
  const body = match[1]

  // 找到 data 字段的值（处理嵌套花括号）
  const dataMatch = body.match(/\bdata\s*:\s*(\{)/)
  if (!dataMatch) return {}
  const startIdx = body.indexOf('{', dataMatch.index + 'data'.length)
  let depth = 0
  let endIdx = startIdx
  for (let i = startIdx; i < body.length; i++) {
    if (body[i] === '{') depth++
    if (body[i] === '}') depth--
    if (depth === 0) {
      endIdx = i + 1
      break
    }
  }
  const dataStr = body.slice(startIdx, endIdx)
  return parseJsObjectLiteral(dataStr)
}

/** 安全解析 JS 对象字面量为 JSON 对象（替代 eval/new Function） */
function parseJsObjectLiteral(jsStr) {
  // 预处理：移除注释、处理单引号、处理无引号 key
  let s = jsStr
    .replace(/(^|\n)\s*\/\/[^\n]*/g, '$1')  // 只移除行首注释（避免误删 URL 中的 //）
    .replace(/\/\*[\s\S]*?\*\//g, '')           // 移除块注释
    .replace(/,(\s*[}\]])/g, '$1')                 // 移除尾随逗号
    .replace(/'([^'\\]*(\\.[^'\\]*)*)'/g, '"$1"')  // 单引号 → 双引号
    .replace(/([{,]\s*)([a-zA-Z_$][\w$]*)\s*:/g, '$1"$2":')  // 无引号 key → 双引号 key
  try {
    return JSON.parse(s)
  } catch {
    return {}
  }
}

/** 解析 {{expr}} 中的变量值 */
function resolveBinding(expr, data, loopCtx) {
  expr = (expr || '').trim()

  // 三元表达式：condition ? a : b
  const ternary = expr.match(/^(.+?)\s*\?\s*(.+?)\s*:\s*(.+)$/)
  if (ternary) {
    const cond = resolveBinding(ternary[1], data, loopCtx)
    return cond ? resolveBinding(ternary[2], data, loopCtx) : resolveBinding(ternary[3], data, loopCtx)
  }

  // 简单的属性引用
  const parts = expr.split('.')
  let val = data
  for (const p of parts) {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      val = val[p.trim()]
    } else if (Array.isArray(val)) {
      val = val[parseInt(p)] ?? undefined
    } else {
      return ''
    }
  }
  if (val === undefined || val === null) return ''
  return val
}

/** 替换文本中的 {{...}} 绑定 */
function replaceBindings(text, data, loopCtx) {
  return text.replace(/\{\{(.+?)\}\}/g, (_, expr) => {
    // 处理 wx:for 上下文中的 item/index
    if (loopCtx) {
      const trimmed = expr.trim()
      if (trimmed === loopCtx.item) return String(loopCtx.cur)
      if (trimmed === loopCtx.idx) return String(loopCtx.index)
      if (trimmed.startsWith(loopCtx.item + '.')) {
        const prop = trimmed.slice(loopCtx.item.length + 1)
        const val = loopCtx.cur && typeof loopCtx.cur === 'object' ? loopCtx.cur[prop] : ''
        return val !== undefined && val !== null ? String(val) : ''
      }
    }
    const val = resolveBinding(expr, data, null)
    if (val === undefined || val === null) return ''
    if (typeof val === 'string') return val
    return String(val)
  })
}

// ── 核心转换函数 ─────────────────────────────────────────

/**
 * 将 WXML 字符串转换为 HTML
 *
 * 处理顺序：
 * 1. 展开 wx:for 循环（递归处理嵌套）
 * 2. 移除 wx:if/wx:else 控制（预览模式下全部显示）
 * 3. 替换 {{}} 数据绑定
 * 4. 转换 WXML 标签 → HTML 标签
 */
function convertWXML(wxml, data) {
  let html = wxml

  // ── 1. 展开 wx:for ──
  html = expandWxFor(html, data)

  // ── 2. 移除 wx:if/wx:elif/wx:else 属性（预览模式下全部显示）──
  html = html.replace(/\s+wx:if\s*=\s*"\{\{.+?\}\}"/g, '')
  html = html.replace(/\s+wx:elif\s*=\s*"\{\{.+?\}\}"/g, '')
  html = html.replace(/\s+wx:else\s*/g, '')

  // ── 3. 替换剩余的 {{}} 绑定 ──
  html = replaceBindings(html, data, null)

  // ── 4. 转换标签 ──
  // 4a. 替换开始标签（含属性）
  for (const [wxmlTag, htmlTag] of Object.entries(TAG_MAP)) {
    // 开始标签: <tag 或 <tag>
    html = html.replace(new RegExp(`<${wxmlTag}(\\s|>)`, 'g'), `<${htmlTag}$1`)
    // 结束标签: </tag>
    html = html.replace(new RegExp(`</${wxmlTag}>`, 'g'), `</${htmlTag}>`)
  }

  // ── 5. 清理 ──
  // 移除剩余的 wx: 指令
  html = html.replace(/\s+wx:\w+\s*=\s*"[^"]*"/g, '')
  // 移除 bind/catch 事件（保留也无害）
  // html = html.replace(/\s+(bind|catch)\w+\s*=\s*"[^"]*"/g, '')
  // 处理自闭合标签
  html = html.replace(/<img([^>]*?)\/>/g, '<img$1>')
  html = html.replace(/<input([^>]*?)\/>/g, '<input$1>')
  // 缺失 src 的 img 给占位图
  html = html.replace(/<img((?!src=)[^>]*)>/g, (_, attrs) => `<img src="${IMAGE_PLACEHOLDER}"${attrs}>`)

  return html
}

/**
 * 展开 wx:for 指令
 * 匹配 <tag ... wx:for="{{list}}" ...>...</tag> 并展开为多个元素
 */
function expandWxFor(wxml, data) {
  // 匹配含 wx:for 的标签（开始标签可能跨多行，但生成的 WXML 通常单行）
  const forRegex =
    /<(\w+)((?:\s+[\w:-]+\s*=\s*"[^"]*")*)\s+wx:for\s*=\s*"\{\{(.+?)\}\}"((?:\s+[\w:-]+\s*=\s*"[^"]*")*)\s*\/?>/g

  const tags = []
  let match
  while ((match = forRegex.exec(wxml)) !== null) {
    tags.push({
      start: match.index,
      fullMatch: match[0],
      tag: match[1],
      beforeAttrs: match[2],
      listExpr: match[3].trim(),
      afterAttrs: match[4],
      selfClosing: match[0].endsWith('/>'),
    })
  }

  // 从后往前处理，避免位置偏移
  for (let i = tags.length - 1; i >= 0; i--) {
    const t = tags[i]

    // 解析 item/index 命名
    const itemMatch = t.fullMatch.match(/wx:for-item\s*=\s*"(\w+)"/)
    const idxMatch = t.fullMatch.match(/wx:for-index\s*=\s*"(\w+)"/)
    const itemName = itemMatch ? itemMatch[1] : 'item'
    const idxName = idxMatch ? idxMatch[1] : 'index'

    // 获取循环数据
    const items = resolveBinding(t.listExpr, data, null)
    if (!Array.isArray(items) || items.length === 0) {
      // 没有数据，移除整个元素
      wxml = wxml.slice(0, t.start) + wxml.slice(t.start + t.fullMatch.length)
      continue
    }

    // 自闭合标签不展开
    if (t.selfClosing) {
      const parts = []
      for (let j = 0; j < items.length; j++) {
        let el = `<${t.tag}`
        const cleanAttrs = t.beforeAttrs + ' ' + t.afterAttrs
        el += cleanAttrs.replace(/\s+wx:\w+\s*=\s*"[^"]*"/g, '')
        el += '/>'
        parts.push(el)
      }
      wxml = wxml.slice(0, t.start) + parts.join('\n') + wxml.slice(t.start + t.fullMatch.length)
      continue
    }

    // 找到匹配的结束标签
    const closeTag = `</${t.tag}>`
    const closeIdx = findMatchingCloseTag(wxml, t.start, t.tag)

    if (closeIdx === -1) {
      // 找不到匹配标签，跳过
      wxml =
        wxml.slice(0, t.start) +
        `<!-- wx:for 解析失败: 未找到 </${t.tag}> -->` +
        wxml.slice(t.start + t.fullMatch.length)
      continue
    }

    // 提取内部模板内容
    const innerStart = t.start + t.fullMatch.length
    const innerContent = wxml.slice(innerStart, closeIdx)

    // 为每个 item 生成 HTML
    const parts = []
    for (let j = 0; j < items.length; j++) {
      let el = `<${t.tag}`
      // 复制非 wx: 属性，替换其中的 {{}} 绑定
      const cleanAttrs =
        t.beforeAttrs +
        ' ' +
        t.afterAttrs.replace(/\s+wx:\w+\s*=\s*"[^"]*"/g, '') +
        ` data-wx-index="${j}"`
      el += cleanAttrs
      el += '>'

      // 处理内部内容（递归展开嵌套 wx:for + 替换绑定）
      const ctx = { item: itemName, idx: idxName, cur: items[j], index: j }
      let inner = expandWxFor(innerContent, data) // 递归处理嵌套 wx:for
      inner = replaceBindings(inner, data, ctx)
      el += inner
      el += `</${t.tag}>`
      parts.push(el)
    }

    // 替换原始区块
    wxml = wxml.slice(0, t.start) + parts.join('\n') + wxml.slice(closeIdx + closeTag.length)
  }

  return wxml
}

/** 找到匹配的闭合标签位置 */
function findMatchingCloseTag(html, startIdx, tagName) {
  const openTag = `<${tagName}`
  const closeTag = `</${tagName}>`
  let depth = 1
  let pos = startIdx + openTag.length

  while (pos < html.length) {
    const nextOpen = html.indexOf(openTag, pos)
    const nextClose = html.indexOf(closeTag, pos)

    if (nextClose === -1) return -1 // 没找到闭合标签

    if (nextOpen !== -1 && nextOpen < nextClose) {
      depth++
      pos = nextOpen + openTag.length
    } else {
      depth--
      if (depth === 0) return nextClose
      pos = nextClose + closeTag.length
    }
  }
  return -1
}

// ── WXSS → CSS ──────────────────────────────────────────

/** WXSS 转 CSS（rpx → px） */
function convertWXSS(wxss) {
  if (!wxss) return ''
  // rpx → px：以 375px 宽度为基准，1rpx = 0.5px
  return wxss.replace(/(\d+(?:\.\d+)?)rpx/g, (_, num) => (parseFloat(num) / 2).toFixed(1) + 'px')
}

// ── 公开 API ────────────────────────────────────────────

/**
 * 将小程序文件集合转换为浏览器可渲染的完整 HTML
 *
 * @param {Object} files - { "app.wxss": "...", "pages/index/index.wxml": "...", ... }
 * @param {string} [pagePath] - 指定预览哪个页面（wxml 路径），默认自动选择首页
 * @returns {{ html: string, title: string, pages: string[] }}
 */
export function wxmlToHtml(files, pagePath) {
  if (!files || typeof files !== 'object') {
    return { html: '<p style="padding:20px;color:#999;">无文件数据</p>', title: '无可预览内容', pages: [] }
  }

  // 找出所有可预览的 WXML 页面
  const wxmlKeys = Object.keys(files).filter((k) => k.endsWith('.wxml'))
  if (wxmlKeys.length === 0) {
    return { html: '<p style="padding:20px;color:#999;">项目中无可预览的 WXML 页面</p>', title: '无页面', pages: [] }
  }

  // 选择要预览的页面
  let selectedWxml = pagePath || ''
  if (!selectedWxml || !files[selectedWxml]) {
    // 优先选 index 页面
    selectedWxml = wxmlKeys.find((k) => k.includes('/index/') || k.includes('index.wxml')) || wxmlKeys[0]
  }

  const basePath = selectedWxml.replace(/\.wxml$/, '')
  const jsContent = files[basePath + '.js'] || ''
  const wxssContent = files[selectedWxml.replace(/\.wxml$/, '.wxss')] || ''

  // 提取页面数据
  const pageData = extractPageData(jsContent)

  // 收集所有 WXSS
  let allCSS = ''
  // app.wxss（全局样式）
  if (files['app.wxss']) {
    allCSS += convertWXSS(files['app.wxss']) + '\n'
  }
  // 页面级 WXSS
  if (wxssContent) {
    allCSS += convertWXSS(wxssContent) + '\n'
  }

  // 从 app.json 提取页面标题和全局配置
  let pageTitle = '小程序预览'
  let navBarBg = '#4F46E5'
  let navBarColor = '#ffffff'
  try {
    if (files['app.json']) {
      const appCfg = JSON.parse(files['app.json'])
      if (appCfg.window) {
        pageTitle = appCfg.window.navigationBarTitleText || pageTitle
        navBarBg = appCfg.window.navigationBarBackgroundColor || navBarBg
        navBarColor = appCfg.window.navigationBarTextStyle === 'black' ? '#000000' : '#ffffff'
      }
    }
    if (files[basePath + '.json']) {
      const pageCfg = JSON.parse(files[basePath + '.json'])
      if (pageCfg.navigationBarTitleText) pageTitle = pageCfg.navigationBarTitleText
    }
  } catch {
    /* ignore */
  }

  // 转换 WXML
  const bodyHTML = convertWXML(files[selectedWxml], pageData)

  // 生成完整 HTML 文档
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=375, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>${pageTitle}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    width: 375px;
    margin: 0 auto;
    min-height: 100vh;
    background: #f8f8f8;
    overflow-x: hidden;
  }
  /* ── 导航栏模拟 ── */
  .__navbar {
    background: ${navBarBg};
    color: ${navBarColor};
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 17px;
    font-weight: 600;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .__navbar-back {
    position: absolute;
    left: 12px;
    font-size: 20px;
    cursor: default;
    opacity: 0.9;
  }
  /* ── 基础元素样式 ── */
  div { display: block; }
  span { display: inline; }
  button {
    display: inline-flex; align-items: center; justify-content: center;
    border: none; cursor: default; font-size: 14px;
    padding: 8px 16px; border-radius: 6px;
    background: #f0f0f0; color: #333;
  }
  input {
    border: 1px solid #ddd; border-radius: 6px;
    padding: 8px 12px; font-size: 14px; outline: none;
    width: 100%;
  }
  img { max-width: 100%; height: auto; display: block; }
  a { color: #576b95; text-decoration: none; }

  ${allCSS}
</style>
</head>
<body>
  <div class="__navbar">
    <span class="__navbar-back">‹</span>
    ${pageTitle}
  </div>
  ${bodyHTML}
</body>
</html>`

  return {
    html,
    title: selectedWxml.replace('pages/', '').replace('/index.wxml', ''),
    pages: wxmlKeys,
  }
}

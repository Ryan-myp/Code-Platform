/**
 * 前端静态文件服务器（SPA + /api 反向代理）
 * 参考 DSH 的 dsh-host-frontend-static 模式：
 *  - 路径穿越防护
 *  - SPA fallback（任意未命中 → index.html）
 *  - assets/ 永久缓存、HTML no-cache
 *  - /api/* 反向代理到 Python 后端
 */
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { extname, join, normalize, resolve, sep } from 'node:path'
import http from 'node:http'

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.map': 'application/json',
  '.wasm': 'application/wasm',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml',
  '.webmanifest': 'application/manifest+json',
  '.mp4': 'video/mp4',
  '.mp3': 'audio/mpeg',
  '.pdf': 'application/pdf',
}

/**
 * 启动前端静态服务
 * @param {string} distPath 前端构建产物目录
 * @param {number} port 监听端口
 * @param {string|null} apiProxy 后端 API 基地址（/api/* 反向代理目标）
 */
export async function startFrontend(distPath, port, apiProxy = null) {
  const distIndex = join(distPath, 'index.html')
  if (!existsSync(distIndex)) {
    throw new Error(`Frontend dist not found at ${distPath}`)
  }

  // 预读 index.html（SPA fallback 用）
  let indexHtml = await readFile(distIndex, 'utf-8')

  const server = createServer(async (req, res) => {
    const urlPath = decodeURIComponent((req.url || '/').split('?')[0])

    // ── /api/* 反向代理到后端 ──────────────────────────────
    if (apiProxy && (urlPath.startsWith('/api/') || urlPath.startsWith('/uploads/'))) {
      const target = new URL(urlPath, apiProxy)
      const proxyReq = http.request(
        {
          host: target.hostname,
          port: target.port,
          path: target.pathname + (req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : ''),
          method: req.method,
          headers: { ...req.headers, host: target.host },
        },
        (proxyRes) => {
          res.writeHead(proxyRes.statusCode, proxyRes.headers)
          proxyRes.pipe(res)
        }
      )
      proxyReq.on('error', (e) => {
        res.writeHead(502, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ detail: `后端代理失败: ${e.message}` }))
      })
      req.pipe(proxyReq)
      return
    }

    // ── 静态文件服务 ───────────────────────────────────────
    // 路径穿越防护（参考 DSH）
    const filePath = safeJoin(distPath, urlPath === '/' ? 'index.html' : urlPath)
    if (!filePath) {
      res.writeHead(403, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ detail: 'Forbidden' }))
      return
    }

    try {
      const st = await stat(filePath)
      if (st.isDirectory()) {
        // 目录 → index.html
        const idx = join(filePath, 'index.html')
        if (existsSync(idx)) {
          const body = await readFile(idx)
          res.writeHead(200, { 'Content-Type': MIME['.html'] || 'text/html', 'Cache-Control': 'no-cache' })
          res.end(body)
        } else {
          res.writeHead(404, { 'Content-Type': 'text/plain' })
          res.end('Not Found')
        }
        return
      }

      const ext = extname(filePath).toLowerCase()
      const isAsset = urlPath.includes('/assets/')
      res.writeHead(200, {
        'Content-Type': MIME[ext] || 'application/octet-stream',
        'Cache-Control': isAsset ? 'public, max-age=31536000, immutable' : 'no-cache',
      })
      const body = await readFile(filePath)
      res.end(body)
    } catch {
      // ── SPA fallback：所有未命中 → index.html ────────────
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' })
      res.end(indexHtml)
    }
  })

  server.listen(port, '0.0.0.0', () => {
    console.log(`  🌐 前端静态服务: http://localhost:${port}`)
    if (apiProxy) console.log(`     API 代理 → ${apiProxy}`)
  })

  // 优雅退出
  process.on('SIGINT', () => {
    console.log('\n  ⏹ 正在停止服务...')
    server.close(() => process.exit(0))
    setTimeout(() => process.exit(0), 2000)
  })

  return server
}

/**
 * 安全路径拼接：防止 ../ 穿越
 */
function safeJoin(root, urlPath) {
  const normalized = normalize(urlPath).replace(/^(\.\.[/\\])+/, '')
  const filePath = resolve(join(root, normalized))
  const rootResolved = resolve(root)
  if (!filePath.startsWith(rootResolved + sep) && filePath !== rootResolved) {
    return null
  }
  return filePath
}

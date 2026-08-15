#!/usr/bin/env node
/**
 * 小团智能平台（Code-Platform）一键部署 CLI
 *
 * 用法：
 *   npx @xiaotuan/code-platform web            # 完整启动（前端 + 后端）
 *   npx @xiaotuan/code-platform web --port 3000 --backend-port 8888
 *   npx @xiaotuan/code-platform backend        # 仅启动后端
 *   npx @xiaotuan/code-platform frontend       # 仅启动前端静态服务
 *
 * 原理（参考 DSH 的 npx 机制）：
 *   - 检测系统 Python 3.10+ → 引导/复用项目 .venv（pip install requirements.txt）
 *   - 前端 dist 内置于本包 frontend-dist/（Vite 构建产物，7MB）
 *   - 启动 Python 后端（main.py :8888）+ Node.js SPA 静态服务器（含 /api 反向代理）
 *   - 免服务器：用户本地一键 `npx` 即可运行完整平台
 */

import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)

import { Command } from 'commander'
import { existsSync, readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { bootstrapPython, findPython, getPythonVersion } from '../lib/bootstrap.js'
import { ensureBackend } from '../lib/download.js'
import { startFrontend } from '../lib/server.js'
import { startBackend, waitForBackend } from '../lib/backend.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PKG_ROOT = join(__dirname, '..')
const DIST_PATH = join(PKG_ROOT, 'frontend-dist')

const program = new Command()
program
  .name('code-platform')
  .description('小团智能平台 — AI 驱动的智能研发与创作平台（一键部署）')
  .version('1.0.0')

program
  .command('web')
  .description('启动完整平台（Python 后端 + React 前端）')
  .option('--port <number>', '前端端口', '3000')
  .option('--backend-port <number>', '后端端口', '8888')
  .option('--install-deps', '强制重新安装 Python 依赖', false)
  .option('--no-frontend', '仅启动后端')
  .option('--no-backend', '仅启动前端')
  .action(async (options) => {
    const { port, backendPort, installDeps } = options
    const wantFrontend = options.frontend !== false
    const wantBackend = options.backend !== false

    console.log('')
    console.log('  🚀 小团智能平台 · 一键部署')
    console.log('  ═══════════════════════════════════')

    // ── 1. 检测 Python ─────────────────────────────────────
    const pythonBin = findPython()
    if (!pythonBin) {
      console.error('  ❌ 未检测到 Python 3.10+，请先安装：https://www.python.org/downloads/')
      process.exit(1)
    }
    const pyVer = await getPythonVersion(pythonBin)
    console.log(`  ✅ Python: ${pyVer} (${pythonBin})`)

    // ── 1.5 确保后端源码可用（仓库内/缓存/GitHub 下载） ──
    if (wantBackend) {
      const backendPath = await ensureBackend()
      console.log(`  📂 后端源码: ${backendPath}`)
    }

    // ── 2. 引导 .venv（复用或重建） ───────────────────────
    let venvPython = null
    if (wantBackend) {
      venvPython = await bootstrapPython(installDeps)
      console.log('  ✅ Python 虚拟环境就绪')
    }

    // ── 3. 启动后端 ────────────────────────────────────────
    let backendUrl = null
    if (wantBackend) {
      backendUrl = `http://127.0.0.1:${backendPort}`
      await startBackend(venvPython, backendPort)
      await waitForBackend(backendPort, 120)
      console.log(`  ✅ 后端已就绪: ${backendUrl}`)
    }

    // ── 4. 启动前端静态服务 ────────────────────────────────
    if (wantFrontend) {
      if (!existsSync(join(DIST_PATH, 'index.html'))) {
        console.error(`  ❌ 前端构建产物缺失: ${DIST_PATH}`)
        process.exit(1)
      }
      await startFrontend(DIST_PATH, Number(port), backendUrl)
      console.log(`  ✅ 前端静态服务已启动: http://localhost:${port}`)
    }

    console.log('')
    console.log('  ═══════════════════════════════════')
    console.log('  ✨ 平台已就绪！')
    if (wantFrontend) console.log(`     🌐 前端:  http://localhost:${port}`)
    if (wantBackend) console.log(`     ⚙️ 后端:  ${backendUrl}`)
    console.log('')
    console.log('  按 Ctrl+C 停止服务')
    console.log('')
  })

program
  .command('backend')
  .description('仅启动后端（8888 端口）')
  .option('--port <number>', '后端端口', '8888')
  .action(async (options) => {
    await ensureBackend()
    const pythonBin = findPython()
    if (!pythonBin) {
      console.error('❌ 未检测到 Python 3.10+')
      process.exit(1)
    }
    const venvPython = await bootstrapPython(false)
    await startBackend(venvPython, options.port)
    await waitForBackend(options.port, 120)
    console.log(`✅ 后端已就绪: http://127.0.0.1:${options.port}`)
  })

program
  .command('frontend')
  .description('仅启动前端静态服务')
  .option('--port <number>', '前端端口', '3000')
  .option('--api <url>', '后端 API 地址', 'http://127.0.0.1:8888')
  .action(async (options) => {
    if (!existsSync(join(DIST_PATH, 'index.html'))) {
      console.error(`❌ 前端构建产物缺失: ${DIST_PATH}`)
      process.exit(1)
    }
    await startFrontend(DIST_PATH, Number(options.port), options.api)
    console.log(`✅ 前端已就绪: http://localhost:${options.port}（API → ${options.api}）`)
  })

program
  .command('doctor')
  .description('检查环境是否满足运行条件')
  .action(async () => {
    console.log('🔍 环境检查...')
    const pythonBin = findPython()
    if (pythonBin) {
      console.log(`  ✅ Python: ${await getPythonVersion(pythonBin)}`)
    } else {
      console.log('  ❌ Python 3.10+ 未找到')
    }
    console.log(`  ✅ Node.js: ${process.version}`)
    console.log(`  ✅ 前端产物: ${existsSync(join(DIST_PATH, 'index.html')) ? '存在 (' + formatSize(DIST_PATH) + ')' : '缺失'}`)
    const venvOk = existsSync(join(process.cwd(), '.venv', 'bin', 'python'))
    console.log(`  ${venvOk ? '✅' : '⚠️'} 项目 .venv: ${venvOk ? '已存在（可复用）' : '首次运行将自动创建'}`)
  })

function formatSize(dir) {
  const { statSync, readdirSync } = require('node:fs')
  let total = 0
  const walk = (d) => {
    for (const f of readdirSync(d)) {
      const p = join(d, f)
      const st = statSync(p)
      if (st.isDirectory()) walk(p)
      else total += st.size
    }
  }
  walk(dir)
  return (total / 1024 / 1024).toFixed(1) + 'MB'
}

program.parse()

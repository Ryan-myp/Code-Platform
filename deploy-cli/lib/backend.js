/**
 * 后端启动：spawn Python 进程 + 等待健康检查就绪
 */
import { spawn } from 'node:child_process'
import http from 'node:http'
import { BACKEND_DIR } from './bootstrap.js'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

let backendProc = null

/**
 * 启动 Python 后端（后台进程）
 * @param {string} venvPython venv 内 python 路径
 * @param {number} port 后端端口
 */
export async function startBackend(venvPython, port = 8888) {
  console.log('  ⚙️  正在启动后端...')
  const entry = existsSync(join(BACKEND_DIR, 'app_creation.py')) ? 'app_creation.py' : 'main.py'
  if (!existsSync(join(BACKEND_DIR, entry))) {
    throw new Error(`后端源码缺失: ${BACKEND_DIR}`)
  }
  backendProc = spawn(venvPython, [entry], {
    cwd: BACKEND_DIR,
    env: { ...process.env, PORT: String(port) },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  backendProc.stdout.on('data', (d) => {
    const line = d.toString().trim()
    if (line && !line.includes('INFO:') && !line.includes('WARNING')) {
      console.log(`     [backend] ${line.slice(0, 200)}`)
    }
  })
  backendProc.stderr.on('data', (d) => {
    const line = d.toString().trim()
    if (line) console.log(`     [backend:err] ${line.slice(0, 200)}`)
  })

  backendProc.on('exit', (code) => {
    console.log(`  ⏹  后端进程退出（code=${code}）`)
  })

  process.on('SIGINT', () => {
    if (backendProc) backendProc.kill('SIGTERM')
  })

  return backendProc
}

/**
 * 等待后端健康检查就绪
 * @param {number} port 后端端口
 * @param {number} timeoutSec 超时秒数
 */
export async function waitForBackend(port, timeoutSec = 120) {
  const deadline = Date.now() + timeoutSec * 1000
  while (Date.now() < deadline) {
    if (await isHealthy(port)) return true
    await sleep(1500)
  }
  throw new Error(`后端在 ${timeoutSec}s 内未就绪，请检查日志`)
}

function isHealthy(port) {
  return new Promise((resolvePromise) => {
    const req = http.get(`http://127.0.0.1:${port}/api/health`, { timeout: 3000 }, (res) => {
      res.resume()
      resolvePromise(res.statusCode === 200)
    })
    req.on('error', () => resolvePromise(false))
    req.on('timeout', () => {
      req.destroy()
      resolvePromise(false)
    })
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

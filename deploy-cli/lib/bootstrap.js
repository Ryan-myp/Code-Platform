/**
 * Python 环境引导：检测系统 Python → 创建/复用 .venv → 安装依赖
 * 仅用 Node 内置模块（child_process），零额外依赖
 */
import { execFileSync, execFile } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { findLocalBackend, BACKEND_CACHE } from './download.js'

const __dirname = dirname(fileURLToPath(import.meta.url))

/**
 * 解析项目根目录：
 * - 仓库内运行（deploy-cli 是仓库一部分）→ 仓库根
 * - npm 包安装运行 → 使用本地缓存或下载的后端源码目录
 */
export function resolveProjectRoot() {
  const local = findLocalBackend()
  if (local && local.source === 'repo') {
    return join(__dirname, '..', '..')
  }
  // npm 模式：venv 放在缓存同级（用户主目录 .cache/code-platform）
  return BACKEND_CACHE
}

export const BACKEND_DIR = (() => {
  const local = findLocalBackend()
  return local ? local.path : BACKEND_CACHE
})()

export const REQUIREMENTS = join(BACKEND_DIR, 'requirements.txt')

/**
 * 检测系统 Python 3.10+，返回可执行命令名
 */
export function findPython() {
  const candidates = [
    'python3.13', 'python3.12', 'python3.11', 'python3.10',
    'python3', 'python',
  ]
  for (const cmd of candidates) {
    try {
      const stdout = execFileSync(cmd, ['--version'], { timeout: 5000, stdio: ['ignore', 'pipe', 'ignore'] })
      const m = stdout.toString().match(/Python\s+3\.(\d+)/)
      if (m && parseInt(m[1], 10) >= 10) return cmd
    } catch {
      /* try next */
    }
  }
  return null
}

/**
 * 获取 Python 版本字符串
 */
export async function getPythonVersion(pythonBin) {
  try {
    return await runCapture(pythonBin, ['--version'])
  } catch {
    return pythonBin
  }
}

/**
 * 引导 Python 虚拟环境
 * 策略：
 *  1. venv 已存在且 python 可用 → 直接复用
 *  2. 不存在或 forceReinstall → 创建 + pip install -r requirements.txt
 * 返回 venv 内 python 路径
 */
export async function bootstrapPython(forceReinstall = false) {
  const projectRoot = resolveProjectRoot()
  const venvPath = join(projectRoot, '.venv')
  const venvPython = process.platform === 'win32'
    ? join(venvPath, 'Scripts', 'python.exe')
    : join(venvPath, 'bin', 'python')

  const needsSetup = forceReinstall || !existsSync(venvPython)

  if (needsSetup) {
    console.log('  📦 正在创建 Python 虚拟环境...')
    const pythonBin = findPython()
    await runLive(pythonBin, ['-m', 'venv', venvPath])
    console.log('  📦 正在安装依赖（首次约需 2-5 分钟）...')
    const pipBin = process.platform === 'win32'
      ? join(venvPath, 'Scripts', 'pip.exe')
      : join(venvPath, 'bin', 'pip')
    if (existsSync(REQUIREMENTS)) {
      await runLive(pipBin, ['install', '-r', REQUIREMENTS])
    } else {
      console.warn('  ⚠️ 未找到 requirements.txt，跳过依赖安装')
    }
  } else {
    console.log('  📦 复用已有 .venv')
  }

  return venvPython
}

// ── 内部工具 ──────────────────────────────────────────────

function runCapture(cmd, args) {
  return new Promise((resolvePromise, reject) => {
    execFile(cmd, args, { timeout: 10000 }, (err, stdout) => {
      if (err) reject(err)
      else resolvePromise(stdout.toString().trim())
    })
  })
}

function runLive(cmd, args) {
  return new Promise((resolvePromise, reject) => {
    const child = execFile(cmd, args, { stdio: 'inherit' })
    child.on('exit', (code) => (code === 0 ? resolvePromise() : reject(new Error(`${cmd} exited ${code}`))))
    child.on('error', reject)
  })
}

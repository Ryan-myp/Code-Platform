import { useState, useEffect, useCallback } from 'react'

/**
 * 深色模式（v10.0）
 * - 优先级：localStorage('theme') > 系统 prefers-color-scheme
 * - 初始化时同步设置 <html class="dark">，避免首帧闪烁
 */
export default function useTheme() {
  const [theme, setTheme] = useState(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('theme') : null
    if (saved === 'dark' || saved === 'light') return saved
    return typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light'
  })

  useEffect(() => {
    const root = document.documentElement
    root.classList.add('theme-transition')
    root.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('theme', theme)
    const t = setTimeout(() => root.classList.remove('theme-transition'), 300)
    return () => clearTimeout(t)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggleTheme }
}

import React, { useEffect, useState } from 'react'
import { Check, ChevronDown, Cpu, Loader2 } from 'lucide-react'
import api from '../lib/api'
import { useToast } from '../lib/toast'

/**
 * 全局模型快速切换（Sidebar 底部）。
 * 模型列表来自「系统配置 → 模型列表」（未配置时后端返回内置默认）。
 * 切换后持久化到 config 表，所有 AI 工具立即生效。
 */
export default function ModelSwitcher() {
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [models, setModels] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get('/api/config')
        setCurrent(res.data.model_name || '')
        setModels(Array.isArray(res.data.models) ? res.data.models : [])
      } catch {
        // 静默
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSelect = async (model) => {
    if (model === current) {
      setOpen(false)
      return
    }
    setSaving(true)
    try {
      await api.post('/api/config/save', { model_name: model })
      setCurrent(model)
      setOpen(false)
      toast.success(`模型已切换为 ${model}，即刻生效`)
    } catch (err) {
      toast.error(err.message || '切换模型失败')
    } finally {
      setSaving(false)
    }
  }

  // 当前模型不在列表时补到首位（兼容手动设置 model_name 的场景）
  const modelOptions = models.some((m) => m.name === current)
    ? models.map((m) => m.name)
    : [current, ...models.map((m) => m.name)].filter(Boolean)

  return (
    <div className="relative px-3 mb-1">
      <button
        onClick={() => setOpen(!open)}
        disabled={loading}
        className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-white border border-ink-200/70 hover:border-brand-300 transition-colors text-left"
        title="切换 AI 模型"
      >
        <span className="flex items-center gap-2 min-w-0">
          {saving ? (
            <Loader2 className="w-3.5 h-3.5 text-brand-500 animate-spin flex-shrink-0" />
          ) : (
            <Cpu className="w-3.5 h-3.5 text-brand-500 flex-shrink-0" />
          )}
          <span className="text-xs text-ink-500 flex-shrink-0">模型</span>
          <span className="text-xs font-medium text-ink-800 truncate">{current || '加载中…'}</span>
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-ink-400 transition-transform flex-shrink-0 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-3 right-3 mb-2 z-50 bg-white rounded-xl shadow-xl border border-ink-200/70 p-1.5 animate-page-in">
            <p className="px-2.5 py-1.5 text-[10px] text-ink-400 font-medium">
              切换模型（所有工具生效）
            </p>
            {modelOptions.map((m) => (
              <button
                key={m}
                onClick={() => handleSelect(m)}
                className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs transition-colors ${
                  m === current
                    ? 'bg-brand-50 text-brand-700 font-medium'
                    : 'text-ink-600 hover:bg-ink-50'
                }`}
              >
                <span className="truncate">{m}</span>
                {m === current && <Check className="w-3.5 h-3.5 text-brand-500 flex-shrink-0" />}
              </button>
            ))}
            <a
              href="#/config"
              className="block text-center mt-1 pt-1.5 border-t border-ink-100 text-[11px] text-brand-600 hover:text-brand-700"
              onClick={() => setOpen(false)}
            >
              自定义模型配置 →
            </a>
          </div>
        </>
      )}
    </div>
  )
}

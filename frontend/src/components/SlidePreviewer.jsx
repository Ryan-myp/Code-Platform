import React, { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Expand, Minimize, X } from 'lucide-react'

/**
 * v18-A 专业幻灯片预览器：把 LLM 结构化大纲渲染为可放映的 16:9 幻灯片。
 * - 版式：cover/toc/content/data/case/summary/thanks 差异化渲染
 * - 主题：7 套色板与后端 PPT_TEMPLATES 对齐（business/roadshow/teaching/marketing/tech/consulting/finance）
 * - 段落级：level 0 主论点 / level 1 支撑论据，strong 加粗高亮、quote 引用样式
 * - 图表：chart_suggestion 关键词 → SVG 柱状/折线/饼图（示意数据）
 * - 放映：全屏播放 + 键盘左右切换
 */

export const SLIDE_THEMES = {
  business: {
    name: '商务汇报',
    dark: '#1B263B',
    accent: '#4F46E5',
    accentLight: '#EEF0FF',
    gray: '#6B7280',
    text: '#333A4A',
    white: '#FFFFFF',
  },
  roadshow: {
    name: '融资路演',
    dark: '#160E2B',
    accent: '#E11D48',
    accentLight: '#FDECF0',
    gray: '#8A849A',
    text: '#2A243B',
    white: '#FFFFFF',
  },
  teaching: {
    name: '教学课件',
    dark: '#0F3324',
    accent: '#0E9F6E',
    accentLight: '#E6F7F1',
    gray: '#6B7280',
    text: '#1F2937',
    white: '#FFFFFF',
  },
  marketing: {
    name: '营销方案',
    dark: '#2B163B',
    accent: '#DB2777',
    accentLight: '#FDEF77',
    gray: '#7A7080',
    text: '#352B3D',
    white: '#FFFFFF',
  },
  tech: {
    name: '科技产品',
    dark: '#0A182E',
    accent: '#0096F7',
    accentLight: '#E8F5FE',
    gray: '#64748B',
    text: '#1E293B',
    white: '#FFFFFF',
  },
  consulting: {
    name: '咨询分析',
    dark: '#121A22',
    accent: '#C2410C',
    accentLight: '#FDF0E7',
    gray: '#6B7280',
    text: '#2D3742',
    white: '#FFFFFF',
  },
  finance: {
    name: '金融投研',
    dark: '#141E2E',
    accent: '#0E9384',
    accentLight: '#E6F6F4',
    gray: '#647084',
    text: '#222B3D',
    white: '#FFFFFF',
  },
}

/**
 * 清洗/归一化 slides：兼容旧格式（content 为字符串）与新格式（content 为对象数组）
 */
export function parseSlides(raw, fallback = []) {
  if (!Array.isArray(raw)) return fallback
  return raw
    .map((s) => {
      if (!s || typeof s !== 'object') return null
      const content = Array.isArray(s.content) ? s.content : typeof s.content === 'string' ? [{ text: s.content, level: 1, emphasis: 'normal' }] : []
      return {
        type: typeof s.type === 'string' ? s.type : 'content',
        title: typeof s.title === 'string' ? s.title : '',
        subtitle: typeof s.subtitle === 'string' ? s.subtitle : '',
        content,
        chart_suggestion: typeof s.chart_suggestion === 'string' ? s.chart_suggestion : '',
        notes: typeof s.notes === 'string' ? s.notes : '',
        duration_seconds: Number(s.duration_seconds) || 0,
      }
    })
    .filter(Boolean)
}

/** 根据 chart_suggestion 关键词推断图表类型（可单测） */
export function chartKind(suggestion = '') {
  const s = (suggestion || '').toLowerCase()
  if (/饼|占比|份额|distribution|pie|share/.test(s)) return 'pie'
  if (/折线|趋势|增长|趋势图|line|trend|growth/.test(s)) return 'line'
  if (/柱|对比|柱状|bar|compare|comparison/.test(s)) return 'bar'
  return 'bar'
}

/**
 * 从 LLM 原始 result 提取 slides 数组（可单测）。
 * 兼容：直接对象 / JSON 字符串 / ```json 代码块包裹；损坏或缺失时返回 fallback。
 * 用于生成完成与历史记录回看（旧历史 slides 列可能为空，需从 result 兜底）。
 */
export function extractSlidesFromResult(result, fallback = []) {
  if (!result) return fallback
  if (typeof result === 'object' && Array.isArray(result.slides)) return result.slides
  if (typeof result === 'string') {
    try {
      const m = result.match(/\{[\s\S]*\}/)
      if (m) {
        const parsed = JSON.parse(m[0])
        if (Array.isArray(parsed.slides)) return parsed.slides
      }
    } catch {
      /* result 非法 JSON（旧记录 LLM 输出未转义引号），保持原文展示 */
    }
  }
  return fallback
}

/* ---------- SVG 示意图表（标注“示意数据”，引导下载 PPTX 查看正式版） ---------- */

function BarChartSvg({ accent }) {
  const bars = [42, 68, 51, 84, 63, 92]
  const max = 100
  return (
    <svg viewBox="0 0 300 160" className="w-full h-full">
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1="20" y1={28 + i * 36} x2="280" y2={28 + i * 36} stroke="#E5E7EB" strokeWidth="1" />
      ))}
      {bars.map((v, i) => {
        const h = (v / max) * 120
        return (
          <g key={i}>
            <rect x={24 + i * 44} y={148 - h} width="28" height={h} rx="4" fill={accent} opacity={0.55 + 0.45 * (i / bars.length)} />
            {/* v19-B：柱顶数据标签 */}
            <text x={38 + i * 44} y={148 - h - 6} fontSize="10" fill={accent} textAnchor="middle" fontWeight="600">
              {v}%
            </text>
            <text x={38 + i * 44} y="166" fontSize="11" fill="#9CA3AF" textAnchor="middle">
              {String.fromCharCode(65 + i)}
            </text>
          </g>
        )
      })}
      <text x="150" y="14" fontSize="10" fill="#9CA3AF" textAnchor="middle">示意数据</text>
    </svg>
  )
}

function LineChartSvg({ accent }) {
  const pts = [[20, 120], [75, 96], [130, 104], [185, 62], [240, 74], [282, 30]]
  const path = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`).join(' ')
  return (
    <svg viewBox="0 0 300 160" className="w-full h-full">
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1="20" y1={28 + i * 36} x2="282" y2={28 + i * 36} stroke="#E5E7EB" strokeWidth="1" />
      ))}
      <path d={path} fill="none" stroke={accent} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="4" fill={accent} stroke="#fff" strokeWidth="2" />
      ))}
      <text x="150" y="14" fontSize="10" fill="#9CA3AF" textAnchor="middle">示意数据</text>
    </svg>
  )
}

function PieChartSvg({ accent }) {
  const segs = [
    { v: 38, color: accent },
    { v: 27, color: '#94A3B8' },
    { v: 20, color: '#CBD5E1' },
    { v: 15, color: '#E2E8F0' },
  ]
  const total = segs.reduce((a, s) => a + s.v, 0)
  let angle = -90
  const paths = segs.map((s) => {
    const start = angle
    const end = angle + (s.v / total) * 360
    angle = end
    const rad = (d) => (d * Math.PI) / 180
    const x1 = 70 + 58 * Math.cos(rad(start))
    const y1 = 80 + 58 * Math.sin(rad(start))
    const x2 = 70 + 58 * Math.cos(rad(end))
    const y2 = 80 + 58 * Math.sin(rad(end))
    return { d: `M70,80 L${x1.toFixed(1)},${y1.toFixed(1)} A58,58 0 ${end - start > 180 ? 1 : 0},1 ${x2.toFixed(1)},${y2.toFixed(1)} Z`, color: s.color }
  })
  return (
    <svg viewBox="0 0 300 160" className="w-full h-full">
      {paths.map((p, i) => (
        <path key={i} d={p.d} fill={p.color} stroke="#fff" strokeWidth="2" />
      ))}
      <text x="150" y="14" fontSize="10" fill="#9CA3AF" textAnchor="middle">示意数据</text>
    </svg>
  )
}

function ChartBlock({ suggestion, accent }) {
  const kind = chartKind(suggestion)
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="w-full max-w-[280px]">
        {kind === 'pie' ? <PieChartSvg accent={accent} /> : kind === 'line' ? <LineChartSvg accent={accent} /> : <BarChartSvg accent={accent} />}
      </div>
      {suggestion && (
        <span className="text-[10px] text-gray-400 mt-1 text-center line-clamp-1 max-w-[90%]">
          建议：{suggestion}
        </span>
      )}
    </div>
  )
}

/** 图表类型中文标签（v19-B 数据洞察徽章） */
function chartLabel(suggestion) {
  const k = chartKind(suggestion)
  if (k === 'pie') return '饼图'
  if (k === 'line') return '折线图'
  return '柱状图'
}

/* ---------- 段落级内容渲染 ---------- */

/** 页脚：品牌 + 主题色短线 + 页码（v19-B 视觉升级）；dark 用于深色底页（浅色文字） */
function SlideFooter({ t, index, total, dark = false }) {
  return (
    <div
      className="flex items-center justify-between pt-3 mt-1 text-[10px] opacity-60"
      style={{ color: dark ? '#D0D5DD' : t.gray }}
    >
      <span>小团智能 · {t.name}</span>
      <span className="flex items-center gap-1.5">
        <span className="w-4 h-0.5 rounded" style={{ background: t.accent }} />
        {String(index + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}
      </span>
    </div>
  )
}

function ContentLines({ lines, textColor, accent, accentLight }) {
  if (!Array.isArray(lines) || lines.length === 0) return null
  return (
    <div className="space-y-2.5">
      {lines.map((line, i) => {
        if (typeof line === 'string') {
          return (
            <p key={i} className="text-sm text-gray-600 leading-relaxed">
              {line}
            </p>
          )
        }
        const { text = '', level = 1, emphasis = 'normal' } = line
        if (level === 0) {
          // 主论点：左侧主题色竖条 + 大字号（v19-B）
          return (
            <div key={i} className="flex items-stretch gap-3 mb-1">
              <span className="w-1 rounded-full flex-shrink-0" style={{ background: accent }} />
              <p className="text-lg font-bold leading-snug" style={{ color: textColor }}>
                {text}
              </p>
            </div>
          )
        }
        if (emphasis === 'strong') {
          // 关键数据/结论：主题色浅底数据卡片（v19-B）
          return (
            <div
              key={i}
              className="flex items-start gap-2.5 rounded-lg px-3 py-2"
              style={{ background: accentLight }}
            >
              <span
                className="mt-[9px] w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{ background: accent }}
              />
              <p className="text-sm font-semibold leading-relaxed" style={{ color: textColor }}>
                {text}
              </p>
            </div>
          )
        }
        if (emphasis === 'quote') {
          return (
            <p
              key={i}
              className="text-sm italic border-l-[3px] pl-3 py-1.5 rounded-r-lg leading-relaxed text-gray-600"
              style={{ borderColor: accent, background: `${accentLight}80` }}
            >
              {text}
            </p>
          )
        }
        return (
          <div key={i} className="flex items-start gap-2.5">
            <span
              className="mt-[9px] w-1.5 h-1.5 rounded-full flex-shrink-0 opacity-50"
              style={{ background: accent }}
            />
            <p className="text-sm leading-relaxed text-gray-600">{text}</p>
          </div>
        )
      })}
    </div>
  )
}

/* ---------- 版式 ---------- */

function CoverSlide({ slide, t }) {
  const year = new Date().getFullYear()
  return (
    <div
      className="relative w-full h-full flex flex-col justify-between p-10 overflow-hidden"
      style={{ background: `linear-gradient(135deg, ${t.dark}, ${t.dark}CC)`, color: t.white }}
    >
      {/* v19-B 装饰：大圆环 + 圆点阵列 */}
      <div className="absolute -top-20 -right-20 w-72 h-72 rounded-full border border-white/10" />
      <div className="absolute -top-10 -right-10 w-44 h-44 rounded-full border border-white/10" />
      <div className="absolute top-12 right-16 w-2 h-2 rounded-full bg-white/30" />
      <div className="absolute top-24 right-28 w-1.5 h-1.5 rounded-full" style={{ background: t.accent }} />
      <div className="absolute bottom-40 right-10 w-1.5 h-1.5 rounded-full bg-white/25" />
      <div className="absolute bottom-52 right-24 w-1 h-1 rounded-full bg-white/40" />
      <div className="relative">
        <div className="flex items-center gap-2 text-xs tracking-widest uppercase opacity-70 mb-5">
          <span className="w-7 h-0.5 rounded" style={{ background: t.accent }} />
          {t.name}
        </div>
        <h2 className="text-4xl font-bold leading-tight mb-4 max-w-[85%]">
          {slide.title || '无标题'}
        </h2>
        {slide.subtitle && (
          <p className="text-base opacity-90 max-w-[70%] leading-relaxed">{slide.subtitle}</p>
        )}
      </div>
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs opacity-60">
          <span className="w-8 h-1 rounded" style={{ background: t.accent }} />
          小团智能平台 · AI PPT
        </div>
        <div className="text-xs opacity-40">{year}</div>
      </div>
    </div>
  )
}

function TocSlide({ slide, t, index, total }) {
  const lines = Array.isArray(slide.content) ? slide.content.map((c) => (typeof c === 'string' ? c : c.text)) : []
  return (
    <div className="w-full h-full p-10 flex flex-col" style={{ background: t.white, color: t.text }}>
      <div className="flex items-center gap-3 mb-6">
        <span className="text-2xl font-bold" style={{ color: t.accent }}>
          目录
        </span>
        {slide.title && <span className="text-sm text-gray-400 mt-1">· {slide.title}</span>}
      </div>
      <div className="flex-1 grid grid-cols-2 gap-x-10 gap-y-5 content-start">
        {lines.map((text, i) => (
          <div key={i} className="flex items-center gap-3 border-b border-gray-100 pb-3">
            <span
              className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold text-white flex-shrink-0 shadow-sm"
              style={{ background: t.accent }}
            >
              {String(i + 1).padStart(2, '0')}
            </span>
            <span className="text-sm font-medium">{text}</span>
          </div>
        ))}
      </div>
      <SlideFooter t={t} index={index} total={total} />
    </div>
  )
}

function ContentSlide({ slide, t, index, total }) {
  return (
    <div className="w-full h-full p-10 pt-8 flex flex-col" style={{ background: t.white, color: t.text }}>
      <div className="flex items-center gap-3 mb-1">
        <span className="w-1.5 h-7 rounded-full" style={{ background: t.accent }} />
        <h3 className="text-xl font-bold">{slide.title || '内容页'}</h3>
        {slide.subtitle && <span className="text-xs text-gray-400 ml-1">· {slide.subtitle}</span>}
      </div>
      <div className="w-full h-px bg-gray-100 mt-3 mb-5" />
      <div className="flex-1 min-h-0">
        <ContentLines
          lines={slide.content}
          textColor={t.text}
          accent={t.accent}
          accentLight={t.accentLight}
        />
      </div>
      <SlideFooter t={t} index={index} total={total} />
    </div>
  )
}

function DataSlide({ slide, t, index, total }) {
  return (
    <div className="w-full h-full p-10 pt-8 flex flex-col" style={{ background: t.white, color: t.text }}>
      <div className="flex items-center gap-3 mb-1">
        <span className="w-1.5 h-7 rounded-full" style={{ background: t.accent }} />
        <h3 className="text-xl font-bold">{slide.title || '数据页'}</h3>
        {slide.subtitle && <span className="text-xs text-gray-400 ml-1">· {slide.subtitle}</span>}
      </div>
      <div className="w-full h-px bg-gray-100 mt-3 mb-5" />
      <div className="flex-1 grid grid-cols-2 gap-6 min-h-0">
        <div className="overflow-auto pr-1">
          <ContentLines
            lines={slide.content}
            textColor={t.text}
            accent={t.accent}
            accentLight={t.accentLight}
          />
        </div>
        {/* v19-B：图表卡片（标题 + 类型徽章 + 示意图） */}
        <div className="bg-gray-50 rounded-xl border border-gray-100 p-4 flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-700">数据洞察</span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded-full"
              style={{ background: t.accentLight, color: t.accent }}
            >
              {chartLabel(slide.chart_suggestion)}
            </span>
          </div>
          <div className="flex-1 min-h-0">
            <ChartBlock suggestion={slide.chart_suggestion} accent={t.accent} />
          </div>
        </div>
      </div>
      <SlideFooter t={t} index={index} total={total} />
    </div>
  )
}

function CaseSlide({ slide, t, index, total }) {
  return (
    <div
      className="w-full h-full p-10 pt-8 flex flex-col"
      style={{ background: t.accentLight, color: t.text }}
    >
      <div className="flex items-center gap-3 mb-1">
        <span className="w-1.5 h-7 rounded-full" style={{ background: t.accent }} />
        <h3 className="text-xl font-bold">{slide.title || '案例'}</h3>
        {slide.subtitle && <span className="text-xs text-gray-400 ml-1">· {slide.subtitle}</span>}
      </div>
      <div className="w-full h-px mt-3 mb-5" style={{ background: `${t.accent}22` }} />
      <div
        className="flex-1 rounded-2xl p-6 shadow-sm border"
        style={{ background: t.white, borderColor: `${t.accent}22` }}
      >
        <ContentLines
          lines={slide.content}
          textColor={t.text}
          accent={t.accent}
          accentLight={t.accentLight}
        />
      </div>
      <SlideFooter t={t} index={index} total={total} />
    </div>
  )
}

function SummarySlide({ slide, t, index, total }) {
  return (
    <div
      className="w-full h-full p-10 flex flex-col items-center justify-center text-center"
      style={{ background: t.white, color: t.text }}
    >
      <div className="flex items-center gap-2 text-xs tracking-widest uppercase mb-4">
        <span className="w-6 h-0.5 rounded" style={{ background: t.accent }} />
        <span style={{ color: t.accent }}>总结</span>
        <span className="w-6 h-0.5 rounded" style={{ background: t.accent }} />
      </div>
      <h3 className="text-2xl font-bold leading-snug mb-5 max-w-[80%]">{slide.title || '核心结论'}</h3>
      <div className="max-w-[70%] w-full text-left">
        <ContentLines
          lines={slide.content}
          textColor={t.text}
          accent={t.accent}
          accentLight={t.accentLight}
        />
      </div>
      <div className="w-full mt-6">
        <SlideFooter t={t} index={index} total={total} />
      </div>
    </div>
  )
}

function ThanksSlide({ t, index, total }) {
  return (
    <div
      className="relative w-full h-full flex flex-col items-center justify-center gap-4 overflow-hidden"
      style={{ background: `linear-gradient(135deg, ${t.dark}, ${t.dark}CC)`, color: t.white }}
    >
      {/* v19-B 装饰：左下圆环与封面呼应 */}
      <div className="absolute -bottom-24 -left-24 w-80 h-80 rounded-full border border-white/10" />
      <div className="absolute -bottom-12 -left-12 w-44 h-44 rounded-full border border-white/10" />
      <div className="absolute top-16 right-14 w-1.5 h-1.5 rounded-full bg-white/30" />
      <div className="relative text-4xl font-bold">{'感谢聆听'}</div>
      <div className="relative text-sm opacity-80">欢迎交流与指正</div>
      <div className="relative w-10 h-1 rounded" style={{ background: t.accent }} />
      <div className="absolute bottom-6 left-10 right-10">
        <SlideFooter t={t} index={index} total={total} dark />
      </div>
    </div>
  )
}

function SlideView({ slide, template, index, total }) {
  const t = SLIDE_THEMES[template] || SLIDE_THEMES.business
  const type = slide?.type || 'content'
  if (type === 'cover') return <CoverSlide slide={slide} t={t} />
  if (type === 'toc') return <TocSlide slide={slide} t={t} index={index} total={total} />
  if (type === 'data') return <DataSlide slide={slide} t={t} index={index} total={total} />
  if (type === 'case') return <CaseSlide slide={slide} t={t} index={index} total={total} />
  if (type === 'summary') return <SummarySlide slide={slide} t={t} index={index} total={total} />
  if (type === 'thanks') return <ThanksSlide t={t} index={index} total={total} />
  return <ContentSlide slide={slide} t={t} index={index} total={total} />
}

/* ---------- 预览器主体 ---------- */

export default function SlidePreviewer({ slides, template = 'business', title = '' }) {
  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState(0)
  const list = parseSlides(slides)

  const next = useCallback(() => setCurrent((c) => Math.min(c + 1, list.length - 1)), [list.length])
  const prev = useCallback(() => setCurrent((c) => Math.max(c - 1, 0)), [])

  useEffect(() => {
    if (!playing) return undefined
    const onKey = (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') next()
      else if (e.key === 'ArrowLeft') prev()
      else if (e.key === 'Escape') setPlaying(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playing, next, prev])

  if (list.length === 0) return null

  const t = SLIDE_THEMES[template] || SLIDE_THEMES.business

  return (
    <div className="space-y-3">
      {/* 工具栏 */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className="text-xs text-gray-500">
          {list.length} 页 · {t.name} · 主题色板
          <span className="inline-flex items-center gap-1 ml-2 align-middle">
            {[t.dark, t.accent, t.accentLight].map((c) => (
              <span key={c} className="w-3 h-3 rounded-full border border-gray-200" style={{ background: c }} />
            ))}
          </span>
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{title ? `${title.slice(0, 20)}${title.length > 20 ? '…' : ''}` : ''}</span>
          <button
            onClick={() => {
              setCurrent(0)
              setPlaying(true)
            }}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-white hover:opacity-90 transition-opacity"
            style={{ background: t.accent }}
          >
            <Expand className="w-3 h-3" /> 放映
          </button>
        </div>
      </div>

      {/* 缩略图网格 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {list.map((slide, i) => (
          <div key={i} className="group relative rounded-xl overflow-hidden shadow-sm border border-gray-200 bg-white">
            <div className="aspect-[16/9] w-full">
              <SlideView slide={slide} template={template} index={i} total={list.length} />
            </div>
            {slide.notes && (
              <div className="px-3 py-1.5 text-[10px] text-gray-400 bg-gray-50 border-t border-gray-100">
                备注：{slide.notes.slice(0, 60)}
                {slide.notes.length > 60 ? '…' : ''}
              </div>
            )}
            <button
              onClick={() => {
                setCurrent(i)
                setPlaying(true)
              }}
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-black/30 flex items-center justify-center"
            >
              <span className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/90 text-xs font-medium text-gray-800 shadow">
                <Expand className="w-3 h-3" /> 查看第 {i + 1} 页
              </span>
            </button>
          </div>
        ))}
      </div>

      {/* 放映模式 */}
      {playing && (
        <div className="fixed inset-0 z-[100] bg-black flex items-center justify-center" onClick={() => setPlaying(false)}>
          <div
            className="relative w-full max-w-[1200px] mx-auto px-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="aspect-[16/9] w-full rounded-lg overflow-hidden shadow-2xl">
              <SlideView slide={list[current]} template={template} index={current} total={list.length} />
            </div>
            <div className="flex items-center justify-between mt-4 text-white/80">
              <div className="text-sm">
                {current + 1} / {list.length}
              </div>
              <div className="flex items-center gap-2">
                {list[current]?.notes && (
                  <div className="text-xs text-white/60 max-w-[50%] truncate">备注：{list[current].notes}</div>
                )}
                <button onClick={prev} disabled={current === 0} className="p-2 rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-30" aria-label="上一页">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button onClick={next} disabled={current === list.length - 1} className="p-2 rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-30" aria-label="下一页">
                  <ChevronRight className="w-5 h-5" />
                </button>
                <button onClick={() => setPlaying(false)} className="p-2 rounded-lg bg-white/10 hover:bg-white/20" aria-label="退出放映">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

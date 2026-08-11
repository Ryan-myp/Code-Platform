/**
 * v18-A 幻灯片预览器单测：大纲归一化 / 图表类型推断 / 版式渲染。
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SlidePreviewer, { parseSlides, chartKind, extractSlidesFromResult, SLIDE_THEMES } from '../../components/SlidePreviewer'

const NEW_SLIDE = {
  type: 'content',
  title: '核心结论',
  content: [
    { text: '主论点', level: 0, emphasis: 'strong' },
    { text: '支撑数据', level: 1, emphasis: 'normal' },
  ],
  chart_suggestion: '柱状图对比',
  notes: '强调增长',
  duration_seconds: 60,
}

describe('extractSlidesFromResult', () => {
  it('直接对象：返回 slides 数组', () => {
    expect(extractSlidesFromResult({ slides: [NEW_SLIDE] })).toEqual([NEW_SLIDE])
  })

  it('JSON 字符串（```json 代码块包裹）：提取 slides', () => {
    const raw = '\n\n```json\n' + JSON.stringify({ meta: {}, slides: [NEW_SLIDE] }) + '\n```\n'
    const slides = extractSlidesFromResult(raw)
    expect(slides.length).toBe(1)
    expect(slides[0].title).toBe('核心结论')
  })

  it('损坏 JSON（未转义引号）：回退 fallback', () => {
    const raw = '{"notes": "强调"诊断"原则"}'
    expect(extractSlidesFromResult(raw)).toEqual([])
    expect(extractSlidesFromResult(raw, [{ title: 'x' }])).toEqual([{ title: 'x' }])
  })

  it('空值/非 slides 结构：回退 fallback', () => {
    expect(extractSlidesFromResult('')).toEqual([])
    expect(extractSlidesFromResult(null)).toEqual([])
    expect(extractSlidesFromResult('纯文本内容')).toEqual([])
    expect(extractSlidesFromResult('{"meta": {}}')).toEqual([])
  })
})

describe('parseSlides', () => {
  it('非数组返回 fallback', () => {
    expect(parseSlides(null, [])).toEqual([])
    expect(parseSlides('abc', [1])).toEqual([1])
  })

  it('新格式 content 数组原样保留', () => {
    const out = parseSlides([NEW_SLIDE])
    expect(out).toHaveLength(1)
    expect(out[0].content).toHaveLength(2)
    expect(out[0].type).toBe('content')
    expect(out[0].notes).toBe('强调增长')
  })

  it('旧格式 content 字符串包装为 level 1 数组', () => {
    const out = parseSlides([{ title: '旧页', content: '一行文字' }])
    expect(out[0].content).toEqual([{ text: '一行文字', level: 1, emphasis: 'normal' }])
  })

  it('缺失字段安全补默认值，非法项过滤', () => {
    const out = parseSlides([null, {}, { title: 'ok' }])
    expect(out).toHaveLength(2)
    expect(out[0].type).toBe('content')
    expect(out[1].title).toBe('ok')
  })
})

describe('chartKind', () => {
  it('关键词推断图表类型', () => {
    expect(chartKind('占比饼图')).toBe('pie')
    expect(chartKind('市场份额 distribution')).toBe('pie')
    expect(chartKind('增长趋势折线图')).toBe('line')
    expect(chartKind('trend line')).toBe('line')
    expect(chartKind('柱状图对比')).toBe('bar')
    expect(chartKind('')).toBe('bar')
    expect(chartKind(null)).toBe('bar')
  })
})

describe('SLIDE_THEMES', () => {
  it('7 套主题色板与后端模板对齐', () => {
    expect(Object.keys(SLIDE_THEMES)).toEqual(['business', 'roadshow', 'teaching', 'marketing', 'tech', 'consulting', 'finance'])
    for (const t of Object.values(SLIDE_THEMES)) {
      expect(t.accent).toMatch(/^#[0-9A-Fa-f]{6}$/)
      expect(t.dark).toMatch(/^#[0-9A-Fa-f]{6}$/)
    }
  })
})

describe('SlidePreviewer 渲染', () => {
  const slides = [
    { type: 'cover', title: '2026 产品战略', subtitle: '汇报人：张三' },
    { type: 'toc', content: [{ text: '背景' }, { text: '方案' }, { text: '落地' }] },
    { ...NEW_SLIDE, type: 'data' },
    { type: 'thanks' },
  ]

  it('渲染全部页与放映按钮', () => {
    render(<SlidePreviewer slides={slides} template="business" />)
    expect(screen.getByText('2026 产品战略')).toBeTruthy()
    expect(screen.getByText(/^4 页/)).toBeTruthy() // 文本被多节点拆分且含「查看第 N 页」遮罩，用行首正则精确定位
    expect(screen.getByText('放映')).toBeTruthy()
    expect(screen.getByText('背景')).toBeTruthy()
    expect(screen.getByText('核心结论')).toBeTruthy()
  })

  it('v19-B 视觉升级：封面年份 + 页脚页码 + 数据洞察徽章', () => {
    render(<SlidePreviewer slides={slides} template="business" />)
    // 封面底部年份
    expect(screen.getByText(String(new Date().getFullYear()))).toBeTruthy()
    // 页脚页码：toc/data/thanks 三页（cover 无页脚）
    expect(screen.getAllByText(/\/ 04$/).length).toBe(3)
    expect(screen.getAllByText('小团智能 · 商务汇报').length).toBe(3)
    // 数据页：数据洞察标题 + 图表类型徽章（'柱状图对比' → 柱状图）
    expect(screen.getByText('数据洞察')).toBeTruthy()
    expect(screen.getByText('柱状图')).toBeTruthy()
    // 论点竖条渲染（level 0 + strong）
    expect(screen.getByText('主论点')).toBeTruthy()
  })

  it('空 slides 渲染 null', () => {
    const { container } = render(<SlidePreviewer slides={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('未知主题回退 business 色板', () => {
    const { container } = render(<SlidePreviewer slides={slides} template="unknown" />)
    expect(container.querySelector('[style*="#1B263B"]')).toBeTruthy() // cover 深色渐变含 business.dark
  })
})

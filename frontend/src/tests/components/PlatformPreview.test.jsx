import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PlatformPreview, {
  extractTitle,
  extractTags,
  splitBody,
  analyzeContent,
} from '../../components/PlatformPreview'

const NOTE = `# 上班族必看！3 个提升效率的方法

通勤路上也能完成 80% 的工作，只需要做好这 3 件事。

## 方法一：清单化
把任务拆成可执行清单，优先级从高到低。

## 方法二：批量处理
同类任务集中处理，减少切换成本。

**记住**：效率不是做得快，而是做得对。

#效率提升 #职场 #时间管理`

describe('PlatformPreview 解析纯函数', () => {
  it('extractTitle 提取首个标题', () => {
    expect(extractTitle(NOTE)).toBe('上班族必看！3 个提升效率的方法')
    expect(extractTitle('## 二级标题\n内容')).toBe('二级标题')
    expect(extractTitle('没有标题的正文')).toBe('')
    expect(extractTitle('')).toBe('')
  })

  it('extractTags 提取话题标签并去重，排除 ## 标题与链接锚点', () => {
    expect(extractTags(NOTE)).toEqual(['效率提升', '职场', '时间管理'])
    expect(extractTags('#旅行 #美食 分享')).toEqual(['旅行', '美食'])
    expect(extractTags('参考 [文档](#url) 与 ## 标题')).toEqual([])
    expect(extractTags('#a #b #c #d #e #f #g #h #i').length).toBe(8)
  })

  it('splitBody 剥离首行标题与纯标签行，按空行分段', () => {
    const paragraphs = splitBody(NOTE)
    expect(paragraphs.length).toBe(4)
    expect(paragraphs[0]).toBe('通勤路上也能完成 80% 的工作，只需要做好这 3 件事。')
    expect(paragraphs[1]).toContain('## 方法一：清单化')
    expect(paragraphs[3]).toContain('**记住**：效率不是做得快，而是做得对。')
    expect(paragraphs.some((p) => p.includes('#效率提升'))).toBe(false)
    expect(splitBody('')).toEqual([])
  })

  it('analyzeContent 统计字数/段落/小标题/标签', () => {
    const stats = analyzeContent(NOTE)
    expect(stats.headings).toBe(3)
    expect(stats.tags).toBe(3)
    expect(stats.paragraphs).toBe(4)
    expect(stats.chars).toBeGreaterThan(50)
    expect(analyzeContent('')).toEqual({ chars: 0, paragraphs: 0, headings: 0, tags: 0 })
  })
})

describe('PlatformPreview 渲染', () => {
  it('小红书模式：渲染标题、话题标签、互动栏与关注按钮', () => {
    render(<PlatformPreview content={NOTE} platform="xiaohongshu" />)
    expect(screen.getByText('上班族必看！3 个提升效率的方法')).toBeTruthy()
    expect(screen.getByText('#效率提升')).toBeTruthy()
    expect(screen.getByText('#职场')).toBeTruthy()
    expect(screen.getByText('关注')).toBeTruthy()
    expect(screen.getByText('灵感笔记')).toBeTruthy()
    // 正文与内联加粗
    expect(screen.getByText(/通勤路上也能完成/)).toBeTruthy()
    expect(screen.getByText('记住')).toBeTruthy()
  })

  it('小红书模式：无标签时正常渲染', () => {
    render(<PlatformPreview content="简单内容" platform="xiaohongshu" />)
    expect(screen.getByText('简单内容')).toBeTruthy()
  })

  it('公众号模式：渲染居中标题与关注栏', () => {
    render(<PlatformPreview content={NOTE} platform="wechat" />)
    expect(screen.getByText('上班族必看！3 个提升效率的方法')).toBeTruthy()
    expect(screen.getByText('关注')).toBeTruthy()
    expect(screen.getByText('灵感创作')).toBeTruthy()
    expect(screen.getByText('AI 创作助手')).toBeTruthy()
  })

  it('通用模式：渲染阅读排版', () => {
    render(<PlatformPreview content={NOTE} platform="" />)
    expect(screen.getByText('上班族必看！3 个提升效率的方法')).toBeTruthy()
    expect(screen.getByText(/通勤路上也能完成/)).toBeTruthy()
  })

  it('空内容返回 null', () => {
    const { container } = render(<PlatformPreview content="" platform="xiaohongshu" />)
    expect(container.firstChild).toBeNull()
  })

  it('传入 title 作为标题回退', () => {
    render(<PlatformPreview content="无标题正文" platform="xiaohongshu" title="我的标题" />)
    // 标题与封面占位均可能展示，断言至少一处
    expect(screen.getAllByText('我的标题').length).toBeGreaterThan(0)
  })
})

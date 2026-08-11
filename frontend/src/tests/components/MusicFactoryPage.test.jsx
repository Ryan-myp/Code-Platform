/**
 * v20 音乐工厂单测：歌词段落解析 + 歌词卡片渲染（段落徽章 / Hook 行强调 / 无标注降级）。
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LyricsCard, parseLyricsSections } from '../../pages/MusicFactoryPage'

const SAMPLE = `[Verse 1]
阳光透过窗帘
洒在你脸上

[Chorus]
你是我最美的遇见
像星光照亮我的夜`

describe('parseLyricsSections', () => {
  it('解析英文标注段落', () => {
    const sections = parseLyricsSections(SAMPLE)
    expect(sections.map((s) => s.title)).toEqual(['Verse 1', 'Chorus'])
    expect(sections[0].lines).toEqual(['阳光透过窗帘', '洒在你脸上'])
    expect(sections[1].isHook).toBe(true)
  })

  it('解析中文/全角标注', () => {
    expect(parseLyricsSections('（副歌）\n金句')[0]).toMatchObject({ title: 'Chorus', isHook: true })
    expect(parseLyricsSections('【主歌】\n段落')[0]).toMatchObject({ title: 'Verse', isHook: false })
  })

  it('无标注降级单段', () => {
    const sections = parseLyricsSections(`纯文本歌词\n第二行`)
    expect(sections.length).toBe(1)
    expect(sections[0].title).toBe('歌词')
  })

  it('空输入返回空数组', () => {
    expect(parseLyricsSections('')).toEqual([])
    expect(parseLyricsSections(null)).toEqual([])
  })
})

describe('LyricsCard', () => {
  it('渲染段落徽章与 Hook 强调行', () => {
    render(<LyricsCard text={SAMPLE} />)
    expect(screen.getByText('Verse 1')).toBeInTheDocument()
    expect(screen.getByText('Chorus')).toBeInTheDocument()
    expect(screen.getByText('🎵 记忆点 Hook')).toBeInTheDocument()
    // Hook 首行强调样式
    const hookLine = screen.getByText('你是我最美的遇见')
    expect(hookLine.className).toContain('text-purple-800')
    expect(hookLine.className).toContain('font-semibold')
    // 普通行不强调
    expect(screen.getByText('阳光透过窗帘').className).toContain('text-gray-700')
  })

  it('无标注歌词也渲染', () => {
    render(<LyricsCard text={'纯文本歌词\n第二行'} />)
    expect(screen.getByText('歌词')).toBeInTheDocument()
    expect(screen.getByText('纯文本歌词')).toBeInTheDocument()
  })

  it('空内容不渲染', () => {
    const { container } = render(<LyricsCard text="" />)
    expect(container.innerHTML).toBe('')
  })
})

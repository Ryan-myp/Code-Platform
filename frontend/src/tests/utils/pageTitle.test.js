/**
 * v17-F 路由级页面标题单测：TOOL_META 收录 / 通用页 / 动态前缀 / 未知回退。
 */
import { describe, it, expect } from 'vitest'
import { pageTitleFor, SITE_NAME } from '../../lib/pageTitle'

describe('pageTitleFor', () => {
  it('TOOL_META 收录页返回「页面名 - 站点名」', () => {
    expect(pageTitleFor('/workspace')).toBe(`AI 工作台 - ${SITE_NAME}`)
    expect(pageTitleFor('/image-factory')).toBe(`图片工厂 - ${SITE_NAME}`)
    expect(pageTitleFor('/digital-human')).toBe(`AI 数字人 - ${SITE_NAME}`)
  })

  it('通用页补充映射生效', () => {
    expect(pageTitleFor('/home')).toBe(`首页 - ${SITE_NAME}`)
    expect(pageTitleFor('/login')).toBe(`登录 - ${SITE_NAME}`)
    expect(pageTitleFor('/skills')).toBe(`技能库 - ${SITE_NAME}`)
    expect(pageTitleFor('/not-found')).toBe(`页面不存在 - ${SITE_NAME}`)
  })

  it('动态路径按前缀匹配基础标题', () => {
    expect(pageTitleFor('/projects/p1')).toBe(`项目空间 - ${SITE_NAME}`)
    expect(pageTitleFor('/agents/a1')).toBe(`Agent 执行 - ${SITE_NAME}`)
    expect(pageTitleFor('/workflows/w1/edit')).toBe(`Workflow 编辑 - ${SITE_NAME}`)
    expect(pageTitleFor('/tool/t1')).toBe(`AI 工具 - ${SITE_NAME}`)
    expect(pageTitleFor('/share/abc')).toBe(`分享 - ${SITE_NAME}`)
  })

  it('未知路径回退为站点名', () => {
    expect(pageTitleFor('/unknown-page')).toBe(SITE_NAME)
    expect(pageTitleFor('')).toBe(SITE_NAME)
    expect(pageTitleFor(null)).toBe(SITE_NAME)
  })

  it('TOOL_META 精确匹配优先于前缀匹配', () => {
    // /tools 是精确映射（工具中心），不应落入前缀逻辑
    expect(pageTitleFor('/tools')).toBe(`工具中心 - ${SITE_NAME}`)
  })
})

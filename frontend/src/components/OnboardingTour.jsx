import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Home,
  LayoutDashboard,
  Sparkles,
  UserCircle,
  Wrench,
  X,
  Zap,
  PartyPopper,
  Rocket,
} from 'lucide-react'

/**
 * 新手引导（首次登录自动弹出，帮助页可重播）。
 * 步骤：平台概览 → AI 工作台智能闭环 → 创作工厂 → 个人中心与额度。
 */
const STEPS = [
  {
    title: '欢迎来到小团智能平台',
    desc: '一个 AI 赋能各行各业的智能工作平台。左侧导航按「研发管理 / 创作工厂 / 效率工具箱」组织，所有 AI 能力一键直达。',
    icon: PartyPopper,
    color: 'from-brand-500 to-indigo-600',
  },
  {
    title: 'AI 工作台 · 智能研发闭环',
    desc: '从需求 PRD 开始，依次完成审查、技术方案、测试用例、代码生成与审查，最后一键部署到沙箱。需求变更自动标记下游「需更新」，部署失败 AI 自动诊断修复，全程可回退、可控制。',
    icon: Rocket,
    color: 'from-brand-500 to-brand-600',
    target: '/workspace',
  },
  {
    title: '创作工厂 · 一站式创作',
    desc: '图片、视频、音乐、文案、翻译、PPT 六大工厂帮你搞定全部创作需求。按 ⌘K / Ctrl+K 可随时打开全局搜索，快速找到任何功能或需求。',
    icon: Sparkles,
    color: 'from-accent-500 to-blue-600',
    target: '/image-factory',
  },
  {
    title: '玩法工坊 · 更多创作形态',
    desc: '除了图片视频，还能一键生成小游戏（网页+微信双版本）、表情包（10+ 模板 / 16 种 AI 风格）、短剧（题材模板+数字人播报）、音乐（16 种乐器 / 12 种情绪）、小程序（模板套件）。所有作品自动保存历史，可随时复用、收藏、分享。',
    icon: Wrench,
    color: 'from-fuchsia-500 to-pink-600',
    target: '/game-factory',
  },
  {
    title: '个人中心 · 额度与安全',
    desc: '免费用户每天 30 次 AI 调用额度，点击左下角头像进入个人中心可查看剩余额度、修改资料密码；结果支持一键生成分享链接。',
    icon: UserCircle,
    color: 'from-emerald-500 to-teal-600',
    target: '/profile',
  },
]

export default function OnboardingTour({ isAuthenticated }) {
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)
  const navigate = useNavigate()

  // 首次登录自动弹出
  useEffect(() => {
    if (isAuthenticated && !localStorage.getItem('onboarding_done')) {
      setOpen(true)
      localStorage.setItem('onboarding_done', '1')
    }
  }, [isAuthenticated])

  // 帮助页可重播
  useEffect(() => {
    const handler = () => {
      setStep(0)
      setOpen(true)
    }
    window.addEventListener('open-onboarding', handler)
    return () => window.removeEventListener('open-onboarding', handler)
  }, [])

  const close = () => setOpen(false)

  const next = () => {
    if (step >= STEPS.length - 1) {
      close()
      return
    }
    setStep(step + 1)
  }

  const goTo = () => {
    const target = STEPS[step].target
    if (target) navigate(target)
    close()
  }

  if (!open) return null

  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-page-in">
        {/* 顶部渐变 */}
        <div className={`h-2 bg-gradient-to-r ${current.color}`} />

        <div className="p-8">
          <div className="flex items-start justify-between mb-6">
            <div
              className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${current.color} flex items-center justify-center shadow-glow`}
            >
              <current.icon className="w-7 h-7 text-white" />
            </div>
            <button
              onClick={close}
              className="p-1.5 hover:bg-ink-50 rounded-lg text-ink-400 hover:text-ink-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <h2 className="text-xl font-bold text-ink-900 mb-2">{current.title}</h2>
          <p className="text-sm text-ink-500 leading-relaxed mb-8">{current.desc}</p>

          {/* 步骤指示 */}
          <div className="flex items-center gap-1.5 mb-8">
            {STEPS.map((s, i) => (
              <div
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  i === step ? 'w-8 bg-brand-500' : i < step ? 'w-4 bg-brand-300' : 'w-4 bg-ink-200'
                }`}
              />
            ))}
            <span className="ml-auto text-xs text-ink-400">
              {step + 1} / {STEPS.length}
            </span>
          </div>

          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setStep(Math.max(0, step - 1))}
              disabled={step === 0}
              className="flex items-center gap-1 px-3 py-2 text-sm rounded-xl text-ink-500 hover:bg-ink-50 disabled:opacity-40 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              上一步
            </button>
            <div className="flex items-center gap-2">
              {current.target && (
                <button
                  onClick={goTo}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-xl text-brand-600 hover:bg-brand-50 transition-colors"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  去看看
                </button>
              )}
              <button
                onClick={next}
                className={`flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-white font-medium shadow-soft transition-all bg-gradient-to-r ${current.color} hover:opacity-90`}
              >
                {isLast ? (
                  <>
                    <Check className="w-4 h-4" />
                    开始使用
                  </>
                ) : (
                  <>
                    下一步
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* 底部提示 */}
        <div className="px-8 py-3 bg-ink-50/60 border-t border-ink-100 flex items-center gap-2 text-xs text-ink-400">
          <Zap className="w-3.5 h-3.5 text-brand-400" />
          提示：以后可在「帮助中心 → 使用帮助」中重新查看引导
        </div>
      </div>
    </div>
  )
}

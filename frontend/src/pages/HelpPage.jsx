import React, { useState } from 'react'
import {
  BookOpen, ChevronDown, Code2, HelpCircle, Mail, MessageCircle,
  Play, Sparkles, UserCircle, Wand2, Wrench, Zap, Shield,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const FEATURES = [
  {
    title: '研发管理',
    desc: '需求看板、AI 工作台、代码生成与审查、CI/CD 流水线，从需求到部署全流程 AI 驱动，失败自动修复。',
    icon: Code2,
    color: 'from-brand-500 to-brand-600',
    path: '/workspace',
  },
  {
    title: '创作工厂',
    desc: '图片、视频、音乐、文案、翻译、PPT 六大 AI 工厂，内容创作一步到位。',
    icon: Wand2,
    color: 'from-accent-500 to-blue-600',
    path: '/image-factory',
  },
  {
    title: '效率工具箱',
    desc: '30+ 覆盖职场办公、自媒体、学习研究的 AI 工具，模板化一键生成。',
    icon: Wrench,
    color: 'from-orange-500 to-red-600',
    path: '/tool-hub',
  },
  {
    title: '个人中心',
    desc: '查看每日额度、修改昵称头像与密码，会员等级一目了然。',
    icon: UserCircle,
    color: 'from-emerald-500 to-teal-600',
    path: '/profile',
  },
]

const FAQS = [
  {
    q: '如何注册和登录？',
    a: '点击登录页的「注册」按钮，输入用户名（2-20 位）和密码（至少 6 位）即可完成注册并自动登录。默认管理员账号 admin / admin123。',
  },
  {
    q: '每日额度是怎么计算的？',
    a: '免费用户每天 30 次 AI 调用额度，专业版 200 次，至尊版无限。每次调用工具、生成图片、翻译等都会消耗 1 次额度，每天 0 点自动重置。',
  },
  {
    q: '额度用完了怎么办？',
    a: '额度耗尽后工具调用会提示「今日免费额度已用完」。可以联系平台管理员开通会员，或等待次日 0 点额度自动重置。',
  },
  {
    q: '如何在 AI 工作台从需求做到部署？',
    a: '在「AI 工作台」先创建需求（PRD），然后依次经过 PRD 审查 → 技术方案 → 测试用例 → 代码生成 → 代码审查六个阶段，顶部状态条会显示每个阶段的完成情况。代码审查通过后点击「一键部署」，系统会自动构建镜像并在沙箱容器中运行，部署完成后可直接访问服务地址。每个阶段的产物都会留存，随时可以回到任意阶段修改并重新生成。',
  },
  {
    q: '修改需求后，下游产物会怎样？',
    a: '需求变更后，系统会自动将受影响的后续阶段标记为「需更新」（琥珀色徽标），提醒你重新生成技术方案、代码等下游产物，避免基于旧需求开发。点击徽标即可跳转到对应阶段重新生成，保证全流程产物一致。',
  },
  {
    q: '部署失败了怎么办？',
    a: '部署失败时系统会自动开启 AI 诊断修复：拉取容器日志 → AI 定位根因 → 修改代码 → 重新构建部署 → 健康检查，最多自动尝试 3 轮。也可以手动点击「AI 诊断修复」按钮重新触发；在「沙箱运行」页打开日志弹窗，点击「AI 分析日志定位问题」可获得详细的诊断报告与修复建议。',
  },
  {
    q: '怎么快速找到某个功能或需求？',
    a: '按 ⌘K（Mac）或 Ctrl+K（Windows）打开全局搜索面板，或点击左侧边栏顶部的搜索框。输入关键词可实时搜索需求、流水线部署和全部功能命令，回车即可跳转。',
  },
  {
    q: '如何分享我的生成结果？',
    a: '在工具结果区点击「分享」按钮，系统会生成公开分享链接并自动复制到剪贴板，把链接发给朋友即可查看，无需登录。',
  },
  {
    q: '可以切换 AI 模型吗？',
    a: '可以在「系统配置 → 模型配置」中查看和调整平台使用的模型；部分工具支持在高级选项中切换模型。',
  },
  {
    q: '如何修改密码或找回账号？',
    a: '登录后点击左下角头像进入「个人中心」，在「修改密码」中填入原密码和新密码即可完成修改。',
  },
]

export default function HelpPage() {
  const [openIndex, setOpenIndex] = useState(0)

  const replayTour = () => {
    window.dispatchEvent(new CustomEvent('open-onboarding'))
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-page-in">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink-900 flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-brand-600" />
            帮助中心
          </h1>
          <p className="text-sm text-ink-500">快速上手小团智能平台，常见问题一站解答</p>
        </div>
        <button
          onClick={replayTour}
          className="flex items-center gap-2 px-4 py-2.5 text-sm rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 text-white font-medium shadow-soft hover:opacity-90 transition-all"
        >
          <Play className="w-4 h-4" />
          重新查看新手引导
        </button>
      </div>

      {/* 快速上手 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {FEATURES.map((f) => (
          <Link
            key={f.title}
            to={f.path}
            className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-5 hover:shadow-lg hover:-translate-y-0.5 transition-all group"
          >
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center mb-3 shadow-soft`}>
              <f.icon className="w-5 h-5 text-white" />
            </div>
            <h3 className="font-semibold text-ink-900 group-hover:text-brand-600 transition-colors">{f.title}</h3>
            <p className="text-xs text-ink-500 mt-1.5 leading-relaxed">{f.desc}</p>
          </Link>
        ))}
      </div>

      {/* 常见问题 */}
      <div className="bg-white rounded-2xl border border-ink-200/60 shadow-soft p-6">
        <h3 className="font-semibold text-ink-900 flex items-center gap-2 mb-4">
          <BookOpen className="w-4 h-4 text-brand-500" />
          常见问题
        </h3>
        <div className="space-y-2.5">
          {FAQS.map((faq, i) => (
            <div key={i} className="border border-ink-100 rounded-xl overflow-hidden">
              <button
                onClick={() => setOpenIndex(openIndex === i ? -1 : i)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-ink-800 hover:bg-ink-50 transition-colors"
              >
                <span className="flex items-center gap-2.5">
                  <span className="w-5 h-5 rounded-md bg-brand-50 text-brand-600 text-xs font-bold flex items-center justify-center flex-shrink-0">
                    Q
                  </span>
                  {faq.q}
                </span>
                <ChevronDown className={`w-4 h-4 text-ink-400 transition-transform ${openIndex === i ? 'rotate-180' : ''}`} />
              </button>
              {openIndex === i && (
                <div className="px-4 pb-3.5 pl-11 text-sm text-ink-500 leading-relaxed bg-ink-50/40">
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 联系我们 */}
      <div className="bg-gradient-to-r from-brand-50 to-indigo-50 border border-brand-100 rounded-2xl p-6 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <MessageCircle className="w-4 h-4 text-brand-500" />
            需要更多帮助？
          </h3>
          <p className="text-sm text-ink-500 mt-1">
            联系平台管理员开通会员、配置模型，或反馈使用问题
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-white rounded-xl border border-ink-200/60 text-sm text-ink-600">
            <Mail className="w-4 h-4 text-brand-500" />
            admin@xiaotuan.ai
          </div>
          <Link
            to="/config"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-ink-800 text-white text-sm font-medium hover:bg-ink-900 transition-colors"
          >
            <Shield className="w-4 h-4" />
            模型配置
          </Link>
        </div>
      </div>

      {/* 额度说明条 */}
      <div className="flex items-center gap-3 px-5 py-4 bg-white rounded-2xl border border-ink-200/60 shadow-soft text-sm text-ink-500">
        <Zap className="w-4 h-4 text-amber-500 flex-shrink-0" />
        <p>
          免费版每日 <span className="font-semibold text-ink-800">30 次</span> 额度 ·
          专业版每日 <span className="font-semibold text-ink-800">200 次</span> ·
          至尊版 <span className="font-semibold text-ink-800">无限使用</span>
          <Link to="/profile" className="ml-2 text-brand-600 hover:underline">
            查看我的额度 →
          </Link>
        </p>
      </div>
    </div>
  )
}

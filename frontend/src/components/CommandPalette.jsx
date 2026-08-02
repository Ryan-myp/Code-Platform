import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, Bot, Layers, FolderKanban, Image, Film, Music, Database,
  Wrench, Server, Settings, MessageSquare, Brain, FileText, CheckCircle2,
  Bell, Zap, Users, Play, ArrowRight, Home, Shield, GitBranch,
  PenTool, Languages, BarChart3, FlaskConical, Presentation, Table2,
  Code2, Puzzle
} from 'lucide-react'

const COMMANDS = [
  // 导航
  { id: 'nav-home', label: '首页', description: '返回工作台首页', icon: Home, path: '/home', category: '导航' },
  { id: 'nav-board', label: '需求看板', description: '查看需求看板', icon: FileText, path: '/board', category: '导航' },
  { id: 'nav-workspace', label: 'AI 工作台', description: '打开 AI 工作台', icon: Zap, path: '/workspace', category: '导航' },
  { id: 'nav-projects', label: '项目空间', description: '查看所有项目', icon: FolderKanban, path: '/projects', category: '导航' },
  { id: 'nav-artifacts', label: '成果仓库', description: '查看所有成果', icon: FileText, path: '/artifacts', category: '导航' },
  
  // 智能体
  { id: 'nav-agents', label: 'Agent 列表', description: '管理智能体', icon: Bot, path: '/agents', category: '智能体' },
  { id: 'nav-teams', label: 'Team 管理', description: '管理团队', icon: Users, path: '/teams', category: '智能体' },
  { id: 'nav-workflows', label: 'Workflow 管理', description: '管理工作流', icon: Layers, path: '/workflows', category: '智能体' },
  { id: 'nav-sandbox', label: '沙箱运行', description: '沙箱环境', icon: Play, path: '/sandbox', category: '智能体' },
  { id: 'nav-pipelines', label: 'CI/CD 流水线', description: '管理流水线', icon: GitBranch, path: '/pipelines', category: '智能体' },
  
  // 研发工具
  { id: 'nav-codegen', label: '代码生成', description: 'AI 代码生成', icon: Code2, path: '/code-gen', category: '研发工具' },
  { id: 'nav-codereview', label: '代码审查', description: 'AI 代码审查', icon: Shield, path: '/code-review', category: '研发工具' },
  
  // 创作工厂
  { id: 'nav-image', label: '图片工厂', description: 'AI 图片生成', icon: Image, path: '/image-factory', category: '创作' },
  { id: 'nav-video', label: '视频工厂', description: 'AI 视频生成', icon: Film, path: '/video-factory', category: '创作' },
  { id: 'nav-music', label: '音乐工厂', description: 'AI 音乐生成', icon: Music, path: '/music-factory', category: '创作' },
  { id: 'nav-copywriting', label: '文案工厂', description: 'AI 文案生成', icon: PenTool, path: '/copywriting', category: '创作' },
  { id: 'nav-translation', label: '翻译中心', description: 'AI 多语言翻译', icon: Languages, path: '/translation', category: '创作' },
  
  // 办公效率
  { id: 'nav-tool-hub', label: '效率工具箱', description: 'AI 效率工具集合', icon: Wrench, path: '/tool-hub', category: '办公' },
  { id: 'nav-ppt', label: 'PPT 生成', description: 'AI PPT 大纲生成', icon: Presentation, path: '/ppt-factory', category: '办公' },
  { id: 'nav-excel', label: 'Excel 助手', description: 'AI 数据分析', icon: Table2, path: '/excel', category: '办公' },
  
  // 运营分析
  { id: 'nav-dashboard', label: '数据仪表盘', description: '平台数据概览', icon: BarChart3, path: '/dashboard', category: '运营' },
  { id: 'nav-abtest', label: 'A/B 测试', description: '实验管理', icon: FlaskConical, path: '/ab-testing', category: '运营' },
  
  // 系统
  { id: 'nav-config', label: '模型配置', description: '配置 AI 模型', icon: Settings, path: '/config', category: '系统' },
  { id: 'nav-knowledge', label: '知识库', description: '管理知识库', icon: Database, path: '/knowledge-bases', category: '系统' },
  { id: 'nav-skills', label: 'Skills', description: '管理技能', icon: Wrench, path: '/skills', category: '系统' },
  { id: 'nav-mcp', label: 'MCP Servers', description: '管理 MCP 服务', icon: Server, path: '/mcp-servers', category: '系统' },
  
  // 其他
  { id: 'nav-plugins', label: '插件市场', description: '浏览插件', icon: Puzzle, path: '/plugins', category: '其他' },
  { id: 'nav-chat', label: '任务对话', description: '智能协作', icon: MessageSquare, path: '/chat', category: '其他' },
  { id: 'nav-evolution', label: '自进化中心', description: '平台自进化', icon: Brain, path: '/evolution', category: '其他' },
  { id: 'nav-tasks', label: '任务中心', description: '管理所有任务', icon: CheckCircle2, path: '/tasks', category: '其他' },
  { id: 'nav-notifications', label: '通知中心', description: '查看所有通知', icon: Bell, path: '/notifications', category: '其他' },
]

export default function CommandPalette({ isOpen, onClose }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (isOpen) {
          onClose()
        } else {
          // 触发打开
          window.dispatchEvent(new CustomEvent('open-command-palette'))
        }
      }
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // 过滤命令
  const filteredCommands = COMMANDS.filter(cmd => {
    if (!query) return true
    const search = query.toLowerCase()
    return (
      cmd.label.toLowerCase().includes(search) ||
      cmd.description.toLowerCase().includes(search) ||
      cmd.category.toLowerCase().includes(search)
    )
  })

  // 按类别分组
  const groupedCommands = filteredCommands.reduce((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = []
    acc[cmd.category].push(cmd)
    return acc
  }, {})

  // 键盘导航
  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => Math.min(prev + 1, filteredCommands.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filteredCommands[selectedIndex]) {
        executeCommand(filteredCommands[selectedIndex])
      }
    }
  }

  const executeCommand = (cmd) => {
    navigate(cmd.path)
    onClose()
  }

  if (!isOpen) return null

  // 计算当前选中项的索引（扁平化）
  let flatIndex = 0
  const flatCommands = []
  Object.entries(groupedCommands).forEach(([category, cmds]) => {
    cmds.forEach(cmd => {
      flatCommands.push({ ...cmd, flatIndex: flatIndex++ })
    })
  })

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* 背景遮罩 */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      
      {/* 命令面板 */}
      <div className="relative w-full max-w-xl bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden">
        {/* 搜索框 */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200">
          <Search className="w-5 h-5 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }}
            onKeyDown={handleKeyDown}
            placeholder="输入命令或搜索..."
            className="flex-1 text-sm text-gray-900 placeholder-gray-400 outline-none"
          />
          <kbd className="px-2 py-0.5 text-xs text-gray-400 bg-gray-100 rounded">
            ESC
          </kbd>
        </div>

        {/* 命令列表 */}
        <div className="max-h-80 overflow-y-auto py-2">
          {filteredCommands.length === 0 ? (
            <div className="px-4 py-8 text-center text-gray-400">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">没有找到匹配的命令</p>
            </div>
          ) : (
            Object.entries(groupedCommands).map(([category, cmds]) => (
              <div key={category}>
                <div className="px-4 py-1.5 text-xs font-medium text-gray-400 uppercase">
                  {category}
                </div>
                {cmds.map((cmd) => {
                  const isSelected = cmd.flatIndex === selectedIndex
                  const Icon = cmd.icon
                  return (
                    <button
                      key={cmd.id}
                      onClick={() => executeCommand(cmd)}
                      onMouseEnter={() => setSelectedIndex(cmd.flatIndex)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                        isSelected ? 'bg-brand-50 text-brand-700' : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        isSelected ? 'bg-brand-100' : 'bg-gray-100'
                      }`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium">{cmd.label}</div>
                        <div className="text-xs text-gray-500 truncate">{cmd.description}</div>
                      </div>
                      {isSelected && (
                        <ArrowRight className="w-4 h-4 text-brand-500" />
                      )}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* 底部提示 */}
        <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded">↑↓</kbd>
              导航
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded">↵</kbd>
              执行
            </span>
          </div>
          <span>共 {filteredCommands.length} 个命令</span>
        </div>
      </div>
    </div>
  )
}

import React from 'react'
import { useI18n } from '../i18n/index.jsx'
import { Keyboard, Search, Zap, Grid3x3, Download, Share2, Settings, Sun, Moon } from 'lucide-react'

const buildKeymap = (t) => [
  { keys: ['Ctrl', 'K'], action: '打开搜索面板', section: t('shortcuts.general') },
  { keys: ['Ctrl', 'Shift', 'K'], action: '打开命令面板', section: t('shortcuts.general') },
  { keys: ['Esc'], action: '关闭弹窗/面板', section: t('shortcuts.general') },
  { keys: ['/'], action: '聚焦搜索框', section: t('shortcuts.general') },
  { keys: ['Ctrl', 'N'], action: '新建项目', section: '文件' },
  { keys: ['Ctrl', 'S'], action: '保存当前内容', section: '文件' },
  { keys: ['Ctrl', 'O'], action: '打开文件', section: '文件' },
  { keys: ['Ctrl', 'W'], action: '关闭当前标签', section: '文件' },
  { keys: ['Ctrl', 'Tab'], action: '切换标签页', section: '文件' },
  { keys: ['Ctrl', 'Shift', 'Tab'], action: '向前切换标签页', section: '文件' },
  { keys: ['Ctrl', '1-9'], action: '跳转到第N个标签页', section: '文件' },
  { keys: ['Ctrl', 'Enter'], action: '发送对话', section: '编辑' },
  { keys: ['Shift', 'Enter'], action: '换行', section: '编辑' },
  { keys: ['Ctrl', 'D'], action: '复制当前行', section: '编辑' },
  { keys: ['Ctrl', 'L'], action: '选中整行', section: '编辑' },
  { keys: ['Ctrl', 'Alt', 'Arrow'], action: '多光标选择', section: '编辑' },
  { keys: ['F11'], action: '全屏模式', section: '视图' },
  { keys: ['Ctrl', '+'], action: '放大界面', section: '视图' },
  { keys: ['Ctrl', '-'], action: '缩小界面', section: '视图' },
  { keys: ['Ctrl', '0'], action: '重置缩放', section: '视图' },
  { keys: ['Ctrl', 'B'], action: '切换侧边栏', section: '视图' },
  { keys: ['Ctrl', 'Shift', 'P'], action: '命令面板（万能搜索）', section: '视图' },
  { keys: ['Ctrl', 'G'], action: '跳转到行', section: '编辑' },
  { keys: ['Ctrl', 'F'], action: '查找', section: '编辑' },
  { keys: ['Ctrl', 'H'], action: '查找替换', section: '编辑' },
  { keys: ['F5'], action: '运行/刷新', section: '工具' },
  { keys: ['Ctrl', 'Shift', 'F5'], action: '强制刷新', section: '工具' },
]

export default function ShortcutsPage() {
  const { t } = useI18n()
  const KEYMAP = buildKeymap(t)
  const SECTIONS = [t('shortcuts.general'), '文件', '编辑', '视图', '工具']
  const [search, setSearch] = React.useState('')
  const [activeSection, setActiveSection] = React.useState('all')

  const filtered = KEYMAP.filter(k => {
    const matchSearch = !search || k.action.includes(search) || k.keys.some(k => k.toLowerCase().includes(search.toLowerCase()))
    const matchSection = activeSection === 'all' || k.section === activeSection
    return matchSearch && matchSection
  })

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-page-in">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-violet-600 rounded-2xl flex items-center justify-center">
          <Keyboard className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-ink-900">快捷键指南</h1>
          <p className="text-gray-500 text-sm mt-0.5">高效操作的秘密武器</p>
        </div>
      </div>

      {/* 搜索 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={t('shortcuts.search_key')}
          className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl focus:border-purple-500 outline-none"
        />
      </div>

      {/* 分类筛选 */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveSection('all')}
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
            activeSection === 'all' ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          全部
        </button>
        {SECTIONS.map(sec => (
          <button
            key={sec}
            onClick={() => setActiveSection(sec)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
              activeSection === sec ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {sec}
          </button>
        ))}
      </div>

      {/* 快捷键列表 */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="divide-y divide-gray-100">
          {filtered.length === 0 ? (
            <div className="p-8 text-center">
              <Keyboard className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">没有找到匹配的快捷键</p>
            </div>
          ) : (
            filtered.map((k, i) => (
              <div key={i} className="flex items-center justify-between px-5 py-3.5 hover:bg-gray-50">
                <div className="flex items-center gap-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    k.section === t('shortcuts.general') ? 'bg-blue-100 text-blue-700' :
                    k.section === '文件' ? 'bg-green-100 text-green-700' :
                    k.section === '编辑' ? 'bg-purple-100 text-purple-700' :
                    k.section === '视图' ? 'bg-amber-100 text-amber-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {k.section}
                  </span>
                  <span className="text-gray-700">{k.action}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {k.keys.map((key, j) => (
                    <kbd
                      key={j}
                      className="px-2 py-1 bg-gray-100 border border-gray-300 rounded-lg text-xs font-mono font-medium text-gray-700 shadow-sm"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 提示 */}
      <div className="bg-gradient-to-r from-purple-50 to-violet-50 border border-purple-200 rounded-2xl p-4 flex items-start gap-3">
        <Zap className="w-5 h-5 text-purple-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-purple-900">💡 提示</p>
          <p className="text-sm text-purple-700 mt-1">
            按 <kbd className="px-1.5 py-0.5 bg-white border border-purple-300 rounded text-xs font-mono">Ctrl+K</kbd> 可快速打开全局搜索面板
          </p>
        </div>
      </div>
    </div>
  )
}

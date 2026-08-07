import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Wrench,
  Plus,
  Trash2,
  Search,
  Edit2,
  Eye,
  FileText,
  RefreshCw,
  LayoutGrid,
  List as ListIcon,
  Link2,
  Code2,
  PenTool,
  BarChart3,
  ShieldCheck,
  Sparkles,
  BookOpen,
  Upload,
  FolderOpen,
  FileArchive,
  Folder,
  FileCode2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime } from '../lib/format'
import {
  Modal,
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  PageHeader,
  ConfirmDialog,
} from '../components/ui'
import SkillExplorer from '../components/SkillExplorer'

const isThisMonth = (val) => {
  if (!val) return false
  const d = new Date(val)
  if (isNaN(d.getTime())) return false
  const now = new Date()
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()
}

// 技能分类
const SKILL_CATEGORIES = [
  { value: 'all', label: '全部', icon: Sparkles },
  { value: 'coding', label: '编程', icon: Code2 },
  { value: 'writing', label: '写作', icon: PenTool },
  { value: 'analysis', label: '分析', icon: BarChart3 },
  { value: 'testing', label: '测试', icon: ShieldCheck },
  { value: 'general', label: '通用', icon: BookOpen },
]

// 技能快速模板
const SKILL_TEMPLATES = [
  {
    name: '代码审查',
    description: '自动化代码审查，检查代码质量、安全性和最佳实践',
    icon: Code2,
    color: 'from-blue-500 to-indigo-600',
    category: 'coding',
    defaults: {
      name: '代码审查专家',
      description: '自动化代码审查，检查代码质量、安全性和最佳实践',
      content:
        '## 代码审查清单\n\n### 1. 代码质量\n- 命名规范是否一致？\n- 是否有重复代码？\n- 函数/方法是否足够简洁？\n\n### 2. 安全性\n- 是否有SQL注入风险？\n- 输入是否经过验证？\n- 敏感信息是否暴露？\n\n### 3. 性能\n- 是否有不必要的循环？\n- 数据库查询是否优化？\n- 是否有内存泄漏风险？\n\n### 4. 可维护性\n- 注释是否充分？\n- 错误处理是否完善？\n- 是否遵循设计模式？',
      references: '',
    },
  },
  {
    name: '文档生成',
    description: '根据代码或需求自动生成技术文档',
    icon: PenTool,
    color: 'from-emerald-500 to-green-600',
    category: 'writing',
    defaults: {
      name: '文档生成助手',
      description: '根据代码或需求自动生成高质量技术文档',
      content:
        '## 文档生成模板\n\n### API 文档\n- 接口名称和路径\n- 请求参数说明\n- 响应格式示例\n- 错误码说明\n\n### 技术设计文档\n- 背景与目标\n- 架构设计\n- 核心流程\n- 数据模型\n- 风险评估\n\n### 用户手册\n- 功能概述\n- 操作步骤\n- 常见问题\n- 联系方式',
      references: '',
    },
  },
  {
    name: '数据分析',
    description: '数据集分析、统计摘要、趋势洞察',
    icon: BarChart3,
    color: 'from-amber-500 to-orange-600',
    category: 'analysis',
    defaults: {
      name: '数据分析专家',
      description: '数据集分析、统计摘要、趋势洞察和可视化建议',
      content:
        '## 数据分析框架\n\n### 1. 数据概览\n- 数据规模和结构\n- 缺失值统计\n- 数据类型分布\n\n### 2. 统计摘要\n- 基本统计量（均值/中位数/标准差）\n- 相关性分析\n- 异常值检测\n\n### 3. 趋势洞察\n- 时间序列趋势\n- 同比/环比分析\n- 关键指标变化\n\n### 4. 建议\n- 数据质量改进\n- 进一步分析方向\n- 可视化建议',
      references: '',
    },
  },
  {
    name: '测试用例',
    description: '根据需求自动生成测试用例和测试计划',
    icon: ShieldCheck,
    color: 'from-violet-500 to-purple-600',
    category: 'testing',
    defaults: {
      name: '测试用例生成器',
      description: '根据需求自动生成全面的测试用例和测试计划',
      content:
        '## 测试用例模板\n\n### 功能测试\n- 正常流程测试\n- 边界条件测试\n- 异常输入测试\n- 并发场景测试\n\n### 性能测试\n- 响应时间基准\n- 吞吐量目标\n- 资源使用上限\n\n### 安全测试\n- 认证授权测试\n- 输入验证测试\n- 会话管理测试\n\n### 兼容性测试\n- 浏览器兼容\n- 设备兼容\n- 系统版本兼容',
      references: '',
    },
  },
]

// 根据描述猜测分类
function guessCategory(skill) {
  const text = `${skill.name || ''} ${skill.description || ''} ${skill.content || ''}`.toLowerCase()
  if (/代码|编程|开发|code|debug|api|函数|组件/.test(text)) return 'coding'
  if (/文档|写作|文案|翻译|blog|文章|内容/.test(text)) return 'writing'
  if (/分析|数据|统计|报表|dashboard|图表/.test(text)) return 'analysis'
  if (/测试|test|qa|用例|bug|缺陷/.test(text)) return 'testing'
  return 'general'
}

// 标准目录结构（展示顺序固定，保证与 Agent Skills 规范一致）
const STRUCTURE_DIRS = ['scripts', 'references', 'examples', 'assets']

function StructureRow({ dirCounts }) {
  return (
    <div className="flex items-center gap-2 flex-wrap text-[11px] text-gray-400">
      <span className="inline-flex items-center gap-1">
        <FileText className="w-3 h-3 text-violet-400" />
        SKILL.md
      </span>
      {STRUCTURE_DIRS.map((d) => (
        <span key={d} className="inline-flex items-center gap-1">
          <FolderOpen className="w-3 h-3 text-amber-400" />
          {d}
          {dirCounts[d] > 0 && <span className="text-gray-500 font-medium">{dirCounts[d]}</span>}
        </span>
      ))}
    </div>
  )
}

function SkillCard({ skill, onView, onEdit, onDelete, viewMode }) {
  const initial = skill.name?.[0]?.toUpperCase() || 'S'
  const category = skill.category || guessCategory(skill)
  const catMeta = SKILL_CATEGORIES.find((c) => c.value === category) || SKILL_CATEGORIES[5]
  const refCount = skill.references
    ? skill.references.split('\n').filter((l) => l.trim()).length
    : 0
  const dirCounts = skill.dir_counts || {}

  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white font-bold flex-shrink-0">
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{skill.name}</h3>
            <span
              className={`px-1.5 py-0.5 rounded text-xs font-medium ${catMeta.value === 'coding' ? 'bg-blue-50 text-blue-600' : catMeta.value === 'writing' ? 'bg-emerald-50 text-emerald-600' : catMeta.value === 'analysis' ? 'bg-amber-50 text-amber-600' : catMeta.value === 'testing' ? 'bg-violet-50 text-violet-600' : 'bg-gray-100 text-gray-600'}`}
            >
              {catMeta.label}
            </span>
          </div>
          <p className="text-sm text-gray-500 truncate">{skill.description || '暂无描述'}</p>
          <div className="mt-1.5">
            <StructureRow dirCounts={dirCounts} />
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-3 text-xs text-gray-500 flex-shrink-0">
          {skill.content ? (
            <span className="flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" />
              有内容
            </span>
          ) : null}
          {refCount > 0 ? (
            <span className="flex items-center gap-1">
              <Link2 className="w-3.5 h-3.5" />
              {refCount} 引用
            </span>
          ) : null}
          {['scripts', 'references', 'examples', 'assets']
            .filter((d) => dirCounts[d] > 0)
            .map((d) => (
              <span key={d} className="flex items-center gap-1">
                <FolderOpen className="w-3.5 h-3.5" />
                {d}: {dirCounts[d]}
              </span>
            ))}
          <span>{formatRelativeTime(skill.created_at)}</span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onView(skill)}
            className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
            title="查看"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(skill)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(skill)}
            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-lg transition-all duration-200 flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg flex-shrink-0">
            {initial}
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{skill.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className={`px-1.5 py-0.5 rounded text-xs font-medium ${catMeta.value === 'coding' ? 'bg-blue-50 text-blue-600' : catMeta.value === 'writing' ? 'bg-emerald-50 text-emerald-600' : catMeta.value === 'analysis' ? 'bg-amber-50 text-amber-600' : catMeta.value === 'testing' ? 'bg-violet-50 text-violet-600' : 'bg-gray-100 text-gray-600'}`}
              >
                {catMeta.label}
              </span>
              <p className="text-xs text-gray-500">{formatRelativeTime(skill.created_at)}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {skill.content && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full text-xs">
              <FileText className="w-3 h-3" />
              内容
            </span>
          )}
          {refCount > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded-full text-xs">
              <Link2 className="w-3 h-3" />
              {refCount}
            </span>
          )}
          {skill.file_count > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-600 rounded-full text-xs">
              <FolderOpen className="w-3 h-3" />
              {skill.file_count} 文件
            </span>
          )}
          {['scripts', 'references', 'examples', 'assets']
            .filter((d) => dirCounts[d] > 0)
            .map((d) => (
              <span
                key={d}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-violet-50 text-violet-600 rounded-full text-xs"
              >
                <FolderOpen className="w-3 h-3" />
                {d}: {dirCounts[d]}
              </span>
            ))}
        </div>
      </div>

      <p className="text-sm text-gray-600 line-clamp-2 mb-3 flex-1">
        {skill.description || '暂无描述'}
      </p>

      <div className="mb-4">
        <StructureRow dirCounts={dirCounts} />
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">{formatRelativeTime(skill.created_at)}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onView(skill)}
            className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
            title="查看"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(skill)}
            className="p-2 hover:bg-purple-50 text-gray-400 hover:text-purple-600 rounded-lg transition-colors"
            title="编辑"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(skill)}
            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// 只读目录树（编辑弹窗内展示标准结构，不含交互操作）
function StaticTree({ node, depth = 0, rootName }) {
  const isDir = node.type === 'dir'
  const icon = isDir ? (
    <FolderOpen className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
  ) : node.name === 'SKILL.md' ? (
    <FileText className="w-3.5 h-3.5 text-violet-400 flex-shrink-0" />
  ) : (
    <FileCode2 className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
  )
  return (
    <div>
      <div className="flex items-center gap-1.5 py-1" style={{ paddingLeft: depth * 14 }}>
        {icon}
        <span
          className={`truncate ${isDir ? 'font-medium text-gray-600' : 'font-mono text-xs text-gray-500'}`}
        >
          {node.path === '' ? rootName : node.name}
        </span>
        {isDir && node.file_count > 0 && (
          <span className="text-[10px] px-1 rounded-full bg-gray-200/70 text-gray-500 flex-shrink-0">
            {node.file_count}
          </span>
        )}
      </div>
      {(node.children || []).map((child) => (
        <StaticTree key={child.path} node={child} depth={depth + 1} rootName={rootName} />
      ))}
    </div>
  )
}

function SkillFormModal({ open, onClose, onSubmit, editing, defaults, loading }) {
  const [form, setForm] = useState({ name: '', description: '', content: '', references: '' })
  const [errors, setErrors] = useState({})
  const [tree, setTree] = useState(null)
  const [treeLoading, setTreeLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    if (editing) {
      setForm({
        name: editing.name || '',
        description: editing.description || '',
        content: editing.content || '',
        references: editing.references || '',
      })
    } else if (defaults) {
      setForm({
        name: defaults.name || '',
        description: defaults.description || '',
        content: defaults.content || '',
        references: defaults.references || '',
      })
    } else {
      setForm({ name: '', description: '', content: '', references: '' })
    }
    setErrors({})
    // 编辑模式加载标准目录树（只读展示）
    setTree(null)
    if (editing?.id) {
      setTreeLoading(true)
      api
        .get(`/api/skills/${editing.id}/files/tree`)
        .then((res) => setTree(res.data))
        .catch(() => setTree(null))
        .finally(() => setTreeLoading(false))
    }
  }, [open, editing, defaults])

  const setField = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入 Skill 名称'
    if (form.name.length > 80) e.name = '名称不能超过 80 个字符'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    onSubmit({ ...form, name: form.name.trim() })
  }

  const inputCls = (err) =>
    `w-full px-4 py-2 rounded-xl border focus:ring-2 focus:border-transparent outline-none transition-all ${
      err
        ? 'border-red-300 focus:ring-red-500/20'
        : 'border-gray-200 focus:ring-purple-500/20 focus:border-purple-500'
    }`

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? '编辑 Skill' : '新建 Skill'}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={loading}>
            {editing ? '保存' : '创建'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setField('name', e.target.value)}
            placeholder="例如：代码审查专家"
            className={inputCls(errors.name)}
          />
          {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => setField('description', e.target.value)}
            placeholder="简要说明 Skill 的用途"
            className={inputCls(false)}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            内容（指令/模板）
          </label>
          <textarea
            value={form.content}
            onChange={(e) => setField('content', e.target.value)}
            rows={6}
            placeholder="输入 Skill 的详细内容或系统指令…"
            className={`${inputCls(false)} font-mono text-sm`}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            引用 / 参考（References）
          </label>
          <textarea
            value={form.references}
            onChange={(e) => setField('references', e.target.value)}
            rows={3}
            placeholder="输入参考文档、链接或其他 Skill 名称，每行一个…"
            className={inputCls(false)}
          />
          <p className="text-xs text-gray-400 mt-1">用于在对话中引用相关知识或其他 Skill</p>
        </div>

        {/* 标准目录结构（只读） */}
        {editing ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">标准目录结构</label>
            <div className="bg-gray-50 rounded-xl p-3 max-h-44 overflow-y-auto">
              {treeLoading ? (
                <p className="text-xs text-gray-400">加载中…</p>
              ) : tree ? (
                <StaticTree node={tree} rootName={editing.name} />
              ) : (
                <p className="text-xs text-gray-400">目录结构加载失败</p>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-1">目录为只读展示，文件增删请在「查看」中操作</p>
          </div>
        ) : (
          <div className="flex items-start gap-2 bg-violet-50 border border-violet-100 rounded-xl px-3 py-2.5">
            <Folder className="w-4 h-4 text-violet-500 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-violet-600 leading-relaxed">
              创建后将自动生成标准目录结构：<code className="font-mono">SKILL.md</code> +{' '}
              <code className="font-mono">scripts/ references/ examples/ assets/</code>，与 Agent
              Skills 规范一致
            </p>
          </div>
        )}
      </div>
    </Modal>
  )
}

export default function SkillsPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState('grid')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [editingSkill, setEditingSkill] = useState(null)
  const [saving, setSaving] = useState(false)
  const [viewTarget, setViewTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [formDefaults, setFormDefaults] = useState(null)
  // 标准 SKILL.md 导入
  const [showImport, setShowImport] = useState(false)
  const [importText, setImportText] = useState('')
  const [importing, setImporting] = useState(false)
  const zipInputRef = useRef(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/api/skills')
      setItems(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const filteredItems = items.filter((s) => {
    const q = searchTerm.toLowerCase()
    const matchSearch =
      !q ||
      (s.name || '').toLowerCase().includes(q) ||
      (s.description || '').toLowerCase().includes(q) ||
      (s.content || '').toLowerCase().includes(q) ||
      (s.references || '').toLowerCase().includes(q)
    const cat = s.category || guessCategory(s)
    const matchCategory = categoryFilter === 'all' || cat === categoryFilter
    return matchSearch && matchCategory
  })

  const openCreate = () => {
    setEditingSkill(null)
    setFormDefaults(null)
    setShowForm(true)
  }
  const openEdit = (skill) => {
    setEditingSkill(skill)
    setShowForm(true)
  }

  const handleImport = async () => {
    const text = importText.trim()
    if (!text) {
      toast.error('请粘贴 SKILL.md 内容')
      return
    }
    setImporting(true)
    try {
      const res = await api.post('/api/skills/import', { markdown: text })
      toast.success(`Skill「${res.data.name}」导入成功`)
      setShowImport(false)
      setImportText('')
      loadData()
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || '导入失败')
    } finally {
      setImporting(false)
    }
  }

  const handleImportZip = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post('/api/skills/import-zip', fd)
      toast.success(`Skill「${res.data.name}」导入成功（${res.data.imported} 个文件）`)
      loadData()
    } catch (err) {
      toast.error(err.message || 'ZIP 导入失败')
    } finally {
      setImporting(false)
      if (zipInputRef.current) zipInputRef.current.value = ''
    }
  }

  const handleSubmit = async (payload) => {
    setSaving(true)
    try {
      if (editingSkill) {
        await api.put(`/api/skills/${editingSkill.id}`, payload)
        toast.success(`Skill「${payload.name}」已更新`)
      } else {
        await api.post('/api/skills', payload)
        toast.success(`Skill「${payload.name}」已创建`)
      }
      setShowForm(false)
      setEditingSkill(null)
      loadData()
    } catch (e) {
      toast.error(`操作失败：${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return false
    try {
      await api.delete(`/api/skills/${deleteTarget.id}`)
      toast.success(`Skill「${deleteTarget.name}」已删除`)
      setDeleteTarget(null)
      loadData()
      return true
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
      return false
    }
  }

  const stats = [
    {
      label: '总技能数',
      value: items.length,
      icon: Wrench,
      color: 'from-violet-500 to-purple-600',
    },
    {
      label: '含内容',
      value: items.filter((s) => s.content?.trim()).length,
      icon: FileText,
      color: 'from-blue-500 to-cyan-600',
    },
    {
      label: '含引用',
      value: items.filter((s) => s.references?.trim()).length,
      icon: Link2,
      color: 'from-emerald-500 to-green-600',
    },
    {
      label: '本月新增',
      value: items.filter((s) => isThisMonth(s.created_at)).length,
      icon: Sparkles,
      color: 'from-amber-500 to-orange-600',
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Skills 管理"
        description="创建和管理 AI 技能，定义 Agent 的行为和能力"
        icon={Wrench}
        iconColor="from-violet-500 to-purple-600"
        actions={
          <>
            <Button
              variant="secondary"
              icon={FileArchive}
              loading={importing}
              onClick={() => zipInputRef.current?.click()}
            >
              导入 ZIP
            </Button>
            <Button variant="secondary" icon={Upload} onClick={() => setShowImport(true)}>
              导入 SKILL.md
            </Button>
            <Button variant="primary" icon={Plus} onClick={openCreate}>
              新建 Skill
            </Button>
            <input
              ref={zipInputRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={handleImportZip}
            />
          </>
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div
                className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center flex-shrink-0`}
              >
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 快速模板（仅在技能为空时显示） */}
      {items.length === 0 && !loading && !error && (
        <div className="bg-gradient-to-r from-violet-50 to-purple-50 rounded-2xl border border-violet-200/50 p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-500" />
            从模板快速创建
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {SKILL_TEMPLATES.map((tpl) => (
              <button
                key={tpl.name}
                onClick={() => {
                  setFormDefaults(tpl.defaults)
                  setShowForm(true)
                }}
                className="bg-white rounded-xl p-4 border border-gray-200 hover:border-violet-300 hover:shadow-md transition-all text-left group"
              >
                <div
                  className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tpl.color} flex items-center justify-center text-white mb-3`}
                >
                  <tpl.icon className="w-4.5 h-4.5" />
                </div>
                <h4 className="text-sm font-semibold text-gray-800 mb-1">{tpl.name}</h4>
                <p className="text-xs text-gray-500 line-clamp-2">{tpl.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 分类筛选 + 搜索 */}
      <div className="bg-white rounded-2xl border border-gray-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索 Skill 名称、描述、内容或引用…"
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
          />
        </div>
        <div className="flex items-center gap-2">
          {/* 分类标签 */}
          <div className="flex items-center gap-1 overflow-x-auto">
            {SKILL_CATEGORIES.map((cat) => (
              <button
                key={cat.value}
                onClick={() => setCategoryFilter(cat.value)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                  categoryFilter === cat.value
                    ? 'bg-purple-100 text-purple-700'
                    : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
          <Button variant="ghost" size="md" icon={RefreshCw} onClick={loadData}>
            刷新
          </Button>
          <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
              title="网格视图"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
              title="列表视图"
            >
              <ListIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <SkeletonGrid count={6} />
      ) : error ? (
        <ErrorState message={`加载失败：${error.message}`} onRetry={loadData} />
      ) : filteredItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <Empty
            icon={Wrench}
            title={searchTerm || categoryFilter !== 'all' ? '未找到匹配的 Skill' : '暂无 Skill'}
            description={
              searchTerm || categoryFilter !== 'all'
                ? '尝试调整搜索或筛选条件'
                : '点击「新建 Skill」创建你的第一个 AI 技能'
            }
            actionLabel={searchTerm || categoryFilter !== 'all' ? undefined : '新建 Skill'}
            onAction={searchTerm || categoryFilter !== 'all' ? undefined : openCreate}
          />
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              onView={setViewTarget}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              viewMode="grid"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredItems.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              onView={setViewTarget}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              viewMode="list"
            />
          ))}
        </div>
      )}

      {/* 标准 SKILL.md 导入弹窗 */}
      <Modal
        open={showImport}
        onClose={() => {
          setShowImport(false)
          setImportText('')
        }}
        title="导入标准 SKILL.md"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowImport(false)
                setImportText('')
              }}
            >
              取消
            </Button>
            <Button icon={Upload} onClick={handleImport} loading={importing}>
              导入
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-xs text-gray-500 leading-relaxed">
            支持 Agent Skills 标准格式（Anthropic / Claude Code / Qoder 等），自动解析 frontmatter
            中的
            <code className="mx-1 px-1 py-0.5 bg-gray-100 rounded font-mono text-[11px]">
              name
            </code>{' '}
            与
            <code className="mx-1 px-1 py-0.5 bg-gray-100 rounded font-mono text-[11px]">
              description
            </code>
            ：
          </p>
          <pre className="bg-gray-50 rounded-xl p-3 text-[11px] font-mono text-gray-500 overflow-x-auto">{`---
name: 技能名称
description: 技能描述
---
技能正文（Markdown）…`}</pre>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            rows={12}
            placeholder="粘贴 SKILL.md 内容…"
            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all font-mono text-sm"
          />
        </div>
      </Modal>

      <SkillFormModal
        open={showForm}
        onClose={() => {
          setShowForm(false)
          setEditingSkill(null)
          setFormDefaults(null)
        }}
        onSubmit={handleSubmit}
        editing={editingSkill}
        defaults={formDefaults}
        loading={saving}
      />

      <SkillExplorer
        open={!!viewTarget}
        onClose={() => setViewTarget(null)}
        skill={viewTarget}
        onEdit={openEdit}
        onDelete={setDeleteTarget}
        onChanged={loadData}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除 Skill"
        message={
          <>
            确定要删除 Skill「
            <span className="font-medium text-gray-700">{deleteTarget?.name}</span>
            」吗？此操作不可撤销。
          </>
        }
        confirmLabel="确认删除"
      />
    </div>
  )
}

import React, { useState, useEffect } from 'react'
import { GitBranch, Plus, Play, Trash2, Clock, Settings } from 'lucide-react'
import { Card, Button, Badge, Modal, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

const PIPELINE_TYPES = [
  { value: 'ci', label: 'CI 持续集成', color: 'blue' },
  { value: 'cd', label: 'CD 持续部署', color: 'green' },
  { value: 'test', label: '自动化测试', color: 'purple' },
  { value: 'build', label: '构建打包', color: 'amber' },
]

export default function PipelinesPage() {
  const toast = useToast()
  const [pipelines, setPipelines] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', type: 'ci', config: {} })

  useEffect(() => { load() }, [])
  const load = async () => {
    setLoading(true)
    try { const res = await api.get('/api/pipelines'); setPipelines(res.data) } catch (e) { toast.error('加载失败') }
    finally { setLoading(false) }
  }

  const create = async () => {
    if (!form.name.trim()) { toast.error('请输入名称'); return }
    try {
      await api.post('/api/pipelines', form)
      toast.success('流水线已创建'); setShowModal(false)
      setForm({ name: '', description: '', type: 'ci', config: {} }); load()
    } catch (e) { toast.error(`创建失败：${e.message}`) }
  }

  const remove = async (id) => {
    if (!confirm('确定删除？')) return
    try { await api.delete(`/api/pipelines/${id}`); toast.success('已删除'); load() } catch (e) { toast.error('删除失败') }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">CI/CD 流水线</h1>
          <p className="text-sm text-gray-500 mt-1">管理持续集成和持续部署流水线</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>新建流水线</Button>
      </div>

      {loading ? <div className="flex justify-center py-12"><div className="animate-spin h-6 w-6 border-b-2 border-brand-500 rounded-full" /></div>
      : pipelines.length === 0 ? <Card><Empty icon={GitBranch} title="暂无流水线" description="点击新建创建第一条流水线" /></Card>
      : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {pipelines.map(p => {
            const typeConfig = PIPELINE_TYPES.find(t => t.value === p.type) || PIPELINE_TYPES[0]
            return (
              <Card key={p.id}>
                <div className="flex items-start justify-between mb-3">
                  <div className={`w-10 h-10 rounded-lg bg-${typeConfig.color}-100 flex items-center justify-center`}>
                    <GitBranch className={`w-5 h-5 text-${typeConfig.color}-600`} />
                  </div>
                  <Badge color={typeConfig.color}>{typeConfig.label}</Badge>
                </div>
                <h3 className="font-semibold text-gray-900">{p.name}</h3>
                {p.description && <p className="text-sm text-gray-500 mt-1">{p.description}</p>}
                <div className="flex items-center gap-2 mt-4 text-xs text-gray-400">
                  <Clock className="w-3 h-3" /> {p.created_at?.slice(0, 16)}
                </div>
                <div className="flex gap-2 mt-3">
                  <Button variant="ghost" size="sm" className="flex-1" icon={Play}>运行</Button>
                  <Button variant="ghost" size="sm" icon={Trash2} onClick={() => remove(p.id)} />
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="新建流水线" size="md"
        footer={<div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setShowModal(false)}>取消</Button><Button variant="primary" onClick={create}>创建</Button></div>}>
        <div className="space-y-4">
          <div><label className="block text-sm font-medium text-gray-700 mb-1">名称 *</label>
            <input type="text" value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="w-full px-3 py-2 border border-gray-300 rounded-lg" /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            <textarea value={form.description} onChange={(e) => setForm({...form, description: e.target.value})} rows={2} className="w-full px-3 py-2 border border-gray-300 rounded-lg" /></div>
          <div><label className="block text-sm font-medium text-gray-700 mb-1">类型</label>
            <select value={form.type} onChange={(e) => setForm({...form, type: e.target.value})} className="w-full px-3 py-2 border border-gray-300 rounded-lg">
              {PIPELINE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select></div>
        </div>
      </Modal>
    </div>
  )
}

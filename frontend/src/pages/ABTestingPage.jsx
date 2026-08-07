import React, { useState, useEffect } from 'react'
import { FlaskConical, Plus, Trash2, Clock, Play } from 'lucide-react'
import { Card, Button, Badge, Modal, Empty } from '../components/ui'
import { useToast } from '../lib/toast'
import api from '../lib/api'

export default function ABTestingPage() {
  const toast = useToast()
  const [tests, setTests] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', variant_a: '', variant_b: '' })

  useEffect(() => {
    load()
  }, [])
  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/ab-tests')
      setTests(res.data)
    } catch {
      toast.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  const create = async () => {
    if (!form.name.trim()) {
      toast.error('请输入名称')
      return
    }
    try {
      await api.post('/api/ab-tests', form)
      toast.success('实验已创建')
      setShowModal(false)
      setForm({ name: '', description: '', variant_a: '', variant_b: '' })
      load()
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    }
  }

  const remove = async (id) => {
    if (!confirm('确定删除？')) return
    try {
      await api.delete(`/api/ab-tests/${id}`)
      toast.success('已删除')
      load()
    } catch {
      toast.error('删除失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">A/B 测试</h1>
          <p className="text-sm text-gray-500 mt-1">创建和管理实验，对比不同方案效果</p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>
          新建实验
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin h-6 w-6 border-b-2 border-brand-500 rounded-full" />
        </div>
      ) : tests.length === 0 ? (
        <Card>
          <Empty icon={FlaskConical} title="暂无实验" description="点击新建创建第一个 A/B 测试" />
        </Card>
      ) : (
        <div className="space-y-4">
          {tests.map((t) => (
            <Card key={t.id}>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                    <FlaskConical className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{t.name}</h3>
                    {t.description && <p className="text-sm text-gray-500 mt-1">{t.description}</p>}
                    <div className="flex items-center gap-4 mt-3">
                      <div className="px-3 py-1.5 bg-blue-50 rounded-lg text-sm">
                        <span className="text-blue-600 font-medium">A:</span>{' '}
                        {t.variant_a || '未设置'}
                      </div>
                      <span className="text-gray-300">vs</span>
                      <div className="px-3 py-1.5 bg-green-50 rounded-lg text-sm">
                        <span className="text-green-600 font-medium">B:</span>{' '}
                        {t.variant_b || '未设置'}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                      <Clock className="w-3 h-3" /> {t.created_at?.slice(0, 16)}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" icon={Play}>
                    运行
                  </Button>
                  <Button variant="ghost" size="sm" icon={Trash2} onClick={() => remove(t.id)} />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title="新建 A/B 测试"
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowModal(false)}>
              取消
            </Button>
            <Button variant="primary" onClick={create}>
              创建
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">实验名称 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">方案 A</label>
            <input
              type="text"
              value={form.variant_a}
              onChange={(e) => setForm({ ...form, variant_a: e.target.value })}
              placeholder="对照组描述"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">方案 B</label>
            <input
              type="text"
              value={form.variant_b}
              onChange={(e) => setForm({ ...form, variant_b: e.target.value })}
              placeholder="实验组描述"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}

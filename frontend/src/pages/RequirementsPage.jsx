import React, { useState, useEffect } from 'react';
import { ListTodo, FolderKanban, FileText, Plus, RefreshCw, Loader2, AlertCircle, Search, Sparkles, Eye, MessageSquare } from 'lucide-react';
import axios from 'axios';
import RichTextEditor from '../components/RichTextEditor';

const API = 'http://localhost:8888';

export default function RequirementsPage() {
  const [requirements, setRequirements] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [formData, setFormData] = useState({ name: '', description: '', priority: 'P1', project_id: '' });
  const [viewingReq, setViewingReq] = useState(null);
  const [generatingId, setGeneratingId] = useState(null);

  const fetchRequirements = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/api/requirements`);
      setRequirements(res.data);
      const projRes = await axios.get(`${API}/api/projects`);
      setProjects(projRes.data);
    } catch (err) {
      setError('获取需求列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRequirements(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/api/requirements`, formData);
      setShowCreateForm(false);
      setFormData({ name: '', description: '', priority: 'P1', project_id: '' });
      fetchRequirements();
    } catch (err) {
      alert('创建失败');
    }
  };

  const handleGeneratePRD = async (reqId) => {
    setGeneratingId(reqId);
    try {
      const res = await axios.post(`${API}/api/requirements/${reqId}/generate-prd`);
      if (res.data.status === 'success') {
        fetchRequirements();
      }
    } catch (err) {
      alert('生成 PRD 失败: ' + (err.response?.data?.detail || err.message));
    } finally {
      setGeneratingId(null);
    }
  };

  const handleReview = async (reqId) => {
    setGeneratingId(reqId);
    try {
      const res = await axios.post(`${API}/api/requirements/${reqId}/review`);
      if (res.data.status === 'success') {
        fetchRequirements();
      }
    } catch (err) {
      alert('审查失败: ' + (err.response?.data?.detail || err.message));
    } finally {
      setGeneratingId(null);
    }
  };

  const filtered = requirements.filter(r => {
    const matchSearch = !searchTerm || r.name.toLowerCase().includes(searchTerm.toLowerCase()) || (r.description || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchStatus = !filterStatus || r.status === filterStatus;
    return matchSearch && matchStatus;
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><ListTodo className="w-6 h-6 text-indigo-600" /> 需求管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理和跟踪产品需求，自动生成 PRD 和审查报告</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchRequirements} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
            <RefreshCw className="w-4 h-4" /> 刷新
          </button>
          <button onClick={() => setShowCreateForm(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
            <Plus className="w-4 h-4" /> 新建需求
          </button>
        </div>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" placeholder="搜索需求名称或描述..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 text-sm" />
        </div>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 bg-white">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="generated">已生成</option>
          <option value="reviewed">已审查</option>
        </select>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle className="w-5 h-5" /> {error}
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-sm">
          <h3 className="font-medium mb-4">新建需求</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">需求名称</label>
              <input type="text" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent" placeholder="例如：电商下单功能" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">详细描述</label>
              <RichTextEditor value={formData.description} onChange={(html) => setFormData({...formData, description: html})}
                placeholder="描述这个需求的目标、用户故事、验收标准..." minHeight={160} />
            </div>
            <div className="flex gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">优先级</label>
                <select value={formData.priority} onChange={(e) => setFormData({...formData, priority: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option value="P0">P0 - 阻塞</option>
                  <option value="P1">P1 - 重要</option>
                  <option value="P2">P2 - 一般</option>
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">关联项目</label>
                <select value={formData.project_id} onChange={(e) => setFormData({...formData, project_id: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                  <option value="">无</option>
                  {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowCreateForm(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
              <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">创建</button>
            </div>
          </form>
        </div>
      )}

      {/* Requirements List */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-indigo-600" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          {requirements.length === 0 ? '暂无需求，点击「新建需求」开始' : '没有匹配的需求'}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((req) => (
            <div key={req.id} className="p-5 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                    req.priority === 'P0' ? 'bg-red-100 text-red-700' :
                    req.priority === 'P1' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
                  }`}>{req.priority}</span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                    req.status === 'draft' ? 'bg-gray-100 text-gray-600' :
                    req.status === 'generated' ? 'bg-green-100 text-green-700' :
                    req.status === 'reviewed' ? 'bg-purple-100 text-purple-700' : 'bg-yellow-100 text-yellow-700'
                  }`}>{req.status || 'draft'}</span>
                  <h3 className="font-medium text-gray-900">{req.name}</h3>
                </div>
                <button onClick={() => setViewingReq(req)} className="p-1 text-gray-400 hover:text-indigo-600" title="查看详情">
                  <Eye className="w-4 h-4" />
                </button>
              </div>
              <p className="text-sm text-gray-500 line-clamp-2 mb-3" dangerouslySetInnerHTML={{ __html: req.description || '' }} />
              <div className="flex items-center gap-2 text-xs text-gray-400">
                {req.prd_text && <span className="flex items-center gap-1"><FileText className="w-3 h-3" />PRD 已生成</span>}
                {req.review_report && <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" />已审查</span>}
              </div>
              <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
                {(!req.prd_text || req.status !== 'generated') && (
                  <button onClick={() => handleGeneratePRD(req.id)} disabled={generatingId === req.id}
                    className="flex-1 px-3 py-1.5 text-xs bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 disabled:opacity-50 flex items-center justify-center gap-1">
                    {generatingId === req.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    生成PRD
                  </button>
                )}
                {req.prd_text && req.status !== 'reviewed' && (
                  <button onClick={() => handleReview(req.id)} disabled={generatingId === req.id}
                    className="flex-1 px-3 py-1.5 text-xs bg-green-50 text-green-600 rounded-lg hover:bg-green-100 disabled:opacity-50 flex items-center justify-center gap-1">
                    {generatingId === req.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
                    审查
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {viewingReq && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl">
            <div className="p-6 border-b flex justify-between items-center">
              <div>
                <h2 className="text-xl font-bold">{viewingReq.name}</h2>
                <div className="flex gap-2 mt-1">
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                    viewingReq.priority === 'P0' ? 'bg-red-100 text-red-700' : viewingReq.priority === 'P1' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
                  }`}>{viewingReq.priority}</span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                    viewingReq.status === 'draft' ? 'bg-gray-100 text-gray-600' : viewingReq.status === 'generated' ? 'bg-green-100 text-green-700' : 'bg-purple-100 text-purple-700'
                  }`}>{viewingReq.status || 'draft'}</span>
                </div>
              </div>
              <button onClick={() => setViewingReq(null)} className="text-gray-400 hover:text-gray-600 text-2xl">&times;</button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">描述</label>
                <div className="prose prose-sm max-w-none p-3 bg-gray-50 rounded-lg border" dangerouslySetInnerHTML={{ __html: viewingReq.description || '<span class="text-gray-400">暂无描述</span>' }} />
              </div>
              {viewingReq.prd_text && (
                <details>
                  <summary className="cursor-pointer text-sm font-medium text-indigo-600 hover:text-indigo-700">查看 PRD</summary>
                  <div className="mt-2 prose prose-sm max-w-none p-3 bg-gray-50 rounded-lg border whitespace-pre-wrap font-mono text-xs">{viewingReq.prd_text}</div>
                </details>
              )}
              {viewingReq.review_report && (
                <details>
                  <summary className="cursor-pointer text-sm font-medium text-green-600 hover:text-green-700">查看审查报告</summary>
                  <div className="mt-2 prose prose-sm max-w-none p-3 bg-gray-50 rounded-lg border whitespace-pre-wrap font-mono text-xs">{viewingReq.review_report}</div>
                </details>
              )}
            </div>
            <div className="p-6 border-t flex justify-end">
              <button onClick={() => setViewingReq(null)} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

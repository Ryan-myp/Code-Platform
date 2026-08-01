import React, { useState, useEffect } from 'react';
import { ListTodo, FolderKanban, FileText, Code2, Plus, RefreshCw, Loader2, AlertCircle, Search, Eye, MessageSquare, CheckCircle2, Clock, ArrowRight } from 'lucide-react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import RichTextEditor from '../components/RichTextEditor';

const API = 'http://localhost:8888';

export default function ReqBoardPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('requirements');

  const [requirements, setRequirements] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const [showCreateReq, setShowCreateReq] = useState(false);
  const [reqForm, setReqForm] = useState({ name: '', description: '', priority: 'P1', project_id: '' });
  const [viewingReq, setViewingReq] = useState(null);

  const [showCreateProj, setShowCreateProj] = useState(false);
  const [projForm, setProjForm] = useState({ name: '', description: '' });

  const pipeline = [
    { key: 'prd', label: 'PRD', field: 'prd_text', tab: 'prd', icon: FileText },
    { key: 'review', label: '审查', field: 'review_report', tab: 'review', icon: MessageSquare },
    { key: 'td', label: '方案', field: 'tech_design', tab: 'td', icon: Code2 },
    { key: 'test', label: '测试', field: 'test_cases', tab: 'test', icon: ListTodo },
    { key: 'code', label: '代码', field: 'code', tab: 'code', icon: FileText },
  ];

  const goToPipeline = (reqId, tab) => {
    navigate(`/workspace?requirement_id=${reqId}&tab=${tab}`);
  };

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [reqRes, projRes] = await Promise.all([
        axios.get(`${API}/api/requirements`),
        axios.get(`${API}/api/projects`),
      ]);
      setRequirements(reqRes.data);
      setProjects(projRes.data);
    } catch (err) {
      setError('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleCreateReq = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/api/requirements`, reqForm);
      setShowCreateReq(false);
      setReqForm({ name: '', description: '', priority: 'P1', project_id: '' });
      fetchAll();
    } catch (err) { alert('创建失败'); }
  };

  const handleCreateProj = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/api/projects`, projForm);
      setShowCreateProj(false);
      setProjForm({ name: '', description: '' });
      fetchAll();
    } catch (err) { alert('创建失败'); }
  };

  const filtered = requirements.filter(r => {
    const matchSearch = !searchTerm || r.name.toLowerCase().includes(searchTerm.toLowerCase()) || (r.description || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchStatus = !filterStatus || r.status === filterStatus;
    return matchSearch && matchStatus;
  });

  const tabs = [
    { key: 'requirements', label: '需求列表', icon: ListTodo },
    { key: 'projects', label: '项目看板', icon: FolderKanban },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ListTodo className="w-6 h-6 text-indigo-600" /> 需求看板
          </h1>
          <p className="text-sm text-gray-500 mt-1">管理需求和项目，自动生成 PRD 和审查报告</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchAll} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
            <RefreshCw className="w-4 h-4" /> 刷新
          </button>
          {activeTab === 'requirements' ? (
            <button onClick={() => setShowCreateReq(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
              <Plus className="w-4 h-4" /> 新建需求
            </button>
          ) : (
            <button onClick={() => setShowCreateProj(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
              <Plus className="w-4 h-4" /> 新建项目
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {tabs.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            <tab.icon className="w-4 h-4" /> {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle className="w-5 h-5" /> {error}
        </div>
      )}

      {/* === TAB: Requirements === */}
      {activeTab === 'requirements' && (
        <>
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

          {/* Create Form */}
          {showCreateReq && (
            <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-sm">
              <h3 className="font-medium mb-4">新建需求</h3>
              <form onSubmit={handleCreateReq} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">需求名称</label>
                  <input type="text" value={reqForm.name} onChange={(e) => setReqForm({...reqForm, name: e.target.value})} required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent" placeholder="例如：电商下单功能" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">详细描述</label>
                  <RichTextEditor value={reqForm.description} onChange={(html) => setReqForm({...reqForm, description: html})}
                    placeholder="描述这个需求的目标、用户故事、验收标准..." minHeight={160} />
                </div>
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">优先级</label>
                    <select value={reqForm.priority} onChange={(e) => setReqForm({...reqForm, priority: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                      <option value="P0">P0 - 阻塞</option>
                      <option value="P1">P1 - 重要</option>
                      <option value="P2">P2 - 一般</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">关联项目</label>
                    <select value={reqForm.project_id} onChange={(e) => setReqForm({...reqForm, project_id: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg">
                      <option value="">无</option>
                      {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button type="button" onClick={() => setShowCreateReq(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
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
              {/* Pipeline stages */}
              <div className="flex items-center gap-0.5 mt-3 pt-3 border-t border-gray-100 flex-wrap">
                {pipeline.map((p, i) => {
                  const done = !!req[p.field]
                  return (
                    <React.Fragment key={p.key}>
                      {i > 0 && <ArrowRight className="w-3 h-3 text-gray-300" />}
                      <button onClick={() => goToPipeline(req.id, p.tab)}
                        className={`flex items-center gap-1 px-2 py-1 text-xs rounded-md transition-colors ${
                          done
                            ? 'bg-green-50 text-green-700 hover:bg-green-100'
                            : 'bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600'
                        }`}>
                        {done ? <CheckCircle2 className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                        {p.label}
                      </button>
                    </React.Fragment>
                  )
                })}
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
        </>
      )}

      {/* === TAB: Projects === */}
      {activeTab === 'projects' && (
        <>
          {showCreateProj && (
            <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-sm">
              <h3 className="font-medium mb-4">新建项目</h3>
              <form onSubmit={handleCreateProj} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">项目名称</label>
                  <input type="text" value={projForm.name} onChange={(e) => setProjForm({...projForm, name: e.target.value})} required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent" placeholder="例如：电商平台项目" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                  <textarea value={projForm.description} onChange={(e) => setProjForm({...projForm, description: e.target.value})} rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent" placeholder="描述这个项目..." />
                </div>
                <div className="flex gap-2 justify-end">
                  <button type="button" onClick={() => setShowCreateProj(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
                  <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">创建</button>
                </div>
              </form>
            </div>
          )}

          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-indigo-600" /></div>
          ) : projects.length === 0 ? (
            <div className="text-center py-12 text-gray-400">暂无项目，点击「新建项目」开始</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((proj) => (
                <div key={proj.id} className="p-4 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-2">
                    <FolderKanban className="w-5 h-5 text-indigo-600" />
                    <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                      proj.status === 'planning' ? 'bg-blue-100 text-blue-700' :
                      proj.status === 'active' ? 'bg-green-100 text-green-700' :
                      proj.status === 'completed' ? 'bg-gray-100 text-gray-700' : 'bg-yellow-100 text-yellow-700'
                    }`}>{proj.status || 'planning'}</span>
                  </div>
                  <h3 className="font-medium">{proj.name}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">{proj.description}</p>
                  <div className="mt-3 flex items-center gap-4 text-sm text-gray-400">
                    <span>任务: {proj.task_count || 0}</span>
                    <span>完成: {proj.done_count || 0}</span>
                    <span>进度: {proj.progress || 0}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-1.5 mt-2">
                    <div className="bg-indigo-600 h-1.5 rounded-full" style={{ width: `${proj.progress || 0}%` }}></div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

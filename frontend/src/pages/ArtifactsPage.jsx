import React, { useState, useEffect } from 'react';
import { FileText, RefreshCw, Loader2, AlertCircle, Eye, FolderKanban, ListTodo, Search, ChevronDown, ChevronRight, GitBranch, Package } from 'lucide-react';
import axios from 'axios';

const API = 'http://localhost:8888';

export default function ArtifactsPage() {
  const [artifacts, setArtifacts] = useState([]);
  const [projects, setProjects] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [viewMode, setViewMode] = useState('tree'); // 'tree' | 'list' | 'timeline'
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedProjects, setExpandedProjects] = useState({});
  const [expandedReqs, setExpandedReqs] = useState({});
  const [filterType, setFilterType] = useState('');

  const fetchData = async () => {
    try {
      setLoading(true);
      const [artRes, projRes, reqRes] = await Promise.all([
        axios.get(`${API}/api/artifacts`),
        axios.get(`${API}/api/projects`),
        axios.get(`${API}/api/requirements`),
      ]);
      setArtifacts(artRes.data);
      setProjects(projRes.data);
      setRequirements(reqRes.data);
    } catch (err) {
      setError('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const toggleProject = (pid) => {
    setExpandedProjects(prev => ({ ...prev, [pid]: !prev[pid] }))
  }
  const toggleReq = (rid) => {
    setExpandedReqs(prev => ({ ...prev, [rid]: !prev[rid] }))
  }

  const getArtifactIcon = (type) => {
    const icons = { prd: '📋', review: '🔍', td: '📐', test: '🧪', code: '💻' }
    return icons[type] || '📄'
  }

  const getArtifactLabel = (type) => {
    const labels = { prd: 'PRD', review: '审查报告', td: '技术方案', test: '测试用例', code: '代码生成' }
    return labels[type] || type
  }

  const filtered = artifacts.filter(a => {
    const matchSearch = !searchTerm || a.type?.toLowerCase().includes(searchTerm.toLowerCase()) || a.requirement_id?.toLowerCase().includes(searchTerm.toLowerCase())
    const matchType = !filterType || a.type === filterType
    return matchSearch && matchType
  })

  // Group by project -> requirement -> artifacts
  const groupedByProject = {}
  filtered.forEach(art => {
    if (!art.project_id) art.project_id = ''
    if (!groupedByProject[art.project_id]) groupedByProject[art.project_id] = {}
    if (!art.requirement_id) {
      const key = '__unassigned__'
      if (!groupedByProject[art.project_id][key]) groupedByProject[art.project_id][key] = []
      groupedByProject[art.project_id][key].push(art)
    } else {
      if (!groupedByProject[art.project_id][art.requirement_id]) groupedByProject[art.project_id][art.requirement_id] = []
      groupedByProject[art.project_id][art.requirement_id].push(art)
    }
  })

  const getProjectName = (pid) => {
    if (pid === '__unassigned__') return '未关联需求'
    const p = projects.find(p => p.id === pid)
    return p ? p.name : pid
  }

  const getReqName = (rid) => {
    if (rid === '__unassigned__') return '未关联需求'
    const r = requirements.find(r => r.id === rid)
    return r ? r.name : rid
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Package className="w-6 h-6 text-emerald-600" /> 成果查看</h1>
          <p className="text-sm text-gray-500 mt-1">按项目和需求维度查看生成的 PRD、审查报告、技术方案等</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
          <RefreshCw className="w-4 h-4" /> 刷新
        </button>
      </div>

      {/* Search & Filter & View Mode */}
      <div className="flex gap-3 items-center flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" placeholder="搜索成果类型或需求ID..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/10 text-sm" />
        </div>
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="px-4 py-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:border-emerald-500">
          <option value="">全部类型</option>
          <option value="prd">PRD</option>
          <option value="review">审查报告</option>
          <option value="td">技术方案</option>
          <option value="test">测试用例</option>
          <option value="code">代码</option>
        </select>
        <div className="flex bg-gray-100 rounded-lg p-0.5">
          {[
            { key: 'tree', label: '🌳 树形', icon: '🌳' },
            { key: 'list', label: '📋 列表', icon: '📋' },
            { key: 'timeline', label: '⏱ 时间线', icon: '⏱' },
          ].map(mode => (
            <button key={mode.key} onClick={() => setViewMode(mode.key)}
              className={`px-3 py-1.5 text-xs rounded-md transition-all ${viewMode === mode.key ? 'bg-white shadow-sm text-emerald-700 font-medium' : 'text-gray-500 hover:text-gray-700'}`}>
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle className="w-5 h-5" /> {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-emerald-600" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Package className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">暂无成果</p>
          <p className="text-sm mt-1">创建需求并生成 PRD/审查报告后，成果将在此显示</p>
        </div>
      ) : viewMode === 'tree' ? (
        /* ─── 树形视图 ─────────────────────────────────────── */
        <div className="space-y-2">
          {Object.entries(groupedByProject).map(([projectId, reqMap]) => {
            const projectName = getProjectName(projectId)
            const isExpanded = expandedProjects[projectId]
            return (
              <div key={projectId} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <button onClick={() => toggleProject(projectId)}
                  className="w-full flex items-center gap-3 p-4 hover:bg-gray-50 transition-colors">
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                  <FolderKanban className="w-5 h-5 text-amber-500" />
                  <span className="font-medium text-gray-900">{projectName}</span>
                  <span className="text-xs text-gray-400 ml-auto">{Object.values(reqMap).reduce((s, arr) => s + arr.length, 0)} 个成果</span>
                </button>
                {isExpanded && Object.entries(reqMap).map(([reqId, arts]) => {
                  const reqName = getReqName(reqId)
                  const reqExpanded = expandedReqs[reqId]
                  return (
                    <div key={reqId} className="ml-6 border-l-2 border-gray-100 pl-4 py-2">
                      <button onClick={() => toggleReq(reqId)}
                        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 py-1">
                        {reqExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                        <ListTodo className="w-4 h-4 text-gray-400" />
                        <span>{reqName}</span>
                        <span className="text-xs text-gray-400">({arts.length})</span>
                      </button>
                      {reqExpanded && (
                        <div className="ml-6 mt-2 space-y-1">
                          {arts.map(art => (
                            <div key={art.id} className="flex items-center gap-3 p-2.5 hover:bg-gray-50 rounded-lg cursor-pointer group"
                              onClick={() => setSelectedArtifact(art)}>
                              <span className="text-lg">{getArtifactIcon(art.type)}</span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-medium text-gray-800">{getArtifactLabel(art.type)}</span>
                                  <span className="text-xs text-gray-400">v{art.version || 1}</span>
                                </div>
                                <div className="flex items-center gap-3 text-xs text-gray-400">
                                  <span>ID: {art.id.slice(0, 12)}...</span>
                                  <span>{new Date(art.created_at).toLocaleDateString()}</span>
                                  {art.author && <span>作者: {art.author}</span>}
                                </div>
                              </div>
                              <Eye className="w-4 h-4 text-gray-300 group-hover:text-emerald-600" />
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>
      ) : viewMode === 'list' ? (
        /* ─── 列表视图 ─────────────────────────────────────── */
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">类型</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">关联需求</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">版本</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">作者</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">创建时间</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map(art => {
                const req = requirements.find(r => r.id === art.requirement_id)
                const proj = projects.find(p => p.id === art.project_id)
                return (
                  <tr key={art.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3"><span className="text-lg">{getArtifactIcon(art.type)}</span></td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{art.id.slice(0, 16)}...</td>
                    <td className="px-4 py-3">
                      <div className="text-gray-700">{req?.name || '—'}</div>
                      {proj && <div className="text-xs text-gray-400">{proj.name}</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-500">v{art.version || 1}</td>
                    <td className="px-4 py-3 text-gray-500">{art.author || '—'}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{new Date(art.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => setSelectedArtifact(art)} className="text-emerald-600 hover:text-emerald-700 text-sm font-medium">查看</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* ─── 时间线视图 ───────────────────────────────────── */
        <div className="space-y-0">
          {filtered.map((art, idx) => {
            const req = requirements.find(r => r.id === art.requirement_id)
            const proj = projects.find(p => p.id === art.project_id)
            return (
              <div key={art.id} className="flex gap-4 group">
                <div className="flex flex-col items-center">
                  <div className="w-3 h-3 rounded-full bg-emerald-400 ring-4 ring-white group-hover:ring-emerald-50 transition-all" />
                  {idx < filtered.length - 1 && <div className="w-px flex-1 bg-gray-200 my-1" />}
                </div>
                <div className="flex-1 pb-6">
                  <div className="bg-white border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow cursor-pointer" onClick={() => setSelectedArtifact(art)}>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-xl">{getArtifactIcon(art.type)}</span>
                      <div>
                        <span className="text-sm font-semibold text-gray-800">{getArtifactLabel(art.type)}</span>
                        <span className="text-xs text-gray-400 ml-2">v{art.version || 1}</span>
                      </div>
                      <span className="ml-auto text-xs text-gray-400">{new Date(art.created_at).toLocaleString()}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-400">
                      {proj && <span className="flex items-center gap-1"><FolderKanban className="w-3 h-3" />{proj.name}</span>}
                      {req && <span className="flex items-center gap-1"><ListTodo className="w-3 h-3" />{req.name}</span>}
                      <span className="font-mono">{art.id.slice(0, 12)}...</span>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Modal */}
      {selectedArtifact && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedArtifact(null)}>
          <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b bg-gray-50">
              <div>
                <h3 className="font-bold text-gray-900 flex items-center gap-2">
                  <span>{getArtifactIcon(selectedArtifact.type)}</span>
                  {getArtifactLabel(selectedArtifact.type)}
                  <span className="text-sm font-normal text-gray-400">v{selectedArtifact.version || 1}</span>
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">{selectedArtifact.id} · {new Date(selectedArtifact.created_at).toLocaleString()}</p>
              </div>
              <button onClick={() => setSelectedArtifact(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
            </div>
            <div className="p-5 overflow-auto max-h-[65vh]">
              <pre className="whitespace-pre-wrap text-sm font-mono text-gray-800 bg-gray-50 p-5 rounded-xl border leading-relaxed">{selectedArtifact.content || selectedArtifact.content_preview || '无内容'}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

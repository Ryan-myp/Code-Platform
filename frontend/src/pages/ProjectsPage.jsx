import React, { useState, useEffect } from 'react';
import { FolderKanban, Plus, RefreshCw, Loader2, AlertCircle, CheckCircle, Clock, Ban } from 'lucide-react';
import axios from 'axios';

const API = 'http://localhost:8888';

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({ name: '', description: '' });

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/api/projects`);
      setProjects(res.data);
    } catch (err) {
      setError('获取项目列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProjects(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/api/projects`, formData);
      setShowCreateForm(false);
      setFormData({ name: '', description: '' });
      fetchProjects();
    } catch (err) {
      alert('创建失败');
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">项目管理</h1>
          <p className="text-sm text-gray-500 mt-1">跟踪项目进度、任务和里程碑</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchProjects} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
            <RefreshCw className="w-4 h-4" /> 刷新
          </button>
          <button onClick={() => setShowCreateForm(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
            <Plus className="w-4 h-4" /> 新建项目
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle className="w-5 h-5" /> {error}
        </div>
      )}

      {showCreateForm && (
        <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-sm">
          <h3 className="font-medium mb-4">新建项目</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">项目名称</label>
              <input type="text" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent" placeholder="例如：电商平台项目" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <textarea value={formData.description} onChange={(e) => setFormData({...formData, description: e.target.value})} rows={3} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent" placeholder="描述这个项目..." />
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowCreateForm(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
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
                }`}>
                  {proj.status || 'planning'}
                </span>
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
    </div>
  );
}

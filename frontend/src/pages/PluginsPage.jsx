import React, { useState, useEffect } from 'react';
import { Puzzle, RefreshCw, Loader2, AlertCircle, Play, HeartPulse } from 'lucide-react';
import axios from 'axios';

const API = 'http://localhost:8888';

export default function PluginsPage() {
  const [plugins, setPlugins] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [executing, setExecuting] = useState(null);
  const [testResult, setTestResult] = useState(null);

  const fetchPlugins = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/api/plugins`);
      setPlugins(res.data.plugins || []);
      setCategories(res.data.categories || []);
    } catch (err) {
      setError('获取插件列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPlugins(); }, []);

  const handleExecute = async (pluginName) => {
    setExecuting(pluginName);
    setTestResult(null);
    try {
      const res = await axios.post(`${API}/api/plugins/${pluginName}/execute`, {
        input_data: { prd_text: "这是一个测试PRD，用于验证插件功能是否正常" }
      });
      setTestResult(res.data);
    } catch (err) {
      setTestResult({ status: 'failed', error: err.response?.data?.detail || err.message });
    } finally {
      setExecuting(null);
    }
  };

  const filteredPlugins = selectedCategory === 'all' ? plugins : plugins.filter(p => p.category === selectedCategory);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">插件市场</h1>
          <p className="text-sm text-gray-500 mt-1">Plugin 注册中心 — 查看和管理所有已注册的引擎插件</p>
        </div>
        <button onClick={fetchPlugins} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm">
          <RefreshCw className="w-4 h-4" /> 刷新
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle className="w-5 h-5" /> {error}
        </div>
      )}

      {/* Category Filter */}
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setSelectedCategory('all')} className={`px-3 py-1.5 text-sm rounded-lg ${selectedCategory === 'all' ? 'bg-indigo-600 text-white' : 'bg-white border border-gray-300'}`}>全部 ({plugins.length})</button>
        {categories.map(cat => {
          const count = plugins.filter(p => p.category === cat).length;
          return (
            <button key={cat} onClick={() => setSelectedCategory(cat)} className={`px-3 py-1.5 text-sm rounded-lg ${selectedCategory === cat ? 'bg-indigo-600 text-white' : 'bg-white border border-gray-300'}`}>{cat} ({count})</button>
          );
        })}
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-indigo-600" /></div>
      ) : filteredPlugins.length === 0 ? (
        <div className="text-center py-12 text-gray-400">暂无插件</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredPlugins.map((plugin) => (
            <div key={plugin.name} className="p-4 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
                    <Puzzle className="w-4 h-4 text-indigo-600" />
                  </div>
                  <div>
                    <h3 className="font-medium">{plugin.name}</h3>
                    <span className="text-xs text-gray-500">v{plugin.version}</span>
                  </div>
                </div>
                <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">{plugin.category}</span>
              </div>
              <p className="text-sm text-gray-600 mb-3">{plugin.description}</p>
              <div className="flex gap-2">
                <button onClick={() => handleExecute(plugin.name)} disabled={!!executing} className="flex items-center gap-1 px-3 py-1.5 text-xs bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 disabled:opacity-50">
                  {executing === plugin.name ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                  {executing === plugin.name ? '执行中...' : '测试执行'}
                </button>
              </div>
              {testResult && (
                <div className="mt-3 p-3 bg-gray-50 rounded-lg text-xs">
                  <div className="flex items-center gap-1 mb-1">
                    {testResult.status === 'success' ? <HeartPulse className="w-3 h-3 text-green-500" /> : <AlertCircle className="w-3 h-3 text-red-500" />}
                    <span className={`font-medium ${testResult.status === 'success' ? 'text-green-600' : 'text-red-600'}`}>{testResult.status}</span>
                  </div>
                  {testResult.meta && <div className="text-gray-500">耗时: {testResult.meta.elapsed?.toFixed(2)}s</div>}
                  {testResult.error && <div className="text-red-500 mt-1">{testResult.error}</div>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect, useRef } from 'react'
import { Camera, Upload, Scissors, Image as ImageIcon, LayoutTemplate, Sparkles, Download, Trash2, Eye, Plus, Loader, DownloadAll, RefreshCw, Zap } from 'lucide-react'

const API_BASE = 'http://localhost:8888'

export default function ImageFactoryPage() {
  const [activeTab, setActiveTab] = useState('generate')
  const [images, setImages] = useState([])
  const [templates, setTemplates] = useState([])
  const [stats, setStats] = useState({ total_images: 0, total_templates: 0, api_configured: false })
  
  // 生成状态
  const [prompt, setPrompt] = useState('')
  const [size, setSize] = useState('1024x1024')
  const [batchSize, setBatchSize] = useState(1)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedImages, setGeneratedImages] = useState([])
  const [generationError, setGenerationError] = useState(null)
  
  // 模板状态
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [overrides, setOverrides] = useState({})
  
  const fileInputRef = useRef(null)
  
  useEffect(() => {
    loadStats()
    loadImages()
    loadTemplates()
  }, [])
  
  const loadStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/stats`)
      const data = await res.json()
      setStats(data)
    } catch (e) {
      console.error('Failed to load stats', e)
    }
  }
  
  const loadImages = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/images`)
      const data = await res.json()
      setImages(data)
      setGeneratedImages(data.slice(0, 4))
    } catch (e) {
      console.error('Failed to load images', e)
    }
  }
  
  const loadTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/templates`)
      const data = await res.json()
      setTemplates(data)
      if (data.length > 0 && !selectedTemplate) {
        setSelectedTemplate(data[0].id)
      }
    } catch (e) {
      console.error('Failed to load templates', e)
    }
  }
  
  const handleGenerate = async () => {
    if (!prompt.trim()) {
      alert('请输入提示词')
      return
    }
    
    setIsGenerating(true)
    setGenerationError(null)
    setGeneratedImages([])
    
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/generate/text-to-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ 
          prompt, 
          size,
          batch_size: batchSize,
          n: 1
        })
      })
      
      const data = await res.json()
      
      if (data.results && data.results.length > 0) {
        const successResults = data.results.filter(r => !r.error)
        const errorResults = data.results.filter(r => r.error)
        
        setGeneratedImages(successResults.length > 0 ? successResults.map(r => ({
          ...r,
          url: r.url || `http://localhost:8888${r.url}`
        })) : [])
        
        if (errorResults.length > 0) {
          setGenerationError(errorResults[0].error)
        }
        
        loadImages()
      } else {
        setGenerationError(data.detail || '生成失败，请检查 API Key 配置')
      }
    } catch (e) {
      setGenerationError(`请求失败：${e.message}`)
    } finally {
      setIsGenerating(false)
    }
  }
  
  const handleRenderTemplate = async () => {
    if (!selectedTemplate) {
      alert('请选择模板')
      return
    }
    
    setIsGenerating(true)
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/template/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: selectedTemplate,
          overrides
        })
      })
      
      const data = await res.json()
      if (data.url) {
        setGeneratedImages([{ ...data, url: `http://localhost:8888${data.url}` }])
        loadImages()
      }
    } catch (e) {
      console.error('Template render failed', e)
    } finally {
      setIsGenerating(false)
    }
  }
  
  const handleDelete = async (filename) => {
    try {
      await fetch(`${API_BASE}/api/image-factory/images/${filename}`, { method: 'DELETE' })
      loadImages()
      setGeneratedImages(prev => prev.filter(img => img.filename !== filename))
    } catch (e) {
      console.error('Failed to delete', e)
    }
  }
  
  const handleDownload = async (image) => {
    try {
      const res = await fetch(image.url)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = image.filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Download failed', e)
    }
  }
  
  const handleDownloadAll = async () => {
    for (const img of generatedImages) {
      await handleDownload(img)
      await new Promise(r => setTimeout(r, 500))
    }
  }
  
  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    const formData = new FormData()
    formData.append('image', file)
    
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/edit/crop`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (data.url) {
        loadImages()
      }
    } catch (e) {
      console.error('Upload failed', e)
    }
  }
  
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">🎨 图片工厂</h1>
          <p className="text-gray-500 mt-2">AI 图片生成与编辑工具</p>
          {!stats.api_configured && (
            <div className="mt-2 px-3 py-2 bg-yellow-50 text-yellow-700 rounded-lg text-sm">
              ⚠️ 注意：未配置 AGNES_API_KEY，文生图功能将使用本地模拟
            </div>
          )}
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-2xl font-bold text-purple-600">{stats.total_images}</div>
            <div className="text-sm text-gray-500">已生成图片</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-2xl font-bold text-blue-600">{stats.total_templates}</div>
            <div className="text-sm text-gray-500">可用模板</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-2xl font-bold text-green-600">agnes-2.1</div>
            <div className="text-sm text-gray-500">模型版本</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className={`text-2xl font-bold ${stats.api_configured ? 'text-green-600' : 'text-yellow-600'}`}>
              {stats.api_configured ? '✅' : '⚠️'}
            </div>
            <div className="text-sm text-gray-500">API 状态</div>
          </div>
        </div>
        
        {/* Tabs */}
        <div className="flex space-x-2 mb-6 border-b border-gray-200">
          {[
            { id: 'generate', label: '文生图', icon: Sparkles },
            { id: 'template', label: '模板合成', icon: LayoutTemplate },
            { id: 'edit', label: '图片编辑', icon: Scissors },
            { id: 'gallery', label: '图片库', icon: ImageIcon },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-purple-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-100'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
        
        {/* Generate Tab */}
        {activeTab === 'generate' && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">🎨 文生图</h2>
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">提示词</label>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="描述你想要的图片，例如：Professional product photography of a luxury perfume bottle, studio lighting, white background"
                    className="w-full h-32 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">尺寸</label>
                    <select
                      value={size}
                      onChange={(e) => setSize(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="1024x1024">1024x1024 (1:1)</option>
                      <option value="800x600">800x600 (4:3)</option>
                      <option value="600x800">600x800 (3:4)</option>
                      <option value="1280x720">1280x720 (16:9)</option>
                      <option value="720x1280">720x1280 (9:16)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">批量数量</label>
                    <select
                      value={batchSize}
                      onChange={(e) => setBatchSize(Number(e.target.value))}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="1">1 张</option>
                      <option value="2">2 张</option>
                      <option value="3">3 张</option>
                      <option value="4">4 张</option>
                    </select>
                  </div>
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating || !prompt.trim()}
                  className="w-full bg-purple-600 text-white py-3 rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {isGenerating ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      <span>生成中...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      <span>生成图片</span>
                    </>
                  )}
                </button>
                {generationError && (
                  <div className="px-4 py-3 bg-red-50 text-red-700 rounded-lg text-sm">
                    ❌ {generationError}
                  </div>
                )}
              </div>
              
              {/* Generated Images */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium text-gray-700">生成结果</h3>
                  {generatedImages.length > 1 && (
                    <button
                      onClick={handleDownloadAll}
                      className="flex items-center space-x-1 text-sm text-purple-600 hover:text-purple-700"
                    >
                      <DownloadAll className="w-4 h-4" />
                      <span>全部下载</span>
                    </button>
                  )}
                </div>
                {generatedImages.length > 0 ? (
                  <div className="grid grid-cols-2 gap-4">
                    {generatedImages.map((img, idx) => (
                      <div key={idx} className="relative group">
                        <img
                          src={img.url}
                          alt={img.prompt}
                          className="w-full h-48 object-cover rounded-lg shadow-sm"
                        />
                        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-all rounded-lg flex items-center justify-center space-x-2 opacity-0 group-hover:opacity-100">
                          <button
                            onClick={() => window.open(img.url, '_blank')}
                            className="p-2 bg-white rounded-full hover:bg-gray-100"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDownload(img)}
                            className="p-2 bg-white rounded-full hover:bg-green-100 hover:text-green-600"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(img.filename)}
                            className="p-2 bg-white rounded-full hover:bg-red-100 hover:text-red-600"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="h-48 flex items-center justify-center border-2 border-dashed border-gray-300 rounded-lg">
                    <p className="text-gray-400">生成图片后将在这里显示</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Template Tab */}
        {activeTab === 'template' && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">📋 模板合成</h2>
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">选择模板</label>
                  <select
                    value={selectedTemplate}
                    onChange={(e) => setSelectedTemplate(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  >
                    {templates.map(t => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleRenderTemplate}
                  disabled={isGenerating || !selectedTemplate}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {isGenerating ? <><Loader className="w-5 h-5 animate-spin inline" /> 渲染中...</> : <>生成图片</>}
                </button>
              </div>
              
              <div>
                <h3 className="font-medium text-gray-700 mb-4">预览</h3>
                {generatedImages.length > 0 ? (
                  <div className="relative group">
                    <img
                      src={generatedImages[0].url}
                      alt="Template result"
                      className="w-full h-64 object-cover rounded-lg shadow-sm"
                    />
                    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-all rounded-lg flex items-center justify-center space-x-2 opacity-0 group-hover:opacity-100">
                      <button
                        onClick={() => window.open(generatedImages[0].url, '_blank')}
                        className="p-2 bg-white rounded-full hover:bg-gray-100"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDownload(generatedImages[0])}
                        className="p-2 bg-white rounded-full hover:bg-green-100 hover:text-green-600"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="h-64 flex items-center justify-center border-2 border-dashed border-gray-300 rounded-lg">
                    <p className="text-gray-400">选择模板并点击生成</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Edit Tab */}
        {activeTab === 'edit' && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">✂️ 图片编辑</h2>
            <div className="grid grid-cols-3 gap-4">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-center"
              >
                <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="text-sm text-gray-600">上传图片</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </button>
              <button className="p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-center">
                <Scissors className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="text-sm text-gray-600">智能抠图</p>
              </button>
              <button className="p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-center">
                <Zap className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="text-sm text-gray-600">批量处理</p>
              </button>
            </div>
          </div>
        )}
        
        {/* Gallery Tab */}
        {activeTab === 'gallery' && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">📷 图片库</h2>
              <button onClick={loadImages} className="flex items-center space-x-1 px-3 py-1 text-sm text-purple-600 hover:bg-purple-50 rounded-lg">
                <RefreshCw className="w-4 h-4" />
                <span>刷新</span>
              </button>
            </div>
            
            {images.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <ImageIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>暂无图片，去生成一张吧！</p>
              </div>
            ) : (
              <div className="grid grid-cols-4 gap-4">
                {images.map(img => (
                  <div key={img.filename} className="relative group">
                    <img
                      src={img.url}
                      alt={img.filename}
                      className="w-full h-40 object-cover rounded-lg"
                    />
                    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all rounded-lg flex items-center justify-center space-x-2 opacity-0 group-hover:opacity-100">
                      <button
                        onClick={() => window.open(img.url, '_blank')}
                        className="p-2 bg-white rounded-full hover:bg-gray-100"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDownload(img)}
                        className="p-2 bg-white rounded-full hover:bg-green-100 hover:text-green-600"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(img.filename)}
                        className="p-2 bg-white rounded-full hover:bg-red-100 hover:text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 truncate">{img.filename}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

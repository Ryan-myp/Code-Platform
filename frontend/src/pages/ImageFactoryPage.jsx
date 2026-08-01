import React, { useState, useEffect, useRef } from 'react'
import { 
  Sparkles, Image as ImageIcon, LayoutTemplate, Scissors, 
  Download, Trash2, Eye, Upload, Plus, Loader,
  RefreshCw, Zap, Palette, TrendingUp,
  Film, Music, Type, Layers, Maximize2, RotateCw,
  X, ChevronDown, Search, Filter, Grid, List as ListIcon,
  Heart, Share2, MoreVertical, DownloadCloud, Copy,
  Wand2, Sliders, Settings, ArrowLeft, ArrowRight,
  ZoomIn, ZoomOut, Minimize2, Crop, FlipHorizontal,
  Sun, Moon, SunMoon, UserCircle, Shirt, Palette as PaletteIcon,
  Camera, Download as DownloadIcon
} from 'lucide-react'

const API_BASE = 'http://localhost:8888'

// 提示词模板
const PROMPT_TEMPLATES = [
  { name: '商品摄影', prompt: 'Professional product photography of [PRODUCT], studio lighting, white background, high-end commercial style, shot on Canon EOS R5, 85mm lens' },
  { name: '场景图', prompt: 'Lifestyle scene with [SUBJECT], [ACTION], [ENVIRONMENT], golden hour lighting, cinematic composition, 4K quality' },
  { name: '社交媒体', prompt: '[PLATFORM] post design, [THEME], vertical format 9:16, bold typography area, modern aesthetic' },
  { name: 'Logo设计', prompt: 'Minimalist logo design for [BRAND], [STYLE] style, vector graphic, clean lines, modern aesthetic' },
  { name: '海报设计', prompt: 'Promotional poster for [EVENT], dynamic composition, bold colors, typography space, professional design' },
]

// 尺寸选项
const SIZES = [
  { label: '正方形', value: '1024x1024', ratio: '1:1' },
  { label: '横向', value: '1280x720', ratio: '16:9' },
  { label: '纵向', value: '720x1280', ratio: '9:16' },
  { label: '宽屏', value: '1920x1080', ratio: '16:9' },
  { label: '竖版', value: '1080x1350', ratio: '4:5' },
  { label: '封面', value: '800x600', ratio: '4:3' },
]

export default function ImageFactoryPage() {
  const [activeTab, setActiveTab] = useState('generate')
  const [images, setImages] = useState([])
  const [templates, setTemplates] = useState([])
  const [stats, setStats] = useState({ total_images: 0, total_templates: 0, api_configured: false })
  const [darkMode, setDarkMode] = useState(false)
  const [viewMode, setViewMode] = useState('grid') // 'grid' or 'list'
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)
  
  // 生成状态
  const [prompt, setPrompt] = useState('')
  const [selectedSize, setSelectedSize] = useState('1024x1024')
  const [batchSize, setBatchSize] = useState(1)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedImages, setGeneratedImages] = useState([])
  const [generationError, setGenerationError] = useState(null)
  const [generationProgress, setGenerationProgress] = useState(0)
  
  // 模板状态
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [renderingImage, setRenderingImage] = useState(null)
  const [templateOverrides, setTemplateOverrides] = useState({})
  
  // 编辑状态
  const [uploadedImage, setUploadedImage] = useState(null)
  const [editOptions, setEditOptions] = useState({
    angle: '0',
    filter: 'none',
    brightness: 1.0,
    contrast: 1.0,
    saturation: 1.0,
  })

  // 虚拟试衣状态
  const [personImage, setPersonImage] = useState(null)
  const [clothingImage, setClothingImage] = useState(null)
  const [tryOnStyle, setTryOnStyle] = useState('casual')
  const [tryOnBackground, setTryOnBackground] = useState('beach')
  const [tryOnDescription, setTryOnDescription] = useState('')
  const [isTryOnGenerating, setIsTryOnGenerating] = useState(false)
  const [tryOnResult, setTryOnResult] = useState(null)

  const editTools = [
    { icon: Crop, label: '裁剪', action: 'crop' },
    { icon: RotateCw, label: '旋转', action: 'rotate' },
    { icon: FlipHorizontal, label: '翻转', action: 'flip' },
    { icon: Sliders, label: '调整', action: 'adjust' },
  ]

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
      setGeneratedImages(data.slice(0, 8))
    } catch (e) {
      console.error('Failed to load images', e)
    }
  }
  
  const loadTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/templates`)
      const data = await res.json()
      setTemplates(data)
      if (data.length > 0) {
        // 延迟设置默认模板，避免在渲染过程中修改状态
        setTimeout(() => {
          if (!selectedTemplate) {
            setSelectedTemplate(data[0].id)
          }
        }, 0)
      }
    } catch (e) {
      console.error('Failed to load templates', e)
    }
  }
  
  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setGenerationError('请输入提示词')
      return
    }
    
    setIsGenerating(true)
    setGenerationError(null)
    setGenerationProgress(0)
    setGeneratedImages([])
    
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/generate/text-to-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ 
          prompt, 
          size: selectedSize,
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
          url: r.url || `http://localhost:8888${r.url}`,
          prompt: r.prompt || prompt
        })) : [])
        
        if (errorResults.length > 0) {
          setGenerationError(errorResults[0].error)
        }
        
        loadImages()
      } else {
        setGenerationError(data.detail || data.error || '生成失败，请检查 API Key 配置')
      }
    } catch (e) {
      setGenerationError(`请求失败：${e.message}`)
    } finally {
      setIsGenerating(false)
      setGenerationProgress(0)
    }
  }
  
  const handleRenderTemplate = async () => {
    if (!selectedTemplate) {
      alert('请选择模板')
      return
    }
    
    setRenderingImage(selectedTemplate)
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/template/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: selectedTemplate,
          overrides: templateOverrides
        })
      })
      
      const data = await res.json()
      if (data.url) {
        setGeneratedImages([{ ...data, url: `http://localhost:8888${data.url}`, prompt: '模板渲染' }])
        loadImages()
      } else if (data.error) {
        alert(`渲染失败：${data.error}`)
      }
    } catch (e) {
      console.error('Template render failed', e)
    } finally {
      setRenderingImage(null)
    }
  }
  
  const handleDelete = async (filename) => {
    try {
      await fetch(`${API_BASE}/api/image-factory/images/${filename}`, { method: 'DELETE' })
      loadImages()
      setGeneratedImages(prev => prev.filter(img => img.filename !== filename))
      if (selectedImage?.filename === filename) {
        setSelectedImage(null)
      }
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
      await new Promise(r => setTimeout(r, 300))
    }
  }
  
  const handleEditUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    setUploading(true)
    const formData = new FormData()
    formData.append('image', file)
    
    try {
      const res = await fetch(`${API_BASE}/api/image-factory/edit/resize`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (data.url) {
        setUploadedImage({ ...data, url: `${API_BASE}${data.url}` })
        loadImages()
      }
    } catch (e) {
      console.error('Upload failed', e)
    } finally {
      setUploading(false)
    }
  }
  
  const handleEditImage = async (image, editType, options = {}) => {
    try {
      const formData = new FormData()
      formData.append('image', await (await fetch(image.url)).blob())
      
      let endpoint = `/api/image-factory/edit/${editType}`
      let params = {}
      
      if (editType === 'crop') {
        params = { x1: 0, y1: 0, x2: 100, y2: 100 }
      } else if (editType === 'rotate') {
        params = { angle: editOptions.angle || '0' }
      } else if (editType === 'flip') {
        params = { direction: 'horizontal' }
      } else if (editType === 'filter') {
        params = { filter_type: editOptions.filter || 'none', intensity: 0.5 }
      } else if (editType === 'adjust') {
        params = {
          brightness: editOptions.brightness || 1.0,
          contrast: editOptions.contrast || 1.0,
          saturation: editOptions.saturation || 1.0,
        }
      }
      
      Object.entries(params).forEach(([k, v]) => formData.append(k, v))
      
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (data.url) {
        setUploadedImage({ ...data, url: `${API_BASE}${data.url}` })
        loadImages()
      }
    } catch (e) {
      console.error('Edit failed', e)
    }
  }
  
  // 虚拟试衣处理
  const handleTryOn = async () => {
    if (!personImage || !clothingImage) {
      alert('请上传人物照片和衣物照片')
      return
    }
    
    setIsTryOnGenerating(true)
    setTryOnResult(null)
    
    try {
      const formData = new FormData()
      formData.append('person_image', await (await fetch(personImage.url)).blob())
      formData.append('clothing_image', await (await fetch(clothingImage.url)).blob())
      formData.append('description', tryOnDescription)
      formData.append('style', tryOnStyle)
      formData.append('background', tryOnBackground)
      
      const res = await fetch(`${API_BASE}/api/image-factory/try-on/generate`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (data.url) {
        setTryOnResult({ ...data, url: `${API_BASE}${data.url}` })
        loadImages()
      }
    } catch (e) {
      console.error('Try-on failed', e)
      alert('生成失败，请重试')
    } finally {
      setIsTryOnGenerating(false)
    }
  }
  
  const applyTemplate = (tmpl) => {
    setPrompt(tmpl.prompt)
  }
  
  const filteredImages = images.filter(img => 
    img.filename.toLowerCase().includes(searchQuery.toLowerCase())
  )
  
  const currentTemplate = templates.find(t => t.id === selectedTemplate)
  
  // 暗色主题样式
  const theme = {
    bg: darkMode ? 'bg-gray-950' : 'bg-gray-50',
    card: darkMode ? 'bg-gray-900' : 'bg-white',
    cardBorder: darkMode ? 'border-gray-800' : 'border-gray-200',
    text: darkMode ? 'text-white' : 'text-gray-900',
    muted: darkMode ? 'text-gray-400' : 'text-gray-500',
    input: darkMode ? 'bg-gray-800 border-gray-700 text-white placeholder-gray-500' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400',
    hover: darkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-50',
  }
  
  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} transition-colors duration-200`}>
      {/* Header */}
      <div className={`${theme.card} border-b ${theme.cardBorder} sticky top-0 z-20 backdrop-blur-sm bg-opacity-90`}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold">图片工厂</h1>
              <p className={`text-xs ${theme.muted}`}>AI 图片生成与编辑工具</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`p-2 rounded-lg ${theme.hover} transition-colors`}
            >
              {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>
      
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: '已生成图片', value: stats.total_images, icon: ImageIcon, color: 'from-violet-500 to-purple-500' },
            { label: '可用模板', value: stats.total_templates, icon: LayoutTemplate, color: 'from-blue-500 to-cyan-500' },
            { label: '模型版本', value: 'agnes-2.1', icon: Sparkles, color: 'from-pink-500 to-rose-500' },
            { label: 'API 状态', value: stats.api_configured ? '✅ 正常' : '⚠️ 未配置', icon: TrendingUp, color: stats.api_configured ? 'from-green-500 to-emerald-500' : 'from-yellow-500 to-orange-500' },
          ].map((stat, idx) => (
            <div key={idx} className={`${theme.card} rounded-2xl p-4 shadow-sm border ${theme.cardBorder}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className={`text-xs font-medium ${theme.muted} uppercase tracking-wider`}>{stat.label}</p>
                  <p className="text-2xl font-bold mt-1">{stat.value}</p>
                </div>
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center shadow-lg`}>
                  <stat.icon className="w-6 h-6 text-white" />
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {/* Tabs */}
        <div className={`${theme.card} rounded-2xl shadow-sm border ${theme.cardBorder} mb-6 overflow-hidden`}>
          <div className="flex overflow-x-auto">
            {[
              { id: 'generate', label: '文生图', icon: Sparkles, desc: 'AI 生成图片' },
              { id: 'template', label: '模板合成', icon: LayoutTemplate, desc: '电商模板' },
              { id: 'try-on', label: '虚拟试衣', icon: UserCircle, desc: '上传照片试穿' },
              { id: 'edit', label: '图片编辑', icon: Scissors, desc: '裁剪/缩放' },
              { id: 'gallery', label: '图片库', icon: ImageIcon, desc: '查看管理' },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 min-w-[120px] px-6 py-4 flex flex-col items-center space-y-1 transition-all border-b-2 ${
                  activeTab === tab.id
                    ? 'border-violet-500 text-violet-600'
                    : `border-transparent ${theme.muted} hover:text-gray-700`
                }`}
              >
                <tab.icon className="w-5 h-5" />
                <span className="font-medium text-sm">{tab.label}</span>
                <span className="text-xs opacity-60 hidden sm:block">{tab.desc}</span>
              </button>
            ))}
          </div>
        </div>
        
        {/* Generate Tab */}
        {activeTab === 'generate' && (
          <div className={`${theme.card} rounded-2xl shadow-sm border ${theme.cardBorder} p-6`}>
            <div className="grid grid-cols-2 gap-8">
              {/* Left: Controls */}
              <div className="space-y-6">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium">提示词</label>
                    <button 
                      onClick={() => applyTemplate(PROMPT_TEMPLATES[0])}
                      className="text-xs text-violet-500 hover:text-violet-600 flex items-center space-x-1"
                    >
                      <Wand2 className="w-3 h-3" />
                      <span>智能补充</span>
                    </button>
                  </div>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="描述你想要的图片，例如：Professional product photography of a luxury perfume bottle, golden hour lighting, white background..."
                    className={`w-full h-36 px-4 py-3 rounded-xl border ${theme.input} focus:ring-2 focus:ring-violet-500 focus:border-transparent resize-none transition-all`}
                  />
                </div>
                
                {/* Size Selector */}
                <div>
                  <label className="text-sm font-medium mb-3 block">图片尺寸</label>
                  <div className="grid grid-cols-3 gap-2">
                    {SIZES.map(s => (
                      <button
                        key={s.value}
                        onClick={() => setSelectedSize(s.value)}
                        className={`px-3 py-2 rounded-lg border text-center transition-all ${
                          selectedSize === s.value
                            ? 'border-violet-500 bg-violet-50 text-violet-700'
                            : `${theme.cardBorder} ${theme.hover}`
                        }`}
                      >
                        <div className="text-sm font-medium">{s.label}</div>
                        <div className={`text-xs ${theme.muted}`}>{s.ratio}</div>
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Batch Size */}
                <div>
                  <label className="text-sm font-medium mb-3 block">批量生成</label>
                  <div className="flex items-center space-x-3">
                    {[1, 2, 3, 4].map(n => (
                      <button
                        key={n}
                        onClick={() => setBatchSize(n)}
                        className={`w-10 h-10 rounded-lg border font-medium transition-all ${
                          batchSize === n
                            ? 'border-violet-500 bg-violet-500 text-white'
                            : `${theme.cardBorder} ${theme.hover}`
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Generate Button */}
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating || !prompt.trim()}
                  className="w-full bg-gradient-to-r from-violet-600 via-purple-600 to-pink-600 text-white py-4 rounded-xl font-medium hover:from-violet-700 hover:via-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 transition-all shadow-lg hover:shadow-xl"
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
                
                {/* Prompt Templates */}
                <div>
                  <p className={`text-xs ${theme.muted} mb-2`}>提示词模板</p>
                  <div className="flex flex-wrap gap-2">
                    {PROMPT_TEMPLATES.map((tmpl, idx) => (
                      <button
                        key={idx}
                        onClick={() => applyTemplate(tmpl)}
                        className={`px-3 py-1.5 rounded-full text-xs border ${theme.cardBorder} ${theme.hover} transition-colors`}
                      >
                        {tmpl.name}
                      </button>
                    ))}
                  </div>
                </div>
                
                {generationError && (
                  <div className="px-4 py-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
                    ❌ {generationError}
                  </div>
                )}
                
                {!stats.api_configured && (
                  <div className="px-4 py-3 bg-yellow-50 border border-yellow-200 text-yellow-700 rounded-xl text-sm">
                    ⚠️ 未配置 AGNES_API_KEY，API 调用可能失败
                  </div>
                )}
              </div>
              
              {/* Right: Results */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium">生成结果</h3>
                  {generatedImages.length > 1 && (
                    <button
                      onClick={handleDownloadAll}
                      className="flex items-center space-x-1 text-sm text-violet-600 hover:text-violet-700"
                    >
                      <DownloadCloud className="w-4 h-4" />
                      <span>全部下载</span>
                    </button>
                  )}
                </div>
                
                {generatedImages.length > 0 ? (
                  <div className="grid grid-cols-2 gap-4">
                    {generatedImages.map((img, idx) => (
                      <div key={idx} className="relative group rounded-xl overflow-hidden shadow-sm">
                        <img
                          src={img.url}
                          alt={img.prompt}
                          className="w-full h-48 object-cover"
                        />
                        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all flex items-center justify-center space-x-2 opacity-0 group-hover:opacity-100">
                          <button
                            onClick={() => setSelectedImage(img)}
                            className="p-2 bg-white rounded-full hover:bg-gray-100 transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDownload(img)}
                            className="p-2 bg-white rounded-full hover:bg-green-100 hover:text-green-600 transition-colors"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(img.filename)}
                            className="p-2 bg-white rounded-full hover:bg-red-100 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={`h-64 flex flex-col items-center justify-center border-2 border-dashed ${theme.cardBorder} rounded-xl`}>
                    <Sparkles className={`w-12 h-12 ${theme.muted} mb-3 opacity-50`} />
                    <p className={theme.muted}>输入提示词生成图片</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Template Tab */}
        {activeTab === 'template' && (
          <div className={`${theme.card} rounded-2xl shadow-sm border ${theme.cardBorder} p-6`}>
            <div className="grid grid-cols-2 gap-8">
              <div className="space-y-6">
                <div>
                  <label className="text-sm font-medium mb-3 block">选择模板</label>
                  <div className="space-y-2">
                    {templates.map(t => (
                      <button
                        key={t.id}
                        onClick={() => setSelectedTemplate(t.id)}
                        className={`w-full px-4 py-3 rounded-xl border text-left flex items-center justify-between transition-all ${
                          selectedTemplate === t.id
                            ? 'border-violet-500 bg-violet-50'
                            : `${theme.cardBorder} ${theme.hover}`
                        }`}
                      >
                        <div>
                          <div className="font-medium">{t.name}</div>
                          <div className={`text-xs ${theme.muted}`}>{t.width} × {t.height}</div>
                        </div>
                        {selectedTemplate === t.id && (
                          <div className="w-2 h-2 rounded-full bg-violet-500" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
                
                <button
                  onClick={handleRenderTemplate}
                  disabled={renderingImage || !selectedTemplate}
                  className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 text-white py-4 rounded-xl font-medium hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 flex items-center justify-center space-x-2"
                >
                  {renderingImage ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      <span>渲染中...</span>
                    </>
                  ) : (
                    <>
                      <LayoutTemplate className="w-5 h-5" />
                      <span>生成图片</span>
                    </>
                  )}
                </button>
              </div>
              
              <div>
                <h3 className="font-medium mb-4">预览</h3>
                {generatedImages.length > 0 ? (
                  <div className="relative group rounded-xl overflow-hidden shadow-sm">
                    <img
                      src={generatedImages[0].url}
                      alt="Template result"
                      className="w-full h-64 object-cover"
                    />
                    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all flex items-center justify-center space-x-2 opacity-0 group-hover:opacity-100">
                      <button
                        onClick={() => setSelectedImage(generatedImages[0])}
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
                  <div className={`h-64 flex items-center justify-center border-2 border-dashed ${theme.cardBorder} rounded-xl`}>
                    <p className={theme.muted}>选择模板并点击生成</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Edit Tab */}
        {activeTab === 'edit' && (
          <div className={`${theme.card} rounded-2xl shadow-sm border ${theme.cardBorder} p-6`}>
            <h2 className="text-lg font-semibold mb-6">图片编辑工具</h2>
            
            {/* Upload Area */}
            <div className={`border-2 border-dashed ${theme.cardBorder} rounded-xl p-8 text-center mb-6 hover:border-violet-500 transition-colors`}>
              <input
                ref={editFileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => handleEditUpload(e)}
              />
              <Upload className="w-12 h-12 mx-auto text-violet-500 mb-3" />
              <p className={`font-medium ${theme.text}`}>点击上传图片</p>
              <p className={`text-sm ${theme.muted} mt-1`}>支持 JPG、PNG 格式</p>
            </div>

            {uploadedImage && (
              <div className="mb-6">
                <img src={uploadedImage.url} alt="Uploaded" className="w-full max-h-96 object-contain rounded-xl" />
              </div>
            )}

            {/* Edit Tools */}
            {uploadedImage && (
              <div>
                <h3 className="font-medium mb-4">编辑工具</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  {editTools.map((tool, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleEditImage(uploadedImage, tool.action)}
                      className={`p-4 rounded-xl border ${theme.cardBorder} ${theme.hover} transition-all text-center`}
                    >
                      <tool.icon className="w-6 h-6 mx-auto text-violet-500 mb-2" />
                      <p className="font-medium text-sm">{tool.label}</p>
                    </button>
                  ))}
                </div>

                {/* Advanced Controls */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div>
                    <label className="text-sm font-medium mb-2 block">旋转角度</label>
                    <select
                      value={editOptions.angle}
                      onChange={(e) => setEditOptions({...editOptions, angle: e.target.value})}
                      className={`w-full px-3 py-2 rounded-lg border ${theme.input}`}
                    >
                      <option value="0">0°</option>
                      <option value="90">90°</option>
                      <option value="180">180°</option>
                      <option value="270">270°</option>
                    </select>
                    <button
                      onClick={() => handleEditImage(uploadedImage, 'rotate')}
                      className="mt-2 w-full px-3 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700"
                    >
                      应用旋转
                    </button>
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">滤镜效果</label>
                    <select
                      value={editOptions.filter}
                      onChange={(e) => setEditOptions({...editOptions, filter: e.target.value})}
                      className={`w-full px-3 py-2 rounded-lg border ${theme.input}`}
                    >
                      <option value="none">无</option>
                      <option value="grayscale">黑白</option>
                      <option value="sepia">复古</option>
                      <option value="blur">模糊</option>
                      <option value="sharpen">锐化</option>
                      <option value="emboss">浮雕</option>
                      <option value="contour">轮廓</option>
                    </select>
                    <button
                      onClick={() => handleEditImage(uploadedImage, 'filter')}
                      className="mt-2 w-full px-3 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700"
                    >
                      应用滤镜
                    </button>
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">亮度: {editOptions.brightness.toFixed(1)}</label>
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.1"
                      value={editOptions.brightness}
                      onChange={(e) => setEditOptions({...editOptions, brightness: parseFloat(e.target.value)})}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">对比度: {editOptions.contrast.toFixed(1)}</label>
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.1"
                      value={editOptions.contrast}
                      onChange={(e) => setEditOptions({...editOptions, contrast: parseFloat(e.target.value)})}
                      className="w-full"
                    />
                  </div>
                </div>

                <button
                  onClick={() => handleEditImage(uploadedImage, 'adjust')}
                  className="w-full px-4 py-3 bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-xl font-medium hover:from-violet-700 hover:to-purple-700"
                >
                  应用调整
                </button>
              </div>
            )}
          </div>
        )}
        
        {/* Try-On Tab */}
        {activeTab === 'try-on' && (
          <div className={`${theme.card} rounded-2xl shadow-sm border ${theme.cardBorder} p-6`}>
            <h2 className="text-lg font-semibold mb-6">虚拟试衣</h2>
            
            <div className="grid grid-cols-2 gap-8">
              {/* Left: Upload Area */}
              <div className="space-y-6">
                {/* Person Upload */}
                <div>
                  <label className="text-sm font-medium mb-3 block">上传人物照片</label>
                  <div className={`border-2 border-dashed ${theme.cardBorder} rounded-xl p-8 text-center hover:border-violet-500 transition-colors`}>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      id="person-upload"
                      onChange={(e) => {
                        const file = e.target.files[0]
                        if (file) {
                          const url = URL.createObjectURL(file)
                          setPersonImage({ url, file })
                        }
                      }}
                    />
                    <label htmlFor="person-upload" className="cursor-pointer">
                      {personImage ? (
                        <img src={personImage.url} alt="Person" className="w-full h-48 object-contain rounded-lg" />
                      ) : (
                        <>
                          <Camera className="w-12 h-12 mx-auto text-violet-500 mb-3" />
                          <p className={`font-medium ${theme.text}`}>上传人物照片</p>
                          <p className={`text-sm ${theme.muted} mt-1`}>全身照效果最佳</p>
                        </>
                      )}
                    </label>
                  </div>
                </div>
                
                {/* Clothing Upload */}
                <div>
                  <label className="text-sm font-medium mb-3 block">上传衣物照片</label>
                  <div className={`border-2 border-dashed ${theme.cardBorder} rounded-xl p-8 text-center hover:border-violet-500 transition-colors`}>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      id="clothing-upload"
                      onChange={(e) => {
                        const file = e.target.files[0]
                        if (file) {
                          const url = URL.createObjectURL(file)
                          setClothingImage({ url, file })
                        }
                      }}
                    />
                    <label htmlFor="clothing-upload" className="cursor-pointer">
                      {clothingImage ? (
                        <img src={clothingImage.url} alt="Clothing" className="w-full h-48 object-contain rounded-lg" />
                      ) : (
                        <>
                          <Shirt className="w-12 h-12 mx-auto text-violet-500 mb-3" />
                          <p className={`font-medium ${theme.text}`}>上传衣物照片</p>
                          <p className={`text-sm ${theme.muted} mt-1`}>正面平铺效果最佳</p>
                        </>
                      )}
                    </label>
                  </div>
                </div>
                
                {/* Description */}
                <div>
                  <label className="text-sm font-medium mb-2 block">描述（可选）</label>
                  <textarea
                    value={tryOnDescription}
                    onChange={(e) => setTryOnDescription(e.target.value)}
                    placeholder="例如：这件衣服是夏季轻薄面料，适合海边度假..."
                    className={`w-full h-24 px-4 py-3 rounded-lg border ${theme.input} focus:ring-2 focus:ring-violet-500 focus:border-transparent resize-none`}
                  />
                </div>
                
                {/* Style Selection */}
                <div>
                  <label className="text-sm font-medium mb-3 block">风格</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { id: 'casual', label: '休闲', icon: '👕' },
                      { id: 'formal', label: '正式', icon: '👔' },
                      { id: 'sporty', label: '运动', icon: '🏃' },
                      { id: 'fashion', label: '时尚', icon: '✨' },
                    ].map(style => (
                      <button
                        key={style.id}
                        onClick={() => setTryOnStyle(style.id)}
                        className={`p-3 rounded-lg border text-center transition-all ${
                          tryOnStyle === style.id
                            ? 'border-violet-500 bg-violet-50 text-violet-700'
                            : `${theme.cardBorder} ${theme.hover}`
                        }`}
                      >
                        <div className="text-2xl mb-1">{style.icon}</div>
                        <div className="text-sm font-medium">{style.label}</div>
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Background Selection */}
                <div>
                  <label className="text-sm font-medium mb-3 block">背景场景</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: 'beach', label: '沙滩', icon: '🏖️' },
                      { id: 'city', label: '城市', icon: '🏙️' },
                      { id: 'space', label: '太空', icon: '🚀' },
                      { id: 'studio', label: '摄影棚', icon: '📷' },
                      { id: 'forest', label: '森林', icon: '🌲' },
                      { id: 'snow', label: '雪景', icon: '❄️' },
                    ].map(bg => (
                      <button
                        key={bg.id}
                        onClick={() => setTryOnBackground(bg.id)}
                        className={`p-3 rounded-lg border text-center transition-all ${
                          tryOnBackground === bg.id
                            ? 'border-violet-500 bg-violet-50 text-violet-700'
                            : `${theme.cardBorder} ${theme.hover}`
                        }`}
                      >
                        <div className="text-2xl mb-1">{bg.icon}</div>
                        <div className="text-xs font-medium">{bg.label}</div>
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Generate Button */}
                <button
                  onClick={handleTryOn}
                  disabled={isTryOnGenerating || !personImage || !clothingImage}
                  className="w-full px-4 py-3 bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-xl font-medium hover:from-violet-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {isTryOnGenerating ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      <span>生成中...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-5 h-5" />
                      <span>生成试穿效果</span>
                    </>
                  )}
                </button>
              </div>
              
              {/* Right: Result Area */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">试穿效果</h3>
                  {tryOnResult && (
                    <div className="flex items-center space-x-2">
                      <a
                        href={tryOnResult.url}
                        download
                        className={`flex items-center space-x-1 px-3 py-1.5 ${theme.hover} rounded-lg text-sm`}
                      >
                        <DownloadIcon className="w-4 h-4" />
                        <span>下载</span>
                      </a>
                    </div>
                  )}
                </div>
                
                {tryOnResult ? (
                  <div className="rounded-xl overflow-hidden border ${theme.cardBorder}">
                    <img src={tryOnResult.url} alt="Try-on result" className="w-full h-96 object-cover" />
                  </div>
                ) : (
                  <div className={`border-2 border-dashed ${theme.cardBorder} rounded-xl p-12 text-center h-96 flex flex-col items-center justify-center`}>
                    <UserCircle className="w-16 h-16 text-gray-300 mb-4" />
                    <p className={`font-medium ${theme.muted}`}>上传照片后生成试穿效果</p>
                    <p className={`text-sm ${theme.muted} mt-2`}>支持人物全身照 + 衣物平铺照</p>
                  </div>
                )}
                
                {/* Tips */}
                <div className={`p-4 rounded-lg ${darkMode ? 'bg-gray-800' : 'bg-gray-50'}`}>
                  <h4 className="font-medium text-sm mb-2">💡 使用提示</h4>
                  <ul className={`text-xs ${theme.muted} space-y-1`}>
                    <li>• 人物照片：全身照效果最佳，光线均匀</li>
                    <li>• 衣物照片：正面平铺或挂拍，背景干净</li>
                    <li>• 可尝试不同风格和背景组合</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Gallery Tab */}
        {activeTab === 'gallery' && (
          <div className={`${theme.card} rounded-2xl shadow-sm border ${theme.cardBorder} p-6`}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold">图片库</h2>
              <div className="flex items-center space-x-2">
                <button onClick={loadImages} className={`flex items-center space-x-1 px-3 py-2 ${theme.hover} rounded-lg transition-colors`}>
                  <RefreshCw className="w-4 h-4" />
                  <span>刷新</span>
                </button>
                <button 
                  onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
                  className={`p-2 ${theme.hover} rounded-lg transition-colors`}
                >
                  {viewMode === 'grid' ? <ListIcon className="w-4 h-4" /> : <Grid className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            {/* Search */}
            <div className="relative mb-4">
              <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme.muted}`} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索图片..."
                className={`w-full pl-10 pr-4 py-2 rounded-lg border ${theme.input} focus:ring-2 focus:ring-violet-500`}
              />
            </div>
            
            {filteredImages.length === 0 ? (
              <div className="text-center py-16">
                <ImageIcon className={`w-16 h-16 mx-auto ${theme.muted} mb-4 opacity-50`} />
                <p className={theme.muted}>暂无图片，去生成一张吧！</p>
              </div>
            ) : viewMode === 'grid' ? (
              <div className="grid grid-cols-4 gap-4">
                {filteredImages.map(img => (
                  <div key={img.filename} className="group relative rounded-xl overflow-hidden shadow-sm">
                    <img
                      src={img.url}
                      alt={img.filename}
                      className="w-full h-40 object-cover"
                    />
                    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all flex items-center justify-center space-x-2 opacity-0 group-hover:opacity-100">
                      <button
                        onClick={() => setSelectedImage(img)}
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
                    <p className={`absolute bottom-0 left-0 right-0 px-2 py-1 text-xs ${darkMode ? 'bg-gray-900' : 'bg-white bg-opacity-90'} truncate`}>
                      {img.filename}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {filteredImages.map(img => (
                  <div key={img.filename} className={`flex items-center space-x-4 p-3 rounded-lg ${theme.hover} transition-colors`}>
                    <img src={img.url} alt={img.filename} className="w-16 h-16 object-cover rounded-lg" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{img.filename}</p>
                      <p className={`text-sm ${theme.muted}`}>{new Date(img.created_at).toLocaleString()}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button onClick={() => setSelectedImage(img)} className={`p-2 ${theme.hover} rounded-lg`}>
                        <Eye className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleDownload(img)} className={`p-2 ${theme.hover} rounded-lg`}>
                        <Download className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleDelete(img.filename)} className={`p-2 ${theme.hover} rounded-lg text-red-500`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* Image Preview Modal */}
      {selectedImage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75" onClick={() => setSelectedImage(null)}>
          <div className={`${theme.card} rounded-2xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-auto`} onClick={e => e.stopPropagation()}>
            <div className="p-4 flex items-center justify-between border-b border-gray-200">
              <h3 className="font-medium">{selectedImage.filename}</h3>
              <button onClick={() => setSelectedImage(null)} className={`p-2 ${theme.hover} rounded-lg`}>
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4">
              <img src={selectedImage.url} alt={selectedImage.filename} className="w-full rounded-lg" />
            </div>
            <div className="p-4 border-t border-gray-200 flex justify-end space-x-2">
              <button onClick={() => handleDownload(selectedImage)} className="flex items-center space-x-1 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700">
                <Download className="w-4 h-4" />
                <span>下载</span>
              </button>
              <button onClick={() => handleDelete(selectedImage.filename)} className="flex items-center space-x-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
                <Trash2 className="w-4 h-4" />
                <span>删除</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

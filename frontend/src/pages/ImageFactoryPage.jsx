import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Sparkles,
  Image as ImageIcon,
  LayoutTemplate,
  Scissors,
  Download,
  Trash2,
  Eye,
  Upload,
  Wand2,
  Loader2,
  RefreshCw,
  TrendingUp,
  LayoutGrid,
  List as ListIcon,
  UserCircle,
  Shirt,
  Camera,
  Crop,
  RotateCw,
  FlipHorizontal,
  Sliders,
  DownloadCloud,
  Search,
  Image,
  Plus,
  FileJson2,
  Package,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import { formatRelativeTime, formatBytes } from '../lib/format'
import {
  Modal,
  Button,
  Empty,
  SkeletonGrid,
  ErrorState,
  PageHeader,
  ConfirmDialog,
} from '../components/ui'
import ShareButton from '../components/ShareButton'
import EnhancePromptButton from '../components/EnhancePromptButton'
import RandomPromptButton from '../components/RandomPromptButton'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'

const MEDIA_BASE = api.defaults.baseURL
const absUrl = (u) => (u ? (u.startsWith('http') ? u : `${MEDIA_BASE}${u}`) : '')

// 发布包平台规格预设（商业化 v14）
const PUBLISH_PLATFORMS = [
  { id: 'xiaohongshu', name: '小红书', spec: '1242×1660（3:4 图文笔记）' },
  { id: 'douyin', name: '抖音', spec: '1080×1920（9:16 竖屏）' },
  { id: 'taobao', name: '淘宝', spec: '800×800（商品主图）' },
  { id: 'wechat', name: '公众号', spec: '900×383（头图）' },
]

// 随机提示词预设
const RANDOM_PROMPTS = [
  'Professional product photography of a luxury perfume bottle, golden hour lighting, white background, soft shadows, 8k',
  'Cyberpunk city street at night, neon lights reflecting on wet asphalt, cinematic, ultra detailed, atmospheric',
  'A cute corgi puppy wearing a tiny yellow raincoat, walking in a puddle, studio lighting, adorable, high detail',
  'Minimalist Japanese zen garden with raked sand and bonsai tree, soft morning light, serene, tranquil atmosphere',
  'Fantasy castle floating on clouds above a sea of mist, dramatic epic scale, matte painting, cinematic lighting',
  'Delicious strawberry cheesecake slice on a marble table, professional food photography, fresh ingredients, shallow depth of field',
]

// 提示词模板
const PROMPT_TEMPLATES = [
  {
    name: '商品摄影',
    prompt:
      'Professional product photography of [PRODUCT], studio lighting, white background, high-end commercial style, shot on Canon EOS R5, 85mm lens',
  },
  {
    name: '场景图',
    prompt:
      'Lifestyle scene with [SUBJECT], [ACTION], [ENVIRONMENT], golden hour lighting, cinematic composition, 4K quality',
  },
  {
    name: '社交媒体',
    prompt:
      '[PLATFORM] post design, [THEME], vertical format 9:16, bold typography area, modern aesthetic',
  },
  {
    name: 'Logo设计',
    prompt:
      'Minimalist logo design for [BRAND], [STYLE] style, vector graphic, clean lines, modern aesthetic',
  },
  {
    name: '海报设计',
    prompt:
      'Promotional poster for [EVENT], dynamic composition, bold colors, typography space, professional design',
  },
]

// 艺术风格预设（选择后自动追加英文风格关键词到提示词，可再次点击取消）
const ART_STYLES = [
  { id: 'photoreal', label: '写实摄影', icon: '📷', keyword: 'photorealistic, professional photography, sharp focus, natural lighting, 8k' },
  { id: 'anime', label: '动漫', icon: '🎨', keyword: 'anime style, vibrant colors, detailed anime illustration, clean lineart' },
  { id: '3d', label: '3D渲染', icon: '🧊', keyword: '3D render, octane render, soft global illumination, high detail' },
  { id: 'oil', label: '油画', icon: '🖼️', keyword: 'oil painting, impressionist brushstrokes, rich texture, canvas texture' },
  { id: 'watercolor', label: '水彩', icon: '💧', keyword: 'watercolor painting, soft washes, delicate paper texture, pastel palette' },
  { id: 'pixel', label: '像素', icon: '👾', keyword: 'pixel art, 8-bit style, retro game sprite, crisp pixels' },
  { id: 'cyberpunk', label: '赛博朋克', icon: '🌃', keyword: 'cyberpunk, neon glow, rain-soaked city, cinematic, high contrast' },
  { id: 'minimal', label: '极简', icon: '⬜', keyword: 'minimalist, clean composition, negative space, muted color palette' },
  { id: 'chinese', label: '国风水墨', icon: '🏮', keyword: 'Chinese ink wash painting, shuimo style, elegant brushwork, rice paper' },
  { id: 'vaporwave', label: '蒸汽波', icon: '🌴', keyword: 'vaporwave aesthetic, retro 80s, pastel gradients, glitch art' },
]

// 尺寸选项（label 区分语义，ratio 展示实际分辨率避免歧义）
const SIZES = [
  { label: '正方形', value: '1024x1024', ratio: '1:1 · 1024×1024' },
  { label: '横向', value: '1280x720', ratio: '16:9 · 1280×720' },
  { label: '纵向', value: '720x1280', ratio: '9:16 · 720×1280' },
  { label: '宽屏', value: '1920x1080', ratio: '16:9 高清 · 1920×1080' },
  { label: '竖版', value: '1080x1350', ratio: '4:5 · 1080×1350' },
  { label: '封面', value: '800x600', ratio: '4:3 · 800×600' },
]

const TRYON_STYLES = [
  { id: 'casual', label: '休闲', icon: '👕' },
  { id: 'formal', label: '正式', icon: '👔' },
  { id: 'sporty', label: '运动', icon: '🏃' },
  { id: 'fashion', label: '时尚', icon: '✨' },
]

const TRYON_BACKGROUNDS = [
  { id: 'beach', label: '沙滩', icon: '🏖️' },
  { id: 'city', label: '城市', icon: '🏙️' },
  { id: 'space', label: '太空', icon: '🚀' },
  { id: 'studio', label: '摄影棚', icon: '📷' },
  { id: 'forest', label: '森林', icon: '🌲' },
  { id: 'snow', label: '雪景', icon: '❄️' },
]

// 背景替换场景（后端 make_scene_background 支持）
const BG_SCENES = [
  { id: 'beach', label: '沙滩', icon: '🏖️' },
  { id: 'city', label: '城市', icon: '🏙️' },
  { id: 'space', label: '太空', icon: '🚀' },
  { id: 'studio', label: '摄影棚', icon: '📷' },
  { id: 'forest', label: '森林', icon: '🌲' },
  { id: 'snow', label: '雪景', icon: '❄️' },
  { id: 'sunset', label: '日落', icon: '🌇' },
  { id: 'night', label: '夜景', icon: '🌃' },
  { id: 'pastel', label: '粉彩', icon: '🎨' },
]

const EDIT_TOOLS = [
  { icon: Crop, label: '裁剪', action: 'crop' },
  { icon: RotateCw, label: '旋转', action: 'rotate' },
  { icon: FlipHorizontal, label: '翻转', action: 'flip' },
  { icon: Sliders, label: '调整', action: 'adjust' },
]

const TABS = [
  { id: 'generate', label: '文生图', icon: Sparkles, desc: 'AI 生成图片' },
  { id: 'img2img', label: '图生图', icon: Image, desc: '参考图变体' },
  { id: 'template', label: '模板合成', icon: LayoutTemplate, desc: '电商模板' },
  { id: 'try-on', label: '虚拟试衣', icon: UserCircle, desc: '上传照片试穿' },
  { id: 'edit', label: '图片编辑', icon: Scissors, desc: '裁剪/缩放' },
  { id: 'gallery', label: '图片库', icon: ImageIcon, desc: '查看管理' },
]

export default function ImageFactoryPage() {
  const toast = useToast()
  // 专业基线：输入态持久化（刷新/误关页面不丢草稿）
  const [inputs, setInputs] = usePersistentToolState('image_factory_inputs', {
    activeTab: 'generate',
    prompt: '',
    selectedSize: '1024x1024',
    batchSize: 1,
    artStyle: '',
    negativePrompt: '',
  })
  const { activeTab, prompt, selectedSize, batchSize, artStyle, negativePrompt } = inputs
  const setActiveTab = (v) => setInputs((p) => ({ ...p, activeTab: v }))
  const setPrompt = (v) => setInputs((p) => ({ ...p, prompt: v ?? '' }))
  const setSelectedSize = (v) => setInputs((p) => ({ ...p, selectedSize: v }))
  const setBatchSize = (v) => setInputs((p) => ({ ...p, batchSize: v }))
  const setArtStyle = (v) => setInputs((p) => ({ ...p, artStyle: v ?? '' }))
  const setNegativePrompt = (v) => setInputs((p) => ({ ...p, negativePrompt: v ?? '' }))
  const [images, setImages] = useState([])
  const [templates, setTemplates] = useState([])
  const [stats, setStats] = useState({ total_images: 0, total_templates: 0, api_configured: false })
  const [loadingGallery, setLoadingGallery] = useState(true)
  const [galleryError, setGalleryError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState('grid')
  const [previewImage, setPreviewImage] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  // 发布包（商业化 v14）：图片库 → 平台规格成品 + 2x 高清 + 上架文案 + 质量报告
  const [packOpen, setPackOpen] = useState(false)
  const [packPlatform, setPackPlatform] = useState('xiaohongshu')
  const [packTitle, setPackTitle] = useState('AI 原创插画集')
  const [packUpscale, setPackUpscale] = useState(true)
  const [packing, setPacking] = useState(false)

  // 生成
  const [generating, setGenerating] = useState(false)
  const [generatedImages, setGeneratedImages] = useState([])
  const [generationError, setGenerationError] = useState(null)
  // 异步任务进度（task_id + 轮询进度）
  const [genTask, setGenTask] = useState(null)
  const { submitTask } = useAsyncTask()

  // 模板
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [rendering, setRendering] = useState(false)

  // 图生图
  const [img2imgPrompt, setImg2imgPrompt] = useState('')
  const [img2imgFile, setImg2imgFile] = useState(null) // File
  const [img2imgPreview, setImg2imgPreview] = useState('')
  const [img2imgStrength, setImg2imgStrength] = useState(0.35)
  const [img2imgSize, setImg2imgSize] = useState('1024x1024')
  const [img2imgBusy, setImg2imgBusy] = useState(false)
  const img2imgRef = useRef(null)

  // 模板管理
  const [templateModal, setTemplateModal] = useState(false) // 'create' | 'upload' | null
  const [templateForm, setTemplateForm] = useState({
    name: '',
    width: 1080,
    height: 1920,
    background: '#FFFFFF',
    layers: '',
  })
  const [templateSaving, setTemplateSaving] = useState(false)
  const [deletingTemplate, setDeletingTemplate] = useState(null)

  // 编辑
  const [uploadedImage, setUploadedImage] = useState(null) // { url, filename }
  const [editOptions, setEditOptions] = useState({
    angle: '0',
    filter: 'none',
    brightness: 1.0,
    contrast: 1.0,
    saturation: 1.0,
  })
  const [editBusy, setEditBusy] = useState(false)
  const editFileRef = useRef(null)
  // 人像分割 / 背景替换
  const [segFeather, setSegFeather] = useState(2)
  const [bgScene, setBgScene] = useState('beach')
  const [bgColor, setBgColor] = useState('')
  const [bgAIDesc, setBgAIDesc] = useState('')

  // 试衣
  const [personImage, setPersonImage] = useState(null)
  const [clothingImage, setClothingImage] = useState(null)
  const [tryOnStyle, setTryOnStyle] = useState('casual')
  const [tryOnBackground, setTryOnBackground] = useState('beach')
  const [tryOnDescription, setTryOnDescription] = useState('')
  const [tryOnGenerating, setTryOnGenerating] = useState(false)
  const [tryOnResult, setTryOnResult] = useState(null)
  const [showImagePicker, setShowImagePicker] = useState(null)

  // 3D 旋转
  const [rotationY, setRotationY] = useState(0)
  const [rotationX, setRotationX] = useState(0)
  const [isAutoRotate, setIsAutoRotate] = useState(false)
  const [rotationSpeed, setRotationSpeed] = useState(1)

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/api/image-factory/stats')
      setStats(res.data)
    } catch {
      /* 静默 */
    }
  }, [])

  const fetchImages = useCallback(async () => {
    setLoadingGallery(true)
    setGalleryError(null)
    try {
      const res = await api.get('/api/image-factory/images')
      setImages(res.data)
    } catch (e) {
      setGalleryError(e)
    } finally {
      setLoadingGallery(false)
    }
  }, [])

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await api.get('/api/image-factory/templates')
      setTemplates(res.data)
      if (res.data.length > 0 && !selectedTemplate) setSelectedTemplate(res.data[0].id)
    } catch {
      /* 静默 */
    }
  }, [selectedTemplate])

  useEffect(() => {
    fetchStats()
    fetchImages()
    fetchTemplates()
  }, [fetchStats, fetchImages, fetchTemplates])

  // 3D 自动旋转
  useEffect(() => {
    if (!isAutoRotate) return
    const id = setInterval(() => setRotationY((p) => (p + rotationSpeed) % 360), 50)
    return () => clearInterval(id)
  }, [isAutoRotate, rotationSpeed])

  const applyTemplate = (tmpl) => setPrompt(tmpl.prompt)

  const handleDownload = async (image) => {
    try {
      const res = await fetch(absUrl(image.url))
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ext = (image.filename || 'png').split('.').pop()
      a.download = (image.title ? `${image.title}.${ext}` : image.filename || 'image.png')
      a.click()
      URL.revokeObjectURL(url)
      toast.success('已开始下载')
    } catch (e) {
      toast.error(`下载失败：${e.message}`)
    }
  }

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setGenerationError('请输入提示词')
      return
    }
    setGenerating(true)
    setGenerationError(null)
    setGeneratedImages([])
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const form = new FormData()
    const styleKw = ART_STYLES.find((s) => s.id === artStyle)?.keyword
    form.append('prompt', styleKw ? `${prompt}, ${styleKw}` : prompt)
    form.append('size', selectedSize)
    form.append('batch_size', batchSize)
    form.append('n', 1)
    if (negativePrompt.trim()) form.append('negative', negativePrompt.trim())
    await submitTask('/api/image-factory/generate/text-to-image', form, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: (data) => {
        const success = (data.results || []).filter((r) => !r.error)
        const errors = (data.results || []).filter((r) => r.error)
        setGeneratedImages(
          success.map((r) => ({ ...r, url: absUrl(r.url), prompt: r.prompt || prompt }))
        )
        if (errors.length > 0) {
          setGenerationError(errors[0].error)
        } else if (success.length > 0) {
          toast.success(`成功生成 ${success.length} 张图片`)
        } else {
          setGenerationError('生成失败，请检查 API Key 配置')
        }
        setGenerating(false)
        fetchImages()
      },
      onError: (e) => {
        setGenerating(false)
        setGenerationError(`生成失败：${e.message}`)
      },
    })
  }

  const handleRenderTemplate = async () => {
    if (!selectedTemplate) {
      toast.error('请选择模板')
      return
    }
    setRendering(true)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    await submitTask(
      '/api/image-factory/template/render',
      {
        template_id: selectedTemplate,
        overrides: {},
      },
      {
        onUpdate: (t) => setGenTask(t),
        onSuccess: (data) => {
          if (data.url) {
            setGeneratedImages([{ ...data, url: absUrl(data.url), prompt: '模板渲染' }])
            toast.success('模板渲染完成')
            fetchImages()
          } else {
            toast.error('渲染失败，未返回图片')
          }
          setRendering(false)
        },
        onError: (e) => {
          setRendering(false)
          toast.error(`渲染失败：${e.message}`)
        },
      }
    )
  }

  // ── 图生图 ──
  const handleImg2ImgUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImg2imgFile(file)
    setImg2imgPreview(URL.createObjectURL(file))
  }

  const handleImg2Img = async () => {
    if (!img2imgPrompt.trim()) {
      toast.error('请输入提示词')
      return
    }
    if (!img2imgFile) {
      toast.error('请先上传参考图')
      return
    }
    setImg2imgBusy(true)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const form = new FormData()
    form.append('prompt', img2imgPrompt)
    form.append('image', img2imgFile)
    form.append('size', img2imgSize)
    form.append('strength', img2imgStrength)
    if (negativePrompt.trim()) form.append('negative', negativePrompt.trim())
    await submitTask('/api/image-factory/generate/image-to-image', form, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: (data) => {
        if (data.url || data.image_url) {
          const url = data.url || data.image_url
          setGeneratedImages([
            {
              ...data,
              url: absUrl(url),
              prompt: img2imgPrompt,
              filename: data.filename || url.split('/').pop(),
            },
          ])
          toast.success('图生图完成')
          fetchImages()
        } else {
          toast.error('生成失败，请检查 API Key 配置')
        }
        setImg2imgBusy(false)
      },
      onError: (e) => {
        setImg2imgBusy(false)
        toast.error(`图生图失败：${e.message}`)
      },
    })
  }

  // ── 模板管理 ──
  const handleCreateTemplate = async () => {
    if (!templateForm.name.trim()) {
      toast.error('请输入模板名称')
      return
    }
    setTemplateSaving(true)
    try {
      let layers = []
      try {
        layers = templateForm.layers.trim() ? JSON.parse(templateForm.layers) : []
      } catch {
        toast.error('图层 JSON 格式错误')
        setTemplateSaving(false)
        return
      }
      const res = await api.post('/api/image-factory/template/create', {
        name: templateForm.name.trim(),
        width: Number(templateForm.width) || 1080,
        height: Number(templateForm.height) || 1920,
        background: templateForm.background,
        layers,
      })
      toast.success(`模板「${res.data.name}」已创建`)
      setTemplateModal(false)
      setTemplateForm({ name: '', width: 1080, height: 1920, background: '#FFFFFF', layers: '' })
      fetchTemplates()
    } catch (e) {
      toast.error(`创建失败：${e.message}`)
    } finally {
      setTemplateSaving(false)
    }
  }

  const handleUploadTemplate = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setTemplateSaving(true)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('name', file.name.replace(/\.json$/i, '') || '上传模板')
      const res = await api.post('/api/image-factory/template/upload', form)
      toast.success(`模板「${res.data.name || '未命名'}」已上传`)
      setTemplateModal(false)
      fetchTemplates()
    } catch (e) {
      toast.error(`上传失败：${e.message}`)
    } finally {
      setTemplateSaving(false)
      e.target.value = ''
    }
  }

  const handleDeleteTemplate = async () => {
    if (!deletingTemplate) return
    try {
      await api.delete(`/api/image-factory/templates/${deletingTemplate}`)
      toast.success('模板已删除')
      setDeletingTemplate(null)
      if (selectedTemplate === deletingTemplate) setSelectedTemplate('')
      fetchTemplates()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/api/image-factory/images/${deleteTarget.filename}`)
      toast.success('图片已删除')
      setDeleteTarget(null)
      setGeneratedImages((prev) => prev.filter((img) => img.filename !== deleteTarget.filename))
      if (previewImage?.filename === deleteTarget.filename) setPreviewImage(null)
      fetchImages()
    } catch (e) {
      toast.error(`删除失败：${e.message}`)
    }
  }

  const handleEditUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setEditBusy(true)
    const form = new FormData()
    form.append('image', file)
    try {
      const res = await api.post('/api/image-factory/edit/resize', form, { timeout: 120000 })
      const data = res.data
      if (data.url) {
        setUploadedImage({ ...data, url: absUrl(data.url) })
        fetchImages()
        toast.success('图片已上传')
      }
    } catch (e) {
      toast.error(`上传失败：${e.message}`)
    } finally {
      setEditBusy(false)
    }
  }

  const handleEditImage = async (editType) => {
    if (!uploadedImage) return
    setEditBusy(true)
    try {
      const imgResp = await fetch(uploadedImage.url)
      const blob = await imgResp.blob()
      const form = new FormData()
      form.append('image', blob, uploadedImage.filename || 'image.png')
      if (editType === 'crop') {
        form.append('x1', 0)
        form.append('y1', 0)
        form.append('x2', 100)
        form.append('y2', 100)
      } else if (editType === 'rotate') {
        form.append('angle', editOptions.angle || '0')
      } else if (editType === 'flip') {
        form.append('direction', 'horizontal')
      } else if (editType === 'filter') {
        form.append('filter_type', editOptions.filter || 'none')
        form.append('intensity', 0.5)
      } else if (editType === 'adjust') {
        form.append('brightness', editOptions.brightness)
        form.append('contrast', editOptions.contrast)
        form.append('saturation', editOptions.saturation)
      }
      const res = await api.post(`/api/image-factory/edit/${editType}`, form, { timeout: 120000 })
      const data = res.data
      if (data.url) {
        setUploadedImage({ ...data, url: absUrl(data.url) })
        fetchImages()
        toast.success('编辑已应用')
      }
    } catch (e) {
      toast.error(`编辑失败：${e.message}`)
    } finally {
      setEditBusy(false)
    }
  }

  // 人像分割：rembg 语义分割，输出透明背景 PNG
  const handleSegmentation = async () => {
    if (!uploadedImage) return
    setEditBusy(true)
    try {
      const imgResp = await fetch(uploadedImage.url)
      const blob = await imgResp.blob()
      const form = new FormData()
      form.append('image', blob, uploadedImage.filename || 'image.png')
      form.append('feather', segFeather)
      const res = await api.post('/api/image-factory/edit/personal-segmentation', form, {
        timeout: 180000,
      })
      if (res.data.url) {
        setUploadedImage({ ...res.data, url: absUrl(res.data.url) })
        fetchImages()
        toast.success('人像分割完成，背景已透明化')
      }
    } catch (e) {
      toast.error(`分割失败：${e.message}`)
    } finally {
      setEditBusy(false)
    }
  }

  // 背景替换：AI 抠图 + 新背景合成（场景渐变 / 纯色 / AI 生成）
  const handleReplaceBackground = async () => {
    if (!uploadedImage) return
    setEditBusy(true)
    try {
      const imgResp = await fetch(uploadedImage.url)
      const blob = await imgResp.blob()
      const form = new FormData()
      form.append('image', blob, uploadedImage.filename || 'image.png')
      form.append('background', bgScene)
      if (bgColor.trim()) form.append('force_color', bgColor.trim())
      if (bgAIDesc.trim()) form.append('ai_background', bgAIDesc.trim())
      const res = await api.post('/api/image-factory/edit/replace-background', form, {
        timeout: 240000,
      })
      if (res.data.url) {
        setUploadedImage({ ...res.data, url: absUrl(res.data.url) })
        fetchImages()
        toast.success('背景替换完成')
      }
    } catch (e) {
      toast.error(`背景替换失败：${e.message}`)
    } finally {
      setEditBusy(false)
    }
  }

  const handleTryOn = async () => {
    if (!personImage || !clothingImage) {
      toast.error('请上传人物照片和衣物照片')
      return
    }
    setTryOnGenerating(true)
    setTryOnResult(null)
    setGenTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    try {
      const [personResp, clothingResp] = await Promise.all([
        fetch(personImage.url),
        fetch(clothingImage.url),
      ])
      const personBlob = await personResp.blob()
      const clothingBlob = await clothingResp.blob()
      const form = new FormData()
      form.append('person_image', personBlob, 'person.png')
      form.append('clothing_image', clothingBlob, 'clothing.png')
      form.append('description', tryOnDescription)
      form.append('style', tryOnStyle)
      form.append('background', tryOnBackground)
      await submitTask('/api/image-factory/try-on/generate', form, {
        onUpdate: (t) => setGenTask(t),
        onSuccess: (data) => {
          if (data.url) {
            setTryOnResult({ ...data, url: absUrl(data.url) })
            toast.success('试穿效果已生成')
            fetchImages()
          } else {
            toast.error('生成失败，请重试')
          }
          setTryOnGenerating(false)
        },
        onError: (e) => {
          setTryOnGenerating(false)
          toast.error(`生成失败：${e.message}`)
        },
      })
    } catch (e) {
      setTryOnGenerating(false)
      toast.error(`生成失败：${e.message}`)
    }
  }

  const filteredImages = images.filter((img) => {
    const q = searchQuery.toLowerCase()
    return (
      img.filename.toLowerCase().includes(q) ||
      (img.title || '').toLowerCase().includes(q) ||
      (img.prompt || '').toLowerCase().includes(q)
    )
  })

  // 发布包：当前图片库全部按选中平台规格输出成品 + 2x 高清 + 上架文案 + 质量报告
  const downloadPublishPack = async () => {
    const picked = filteredImages.map((f) => f.filename)
    if (picked.length === 0) {
      toast.error('图片库为空，请先生成或上传图片')
      return
    }
    setPacking(true)
    try {
      const fd = new FormData()
      picked.slice(0, 50).forEach((f) => fd.append('ids', f))
      fd.append('platform', packPlatform)
      fd.append('pack_title', packTitle.trim() || 'AI 原创插画集')
      fd.append('upscale', packUpscale ? 'true' : 'false')
      const res = await api.post('/api/image-factory/publish-pack', fd, {
        responseType: 'blob',
        timeout: 300000,
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `image_publish_pack_${Date.now()}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setPackOpen(false)
      toast.success(`图片发布包已生成：${Math.min(picked.length, 50)} 张（规格成品 + 高清版 + 上架文案）`)
    } catch (e) {
      toast.error(`发布包生成失败：${e.message}`)
    } finally {
      setPacking(false)
    }
  }

  const statsCards = [
    {
      label: '已生成图片',
      value: stats.total_images,
      icon: ImageIcon,
      color: 'from-violet-500 to-purple-500',
    },
    {
      label: '可用模板',
      value: stats.total_templates,
      icon: LayoutTemplate,
      color: 'from-blue-500 to-cyan-500',
    },
    { label: '模型版本', value: 'agnes-2.1', icon: Sparkles, color: 'from-pink-500 to-rose-500' },
    {
      label: 'API 状态',
      value: stats.api_configured ? '正常' : '未配置',
      icon: TrendingUp,
      color: stats.api_configured
        ? 'from-green-500 to-emerald-500'
        : 'from-yellow-500 to-orange-500',
    },
  ]

  const renderImageActions = (img) => (
    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-all flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
      <button
        onClick={() => setPreviewImage(img)}
        className="p-2 bg-white rounded-full hover:bg-gray-100 transition-colors"
        title="预览"
      >
        <Eye className="w-4 h-4" />
      </button>
      <button
        onClick={() => handleDownload(img)}
        className="p-2 bg-white rounded-full hover:bg-green-100 hover:text-green-600 transition-colors"
        title="下载"
      >
        <Download className="w-4 h-4" />
      </button>
      <span onClick={(e) => e.stopPropagation()}>
        <ShareButton
          content={`# AI 图片作品\n\n提示词：${img.prompt || ''}\n\n> 由小团智能平台 AI 图片工厂生成 · ${new Date().toLocaleString()}`}
          title="AI 图片作品"
          contentType="image"
          className="!p-2 !bg-white !rounded-full"
        />
      </span>
      <button
        onClick={() => setDeleteTarget(img)}
        className="p-2 bg-white rounded-full hover:bg-red-100 hover:text-red-600 transition-colors"
        title="删除"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="图片工厂"
        description="AI 图片生成、模板合成、虚拟试衣与图片编辑"
        icon={Sparkles}
        iconColor="from-violet-500 via-purple-500 to-pink-500"
        actions={
          <Button
            variant="secondary"
            icon={RefreshCw}
            onClick={() => {
              fetchStats()
              fetchImages()
            }}
          >
            刷新
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statsCards.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-2xl p-4 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {stat.label}
                </p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
              </div>
              <div
                className={`w-11 h-11 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center shadow-sm flex-shrink-0`}
              >
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="flex flex-wrap">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 min-w-[120px] px-6 py-4 flex flex-col items-center gap-1 transition-all border-b-2 ${
                activeTab === tab.id
                  ? 'border-violet-500 text-violet-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
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
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 space-y-6">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-medium text-gray-700">
                    提示词 <span className="text-red-500">*</span>
                  </label>
                  <div className="flex items-center gap-3">
                    <RandomPromptButton
                      prompts={RANDOM_PROMPTS}
                      onPick={(t) => setPrompt(t)}
                      className="text-violet-500 hover:text-violet-700"
                    />
                    <EnhancePromptButton
                      text={prompt}
                      onEnhance={(t) => setPrompt(t)}
                      style="image"
                      className="text-violet-600 hover:text-violet-700"
                    />
                  </div>
                </div>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="描述你想要的图片，例如：Professional product photography of a luxury perfume bottle, golden hour lighting, white background..."
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !generating) {
                      e.preventDefault()
                      handleGenerate()
                    }
                  }}
                  className="w-full h-36 px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none transition-all"
                />
                {negativePrompt && (
                  <p className="mt-1.5 text-[11px] text-violet-500">已启用负面提示词：{negativePrompt}</p>
                )}
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">艺术风格</label>
                <div className="grid grid-cols-5 gap-1.5">
                  {ART_STYLES.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setArtStyle(artStyle === s.id ? '' : s.id)}
                      title={s.keyword}
                      className={`px-1.5 py-2 rounded-lg border text-center transition-all text-[11px] ${
                        artStyle === s.id
                          ? 'border-violet-500 bg-violet-50 text-violet-700 font-medium'
                          : 'border-gray-200 hover:bg-gray-50 text-gray-600'
                      }`}
                    >
                      <div className="text-base leading-none mb-1">{s.icon}</div>
                      {s.label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-gray-400 mt-1.5">
                  选择后自动追加风格关键词到提示词，再次点击取消；当前风格：
                  <span className="text-violet-500">
                    {ART_STYLES.find((s) => s.id === artStyle)?.label || '无（自由发挥）'}
                  </span>
                </p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">负面提示词（可选）</label>
                <textarea
                  value={negativePrompt}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                  rows={2}
                  placeholder="排除不想要的元素，如：low quality, blurry, watermark, distorted hands（支持中文）"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm resize-none"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-3 block">图片尺寸</label>
                <div className="grid grid-cols-3 gap-2">
                  {SIZES.map((s) => (
                    <button
                      key={s.value}
                      onClick={() => setSelectedSize(s.value)}
                      className={`px-3 py-2 rounded-lg border text-center transition-all ${
                        selectedSize === s.value
                          ? 'border-violet-500 bg-violet-50 text-violet-700'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div className="text-sm font-medium">{s.label}</div>
                      <div className="text-xs text-gray-500">{s.ratio}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-3 block">批量生成</label>
                <div className="flex items-center gap-3">
                  {[1, 2, 3, 4].map((n) => (
                    <button
                      key={n}
                      onClick={() => setBatchSize(n)}
                      className={`w-10 h-10 rounded-lg border font-medium transition-all ${
                        batchSize === n
                          ? 'border-violet-500 bg-violet-500 text-white'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              <Button
                variant="gradient"
                size="lg"
                icon={Sparkles}
                loading={generating}
                disabled={!prompt.trim()}
                onClick={handleGenerate}
                className="w-full"
              >
                {generating ? '生成任务执行中（后台）…' : '生成图片'}
              </Button>
              {generating && genTask && (
                <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2 mt-2">
                  <div className="flex items-center gap-2 text-xs text-violet-700">
                    <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                    <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                    <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-violet-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-purple-600 rounded-full transition-all"
                      style={{ width: `${genTask.progress || 0}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                  </p>
                </div>
              )}

              <div>
                <p className="text-xs text-gray-500 mb-2">提示词模板</p>
                <div className="flex flex-wrap gap-2">
                  {PROMPT_TEMPLATES.map((tmpl, idx) => (
                    <button
                      key={idx}
                      onClick={() => applyTemplate(tmpl)}
                      className="px-3 py-1.5 rounded-full text-xs border border-gray-200 hover:bg-gray-50 transition-colors"
                    >
                      {tmpl.name}
                    </button>
                  ))}
                </div>
              </div>

              {generationError && (
                <div className="px-4 py-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
                  {generationError}
                </div>
              )}

              {!stats.api_configured && (
                <div className="px-4 py-3 bg-yellow-50 border border-yellow-200 text-yellow-700 rounded-xl text-sm">
                  未配置 AGNES_API_KEY，API 调用可能失败
                </div>
              )}
            </div>

            {/* Results */}
            <div className="lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-gray-900">生成结果</h3>
                <div className="flex items-center gap-3">
                  {generatedImages.length > 1 && (
                    <button
                      onClick={() => generatedImages.forEach((img) => handleDownload(img))}
                      className="flex items-center gap-1 text-sm text-violet-600 hover:text-violet-700"
                    >
                      <DownloadCloud className="w-4 h-4" />
                      <span>全部下载</span>
                    </button>
                  )}
                  {generatedImages.length > 0 && (
                    <button
                      onClick={handleGenerate}
                      disabled={generating || !prompt.trim()}
                      className="flex items-center gap-1 text-sm text-violet-600 hover:text-violet-700 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
                      <span>换一版</span>
                    </button>
                  )}
                </div>
              </div>

              {generating ? (
                <div className="grid grid-cols-2 gap-4">
                  {Array.from({ length: batchSize }).map((_, i) => (
                    <div key={i} className="h-48 rounded-xl bg-gray-100 animate-pulse" />
                  ))}
                </div>
              ) : generatedImages.length > 0 ? (
                <div className="grid grid-cols-2 gap-4">
                  {generatedImages.map((img, idx) => (
                    <div key={idx} className="relative group rounded-xl overflow-hidden shadow-sm">
                      <img src={img.url} alt={img.prompt} className="w-full h-48 object-cover" />
                      {renderImageActions(img)}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-64">
                  <Empty
                    icon={Sparkles}
                    title="暂无生成结果"
                    description="输入提示词，点击生成图片"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Img2Img Tab */}
      {activeTab === 'img2img' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 space-y-5">
              <input
                ref={img2imgRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImg2ImgUpload}
              />
              <div>
                <label className="text-sm font-medium text-gray-700 mb-3 block">参考图</label>
                {img2imgPreview ? (
                  <div className="relative rounded-xl overflow-hidden border border-gray-200">
                    <img src={img2imgPreview} alt="参考图" className="w-full h-56 object-cover" />
                    <button
                      onClick={() => {
                        setImg2imgFile(null)
                        setImg2imgPreview('')
                      }}
                      className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/50 text-white hover:bg-red-500 transition-colors"
                      title="移除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => img2imgRef.current?.click()}
                    className="w-full border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-violet-500 transition-colors"
                  >
                    <Upload className="w-10 h-10 mx-auto text-violet-500 mb-2" />
                    <p className="text-sm font-medium text-gray-900">点击上传参考图</p>
                    <p className="text-xs text-gray-500 mt-1">支持 JPG、PNG 格式</p>
                  </button>
                )}
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">提示词</label>
                <textarea
                  value={img2imgPrompt}
                  onChange={(e) => setImg2imgPrompt(e.target.value)}
                  rows={4}
                  placeholder="描述想要的风格/元素变化，如：把照片变成油画风格、保持人物不变…"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm resize-none"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">尺寸</label>
                <div className="grid grid-cols-3 gap-2">
                  {SIZES.slice(0, 6).map((s) => (
                    <button
                      key={s.value}
                      onClick={() => setImg2imgSize(s.value)}
                      className={`px-2 py-2 rounded-lg border text-center transition-all ${img2imgSize === s.value ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-gray-200 hover:bg-gray-50'}`}
                    >
                      <div className="text-xs font-medium">{s.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  变化强度：{img2imgStrength}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={img2imgStrength}
                  onChange={(e) => setImg2imgStrength(parseFloat(e.target.value))}
                  className="w-full"
                />
                <p className="text-[11px] text-gray-400 mt-1">越小越接近原图，越大变化越明显</p>
              </div>

              <Button
                variant="gradient"
                size="lg"
                icon={Image}
                loading={img2imgBusy}
                disabled={!img2imgPrompt.trim() || !img2imgFile}
                onClick={handleImg2Img}
                className="w-full"
              >
                {img2imgBusy ? '生成任务执行中（后台）…' : '生成变体'}
              </Button>
              {img2imgBusy && genTask && (
                <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2 mt-2">
                  <div className="flex items-center gap-2 text-xs text-violet-700">
                    <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                    <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                    <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-violet-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-purple-600 rounded-full transition-all"
                      style={{ width: `${genTask.progress || 0}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                  </p>
                </div>
              )}
            </div>

            <div className="lg:col-span-2">
              <h3 className="font-medium text-gray-900 mb-4">生成结果</h3>
              {img2imgBusy ? (
                <div className="h-64 rounded-xl bg-gray-100 animate-pulse" />
              ) : generatedImages.length > 0 ? (
                <div className="relative group rounded-xl overflow-hidden shadow-sm">
                  <img
                    src={generatedImages[0].url}
                    alt={img2imgPrompt}
                    className="w-full h-64 object-cover"
                  />
                  {renderImageActions(generatedImages[0])}
                </div>
              ) : (
                <div className="h-64">
                  <Empty
                    icon={Image}
                    title="暂无结果"
                    description="上传参考图并输入提示词，生成风格变体"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Img2Img Tab */}
      {activeTab === 'img2img' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 space-y-5">
              <input
                ref={img2imgRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImg2ImgUpload}
              />
              <div>
                <label className="text-sm font-medium text-gray-700 mb-3 block">参考图</label>
                {img2imgPreview ? (
                  <div className="relative rounded-xl overflow-hidden border border-gray-200">
                    <img src={img2imgPreview} alt="参考图" className="w-full h-56 object-cover" />
                    <button
                      onClick={() => {
                        setImg2imgFile(null)
                        setImg2imgPreview('')
                      }}
                      className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/50 text-white hover:bg-red-500 transition-colors"
                      title="移除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => img2imgRef.current?.click()}
                    className="w-full border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-violet-500 transition-colors"
                  >
                    <Upload className="w-10 h-10 mx-auto text-violet-500 mb-2" />
                    <p className="text-sm font-medium text-gray-900">点击上传参考图</p>
                    <p className="text-xs text-gray-500 mt-1">支持 JPG、PNG 格式</p>
                  </button>
                )}
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">提示词</label>
                <textarea
                  value={img2imgPrompt}
                  onChange={(e) => setImg2imgPrompt(e.target.value)}
                  rows={4}
                  placeholder="描述想要的风格/元素变化，如：把照片变成油画风格、保持人物不变…"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm resize-none"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">尺寸</label>
                <div className="grid grid-cols-3 gap-2">
                  {SIZES.map((s) => (
                    <button
                      key={s.value}
                      onClick={() => setImg2imgSize(s.value)}
                      className={`px-2 py-2 rounded-lg border text-center transition-all ${img2imgSize === s.value ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-gray-200 hover:bg-gray-50'}`}
                    >
                      <div className="text-xs font-medium">{s.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  变化强度：{img2imgStrength}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={img2imgStrength}
                  onChange={(e) => setImg2imgStrength(parseFloat(e.target.value))}
                  className="w-full"
                />
                <p className="text-[11px] text-gray-400 mt-1">越小越接近原图，越大变化越明显</p>
              </div>

              <Button
                variant="gradient"
                size="lg"
                icon={Image}
                loading={img2imgBusy}
                disabled={!img2imgPrompt.trim() || !img2imgFile}
                onClick={handleImg2Img}
                className="w-full"
              >
                {img2imgBusy ? '生成任务执行中（后台）…' : '生成变体'}
              </Button>
              {img2imgBusy && genTask && (
                <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2 mt-2">
                  <div className="flex items-center gap-2 text-xs text-violet-700">
                    <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                    <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                    <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-violet-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-purple-600 rounded-full transition-all"
                      style={{ width: `${genTask.progress || 0}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                  </p>
                </div>
              )}
            </div>

            <div className="lg:col-span-2">
              <h3 className="font-medium text-gray-900 mb-4">生成结果</h3>
              {img2imgBusy ? (
                <div className="h-64 rounded-xl bg-gray-100 animate-pulse" />
              ) : generatedImages.length > 0 ? (
                <div className="relative group rounded-xl overflow-hidden shadow-sm">
                  <img
                    src={generatedImages[0].url}
                    alt={img2imgPrompt}
                    className="w-full h-64 object-cover"
                  />
                  {renderImageActions(generatedImages[0])}
                </div>
              ) : (
                <div className="h-64">
                  <Empty
                    icon={Image}
                    title="暂无结果"
                    description="上传参考图并输入提示词，生成风格变体"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Template Tab */}
      {activeTab === 'template' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 space-y-6">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-medium text-gray-700">选择模板</label>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => setTemplateModal('create')}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-violet-50 text-violet-600 border border-violet-200 hover:bg-violet-100 transition-all"
                    >
                      <Plus className="w-3 h-3" /> 新建
                    </button>
                    <button
                      onClick={() => document.getElementById('tmpl-upload-input')?.click()}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-all"
                    >
                      <Upload className="w-3 h-3" /> 上传
                    </button>
                    <input
                      id="tmpl-upload-input"
                      type="file"
                      accept=".json"
                      className="hidden"
                      onChange={handleUploadTemplate}
                    />
                  </div>
                </div>
                {templates.length === 0 ? (
                  <p className="text-sm text-gray-500">暂无可用模板</p>
                ) : (
                  <div className="space-y-2">
                    {templates.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setSelectedTemplate(t.id)}
                        className={`w-full px-4 py-3 rounded-xl border text-left flex items-center justify-between transition-all ${
                          selectedTemplate === t.id
                            ? 'border-violet-500 bg-violet-50'
                            : 'border-gray-200 hover:bg-gray-50'
                        }`}
                      >
                        <div>
                          <div className="font-medium text-gray-900">{t.name}</div>
                          <div className="text-xs text-gray-500">
                            {t.width} × {t.height}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {selectedTemplate === t.id && (
                            <div className="w-2 h-2 rounded-full bg-violet-500" />
                          )}
                          <span
                            onClick={(e) => {
                              e.stopPropagation()
                              setDeletingTemplate(t.id)
                            }}
                            className="p-1 rounded-md text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                            title="删除模板"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <Button
                variant="gradient"
                size="lg"
                icon={LayoutTemplate}
                loading={rendering}
                disabled={!selectedTemplate}
                onClick={handleRenderTemplate}
                className="w-full"
              >
                {rendering ? '渲染任务执行中（后台）…' : '生成图片'}
              </Button>
              {rendering && genTask && (
                <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2 mt-2">
                  <div className="flex items-center gap-2 text-xs text-violet-700">
                    <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                    <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                    <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-violet-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-purple-600 rounded-full transition-all"
                      style={{ width: `${genTask.progress || 0}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                  </p>
                </div>
              )}
            </div>

            <div className="lg:col-span-2">
              <h3 className="font-medium text-gray-900 mb-4">预览</h3>
              {rendering ? (
                <div className="h-64 rounded-xl bg-gray-100 animate-pulse" />
              ) : generatedImages.length > 0 ? (
                <div className="relative group rounded-xl overflow-hidden shadow-sm">
                  <img
                    src={generatedImages[0].url}
                    alt="模板结果"
                    className="w-full h-64 object-cover"
                  />
                  {renderImageActions(generatedImages[0])}
                </div>
              ) : (
                <div className="h-64">
                  <Empty icon={LayoutTemplate} title="暂无预览" description="选择模板并点击生成" />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Tab */}
      {activeTab === 'edit' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">图片编辑工具</h2>

          <input
            ref={editFileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleEditUpload}
          />

          <button
            onClick={() => editFileRef.current?.click()}
            className="w-full border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-violet-500 transition-colors"
          >
            <Upload className="w-12 h-12 mx-auto text-violet-500 mb-3" />
            <p className="font-medium text-gray-900">点击上传图片</p>
            <p className="text-sm text-gray-500 mt-1">支持 JPG、PNG 格式</p>
          </button>

          {uploadedImage && (
            <div className="mt-6 mb-6">
              <img
                src={uploadedImage.url}
                alt="待编辑"
                className="w-full max-h-96 object-contain rounded-xl"
              />
            </div>
          )}

          {uploadedImage && (
            <div>
              <h3 className="font-medium text-gray-900 mb-4">编辑工具</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                {EDIT_TOOLS.map((tool, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleEditImage(tool.action)}
                    disabled={editBusy}
                    className="p-4 rounded-xl border border-gray-200 hover:bg-gray-50 transition-all text-center disabled:opacity-50"
                  >
                    <tool.icon className="w-6 h-6 mx-auto text-violet-500 mb-2" />
                    <p className="font-medium text-sm text-gray-900">{tool.label}</p>
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">旋转角度</label>
                  <select
                    value={editOptions.angle}
                    onChange={(e) => setEditOptions({ ...editOptions, angle: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                  >
                    <option value="0">0°</option>
                    <option value="90">90°</option>
                    <option value="180">180°</option>
                    <option value="270">270°</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">滤镜效果</label>
                  <select
                    value={editOptions.filter}
                    onChange={(e) => setEditOptions({ ...editOptions, filter: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                  >
                    <option value="none">无</option>
                    <option value="grayscale">黑白</option>
                    <option value="sepia">复古</option>
                    <option value="blur">模糊</option>
                    <option value="sharpen">锐化</option>
                    <option value="emboss">浮雕</option>
                    <option value="contour">轮廓</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">
                    亮度: {editOptions.brightness.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={editOptions.brightness}
                    onChange={(e) =>
                      setEditOptions({ ...editOptions, brightness: parseFloat(e.target.value) })
                    }
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">
                    对比度: {editOptions.contrast.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={editOptions.contrast}
                    onChange={(e) =>
                      setEditOptions({ ...editOptions, contrast: parseFloat(e.target.value) })
                    }
                    className="w-full"
                  />
                </div>
              </div>

              <Button
                variant="gradient"
                icon={Sliders}
                loading={editBusy}
                onClick={() => handleEditImage('adjust')}
                className="w-full"
              >
                应用调整
              </Button>

              {/* 人像分割 */}
              <div className="mt-8 border-t border-gray-100 pt-6">
                <h4 className="font-medium text-gray-900 mb-1 flex items-center gap-2">
                  <Scissors className="w-4 h-4 text-violet-500" />
                  人像分割
                </h4>
                <p className="text-xs text-gray-500 mb-4">
                  rembg 语义分割：将人物从背景中分离，输出透明背景 PNG（可用于合成、做贴纸）
                </p>
                <div className="mb-4">
                  <label className="text-sm font-medium text-gray-700 mb-2 block">
                    边缘羽化: {segFeather}（发丝/毛边场景建议 2）
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="8"
                    step="1"
                    value={segFeather}
                    onChange={(e) => setSegFeather(parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>
                <Button
                  variant="gradient"
                  icon={Scissors}
                  loading={editBusy}
                  onClick={handleSegmentation}
                  className="w-full"
                >
                  一键分割（透明背景）
                </Button>
              </div>

              {/* 背景替换 */}
              <div className="mt-8 border-t border-gray-100 pt-6">
                <h4 className="font-medium text-gray-900 mb-1 flex items-center gap-2">
                  <Wand2 className="w-4 h-4 text-violet-500" />
                  背景替换
                </h4>
                <p className="text-xs text-gray-500 mb-4">
                  AI 抠图 + 新背景合成：场景渐变 / 纯色 / AI 生成背景（优先级：AI 描述 &gt; 纯色 &gt; 场景）
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">场景</label>
                    <select
                      value={bgScene}
                      onChange={(e) => setBgScene(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                    >
                      {BG_SCENES.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.icon} {s.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      纯色背景（可选，如 #FF5733）
                    </label>
                    <input
                      type="text"
                      placeholder="#RRGGBB"
                      value={bgColor}
                      onChange={(e) => setBgColor(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      AI 背景描述（可选）
                    </label>
                    <input
                      type="text"
                      placeholder="如：清晨的雪山湖泊，薄雾缭绕"
                      value={bgAIDesc}
                      onChange={(e) => setBgAIDesc(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
                    />
                  </div>
                </div>
                <Button
                  variant="gradient"
                  icon={Wand2}
                  loading={editBusy}
                  onClick={handleReplaceBackground}
                  className="w-full"
                >
                  替换背景
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Try-On Tab */}
      {activeTab === 'try-on' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-6">
          <h2 className="text-lg font-semibold text-gray-900">虚拟试衣</h2>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 space-y-6">
              {/* Person Upload */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-medium text-gray-700">上传人物照片</label>
                  <button
                    onClick={() => setShowImagePicker('person')}
                    className="text-xs text-violet-600 hover:text-violet-700 flex items-center gap-1"
                  >
                    <ImageIcon className="w-3 h-3" />
                    <span>从图库选择</span>
                  </button>
                </div>
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-violet-500 transition-colors">
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    id="person-upload"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file)
                        setPersonImage({ url: URL.createObjectURL(file), filename: file.name })
                    }}
                  />
                  <label htmlFor="person-upload" className="cursor-pointer">
                    {personImage ? (
                      <img
                        src={personImage.url}
                        alt="人物"
                        className="w-full h-48 object-contain rounded-lg"
                      />
                    ) : (
                      <>
                        <Camera className="w-12 h-12 mx-auto text-violet-500 mb-3" />
                        <p className="font-medium text-gray-900">上传人物照片</p>
                        <p className="text-sm text-gray-500 mt-1">全身照效果最佳</p>
                      </>
                    )}
                  </label>
                </div>
              </div>

              {/* Clothing Upload */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-medium text-gray-700">上传衣物照片</label>
                  <button
                    onClick={() => setShowImagePicker('clothing')}
                    className="text-xs text-violet-600 hover:text-violet-700 flex items-center gap-1"
                  >
                    <ImageIcon className="w-3 h-3" />
                    <span>从图库选择</span>
                  </button>
                </div>
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-violet-500 transition-colors">
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    id="clothing-upload"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file)
                        setClothingImage({ url: URL.createObjectURL(file), filename: file.name })
                    }}
                  />
                  <label htmlFor="clothing-upload" className="cursor-pointer">
                    {clothingImage ? (
                      <img
                        src={clothingImage.url}
                        alt="衣物"
                        className="w-full h-48 object-contain rounded-lg"
                      />
                    ) : (
                      <>
                        <Shirt className="w-12 h-12 mx-auto text-violet-500 mb-3" />
                        <p className="font-medium text-gray-900">上传衣物照片</p>
                        <p className="text-sm text-gray-500 mt-1">正面平铺效果最佳</p>
                      </>
                    )}
                  </label>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">描述（可选）</label>
                <textarea
                  value={tryOnDescription}
                  onChange={(e) => setTryOnDescription(e.target.value)}
                  placeholder="例如：这件衣服是夏季轻薄面料，适合海边度假..."
                  className="w-full h-24 px-4 py-3 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none resize-none"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-3 block">风格</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {TRYON_STYLES.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setTryOnStyle(s.id)}
                      className={`p-3 rounded-lg border text-center transition-all ${tryOnStyle === s.id ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-gray-200 hover:bg-gray-50'}`}
                    >
                      <div className="text-2xl mb-1">{s.icon}</div>
                      <div className="text-sm font-medium">{s.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-3 block">背景场景</label>
                <div className="grid grid-cols-3 gap-2">
                  {TRYON_BACKGROUNDS.map((bg) => (
                    <button
                      key={bg.id}
                      onClick={() => setTryOnBackground(bg.id)}
                      className={`p-3 rounded-lg border text-center transition-all ${tryOnBackground === bg.id ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-gray-200 hover:bg-gray-50'}`}
                    >
                      <div className="text-2xl mb-1">{bg.icon}</div>
                      <div className="text-xs font-medium">{bg.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              <Button
                variant="gradient"
                size="lg"
                icon={Wand2}
                loading={tryOnGenerating}
                disabled={!personImage || !clothingImage}
                onClick={handleTryOn}
                className="w-full"
              >
                {tryOnGenerating ? '生成任务执行中（后台）…' : '生成试穿效果'}
              </Button>
              {tryOnGenerating && genTask && (
                <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2 mt-2">
                  <div className="flex items-center gap-2 text-xs text-violet-700">
                    <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                    <span className="flex-1 truncate">{genTask.stage || '任务执行中…'}</span>
                    <span className="font-medium">{Math.round(genTask.progress || 0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-violet-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-purple-600 rounded-full transition-all"
                      style={{ width: `${genTask.progress || 0}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    任务已提交后台执行，可关闭页面稍后在「任务中心」查看结果
                  </p>
                </div>
              )}
            </div>

            {/* Result */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-gray-900">试穿效果</h3>
                {tryOnResult && (
                  <Button
                    variant="success"
                    size="sm"
                    icon={Download}
                    onClick={() => handleDownload(tryOnResult)}
                  >
                    下载
                  </Button>
                )}
              </div>

              {tryOnGenerating ? (
                <div className="h-96 rounded-xl bg-gray-100 animate-pulse" />
              ) : tryOnResult ? (
                <div className="rounded-xl overflow-hidden border border-gray-200">
                  <img src={tryOnResult.url} alt="试穿效果" className="w-full h-96 object-cover" />
                </div>
              ) : (
                <div className="h-96">
                  <Empty
                    icon={UserCircle}
                    title="上传照片后生成试穿效果"
                    description="支持人物全身照 + 衣物平铺照"
                  />
                </div>
              )}

              <div className="p-4 rounded-lg bg-gray-50">
                <h4 className="font-medium text-sm text-gray-900 mb-2">使用提示</h4>
                <ul className="text-xs text-gray-500 space-y-1">
                  <li>• 人物照片：全身照效果最佳，光线均匀</li>
                  <li>• 衣物照片：正面平铺或挂拍，背景干净</li>
                  <li>• 可尝试不同风格和背景组合</li>
                </ul>
              </div>
            </div>
          </div>

          {/* 3D Rotation Viewer */}
          {tryOnResult && (
            <div className="p-6 rounded-xl bg-gray-50">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-gray-900">3D 旋转查看</h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIsAutoRotate(!isAutoRotate)}
                    className={`px-3 py-1.5 rounded-lg text-sm ${isAutoRotate ? 'bg-violet-600 text-white' : 'border border-gray-200 hover:bg-gray-100'}`}
                  >
                    {isAutoRotate ? '暂停' : '自动旋转'}
                  </button>
                  <button
                    onClick={() => {
                      setRotationY(0)
                      setRotationX(0)
                    }}
                    className="px-3 py-1.5 rounded-lg text-sm border border-gray-200 hover:bg-gray-100"
                  >
                    重置
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <div
                    className="relative h-80 rounded-xl overflow-hidden cursor-move bg-white"
                    style={{ perspective: '1000px' }}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      const startX = e.clientX
                      const startY = e.clientY
                      const startRotationY = rotationY
                      const startRotationX = rotationX
                      const onMove = (ev) => {
                        setRotationY(startRotationY + (ev.clientX - startX) * 0.5)
                        setRotationX(startRotationX - (ev.clientY - startY) * 0.3)
                      }
                      const onUp = () => {
                        document.removeEventListener('mousemove', onMove)
                        document.removeEventListener('mouseup', onUp)
                      }
                      document.addEventListener('mousemove', onMove)
                      document.addEventListener('mouseup', onUp)
                    }}
                  >
                    <div
                      className="w-full h-full flex items-center justify-center transition-transform duration-100"
                      style={{
                        transform: `rotateY(${rotationY}deg) rotateX(${rotationX}deg)`,
                        transformStyle: 'preserve-3d',
                      }}
                    >
                      <img
                        src={tryOnResult.url}
                        alt="试穿效果"
                        className="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
                      />
                    </div>
                    <div className="absolute bottom-4 left-4 flex items-center gap-2">
                      <div className="px-2 py-1 rounded text-xs bg-white/75">
                        X: {rotationX.toFixed(0)}°
                      </div>
                      <div className="px-2 py-1 rounded text-xs bg-white/75">
                        Y: {rotationY.toFixed(0)}°
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">水平 (Y轴)</span>
                      <span className="text-xs text-gray-500">{rotationY.toFixed(0)}°</span>
                    </div>
                    <input
                      type="range"
                      min="-180"
                      max="180"
                      value={rotationY}
                      onChange={(e) => setRotationY(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">垂直 (X轴)</span>
                      <span className="text-xs text-gray-500">{rotationX.toFixed(0)}°</span>
                    </div>
                    <input
                      type="range"
                      min="-90"
                      max="90"
                      value={rotationX}
                      onChange={(e) => setRotationX(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      自动旋转速度
                    </label>
                    <input
                      type="range"
                      min="0.5"
                      max="5"
                      step="0.5"
                      value={rotationSpeed}
                      onChange={(e) => setRotationSpeed(Number(e.target.value))}
                      className="w-full"
                    />
                    <div className="text-xs text-gray-500 text-center mt-1">{rotationSpeed}x</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Gallery Tab */}
      {activeTab === 'gallery' && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-4">
            <h2 className="text-lg font-semibold text-gray-900">图片库</h2>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索图片..."
                  className="pl-10 pr-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
                />
              </div>
              <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchImages}>
                刷新
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={Package}
                disabled={filteredImages.length === 0}
                onClick={() => setPackOpen(true)}
                title="一键打包为平台规格成品 + 高清版 + 上架文案"
              >
                发布包
              </Button>
              <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-2 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-violet-600' : 'text-gray-500'}`}
                  title="网格视图"
                >
                  <LayoutGrid className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`p-2 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-violet-600' : 'text-gray-500'}`}
                  title="列表视图"
                >
                  <ListIcon className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {loadingGallery ? (
            <SkeletonGrid count={8} />
          ) : galleryError ? (
            <ErrorState message={`加载失败：${galleryError.message}`} onRetry={fetchImages} />
          ) : filteredImages.length === 0 ? (
            <Empty
              icon={ImageIcon}
              title={searchQuery ? '未找到匹配的图片' : '暂无图片'}
              description={searchQuery ? '尝试调整搜索条件' : '去「文生图」生成你的第一张图片'}
            />
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {filteredImages.map((img) => (
                <div
                  key={img.filename}
                  className="group relative rounded-xl overflow-hidden shadow-sm"
                >
                  <img
                    src={absUrl(img.thumb_url || img.url)}
                    alt={img.title || img.filename}
                    className="w-full h-40 object-cover"
                    loading="lazy"
                  />
                  {renderImageActions({ ...img, url: absUrl(img.url) })}
                  <div className="absolute bottom-0 left-0 right-0 px-2 py-1 text-xs text-white truncate bg-black/50">
                    {img.title || img.filename}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredImages.map((img) => (
                <div
                  key={img.filename}
                  className="flex items-center gap-4 p-3 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <img
                    src={absUrl(img.thumb_url || img.url)}
                    alt={img.title || img.filename}
                    className="w-16 h-16 object-cover rounded-lg flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{img.title || img.filename}</p>
                    <p className="text-sm text-gray-500">
                      {formatRelativeTime(img.created_at)} · {formatBytes(img.size)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => setPreviewImage({ ...img, url: absUrl(img.url) })}
                      className="p-2 hover:bg-blue-50 text-gray-400 hover:text-blue-600 rounded-lg transition-colors"
                      title="预览"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDownload({ ...img, url: absUrl(img.url) })}
                      className="p-2 hover:bg-green-50 text-gray-400 hover:text-green-600 rounded-lg transition-colors"
                      title="下载"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setDeleteTarget({ ...img, url: absUrl(img.url) })}
                      className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-lg transition-colors"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 图片发布包 Modal：平台规格成品 + 2x 高清 + 上架文案 + 质量报告 */}
      <Modal
        open={packOpen}
        onClose={() => setPackOpen(false)}
        title="图片发布包（平台规格成品）"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPackOpen(false)} disabled={packing}>
              取消
            </Button>
            <Button
              variant="primary"
              icon={Package}
              loading={packing}
              onClick={downloadPublishPack}
              className="bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700"
            >
              生成发布包（{Math.min(filteredImages.length, 50)} 张）
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-lg bg-violet-50 border border-violet-100 px-3 py-2 text-xs text-violet-700">
            将当前图片库（{filteredImages.length} 张，最多 50 张）按平台规格居中裁剪输出不变形成品，
            附带 2 倍高清版、上架文案（标题/描述/标签）、规格说明、上传指南、商用授权与质量自检报告。
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">目标平台</label>
            <div className="grid grid-cols-2 gap-2">
              {PUBLISH_PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPackPlatform(p.id)}
                  className={`flex flex-col items-start gap-0.5 px-3 py-2.5 rounded-xl border text-left transition-all ${
                    packPlatform === p.id
                      ? 'border-violet-500 bg-violet-50 ring-2 ring-violet-500/20'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-sm font-medium text-gray-800">{p.name}</span>
                  <span className="text-[11px] text-gray-400">{p.spec}</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              合集标题（上架文案用）
            </label>
            <input
              type="text"
              value={packTitle}
              onChange={(e) => setPackTitle(e.target.value)}
              placeholder="如：AI 原创插画集"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={packUpscale}
              onChange={(e) => setPackUpscale(e.target.checked)}
              className="w-4 h-4 accent-violet-500"
            />
            附带 2 倍高清版（lanczos 放大 + 锐化，适合印刷/高清投放）
          </label>
        </div>
      </Modal>

      {/* 图片预览 Modal */}
      <Modal
        open={!!previewImage}
        onClose={() => setPreviewImage(null)}
        title={previewImage?.filename}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPreviewImage(null)}>
              关闭
            </Button>
            <Button variant="success" icon={Download} onClick={() => handleDownload(previewImage)}>
              下载
            </Button>
            <Button variant="danger" icon={Trash2} onClick={() => setDeleteTarget(previewImage)}>
              删除
            </Button>
          </>
        }
      >
        {previewImage && (
          <img src={previewImage.url} alt={previewImage.filename} className="w-full rounded-lg" />
        )}
      </Modal>

      {/* 图库选择 Modal */}
      <Modal
        open={!!showImagePicker}
        onClose={() => setShowImagePicker(null)}
        title={showImagePicker === 'person' ? '选择人物照片' : '选择衣物照片'}
        size="2xl"
      >
        {images.length === 0 ? (
          <Empty icon={ImageIcon} title="图片库为空" description="请先上传或生成图片" />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {images.map((img) => {
              const url = absUrl(img.url)
              const selected =
                (showImagePicker === 'person' && personImage?.url === url) ||
                (showImagePicker === 'clothing' && clothingImage?.url === url)
              return (
                <button
                  key={img.filename}
                  onClick={() => {
                    const picked = { url, filename: img.filename }
                    if (showImagePicker === 'person') setPersonImage(picked)
                    else setClothingImage(picked)
                    setShowImagePicker(null)
                  }}
                  className={`relative rounded-lg overflow-hidden border-2 transition-all ${selected ? 'border-violet-500' : 'border-gray-200 hover:border-violet-400'}`}
                >
                  <img
                    src={absUrl(img.thumb_url || img.url)}
                    alt={img.filename}
                    className="w-full h-32 object-cover"
                    loading="lazy"
                  />
                  <div className="absolute bottom-0 left-0 right-0 bg-black/50 px-2 py-1">
                    <p className="text-xs text-white truncate">{img.filename}</p>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </Modal>

      {/* 删除确认 */}
      {/* 模板管理弹窗 */}
      <Modal
        open={templateModal === 'create'}
        onClose={() => setTemplateModal(false)}
        title="新建模板"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">模板名称 *</label>
            <input
              value={templateForm.name}
              onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
              placeholder="如：电商商品主图"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">宽度</label>
              <input
                type="number"
                value={templateForm.width}
                onChange={(e) => setTemplateForm({ ...templateForm, width: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">高度</label>
              <input
                type="number"
                value={templateForm.height}
                onChange={(e) => setTemplateForm({ ...templateForm, height: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">背景色</label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={templateForm.background}
                onChange={(e) => setTemplateForm({ ...templateForm, background: e.target.value })}
                className="w-12 h-10 rounded-lg border border-gray-200 cursor-pointer"
              />
              <input
                value={templateForm.background}
                onChange={(e) => setTemplateForm({ ...templateForm, background: e.target.value })}
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm font-mono"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              图层配置（JSON，可选）
            </label>
            <textarea
              value={templateForm.layers}
              onChange={(e) => setTemplateForm({ ...templateForm, layers: e.target.value })}
              rows={5}
              placeholder='[{"type":"text","content":"标题","x":50,"y":100}, {"type":"image","url":"…"}]'
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm font-mono resize-none"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={() => setTemplateModal(false)}>
            取消
          </Button>
          <Button
            variant="gradient"
            icon={Plus}
            loading={templateSaving}
            onClick={handleCreateTemplate}
          >
            创建模板
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deletingTemplate}
        onClose={() => setDeletingTemplate(null)}
        onConfirm={handleDeleteTemplate}
        title="删除模板？"
        message="删除后该模板将不可恢复，已生成的图片不受影响。"
        confirmLabel="删除"
        icon={Trash2}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="确认删除图片"
        message={`确定要删除「${deleteTarget?.filename}」吗？此操作不可撤销。`}
        confirmLabel="确认删除"
      />
    </div>
  )
}

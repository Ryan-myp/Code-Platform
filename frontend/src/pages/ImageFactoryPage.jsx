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
  Rotate3d,
  FlipHorizontal,
  Sliders,
  DownloadCloud,
  Search,
  Image,
  Plus,
  FileJson2,
  Package,
  ZoomIn,
  Pencil,
  ArrowUp,
  ArrowDown,
  X,
  Check,
  ChevronDown,
  ChevronUp,
  Type,
  Square,
  Circle,
  Minus,
  Copy,
  Send,
  FileSpreadsheet,
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
  Pagination,
} from '../components/ui'
import ShareButton from '../components/ShareButton'
import FavoriteButton from '../components/FavoriteButton'
import ImageQualityBadge from '../components/ImageQualityBadge'
import EnhancePromptButton from '../components/EnhancePromptButton'
import RandomPromptButton from '../components/RandomPromptButton'
import useAsyncTask from '../hooks/useAsyncTask'
import usePersistentToolState from '../hooks/usePersistentToolState'
import useToolHistory from '../hooks/useToolHistory'
import HistoryPanel from '../components/HistoryPanel'

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
  {
    name: '电商主图',
    prompt:
      'E-commerce product main image of [PRODUCT], clean white background, dramatic lighting, high-resolution commercial photography, space for promotional text',
  },
  {
    name: '头像插画',
    prompt:
      'Stylish avatar illustration of [SUBJECT], [STYLE] style, centered composition, vibrant colors, social media profile picture',
  },
  {
    name: '室内设计',
    prompt:
      'Interior design render of [ROOM], [STYLE] style, natural lighting, photorealistic, architectural visualization, cozy atmosphere',
  },
  {
    name: '美食摄影',
    prompt:
      'Appetizing food photography of [DISH], overhead shot, rustic table setting, warm lighting, steam details, professional food styling',
  },
  {
    name: '风景大片',
    prompt:
      'Breathtaking landscape of [LOCATION], [SEASON], dramatic sky, golden hour, ultra-wide composition, National Geographic style',
  },
  {
    name: '时尚大片',
    prompt:
      'Fashion editorial photo of [SUBJECT], [OCCASION], studio lighting, editorial magazine style, high-fashion pose, sharp details',
  },
  {
    name: '建筑外观',
    prompt:
      'Architectural photography of [BUILDING], [STYLE] architecture, symmetry composition, blue hour, cityscape background',
  },
  {
    name: '宠物摄影',
    prompt:
      'Adorable pet photo of [PET], [BREED], playful moment, shallow depth of field, natural light, heartwarming expression',
  },
  {
    name: '汽车海报',
    prompt:
      'Automotive advertising shot of [CAR], [ENVIRONMENT], dramatic lighting, motion blur, professional car photography, glossy reflections',
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

// 模板分类（模板市场化）
const TEMPLATE_CATEGORIES = ['通用', '电商主图', '促销海报', '节日营销', '社媒封面']

// 字体选项（与后端 FONT_FAMILIES 对应）
const FONT_OPTIONS = [
  { id: '', label: '默认（苹方）' },
  { id: 'pingfang', label: '苹方 PingFang' },
  { id: 'helvetica', label: '黑体 Helvetica' },
  { id: 'hiragino', label: '冬青黑体 Hiragino' },
  { id: 'heiti', label: '黑体 Heiti（中文首选）' },
  { id: 'songti', label: '宋体 Songti' },
  { id: 'noto', label: '思源黑体 Noto（服务端）' },
  { id: 'arial', label: 'Arial' },
  { id: 'times', label: 'Times New Roman' },
]

const FONT_CSS = {
  pingfang: 'PingFang SC, PingFangTC, sans-serif',
  helvetica: 'Helvetica, Arial, sans-serif',
  hiragino: 'Hiragino Sans GB, sans-serif',
  heiti: 'STHeiti, Heiti SC, sans-serif',
  songti: 'Songti SC, STSong, serif',
  noto: 'Noto Sans CJK SC, sans-serif',
  arial: 'Arial, sans-serif',
  times: 'Times New Roman, serif',
}

// 图层属性小工具：粗体/斜体开关
function StyleToggle({ active, onClick, children, title }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all ${
        active ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'
      }`}
    >
      {children}
    </button>
  )
}

// 模板图层属性面板（可视化编辑器）：按图层类型渲染表单
function LayerProps({ layer, onChange }) {
  const inputCls =
    'w-full px-2.5 py-1.5 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-xs'
  const labelCls = 'block text-[11px] font-medium text-gray-500 mb-1'
  const num = (v) => (v === '' || v === null || v === undefined ? '' : Number(v))
  const setNum = (key) => (e) => onChange({ [key]: e.target.value === '' ? 0 : Number(e.target.value) })
  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <label className="text-sm font-medium text-gray-700">
          图层属性 ·{' '}
          <span className="text-violet-600">
            {layer.type === 'text'
              ? '文字'
              : layer.type === 'rect'
                ? '矩形'
                : layer.type === 'circle'
                  ? '圆形'
                  : layer.type === 'line'
                    ? '线条'
                    : '图片'}
          </span>
        </label>
        <span className="text-[11px] text-gray-400">单位：像素（相对画布）</span>
      </div>

      {layer.type === 'text' && (
        <div className="space-y-3">
          <div>
            <label className={labelCls}>文字内容</label>
            <textarea
              value={layer.text || ''}
              onChange={(e) => onChange({ text: e.target.value })}
              placeholder="渲染时显示的文字（支持换行）"
              rows={2}
              className={`${inputCls} resize-none`}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>变量名（可选，渲染时可替换）</label>
              <input
                value={layer.key || ''}
                onChange={(e) => onChange({ key: e.target.value })}
                placeholder="如 price"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>字体</label>
              <select
                value={layer.family || ''}
                onChange={(e) => onChange({ family: e.target.value })}
                className={inputCls}
              >
                {FONT_OPTIONS.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className={labelCls}>样式</label>
              <div className="flex gap-1.5">
                <StyleToggle
                  active={!!layer.bold}
                  onClick={() => onChange({ bold: !layer.bold })}
                  title="粗体"
                >
                  <b>B</b>
                </StyleToggle>
                <StyleToggle
                  active={!!layer.italic}
                  onClick={() => onChange({ italic: !layer.italic })}
                  title="斜体"
                >
                  <i>I</i>
                </StyleToggle>
                <StyleToggle active={false} onClick={() => onChange({ align: layer.align === 'center' ? 'left' : 'center' })} title="对齐：左/中">
                  {layer.align === 'center' ? '居中' : '左对齐'}
                </StyleToggle>
              </div>
            </div>
            <div className="w-28">
              <label className={labelCls}>对齐方式</label>
              <select
                value={layer.align || 'left'}
                onChange={(e) => onChange({ align: e.target.value })}
                className={inputCls}
              >
                <option value="left">左</option>
                <option value="center">中</option>
                <option value="right">右</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>字号</label>
              <input type="number" value={num(layer.font_size)} onChange={setNum('font_size')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>字距</label>
              <input
                type="number"
                value={num(layer.letter_spacing)}
                onChange={setNum('letter_spacing')}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>行高</label>
              <input
                type="number"
                step="0.05"
                value={num(layer.line_height)}
                onChange={setNum('line_height')}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>旋转°</label>
              <input type="number" value={num(layer.rotation)} onChange={setNum('rotation')} className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div>
              <label className={labelCls}>X</label>
              <input type="number" value={num(layer.x)} onChange={setNum('x')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Y</label>
              <input type="number" value={num(layer.y)} onChange={setNum('y')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>最大宽度（0=不换行）</label>
              <input type="number" value={num(layer.max_width)} onChange={setNum('max_width')} className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>文字颜色</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={(layer.color || '#000000').split('→')[0].trim()}
                  onChange={(e) => onChange({ color: e.target.value })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.color || ''}
                  onChange={(e) => onChange({ color: e.target.value })}
                  placeholder="#RRGGBB 或 #A→#B 垂直渐变"
                  className={inputCls}
                />
              </div>
            </div>
            <div>
              <label className={labelCls}>阴影颜色（透明=无阴影）</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={(layer.shadow_color || '#00000080').slice(0, 7)}
                  onChange={(e) => onChange({ shadow_color: `${e.target.value}${(layer.shadow_color || '').slice(7) || '80'}` })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.shadow_color || ''}
                  onChange={(e) => onChange({ shadow_color: e.target.value })}
                  placeholder="#RRGGBBAA，如 #00000080"
                  className={`${inputCls} font-mono`}
                />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>阴影偏移（如 2,3 或 2,3,8）</label>
              <input
                value={layer.shadow || ''}
                onChange={(e) => onChange({ shadow: e.target.value })}
                placeholder="x,y,blur；blur 为模糊半径，留空无阴影"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>描边宽度（0=无）</label>
              <input type="number" value={num(layer.stroke_width)} onChange={setNum('stroke_width')} className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>描边颜色</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={layer.stroke_color || '#000000'}
                  onChange={(e) => onChange({ stroke_color: e.target.value })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.stroke_color || ''}
                  onChange={(e) => onChange({ stroke_color: e.target.value })}
                  className={inputCls}
                />
              </div>
            </div>
            <div className="flex items-end">
              <p className="text-[10px] text-gray-400 leading-relaxed pb-1">
                描边+阴影适合大促主标题；粗体勾选 B 后可用
              </p>
            </div>
          </div>
        </div>
      )}

      {layer.type === 'rect' && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>X</label>
              <input type="number" value={num(layer.x)} onChange={setNum('x')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Y</label>
              <input type="number" value={num(layer.y)} onChange={setNum('y')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>宽度</label>
              <input type="number" value={num(layer.width)} onChange={setNum('width')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>高度</label>
              <input type="number" value={num(layer.height)} onChange={setNum('height')} className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>圆角</label>
              <input type="number" value={num(layer.radius)} onChange={setNum('radius')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>不透明度（0-1）</label>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={num(layer.opacity)}
                onChange={setNum('opacity')}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>边框宽度（0=无）</label>
              <input type="number" value={num(layer.border_width)} onChange={setNum('border_width')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>旋转°</label>
              <input type="number" value={num(layer.rotation)} onChange={setNum('rotation')} className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>填充颜色（支持渐变 #A→#B）</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={String(layer.fill || '#F3F4F6').split('→')[0]}
                  onChange={(e) => onChange({ fill: e.target.value })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.fill || ''}
                  onChange={(e) => onChange({ fill: e.target.value })}
                  placeholder="#F3F4F6 或 #FF6B6B→#C0392B"
                  className={`${inputCls} font-mono`}
                />
              </div>
            </div>
            <div>
              <label className={labelCls}>边框颜色</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={layer.border_color || '#FFFFFF'}
                  onChange={(e) => onChange({ border_color: e.target.value })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.border_color || ''}
                  onChange={(e) => onChange({ border_color: e.target.value })}
                  className={inputCls}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {layer.type === 'circle' && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>圆心 X</label>
              <input type="number" value={num(layer.x)} onChange={setNum('x')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>圆心 Y</label>
              <input type="number" value={num(layer.y)} onChange={setNum('y')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>半径</label>
              <input type="number" value={num(layer.radius)} onChange={setNum('radius')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>不透明度（0-1）</label>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={num(layer.opacity)}
                onChange={setNum('opacity')}
                className={inputCls}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>边框宽度（0=无）</label>
              <input type="number" value={num(layer.border_width)} onChange={setNum('border_width')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>旋转°</label>
              <input type="number" value={num(layer.rotation)} onChange={setNum('rotation')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>填充颜色（支持渐变 #A→#B）</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={String(layer.fill || '#F3F4F6').split('→')[0]}
                  onChange={(e) => onChange({ fill: e.target.value })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.fill || ''}
                  onChange={(e) => onChange({ fill: e.target.value })}
                  placeholder="#F3F4F6 或 #FF6B6B→#C0392B（留空=仅边框）"
                  className={`${inputCls} font-mono`}
                />
              </div>
            </div>
            <div>
              <label className={labelCls}>边框颜色</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={layer.border_color || '#FFFFFF'}
                  onChange={(e) => onChange({ border_color: e.target.value })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.border_color || ''}
                  onChange={(e) => onChange({ border_color: e.target.value })}
                  className={inputCls}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {layer.type === 'line' && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>起点 X</label>
              <input type="number" value={num(layer.x)} onChange={setNum('x')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>起点 Y</label>
              <input type="number" value={num(layer.y)} onChange={setNum('y')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>长度</label>
              <input type="number" value={num(layer.length)} onChange={setNum('length')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>角度°（0=水平向右）</label>
              <input type="number" value={num(layer.angle)} onChange={setNum('angle')} className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>线宽</label>
              <input type="number" value={num(layer.width)} onChange={setNum('width')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>不透明度（0-1）</label>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={num(layer.opacity)}
                onChange={setNum('opacity')}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>颜色</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={layer.color || '#DDDDDD'}
                  onChange={(e) => onChange({ color: e.target.value })}
                  className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
                />
                <input
                  value={layer.color || ''}
                  onChange={(e) => onChange({ color: e.target.value })}
                  className={inputCls}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {layer.type === 'image' && (
        <div className="space-y-3">
          <div>
            <label className={labelCls}>图片地址（留空 = 图片槽，渲染时套入所选图片）</label>
            <input
              value={layer.url || ''}
              onChange={(e) => onChange({ url: e.target.value })}
              placeholder="粘贴图片 URL，或留空作为图片槽"
              className={inputCls}
            />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div>
              <label className={labelCls}>槽位变量名（可选）</label>
              <input
                value={layer.key || ''}
                onChange={(e) => onChange({ key: e.target.value })}
                placeholder="如 product_image"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>槽位标记（可选）</label>
              <input
                value={layer.slot || ''}
                onChange={(e) => onChange({ slot: e.target.value })}
                placeholder="如 main"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>填充方式</label>
              <select
                value={layer.fit || 'cover'}
                onChange={(e) => onChange({ fit: e.target.value })}
                className={inputCls}
              >
                <option value="cover">铺满裁剪</option>
                <option value="contain">完整显示</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>X</label>
              <input type="number" value={num(layer.x)} onChange={setNum('x')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Y</label>
              <input type="number" value={num(layer.y)} onChange={setNum('y')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>宽度</label>
              <input type="number" value={num(layer.width)} onChange={setNum('width')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>高度</label>
              <input type="number" value={num(layer.height)} onChange={setNum('height')} className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={labelCls}>圆角</label>
              <input type="number" value={num(layer.radius)} onChange={setNum('radius')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>不透明度（0-1）</label>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={num(layer.opacity)}
                onChange={setNum('opacity')}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>边框宽度（0=无）</label>
              <input type="number" value={num(layer.border_width)} onChange={setNum('border_width')} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>旋转°</label>
              <input type="number" value={num(layer.rotation)} onChange={setNum('rotation')} className={inputCls} />
            </div>
          </div>
          <div>
            <label className={labelCls}>边框颜色</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={layer.border_color || '#FFFFFF'}
                onChange={(e) => onChange({ border_color: e.target.value })}
                className="w-10 h-8 rounded border border-gray-200 cursor-pointer"
              />
              <input
                value={layer.border_color || ''}
                onChange={(e) => onChange({ border_color: e.target.value })}
                className={inputCls}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const TRYON_BACKGROUNDS = [
  { id: 'none', label: '无', icon: '✨', desc: '保留原背景' },
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

  // 恢复上次选项卡提示：activeTab 持久化自上次会话，非默认页签时提示避免误以为页面异常
  const tabHintShown = useRef(false)
  useEffect(() => {
    if (tabHintShown.current) return
    tabHintShown.current = true
    if (activeTab && activeTab !== 'generate') {
      const label = TABS.find((t) => t.id === activeTab)?.label || activeTab
      toast.info(`已恢复上次的「${label}」页签，可点击上方页签切换`)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const setPrompt = (v) => setInputs((p) => ({ ...p, prompt: v ?? '' }))
  const setSelectedSize = (v) => setInputs((p) => ({ ...p, selectedSize: v }))
  const setBatchSize = (v) => setInputs((p) => ({ ...p, batchSize: v }))
  const setArtStyle = (v) => setInputs((p) => ({ ...p, artStyle: v ?? '' }))
  const setNegativePrompt = (v) => setInputs((p) => ({ ...p, negativePrompt: v ?? '' }))
  const [images, setImages] = useState([])
  // 可用模型列表（含中转站导入的模型），供图片生成切换
  const [modelOptions, setModelOptions] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [imageModelName, setImageModelName] = useState('系统配置')
  const [templates, setTemplates] = useState([])
  const [stats, setStats] = useState({ total_images: 0, total_templates: 0, api_configured: false })
  const [enhancing, setEnhancing] = useState(false) // v20：AI 润色提示词
  const [negativeHint, setNegativeHint] = useState('') // v20：自动负面词建议
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
  // 生成历史（localStorage 持久化，一键复用/删除/清空）
  const { history: genHistory, add: addGenHistory, remove: removeGenHistory, clear: clearGenHistory } =
    useToolHistory('image_factory_gen_history_v1', 30)
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
  // 保留内容：person/pose/background/composition（多选，空=自由发挥）
  const [img2imgPreserve, setImg2imgPreserve] = useState([])
  const img2imgRef = useRef(null)

  // 模板管理
  const [templateModal, setTemplateModal] = useState(false) // 'create' | 'edit' | 'upload' | null
  const [editingTemplateId, setEditingTemplateId] = useState('') // 编辑模式下的模板 id
  const [templateForm, setTemplateForm] = useState({
    name: '',
    width: 1080,
    height: 1920,
    background: '#FFFFFF',
    layers: [], // 图层对象数组（可视化编辑器维护）
    layerJson: '', // 高级模式 JSON 文本
    showJson: false, // 是否展开高级 JSON 编辑
    pricing: { mode: 'free', once: 0, day: 0, month: 0 }, // 市场定价（积分）
  })
  const [selectedLayerIdx, setSelectedLayerIdx] = useState(-1) // 可视化编辑选中的图层
  const [templateSaving, setTemplateSaving] = useState(false)
  const [deletingTemplate, setDeletingTemplate] = useState(null)
  // 模板套版：待渲染图片（多选，批量应用模板）
  const [templateImages, setTemplateImages] = useState([])
  const [showTemplatePicker, setShowTemplatePicker] = useState(false)
  // 模板市场：分类筛选
  const [templateCategoryFilter, setTemplateCategoryFilter] = useState('全部')
  // Excel 批量套版（对标跨境卖家批量出图工具）：上传表格 + 字段映射 → 逐行生成
  const [batchOpen, setBatchOpen] = useState(false)
  const [batchFile, setBatchFile] = useState(null) // File
  const [batchColumns, setBatchColumns] = useState([]) // 表头列名
  const [batchFieldMap, setBatchFieldMap] = useState({}) // {列名: 图层key}
  const [batchName, setBatchName] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchResult, setBatchResult] = useState(null) // {count, images, zip}
  const [batchTask, setBatchTask] = useState(null)
  const batchFileRef = useRef(null)
  // 一键发布（商业化）：图片成品 → 公众号/抖音/快手账号
  const [pubOpen, setPubOpen] = useState(false)
  const [pubTarget, setPubTarget] = useState(null) // 待发布的图片
  const [pubPlatform, setPubPlatform] = useState('wechat')
  const [pubTitle, setPubTitle] = useState('')
  const [pubContent, setPubContent] = useState('')
  const [pubBusy, setPubBusy] = useState(false)
  // 模板编辑：背景模式（纯色/渐变/图片）
  const [bgMode, setBgMode] = useState('solid')
  const [bgGradientFrom, setBgGradientFrom] = useState('#FFFFFF')
  const [bgGradientTo, setBgGradientTo] = useState('#E5E7EB')
  const [showTemplateBgPicker, setShowTemplateBgPicker] = useState(false)
  // 画布拖拽状态（pointer 事件）
  const dragRef = useRef(null)

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
  const [tryOnBackground, setTryOnBackground] = useState('none')
  const [tryOnDescription, setTryOnDescription] = useState('')
  const [tryOnKeepIdentity, setTryOnKeepIdentity] = useState(true)
  const [tryOnGenerating, setTryOnGenerating] = useState(false)
  const [tryOnResult, setTryOnResult] = useState(null)
  const [showImagePicker, setShowImagePicker] = useState(null)

  // 3D 旋转（CSS 快速预览）
  const [rotationY, setRotationY] = useState(0)
  const [rotationX, setRotationX] = useState(0)
  const [isAutoRotate, setIsAutoRotate] = useState(false)
  const [rotationSpeed, setRotationSpeed] = useState(1)
  // 3D 转盘视频（AI 生成人物原地旋转）
  const [turntableBusy, setTurntableBusy] = useState(false)
  const [turntableVideo, setTurntableVideo] = useState(null)
  const [turntableDuration, setTurntableDuration] = useState(5)

  const loadModels = useCallback(async () => {
    try {
      const res = await api.get('/api/config')
      const models = Array.isArray(res.data.models) ? res.data.models : []
      setModelOptions(models)
      setSelectedModel(res.data.image_model || '')
      setImageModelName(res.data.image_model || '系统配置')
    } catch { /* 静默 */ }
  }, [])

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
      // 支持 /image-factory?template=xxx 直达指定模板（模板市场「去使用」跳转）
      const fromUrl = new URLSearchParams(window.location.search).get('template')
      setSelectedTemplate((cur) => {
        if (fromUrl && res.data.some((t) => t.id === fromUrl)) return fromUrl
        if (cur && res.data.some((t) => t.id === cur)) return cur
        return res.data.length > 0 ? res.data[0].id : ''
      })
    } catch {
      /* 静默 */
    }
  }, [])

  useEffect(() => {
    fetchStats()
    fetchImages()
    loadModels()
    fetchTemplates()
  }, [fetchStats, fetchImages, fetchTemplates])

  // 3D 自动旋转
  useEffect(() => {
    if (!isAutoRotate) return
    const id = setInterval(() => setRotationY((p) => (p + rotationSpeed) % 360), 50)
    return () => clearInterval(id)
  }, [isAutoRotate, rotationSpeed])

  const applyTemplate = (tmpl) => setPrompt(tmpl.prompt)
  // 我的提示词收藏（localStorage 持久化，个性化创作）
  const [myPrompts, setMyPrompts] = useState(() => {
    try { return JSON.parse(localStorage.getItem('image_factory_my_prompts') || '[]') } catch { return [] }
  })
  const saveMyPrompt = () => {
    if (!prompt.trim()) { toast.error('请先输入提示词'); return }
    setMyPrompts((prev) => {
      if (prev.includes(prompt.trim())) { toast.info('该提示词已在收藏中'); return prev }
      const next = [prompt.trim(), ...prev].slice(0, 20)
      localStorage.setItem('image_factory_my_prompts', JSON.stringify(next))
      toast.success('已收藏该提示词')
      return next
    })
  }
  const removeMyPrompt = (p) => {
    setMyPrompts((prev) => {
      const next = prev.filter((x) => x !== p)
      localStorage.setItem('image_factory_my_prompts', JSON.stringify(next))
      return next
    })
  }

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

  // v20：AI 润色提示词（调用专用接口，失败静默回退原描述；附带自动负面词建议）
  const handleEnhancePrompt = async () => {
    if (!prompt.trim()) {
      toast.error('请先输入描述，再使用 AI 润色')
      return
    }
    if (enhancing) return
    setEnhancing(true)
    try {
      const fd = new FormData()
      fd.append('prompt', prompt)
      const res = await api.post('/api/image-factory/enhance-prompt', fd)
      const d = res.data || {}
      if (d.enhanced) setPrompt(d.enhanced)
      if (d.negative_auto) setNegativeHint(d.negative_auto)
      toast.success('已 AI 润色，可直接生成')
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'AI 润色失败')
    } finally {
      setEnhancing(false)
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
    if (selectedModel) form.append('model', selectedModel)
    if (negativePrompt.trim()) form.append('negative', negativePrompt.trim())
    await submitTask('/api/image-factory/generate/text-to-image', form, {
      onUpdate: (t) => setGenTask(t),
      onSuccess: (data) => {
        const success = (data.results || []).filter((r) => !r.error)
        const errors = (data.results || []).filter((r) => r.error)
        setGeneratedImages(
          success.map((r) => ({ ...r, url: absUrl(r.url), prompt: r.prompt || prompt }))
        )
        if (success.length > 0) {
          success.forEach((r) =>
            addGenHistory({
              type: '文生图',
              prompt: r.prompt || prompt,
              style: artStyle || '自由',
              size: selectedSize,
              url: r.url,
            })
          )
        }
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
        images: templateImages.map((im) => im.url),
      },
      {
        onUpdate: (t) => setGenTask(t),
        onSuccess: (data) => {
          const list =
            data.images && data.images.length > 0
              ? data.images
              : data.url
                ? [data]
                : []
          if (list.length > 0) {
            setGeneratedImages(list.map((it) => ({ ...it, url: absUrl(it.url), prompt: '模板渲染' })))
            toast.success(`模板渲染完成，共 ${list.length} 张`)
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

  // ── Excel 批量套版（商业化：对标跨境卖家批量出图工具）──
  // 智能匹配：列名与图层 key 规范化后相同/包含则自动映射
  const autoMapColumns = (cols, tmpl) => {
    const map = {}
    const norm = (s) => String(s || '').toLowerCase().replace(/[\s_\-（）()]/g, '')
    ;(tmpl?.layers || [])
      .filter((l) => l.key)
      .forEach((l) => {
        const hit = cols.find((c) => norm(c) === norm(l.key) || norm(c).includes(norm(l.key)))
        if (hit && !Object.values(map).includes(l.key)) map[hit] = l.key
      })
    return map
  }

  const openBatchModal = () => {
    if (!selectedTemplate) {
      toast.error('请先选择模板')
      return
    }
    setBatchOpen(true)
    setBatchFile(null)
    setBatchColumns([])
    setBatchFieldMap({})
    setBatchName('')
    setBatchResult(null)
    setBatchTask(null)
  }

  const handleBatchFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!/\.(xlsx|xls|csv)$/i.test(file.name)) {
      toast.error('请上传 .xlsx / .csv 文件')
      return
    }
    setBatchFile(file)
    setBatchColumns([])
    setBatchFieldMap({})
    setBatchResult(null)
    setBatchTask(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await api.post('/api/image-store/columns', form)
      const cols = res.data.columns || []
      setBatchColumns(cols)
      const tmpl = templates.find((t) => t.id === selectedTemplate)
      setBatchFieldMap(autoMapColumns(cols, tmpl))
      toast.success(`已解析 ${cols.length} 列字段`)
    } catch (err) {
      toast.error(`解析失败：${err.message}`)
    } finally {
      e.target.value = ''
    }
  }

  const handleBatchStart = async () => {
    if (!batchFile) {
      toast.error('请先上传 Excel/CSV 表格')
      return
    }
    if (Object.values(batchFieldMap).filter(Boolean).length === 0) {
      toast.error('请至少映射一个字段')
      return
    }
    setBatchBusy(true)
    setBatchResult(null)
    setBatchTask({ progress: 0, stage: '任务排队中…', status: 'pending' })
    const form = new FormData()
    form.append('template_id', selectedTemplate)
    form.append('file', batchFile)
    form.append('field_map', JSON.stringify(batchFieldMap))
    if (batchName.trim()) form.append('batch_name', batchName.trim())
    await submitTask(
      '/api/image-store/batch',
      form,
      {
        onUpdate: (t) => setBatchTask(t),
        onSuccess: (data) => {
          setBatchResult(data)
          setBatchTask({ progress: 100, stage: '批量生成完成', status: 'success' })
          toast.success(`批量生成完成，共 ${data.count} 张，可下载 zip 压缩包`)
          fetchImages()
          setBatchBusy(false)
        },
        onError: (e) => {
          setBatchBusy(false)
          setBatchTask(null)
          toast.error(`批量生成失败：${e.message}`)
        },
      }
    )
  }

  // ── 一键发布（商业化）：图片成品 → 公众号/抖音/快手账号 ──
  const openPublish = (img) => {
    setPubTarget(img)
    setPubPlatform('wechat')
    setPubTitle(img.prompt ? `AI 图片作品：${img.prompt.slice(0, 18)}` : 'AI 图片作品')
    setPubContent(
      `# AI 图片作品\n\n${img.prompt ? `提示词：${img.prompt}\n\n` : ''}由小团智能平台 AI 图片工厂生成 · ${new Date().toLocaleString()}`
    )
    setPubOpen(true)
  }

  const handlePublish = async () => {
    if (!pubTarget) return
    if (!pubTitle.trim()) {
      toast.error('请输入标题')
      return
    }
    setPubBusy(true)
    try {
      const res = await api.post('/api/publish/submit', {
        platform: pubPlatform,
        content_type: 'image',
        title: pubTitle.trim(),
        content: pubContent.trim(),
        asset_urls: [pubTarget.url.replace(MEDIA_BASE, '')],
      })
      setPubOpen(false)
      const auto = res.data.mode === 'auto'
      toast.success(auto ? '发布成功！内容已自动投递到平台账号' : '素材包已生成，请按发布指引完成发布')
    } catch (e) {
      toast.error(`发布失败：${e.message}`)
    } finally {
      setPubBusy(false)
    }
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
    if (img2imgPreserve.length > 0) form.append('preserve', img2imgPreserve.join(','))
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
  // 新图层默认值（可视化编辑器）
  const LAYER_DEFAULTS = {
    text: { type: 'text', text: '文字内容', key: '', x: 50, y: 100, font_size: 28, color: '#000000', align: 'left', max_width: 0, shadow: '', shadow_color: '#00000080', family: '', bold: false, italic: false, letter_spacing: 0, line_height: 1.35, stroke_width: 0, stroke_color: '#000000', rotation: 0 },
    rect: { type: 'rect', x: 50, y: 50, width: 300, height: 80, radius: 16, fill: '#F3F4F6', opacity: 1, rotation: 0, border_width: 0, border_color: '#FFFFFF' },
    circle: { type: 'circle', x: 200, y: 200, radius: 80, fill: '#F3F4F6', opacity: 1, rotation: 0, border_width: 0, border_color: '#FFFFFF' },
    line: { type: 'line', x: 100, y: 200, length: 300, angle: 0, color: '#DDDDDD', width: 2, opacity: 1 },
    image: { type: 'image', key: '', x: 0, y: 0, width: 300, height: 300, url: '', slot: '', fit: 'cover', radius: 0, opacity: 1, rotation: 0, border_width: 0, border_color: '#FFFFFF' },
  }

  // 复制图层（插入到当前图层之后）
  const duplicateTemplateLayer = (idx) => {
    setTemplateForm((f) => {
      const src = f.layers[idx]
      if (!src) return f
      const copy = { ...src, x: (src.x || 0) + 20, y: (src.y || 0) + 20 }
      const layers = [...f.layers]
      layers.splice(idx + 1, 0, copy)
      return { ...f, layers }
    })
    setSelectedLayerIdx(idx + 1)
  }

  const addTemplateLayer = (type) => {
    setTemplateForm((f) => ({ ...f, layers: [...f.layers, { ...LAYER_DEFAULTS[type] }] }))
    setSelectedLayerIdx(templateForm.layers.length)
  }

  const updateTemplateLayer = (idx, patch) => {
    setTemplateForm((f) => ({
      ...f,
      layers: f.layers.map((l, i) => (i === idx ? { ...l, ...patch } : l)),
    }))
  }

  const removeTemplateLayer = (idx) => {
    setTemplateForm((f) => ({ ...f, layers: f.layers.filter((_, i) => i !== idx) }))
    setSelectedLayerIdx(-1)
  }

  const moveTemplateLayer = (idx, dir) => {
    setTemplateForm((f) => {
      const target = idx + dir
      if (target < 0 || target >= f.layers.length) return f
      const layers = [...f.layers]
      ;[layers[idx], layers[target]] = [layers[target], layers[idx]]
      return { ...f, layers }
    })
    setSelectedLayerIdx(idx + dir)
  }

  // 打开新建模板弹窗
  const openCreateTemplate = () => {
    setEditingTemplateId('')
    setSelectedLayerIdx(-1)
    setBgMode('solid')
    setBgGradientFrom('#FFFFFF')
    setBgGradientTo('#E5E7EB')
    setTemplateForm({
      name: '',
      width: 1080,
      height: 1920,
      background: '#FFFFFF',
      background_image: '',
      background_darken: 0,
      category: '通用',
      layers: [],
      layerJson: '',
      showJson: false,
      pricing: { mode: 'free', once: 0, day: 0, month: 0 },
    })
    setTemplateModal('create')
  }

  // 打开编辑模板弹窗（载入已有模板）
  const handleEditTemplate = (t) => {
    setEditingTemplateId(t.id)
    setSelectedLayerIdx(-1)
    const bg = t.background || '#FFFFFF'
    // 背景模式推断：图片 > 渐变 > 纯色
    if (t.background_image) setBgMode('image')
    else if (String(bg).includes('→')) setBgMode('gradient')
    else setBgMode('solid')
    setBgGradientFrom(String(bg).includes('→') ? bg.split('→')[0].trim() : bg)
    setBgGradientTo(String(bg).includes('→') ? bg.split('→')[1].trim() : '#E5E7EB')
    setTemplateForm({
      name: t.name,
      width: t.width,
      height: t.height,
      background: bg,
      background_image: t.background_image || '',
      background_darken: t.background_darken || 0,
      category: t.category || '通用',
      layers: Array.isArray(t.layers) ? t.layers.map((l) => ({ ...l })) : [],
      layerJson: JSON.stringify(Array.isArray(t.layers) ? t.layers : [], null, 2),
      showJson: false,
      pricing: {
        mode: ['free', 'once', 'day', 'month'].includes(t.pricing?.mode) ? t.pricing.mode : 'free',
        once: Number(t.pricing?.once) || 0,
        day: Number(t.pricing?.day) || 0,
        month: Number(t.pricing?.month) || 0,
      },
    })
    setTemplateModal('edit')
  }

  const handleSaveTemplate = async () => {
    if (!templateForm.name.trim()) {
      toast.error('请输入模板名称')
      return
    }
    setTemplateSaving(true)
    try {
      // 高级 JSON 模式展开时：以 JSON 文本为准
      let layers = templateForm.layers
      if (templateForm.showJson && templateForm.layerJson.trim()) {
        try {
          layers = JSON.parse(templateForm.layerJson)
        } catch {
          toast.error('图层 JSON 格式错误')
          setTemplateSaving(false)
          return
        }
      }
      const body = {
        name: templateForm.name.trim(),
        width: Number(templateForm.width) || 1080,
        height: Number(templateForm.height) || 1920,
        background: templateForm.background,
        category: templateForm.category || '通用',
        background_image: templateForm.background_image || '',
        background_darken: Number(templateForm.background_darken) || 0,
        layers,
        // 市场定价：免费或按次/按天/按月（积分），同步到模板市场
        pricing: templateForm.pricing || { mode: 'free', once: 0, day: 0, month: 0 },
      }
      let res
      if (templateModal === 'edit') {
        res = await api.put(`/api/image-factory/templates/${editingTemplateId}`, body)
        toast.success(`模板「${res.data.name}」已更新`)
      } else {
        res = await api.post('/api/image-factory/template/create', body)
        toast.success(`模板「${res.data.name}」已创建`)
      }
      setTemplateModal(false)
      setEditingTemplateId('')
      setSelectedLayerIdx(-1)
      fetchTemplates()
    } catch (e) {
      toast.error(`保存失败：${e.message}`)
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
      form.append('keep_identity', String(tryOnKeepIdentity))
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

  // 3D 转盘：生成人物原地 360° 旋转视频（展示衣服全角度）
  const handleTurntable = async (srcUrl) => {
    if (!srcUrl) {
      toast.error('请先生成试穿效果')
      return
    }
    setTurntableBusy(true)
    setTurntableVideo(null)
    setGenTask({ progress: 0, stage: '提交 3D 转盘任务…', status: 'pending' })
    try {
      const resp = await fetch(srcUrl)
      const blob = await resp.blob()
      const form = new FormData()
      form.append('image', blob, 'rotate.png')
      form.append('duration', String(turntableDuration))
      await submitTask('/api/image-factory/rotate/turntable', form, {
        onUpdate: (t) => setGenTask(t),
        onSuccess: (data) => {
          if (data.url) {
            setTurntableVideo({ url: absUrl(data.url), id: data.id })
            toast.success('3D 转盘视频已生成')
          } else {
            toast.error('生成失败，请重试')
          }
          setTurntableBusy(false)
        },
        onError: (e) => {
          setTurntableBusy(false)
          toast.error(`生成失败：${e.message}`)
        },
      })
    } catch (e) {
      setTurntableBusy(false)
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
      <button
        onClick={() => openPublish(img)}
        className="p-2 bg-white rounded-full hover:bg-rose-100 hover:text-rose-600 transition-colors"
        title="一键发布到公众号/抖音/快手"
      >
        <Send className="w-4 h-4" />
      </button>
      <span onClick={(e) => e.stopPropagation()}>
        <ShareButton
          content={`# AI 图片作品\n\n提示词：${img.prompt || ''}\n\n> 由小团智能平台 AI 图片工厂生成 · ${new Date().toLocaleString()}`}
          title="AI 图片作品"
          contentType="image"
          className="!p-2 !bg-white !rounded-full"
        />
      </span>
      <span onClick={(e) => e.stopPropagation()}>
        <FavoriteButton
          favType="gallery"
          targetId={img.filename || img.url?.split('/').pop()}
          label={img.prompt?.slice(0, 40) || 'AI 图片'}
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
                    <button
                      onClick={handleEnhancePrompt}
                      disabled={enhancing}
                      className="inline-flex items-center gap-1 text-violet-600 hover:text-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      title="AI 润色为专业提示词（含构图/光线/风格/负面词建议）"
                    >
                      {enhancing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                      {enhancing ? '润色中…' : '✨ AI 润色'}
                    </button>
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
                {negativeHint && !negativePrompt && (
                  <p className="mt-1.5 text-[11px] text-gray-400">
                    建议负面词：<span className="text-violet-500">{negativeHint}</span>
                    <button
                      onClick={() => setNegativePrompt(negativeHint)}
                      className="ml-2 text-violet-600 hover:text-violet-700 underline"
                    >
                      一键填入
                    </button>
                  </p>
                )}
              </div>

              {modelOptions.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">生成模型</label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
                  >
                    <option value="">默认（{imageModelName || '系统配置'}）</option>
                    {modelOptions.map((m) => (
                      <option key={m.name} value={m.name}>
                        {m.name}
                        {m.base_url ? '（中转站）' : ''}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-[11px] text-gray-400">
                    可切换已接入的中转站图片模型；留空使用系统配置
                  </p>
                </div>
              )}

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">艺术风格</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 sm:grid-cols-5 gap-1.5">
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
                <div className="grid grid-cols-2 sm:grid-cols-2 sm:grid-cols-3 gap-2">
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
              {genHistory.length > 0 && (
                <div className="mt-3">
                  <HistoryPanel
                    history={genHistory}
                    onReuse={(item) => {
                      setPrompt(item.prompt)
                      if (item.style && item.style !== '自由') {
                        const found = ART_STYLES.find((s) => s.label === item.style)
                        if (found) setArtStyle(found.id)
                      }
                      toast.info('已恢复提示词，可重新生成')
                    }}
                    onRemove={removeGenHistory}
                    onClear={clearGenHistory}
                    title="生成历史"
                    renderSummary={(item) => (
                      <div className="flex items-center gap-2">
                        <span className="text-gray-700">{item.prompt?.slice(0, 40) || '未命名'}</span>
                        <span className="text-gray-400">{item.style}</span>
                      </div>
                    )}
                  />
                </div>
              )}
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

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-gray-500">我的提示词收藏</p>
                  <button
                    onClick={saveMyPrompt}
                    className="text-[11px] text-violet-500 hover:text-violet-700"
                  >
                    ★ 收藏当前提示词
                  </button>
                </div>
                {myPrompts.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {myPrompts.map((p, i) => (
                      <span key={i} className="group inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs border border-violet-200 bg-violet-50/50 text-violet-700">
                        <button onClick={() => setPrompt(p)} className="max-w-40 truncate hover:text-violet-900" title={p}>
                          {p.slice(0, 24)}{p.length > 24 ? '…' : ''}
                        </button>
                        <button onClick={() => removeMyPrompt(p)} className="text-violet-300 hover:text-red-500" title="删除收藏">×</button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-gray-400">还没有收藏，点击「收藏当前提示词」保存常用创作模板</p>
                )}
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
                // v24：单张图单列大图、多张两列；去掉 aspect-square 硬约束，图片按自身比例完整放大，无需点详情即可看全
                <div className={generatedImages.length === 1 ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-2 gap-4'}>
                  {generatedImages.map((img, idx) => (
                    <div key={idx} className="relative group rounded-xl overflow-hidden shadow-sm bg-gray-50">
                      <img
                        src={img.url}
                        alt={img.prompt}
                        className={`w-full object-contain transition-transform duration-300 group-hover:scale-[1.03] ${
                          generatedImages.length === 1 ? 'max-h-[70vh]' : 'max-h-[46vh]'
                        }`}
                      />
                      <div className="absolute top-2 left-2 z-10">
                        <ImageQualityBadge filename={img.filename} />
                      </div>
                      {generatedImages.length > 1 && (
                        <span className="absolute top-2 left-2 px-1.5 py-0.5 rounded-md bg-black/50 text-white text-[10px] font-medium">
                          {idx + 1}/{generatedImages.length}
                        </span>
                      )}
                      <button
                        onClick={() => setPreviewImage(img)}
                        className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center"
                        aria-label={`放大查看第 ${idx + 1} 张`}
                      >
                        <span className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/90 text-xs font-medium text-gray-800 shadow">
                          <ZoomIn className="w-3.5 h-3.5" /> 放大查看
                        </span>
                      </button>
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
                    <img src={img2imgPreview} alt="参考图" className="w-full max-h-80 object-contain bg-gray-50" />
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
                  placeholder="描述想要的风格/元素变化，如：把照片变成油画风格…"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm resize-none"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  保留内容 <span className="text-gray-400 font-normal">（可多选，不选 = 自由发挥）</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'person', label: '👤 人物不变', desc: '换背景/加元素' },
                    { id: 'pose', label: '🧍 姿态不变', desc: '保持姿势' },
                    { id: 'background', label: '🏞️ 背景不变', desc: '只改人物/加元素' },
                    { id: 'composition', label: '🎨 构图不变', desc: '保持布局/色彩' },
                  ].map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() =>
                        setImg2imgPreserve((prev) =>
                          prev.includes(p.id) ? prev.filter((x) => x !== p.id) : [...prev, p.id]
                        )
                      }
                      className={`px-3 py-2 rounded-xl border text-left transition-all ${img2imgPreserve.includes(p.id) ? 'border-violet-500 bg-violet-50 shadow-sm' : 'border-gray-200 hover:border-violet-300 hover:bg-gray-50'}`}
                      title={p.desc}
                    >
                      <div className="text-xs font-medium text-gray-800">{p.label}</div>
                      <div className="text-[10px] text-gray-400 mt-0.5">{p.desc}</div>
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-gray-400 mt-1.5">
                  {img2imgPreserve.length === 0
                    ? '不勾选时 AI 自由创作，适合换风格/换背景' 
                    : '已锁定「' + img2imgPreserve.map((x) => ({person: '人物', pose: '姿态', background: '背景', composition: '构图'})[x]).join('、') + '」不变，AI 只做其他调整'}
                </p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">尺寸</label>
                <div className="grid grid-cols-2 sm:grid-cols-2 sm:grid-cols-3 gap-2">
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
                <div className="relative group rounded-xl overflow-hidden shadow-sm bg-gray-50">
                  <img
                    src={generatedImages[0].url}
                    alt={img2imgPrompt}
                    className="w-full max-h-[70vh] object-contain transition-transform duration-300 group-hover:scale-[1.03]"
                  />
                  <button
                    onClick={() => setPreviewImage(generatedImages[0])}
                    className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center"
                    aria-label="放大查看结果"
                  >
                    <span className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/90 text-xs font-medium text-gray-800 shadow">
                      <ZoomIn className="w-3.5 h-3.5" /> 放大查看
                    </span>
                  </button>
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
                      onClick={openBatchModal}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-600 border border-emerald-200 hover:bg-emerald-100 transition-all"
                      title="上传 Excel/CSV，按行套版批量生成图片（如商品主图、报价海报）"
                    >
                      <FileSpreadsheet className="w-3 h-3" /> Excel 批量
                    </button>
                    <button
                      onClick={openCreateTemplate}
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
                  <>
                    {/* 分类筛选 */}
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {['全部', ...TEMPLATE_CATEGORIES].map((c) => (
                        <button
                          key={c}
                          onClick={() => setTemplateCategoryFilter(c)}
                          className={`px-2.5 py-1 rounded-full text-xs border transition-all ${
                            templateCategoryFilter === c
                              ? 'border-violet-500 bg-violet-50 text-violet-700 font-medium'
                              : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                          }`}
                        >
                          {c}
                        </button>
                      ))}
                    </div>
                    {/* 卡片网格：封面图 + 名称 + 尺寸 + 分类 */}
                    <div className="grid grid-cols-2 gap-3 max-h-[420px] overflow-y-auto pr-1">
                      {templates
                        .filter(
                          (t) =>
                            templateCategoryFilter === '全部' ||
                            (t.category || '通用') === templateCategoryFilter
                        )
                        .map((t) => (
                          <div
                            key={t.id}
                            onClick={() => setSelectedTemplate(t.id)}
                            className={`group relative rounded-xl border overflow-hidden cursor-pointer transition-all ${
                              selectedTemplate === t.id
                                ? 'border-violet-500 ring-2 ring-violet-200'
                                : 'border-gray-200 hover:border-violet-300 hover:shadow-sm'
                            }`}
                          >
                            <div className="relative aspect-[3/4] bg-gray-100 overflow-hidden">
                              {t.preview ? (
                                <img
                                  src={absUrl(t.preview)}
                                  alt={t.name}
                                  loading="lazy"
                                  className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.04]"
                                />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center">
                                  <LayoutTemplate className="w-8 h-8 text-gray-300" />
                                </div>
                              )}
                              {selectedTemplate === t.id && (
                                <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-violet-500 text-white flex items-center justify-center shadow">
                                  <Check className="w-3 h-3" />
                                </div>
                              )}
                              {/* hover 操作：编辑/删除 */}
                              <div className="absolute bottom-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <span
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleEditTemplate(t)
                                  }}
                                  className="p-1.5 rounded-lg bg-black/60 text-white hover:bg-violet-500 transition-colors"
                                  title="编辑模板"
                                >
                                  <Pencil className="w-3 h-3" />
                                </span>
                                <span
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setDeletingTemplate(t.id)
                                  }}
                                  className="p-1.5 rounded-lg bg-black/60 text-white hover:bg-red-500 transition-colors"
                                  title="删除模板"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </span>
                              </div>
                            </div>
                            <div className="p-2">
                              <div className="text-xs font-medium text-gray-900 truncate">{t.name}</div>
                              <div className="flex items-center justify-between mt-1">
                                <span className="text-[10px] text-gray-400">
                                  {t.width}×{t.height}
                                </span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-50 text-violet-600">
                                  {t.category || '通用'}
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  </>
                )}
              </div>

              {/* 套版图片选择：多选图片后应用模板批量渲染（如大促商品图套版） */}
              <div className="rounded-xl border border-gray-200 p-3">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-gray-700">
                    套版图片{templateImages.length > 0 && `（已选 ${templateImages.length} 张）`}
                  </label>
                  <button
                    onClick={() => setShowTemplatePicker(true)}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-all"
                  >
                    <Image className="w-3 h-3" /> 从图库选择
                  </button>
                </div>
                {templateImages.length === 0 ? (
                  <p className="text-[11px] leading-relaxed text-gray-400">
                    选择图片后应用模板渲染，每张图生成一张成品（适合批量套版）。未选择时按模板默认内容生成。
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {templateImages.map((im) => (
                      <div key={im.filename} className="relative">
                        <img
                          src={absUrl(im.url)}
                          alt={im.filename}
                          className="w-14 h-14 rounded-lg object-cover border border-gray-200"
                        />
                        <button
                          onClick={() =>
                            setTemplateImages((p) => p.filter((x) => x.filename !== im.filename))
                          }
                          className="absolute -top-1.5 -right-1.5 p-0.5 rounded-full bg-red-500 text-white shadow hover:bg-red-600 transition-colors"
                          title="移除"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
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
                {rendering
                  ? '渲染任务执行中（后台）…'
                  : templateImages.length > 0
                    ? `应用模板生成（${templateImages.length} 张）`
                    : '生成图片'}
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
              <h3 className="font-medium text-gray-900 mb-4">
                预览{generatedImages.length > 1 && `（共 ${generatedImages.length} 张）`}
              </h3>
              {rendering ? (
                <div className="h-64 rounded-xl bg-gray-100 animate-pulse" />
              ) : generatedImages.length > 0 ? (
                <div
                  className={`grid gap-4 ${
                    generatedImages.length > 1 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1'
                  }`}
                >
                  {generatedImages.map((img, i) => (
                    <div key={`${img.filename || img.url}-${i}`} className="relative group rounded-xl overflow-hidden shadow-sm bg-gray-50">
                      <img
                        src={img.url}
                        alt="模板结果"
                        className={`w-full object-contain transition-transform duration-300 group-hover:scale-[1.03] ${
                          generatedImages.length > 1 ? 'max-h-[46vh]' : 'max-h-[70vh]'
                        }`}
                      />
                      <div className="absolute top-2 left-2 px-2 py-0.5 rounded-full bg-black/50 text-white text-xs">
                        {i + 1}/{generatedImages.length}
                      </div>
                      <button
                        onClick={() => setPreviewImage(img)}
                        className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center"
                        aria-label={`放大查看第 ${i + 1} 张`}
                      >
                        <span className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/90 text-xs font-medium text-gray-800 shadow">
                          <ZoomIn className="w-3.5 h-3.5" /> 放大查看
                        </span>
                      </button>
                      {renderImageActions(img)}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-64">
                  <Empty icon={LayoutTemplate} title="暂无预览" description="选择模板（可搭配图片）并点击生成" />
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
                        className="w-full max-h-72 object-contain rounded-lg"
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
                        className="w-full max-h-72 object-contain rounded-lg"
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

              <div className="flex items-center justify-between rounded-xl border border-gray-200 px-4 py-3 bg-gray-50/50">
                <div>
                  <div className="text-sm font-medium text-gray-800">人物保持</div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {tryOnKeepIdentity ? '严格锁定你的脸和身材不变，只换衣服' : '允许调整姿势/风格，效果更自然'}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setTryOnKeepIdentity(!tryOnKeepIdentity)}
                  className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${tryOnKeepIdentity ? 'bg-violet-500' : 'bg-gray-300'}`}
                >
                  <span
                    className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${tryOnKeepIdentity ? 'left-[22px]' : 'left-0.5'}`}
                  />
                </button>
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
                <div className="grid grid-cols-2 sm:grid-cols-2 sm:grid-cols-3 gap-2">
                  {TRYON_BACKGROUNDS.map((bg) => (
                    <button
                      key={bg.id}
                      onClick={() => setTryOnBackground(bg.id)}
                      className={`p-3 rounded-lg border text-center transition-all ${tryOnBackground === bg.id ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-gray-200 hover:bg-gray-50'}`}
                    >
                      <div className="text-2xl mb-1">{bg.icon}</div>
                      <div className="text-xs font-medium">{bg.label}</div>
                      {bg.desc && <div className="text-[10px] text-gray-400 mt-0.5">{bg.desc}</div>}
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
                <div className="rounded-xl overflow-hidden border border-gray-200 bg-gray-50">
                  <img src={tryOnResult.url} alt="试穿效果" className="w-full max-h-[70vh] object-contain" />
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
              {/* AI 3D 转盘：生成人物原地旋转视频（真 360° 看衣服） */}
              <div className="mb-5 rounded-xl border border-violet-200 bg-white p-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center">
                      <Rotate3d className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">AI 3D 转盘视频</h3>
                      <p className="text-xs text-gray-400 mt-0.5">让照片中的人物原地 360° 旋转，从前到后看穿上的衣服效果</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={turntableDuration}
                      onChange={(e) => setTurntableDuration(Number(e.target.value))}
                      className="px-2 py-1.5 rounded-lg border border-gray-200 text-xs bg-white"
                    >
                      <option value={5}>5秒</option>
                      <option value={10}>10秒</option>
                    </select>
                    <button
                      onClick={() => handleTurntable(tryOnResult.url)}
                      disabled={turntableBusy}
                      className={`px-4 py-2 rounded-lg text-sm font-medium text-white transition-all flex items-center gap-1.5 ${turntableBusy ? 'bg-violet-300 cursor-not-allowed' : 'bg-gradient-to-r from-violet-500 to-fuchsia-600 hover:opacity-90'}`}
                    >
                      {turntableBusy ? (
                        <><Loader2 className="w-4 h-4 animate-spin" /> 生成中…</>
                      ) : (
                        <><Rotate3d className="w-4 h-4" /> 生成 360° 转盘</>
                      )}
                    </button>
                  </div>
                </div>
                {turntableBusy && genTask && (
                  <div className="mt-3 rounded-lg bg-violet-50 border border-violet-100 px-3 py-2">
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
                    <p className="mt-1 text-[11px] text-gray-400">云端生成约 1-5 分钟，可稍后在「任务中心」查看</p>
                  </div>
                )}
                {turntableVideo && !turntableBusy && (
                  <div className="mt-4">
                    <video
                      src={turntableVideo.url}
                      controls
                      autoPlay
                      loop
                      muted
                      playsInline
                      className="w-full max-h-[55vh] rounded-xl bg-black object-contain"
                    />
                    <div className="flex items-center justify-between mt-2">
                      <p className="text-xs text-gray-500">🎉 人物已旋转 360°，可全屏查看衣服每个角度</p>
                      <button
                        onClick={() => {
                          const a = document.createElement('a')
                          a.href = turntableVideo.url
                          a.download = `turntable_${turntableVideo.id || '360'}.mp4`
                          a.click()
                        }}
                        className="text-xs text-violet-600 hover:text-violet-700 flex items-center gap-1"
                      >
                        <Download className="w-3.5 h-3.5" /> 下载视频
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* CSS 快速预览（平面 3D 翻转，非真实人物旋转） */}
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-gray-900">快速预览（平面翻转）</h3>
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
          ) : (
            <Pagination
              items={filteredImages}
              pageSize={12}
              label={searchQuery ? `找到 ${filteredImages.length} 张图片` : `共 ${filteredImages.length} 张图片`}
              renderItem={(img) =>
                viewMode === 'grid' ? (
                  <div className="group relative rounded-xl overflow-hidden shadow-sm">
                    <img
                      src={absUrl(img.thumb_url || img.url)}
                      alt={img.title || img.filename}
                      className="w-full h-40 object-cover"
                      loading="lazy"
                    />
                    <div className="absolute top-1.5 left-1.5 z-10">
                      <ImageQualityBadge filename={img.filename} />
                    </div>
                    {renderImageActions({ ...img, url: absUrl(img.url) })}
                    <div className="absolute bottom-0 left-0 right-0 px-2 py-1 text-xs text-white truncate bg-black/50">
                      {img.title || img.filename}
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-4 p-3 rounded-lg hover:bg-gray-50 transition-colors">
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
                )
              }
            />
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
        size="xl"
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
          <div className="space-y-3">
            <div className="bg-gray-50 rounded-xl flex items-center justify-center overflow-hidden max-h-[78vh]">
              <img
                src={previewImage.url}
                alt={previewImage.filename}
                className="max-w-full max-h-[78vh] object-contain"
              />
            </div>
            {/* v18-B：灯箱元信息（prompt/尺寸/时间），让每张图可追溯 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
              <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                <div className="text-gray-400 mb-0.5">提示词</div>
                <div className="text-gray-700 line-clamp-2">{previewImage.prompt || '-'}</div>
              </div>
              <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                <div className="text-gray-400 mb-0.5">尺寸</div>
                <div className="text-gray-700">
                  {previewImage.meta?.size || previewImage.size || '-'}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                <div className="text-gray-400 mb-0.5">创建时间</div>
                <div className="text-gray-700">
                  {previewImage.created_at
                    ? String(previewImage.created_at).slice(0, 16).replace('T', ' ')
                    : '-'}
                </div>
              </div>
            </div>
          </div>
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
                    className="w-full h-32 object-contain bg-gray-50"
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
      {/* 模板管理弹窗（可视化图层编辑器） */}
      <Modal
        open={templateModal === 'create' || templateModal === 'edit'}
        onClose={() => setTemplateModal(false)}
        title={templateModal === 'edit' ? '编辑模板' : '新建模板'}
        size="2xl"
      >
        <div className="space-y-5">
          {/* 基础信息 */}
          <div className="grid grid-cols-1 sm:grid-cols-6 gap-3">
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1.5">模板名称 *</label>
              <input
                value={templateForm.name}
                onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                placeholder="如：大促打折海报"
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">分类</label>
              <select
                value={templateForm.category || '通用'}
                onChange={(e) => setTemplateForm({ ...templateForm, category: e.target.value })}
                className="w-full px-3 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm bg-white"
              >
                {TEMPLATE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
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
            <div className="flex items-end">
              <div className="flex gap-1.5 flex-wrap">
                {[
                  ['1080×1920', '竖屏海报'],
                  ['1080×1440', '电商主图'],
                  ['800×800', '方形贴纸'],
                  ['1200×628', '横幅 Banner'],
                ].map(([size, label]) => (
                  <button
                    key={size}
                    onClick={() => {
                      const [w, h] = size.split('×')
                      setTemplateForm({ ...templateForm, width: w, height: h })
                    }}
                    className="px-2 py-1 rounded-lg text-[11px] border border-gray-200 text-gray-500 hover:border-violet-400 hover:text-violet-600 transition-all"
                    title={label}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {/* 市场定价（商业化）：免费或按次/按天/按月，保存后同步到模板市场 */}
          <div className="rounded-xl border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-gray-700">市场定价（积分）</label>
              <span className="text-[11px] text-gray-400">
                收费模板将在模板市场展示价格，用户购买/订阅后才能使用
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                ['free', '免费', '所有人可用'],
                ['once', '按次·永久', '购买后永久可用'],
                ['day', '按天订阅', '1 天有效期'],
                ['month', '按月订阅', '30 天有效期'],
              ].map(([id, label, tip]) => (
                <label
                  key={id}
                  className={`flex items-start gap-2 px-3 py-2 rounded-xl border cursor-pointer transition-all ${
                    templateForm.pricing?.mode === id
                      ? 'border-violet-500 bg-violet-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="radio"
                    checked={templateForm.pricing?.mode === id}
                    onChange={() =>
                      setTemplateForm({
                        ...templateForm,
                        pricing: { ...(templateForm.pricing || {}), mode: id },
                      })
                    }
                    className="mt-0.5"
                  />
                  <span>
                    <span className="block text-xs font-medium text-gray-800">{label}</span>
                    <span className="block text-[10px] text-gray-400">{tip}</span>
                  </span>
                </label>
              ))}
            </div>
            {templateForm.pricing?.mode !== 'free' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 sm:grid-cols-3 gap-3 mt-3">
                {[
                  ['once', '按次价格'],
                  ['day', '按天价格'],
                  ['month', '按月价格'],
                ].map(([key, label]) => (
                  <div key={key}>
                    <label className="block text-xs text-gray-500 mb-1">{label}（积分）</label>
                    <input
                      type="number"
                      min="0"
                      value={templateForm.pricing?.[key] || 0}
                      onChange={(e) =>
                        setTemplateForm({
                          ...templateForm,
                          pricing: {
                            ...(templateForm.pricing || {}),
                            [key]: Math.max(0, Number(e.target.value) || 0),
                          },
                        })
                      }
                      className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* 主体三栏：左=背景+图层 / 中=画布实时预览 / 右=图层属性（编辑与预览同屏） */}
          <div className="grid grid-cols-1 lg:grid-cols-[250px_1fr_300px] gap-5">
            {/* 左栏：背景设置 */}
            <div className="space-y-5">
          {/* 背景：纯色 / 渐变 / 图片 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">背景</label>
            <div className="flex gap-1.5 mb-2.5">
              {[
                ['solid', '纯色'],
                ['gradient', '渐变'],
                ['image', '图片'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => {
                    setBgMode(id)
                    if (id === 'solid') {
                      setTemplateForm((f) => ({ ...f, background: bgGradientFrom }))
                    } else if (id === 'gradient') {
                      setTemplateForm((f) => ({ ...f, background: `${bgGradientFrom}→${bgGradientTo}` }))
                    }
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    bgMode === id
                      ? 'border-violet-500 bg-violet-50 text-violet-700'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {bgMode === 'solid' && (
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={String(templateForm.background || '#FFFFFF').split('→')[0]}
                  onChange={(e) => {
                    setBgGradientFrom(e.target.value)
                    setTemplateForm({ ...templateForm, background: e.target.value })
                  }}
                  className="w-12 h-10 rounded-lg border border-gray-200 cursor-pointer"
                />
                <input
                  value={templateForm.background}
                  onChange={(e) => setTemplateForm({ ...templateForm, background: e.target.value })}
                  className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm font-mono"
                />
              </div>
            )}
            {bgMode === 'gradient' && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-gray-400">从</span>
                  <input
                    type="color"
                    value={bgGradientFrom}
                    onChange={(e) => {
                      setBgGradientFrom(e.target.value)
                      setTemplateForm((f) => ({ ...f, background: `${e.target.value}→${bgGradientTo}` }))
                    }}
                    className="w-12 h-10 rounded-lg border border-gray-200 cursor-pointer"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-gray-400">到</span>
                  <input
                    type="color"
                    value={bgGradientTo}
                    onChange={(e) => {
                      setBgGradientTo(e.target.value)
                      setTemplateForm((f) => ({ ...f, background: `${bgGradientFrom}→${e.target.value}` }))
                    }}
                    className="w-12 h-10 rounded-lg border border-gray-200 cursor-pointer"
                  />
                </div>
                <input
                  value={templateForm.background}
                  onChange={(e) => setTemplateForm({ ...templateForm, background: e.target.value })}
                  className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm font-mono"
                />
              </div>
            )}
            {bgMode === 'image' && (
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <input
                    value={templateForm.background_image}
                    onChange={(e) => setTemplateForm({ ...templateForm, background_image: e.target.value })}
                    placeholder="选择背景图（自动铺满+可暗化）"
                    readOnly
                    className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 bg-gray-50 outline-none text-sm font-mono"
                  />
                  <button
                    onClick={() => setShowTemplateBgPicker(true)}
                    className="flex items-center gap-1 px-3 py-2.5 rounded-xl text-xs font-medium bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-all"
                  >
                    <ImageIcon className="w-3.5 h-3.5" /> 从图库选择
                  </button>
                  {templateForm.background_image && (
                    <button
                      onClick={() => setTemplateForm({ ...templateForm, background_image: '' })}
                      className="p-2.5 rounded-xl text-xs text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                      title="移除背景图"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] text-gray-400 w-14">暗化 {Math.round((templateForm.background_darken || 0) * 100)}%</span>
                  <input
                    type="range"
                    min="0"
                    max="0.7"
                    step="0.05"
                    value={templateForm.background_darken || 0}
                    onChange={(e) =>
                      setTemplateForm({ ...templateForm, background_darken: parseFloat(e.target.value) })
                    }
                    className="flex-1"
                  />
                </div>
              </div>
            )}
            </div>

            {/* 左栏：图层列表 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                图层（列表越靠下，绘制时越靠上层）
              </label>
              {templateForm.layers.length === 0 ? (
                <div className="rounded-xl border-2 border-dashed border-gray-200 px-4 py-6 text-center">
                  <p className="text-sm text-gray-400 mb-3">还没有图层，点击下方按钮添加</p>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {templateForm.layers.map((layer, idx) => (
                    <div
                      key={idx}
                      onClick={() => setSelectedLayerIdx(idx)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all ${
                        selectedLayerIdx === idx
                          ? 'border-violet-500 bg-violet-50'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <span
                        className={`text-xs font-medium px-1.5 py-0.5 rounded ${layer.type === 'text' ? 'bg-blue-50 text-blue-600' : layer.type === 'rect' ? 'bg-amber-50 text-amber-600' : layer.type === 'circle' ? 'bg-rose-50 text-rose-600' : layer.type === 'line' ? 'bg-cyan-50 text-cyan-600' : 'bg-emerald-50 text-emerald-600'}`}
                      >
                        {layer.type === 'text'
                          ? '文字'
                          : layer.type === 'rect'
                            ? '矩形'
                            : layer.type === 'circle'
                              ? '圆形'
                              : layer.type === 'line'
                                ? '线条'
                                : '图片'}
                      </span>
                      <span className="flex-1 text-xs text-gray-600 truncate">
                        {layer.type === 'text'
                          ? layer.text || '（空文字）'
                          : layer.type === 'image'
                            ? layer.key || layer.url || '图片槽'
                            : layer.type === 'circle'
                              ? `半径 ${layer.radius || 0} · 圆心 (${layer.x || 0},${layer.y || 0})`
                              : layer.type === 'line'
                                ? `长度 ${layer.length || 0} · ${layer.angle || 0}°`
                                : `${layer.width}×${layer.height}`}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          moveTemplateLayer(idx, -1)
                        }}
                        disabled={idx === 0}
                        className="p-1 rounded text-gray-300 hover:text-violet-500 hover:bg-violet-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="上移一层"
                      >
                        <ArrowUp className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          moveTemplateLayer(idx, 1)
                        }}
                        disabled={idx === templateForm.layers.length - 1}
                        className="p-1 rounded text-gray-300 hover:text-violet-500 hover:bg-violet-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="下移一层"
                      >
                        <ArrowDown className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          duplicateTemplateLayer(idx)
                        }}
                        className="p-1 rounded text-gray-300 hover:text-blue-500 hover:bg-blue-50 transition-colors"
                        title="复制图层"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          removeTemplateLayer(idx)
                        }}
                        className="p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                        title="删除图层"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mt-2.5">
                <button
                  onClick={() => addTemplateLayer('text')}
                  className="flex items-center justify-center gap-1 px-2 py-2 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-all"
                >
                  <Type className="w-3.5 h-3.5" /> 文字
                </button>
                <button
                  onClick={() => addTemplateLayer('rect')}
                  className="flex items-center justify-center gap-1 px-2 py-2 rounded-lg text-xs font-medium bg-amber-50 text-amber-600 border border-amber-200 hover:bg-amber-100 transition-all"
                >
                  <Square className="w-3.5 h-3.5" /> 矩形
                </button>
                <button
                  onClick={() => addTemplateLayer('circle')}
                  className="flex items-center justify-center gap-1 px-2 py-2 rounded-lg text-xs font-medium bg-rose-50 text-rose-600 border border-rose-200 hover:bg-rose-100 transition-all"
                >
                  <Circle className="w-3.5 h-3.5" /> 圆形
                </button>
                <button
                  onClick={() => addTemplateLayer('line')}
                  className="flex items-center justify-center gap-1 px-2 py-2 rounded-lg text-xs font-medium bg-cyan-50 text-cyan-600 border border-cyan-200 hover:bg-cyan-100 transition-all"
                >
                  <Minus className="w-3.5 h-3.5" /> 线条
                </button>
                <button
                  onClick={() => addTemplateLayer('image')}
                  className="flex items-center justify-center gap-1 px-2 py-2 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-600 border border-emerald-200 hover:bg-emerald-100 transition-all"
                >
                  <ImageIcon className="w-3.5 h-3.5" /> 图片槽
                </button>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-gray-400">
                图片层不填地址即为「图片槽」，渲染时自动套入所选图片（适合批量套版）；文字层的「变量名」可在渲染时批量替换内容。圆形/线条适合做装饰光斑、徽章底与分隔线，支持渐变与透明度。
              </p>
            </div>
            </div>

            {/* 中栏：画布实时预览（sticky 常驻，编辑属性时同步可见） */}
            <div className="lg:sticky lg:top-0 lg:self-start space-y-2">
              <label className="block text-sm font-medium text-gray-700">实时预览（点击/拖拽可选中移动图层）</label>
              {(() => {
                const w = Number(templateForm.width) || 1080
                const h = Number(templateForm.height) || 1920
                const scale = Math.min(1, 460 / w)
                const pv = (v) => (Number(v) || 0) * scale
                const bg = String(templateForm.background || '#FFFFFF')
                const isGradient = bg.includes('→')
                const [gFrom, gTo] = isGradient ? bg.split('→').map((s) => s.trim()) : []
                // 命中检测（从顶层向下），坐标已换算为画布原始像素
                const hitTest = (px, py) => {
                  const layers = templateForm.layers
                  for (let i = layers.length - 1; i >= 0; i--) {
                    const l = layers[i]
                    let hit = false
                    if (l.type === 'rect' || l.type === 'image') {
                      hit =
                        px >= (l.x || 0) &&
                        px <= (l.x || 0) + (l.width || 0) &&
                        py >= (l.y || 0) &&
                        py <= (l.y || 0) + (l.height || 0)
                    } else if (l.type === 'circle') {
                      const r = Number(l.radius) || 0
                      hit = Math.hypot(px - (l.x || 0), py - (l.y || 0)) <= r
                    } else if (l.type === 'line') {
                      // 点到线段距离 <= 线宽×2 视为命中
                      const x1 = l.x || 0
                      const y1 = l.y || 0
                      const ang = ((Number(l.angle) || 0) * Math.PI) / 180
                      const len = Number(l.length) || 100
                      const x2 = x1 + len * Math.cos(ang)
                      const y2 = y1 + len * Math.sin(ang)
                      const dx = x2 - x1
                      const dy = y2 - y1
                      const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy || 1)))
                      hit = Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)) <= Math.max(10, (Number(l.width) || 2) * 2)
                    } else if (l.type === 'text') {
                      const fs = Number(l.font_size) || 28
                      const lines = String(l.text || '').split('\n')
                      const tw = Number(l.max_width) || Math.max(1, ...lines.map((s) => s.length)) * fs * 0.55
                      const th = lines.length * fs * (Number(l.line_height) || 1.35)
                      hit =
                        px >= (l.x || 0) &&
                        px <= (l.x || 0) + tw &&
                        py >= (l.y || 0) &&
                        py <= (l.y || 0) + th
                    }
                    if (hit) return i
                  }
                  return -1
                }
                const shadowCss = (layer) => {
                  if (!layer.shadow) return undefined
                  // v24：支持 x,y,blur 三参数软阴影，缺省 blur 时用 3px
                  const [sx, sy, blur] = String(layer.shadow)
                    .split(',')
                    .map((s) => Number(s.trim()) || 0)
                  return `${sx}px ${sy}px ${blur ? pv(blur) : pv(3)}px ${layer.shadow_color || 'rgba(0,0,0,0.5)'}`
                }
                return (
                  <div
                    className="relative rounded-xl border border-gray-200 overflow-hidden mx-auto shadow-sm cursor-grab active:cursor-grabbing select-none"
                    style={{
                      width: w * scale,
                      height: h * scale,
                      background: isGradient ? `linear-gradient(135deg, ${gFrom}, ${gTo})` : bg,
                    }}
                    onPointerDown={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect()
                      const px = (e.clientX - rect.left) / scale
                      const py = (e.clientY - rect.top) / scale
                      const idx = hitTest(px, py)
                      if (idx >= 0) {
                        setSelectedLayerIdx(idx)
                        dragRef.current = {
                          idx,
                          startX: e.clientX,
                          startY: e.clientY,
                          origX: Number(templateForm.layers[idx].x) || 0,
                          origY: Number(templateForm.layers[idx].y) || 0,
                        }
                        e.currentTarget.setPointerCapture(e.pointerId)
                      }
                    }}
                    onPointerMove={(e) => {
                      const d = dragRef.current
                      if (!d) return
                      updateTemplateLayer(d.idx, {
                        x: Math.round(d.origX + (e.clientX - d.startX) / scale),
                        y: Math.round(d.origY + (e.clientY - d.startY) / scale),
                      })
                    }}
                    onPointerUp={() => {
                      dragRef.current = null
                    }}
                    onPointerCancel={() => {
                      dragRef.current = null
                    }}
                  >
                    {/* 背景图 + 暗化层 */}
                    {templateForm.background_image && (
                      <>
                        <img
                          src={absUrl(templateForm.background_image)}
                          alt="bg"
                          className="absolute inset-0 w-full h-full object-cover"
                        />
                        {(templateForm.background_darken || 0) > 0 && (
                          <div
                            className="absolute inset-0"
                            style={{ background: `rgba(0,0,0,${templateForm.background_darken})` }}
                          />
                        )}
                      </>
                    )}
                    {templateForm.layers.map((layer, idx) => {
                      const selected = selectedLayerIdx === idx
                      const outline = selected ? '2px solid #8b5cf6' : undefined
                      if (layer.type === 'rect') {
                        const fill = String(layer.fill || '#F3F4F6')
                        const grad = fill.includes('→')
                        const [rFrom, rTo] = grad ? fill.split('→').map((s) => s.trim()) : []
                        return (
                          <div
                            key={idx}
                            style={{
                              position: 'absolute',
                              left: pv(layer.x),
                              top: pv(layer.y),
                              width: pv(layer.width),
                              height: pv(layer.height),
                              borderRadius: pv(layer.radius),
                              background: grad ? `linear-gradient(135deg, ${rFrom}, ${rTo})` : fill,
                              opacity: layer.opacity ?? 1,
                              border:
                                layer.border_width > 0
                                  ? `${pv(layer.border_width)}px solid ${layer.border_color || '#FFFFFF'}`
                                  : undefined,
                              transform: layer.rotation ? `rotate(${layer.rotation}deg)` : undefined,
                              transformOrigin: 'center',
                              outline,
                              outlineOffset: -1,
                            }}
                          />
                        )
                      }
                      if (layer.type === 'circle') {
                        const fill = String(layer.fill || '#F3F4F6')
                        const grad = fill.includes('→')
                        const [cFrom, cTo] = grad ? fill.split('→').map((s) => s.trim()) : []
                        const r = Number(layer.radius) || 0
                        return (
                          <div
                            key={idx}
                            style={{
                              position: 'absolute',
                              left: pv((layer.x || 0) - r),
                              top: pv((layer.y || 0) - r),
                              width: pv(r * 2),
                              height: pv(r * 2),
                              borderRadius: '50%',
                              background: grad ? `linear-gradient(135deg, ${cFrom}, ${cTo})` : fill,
                              opacity: layer.opacity ?? 1,
                              border:
                                layer.border_width > 0
                                  ? `${pv(layer.border_width)}px solid ${layer.border_color || '#FFFFFF'}`
                                  : undefined,
                              transform: layer.rotation ? `rotate(${layer.rotation}deg)` : undefined,
                              outline,
                              outlineOffset: -1,
                            }}
                          />
                        )
                      }
                      if (layer.type === 'line') {
                        return (
                          <div
                            key={idx}
                            style={{
                              position: 'absolute',
                              left: pv(layer.x),
                              top: pv((layer.y || 0) - (Number(layer.width) || 2) / 2),
                              width: pv(layer.length || 100),
                              height: pv(Math.max(1, Number(layer.width) || 2)),
                              background: layer.color || '#DDDDDD',
                              opacity: layer.opacity ?? 1,
                              transform: `rotate(${layer.angle || 0}deg)`,
                              transformOrigin: '0 50%',
                              outline,
                              outlineOffset: -1,
                            }}
                          />
                        )
                      }
                      if (layer.type === 'text') {
                        // v24：color 支持 #A→#B 渐变，画布预览用 background-clip 模拟
                        const gradParts = String(layer.color || '').split('→').map((s) => s.trim())
                        const isGradText = gradParts.length > 1 && gradParts[0].startsWith('#')
                        return (
                          <div
                            key={idx}
                            style={{
                              position: 'absolute',
                              left: pv(layer.x),
                              top: pv(layer.y),
                              width: layer.max_width > 0 ? pv(layer.max_width) : undefined,
                              fontSize: Math.max(6, pv(layer.font_size)),
                              color: isGradText ? 'transparent' : layer.color,
                              backgroundImage: isGradText ? `linear-gradient(180deg, ${gradParts[0]}, ${gradParts[1]})` : undefined,
                              WebkitBackgroundClip: isGradText ? 'text' : undefined,
                              WebkitTextFillColor: isGradText ? 'transparent' : undefined,
                              textAlign: layer.align || 'left',
                              lineHeight: Number(layer.line_height) || 1.35,
                              letterSpacing: `${pv(layer.letter_spacing)}px`,
                              whiteSpace: 'pre-wrap',
                              fontFamily: FONT_CSS[layer.family] || FONT_CSS.pingfang,
                              fontWeight: layer.bold ? 700 : 400,
                              fontStyle: layer.italic ? 'italic' : 'normal',
                              textShadow: shadowCss(layer),
                              WebkitTextStroke:
                                layer.stroke_width > 0
                                  ? `${pv(layer.stroke_width)}px ${layer.stroke_color || '#000000'}`
                                  : undefined,
                              paintOrder: layer.stroke_width > 0 ? 'stroke fill' : undefined,
                              transform: layer.rotation ? `rotate(${layer.rotation}deg)` : undefined,
                              transformOrigin: 'center',
                              outline,
                              outlineOffset: -1,
                            }}
                          >
                            {layer.text}
                          </div>
                        )
                      }
                      if (layer.type === 'image') {
                        return layer.url ? (
                          <img
                            key={idx}
                            src={absUrl(layer.url)}
                            alt="layer"
                            className="absolute"
                            style={{
                              left: pv(layer.x),
                              top: pv(layer.y),
                              width: pv(layer.width),
                              height: pv(layer.height),
                              objectFit: layer.fit === 'contain' ? 'contain' : 'cover',
                              borderRadius: pv(layer.radius),
                              opacity: layer.opacity ?? 1,
                              border:
                                layer.border_width > 0
                                  ? `${pv(layer.border_width)}px solid ${layer.border_color || '#FFFFFF'}`
                                  : undefined,
                              transform: layer.rotation ? `rotate(${layer.rotation}deg)` : undefined,
                              transformOrigin: 'center',
                              outline,
                              outlineOffset: -1,
                            }}
                          />
                        ) : (
                          <div
                            key={idx}
                            className="absolute border-2 border-dashed border-violet-300 bg-violet-50/60 flex items-center justify-center text-[10px] text-violet-400"
                            style={{
                              left: pv(layer.x),
                              top: pv(layer.y),
                              width: pv(layer.width),
                              height: pv(layer.height),
                              borderRadius: pv(layer.radius),
                              outline,
                              outlineOffset: -1,
                            }}
                          >
                            {layer.key || '图片槽'}
                          </div>
                        )
                      }
                      return null
                    })}
                    <div className="absolute bottom-1.5 right-2 text-[10px] text-white/70 bg-black/30 px-1.5 py-0.5 rounded">
                      {w} × {h}
                    </div>
                  </div>
                )
              })()}

            </div>

              {/* 右栏：选中图层的属性面板（与画布同屏，改动实时可见） */}
              <div className="space-y-3">
                {selectedLayerIdx >= 0 && templateForm.layers[selectedLayerIdx] ? (
                  <LayerProps
                    layer={templateForm.layers[selectedLayerIdx]}
                    onChange={(patch) => updateTemplateLayer(selectedLayerIdx, patch)}
                  />
                ) : (
                  <div className="rounded-xl border-2 border-dashed border-gray-200 px-4 py-10 text-center">
                    <p className="text-sm text-gray-400 mb-1.5">未选中图层</p>
                    <p className="text-[11px] leading-relaxed text-gray-300">
                      在左侧图层列表或画布上点击图层，即可在这里编辑属性，修改会实时反映到中间预览
                    </p>
                  </div>
                )}
              </div>
            </div>

          {/* 高级模式：JSON 编辑（保留给熟悉格式的用户） */}
          <div className="border-t border-gray-100 pt-3">
            <button
              onClick={() =>
                setTemplateForm((f) => ({
                  ...f,
                  showJson: !f.showJson,
                  layerJson: JSON.stringify(f.layers, null, 2),
                }))
              }
              className="flex items-center gap-1 text-xs font-medium text-gray-400 hover:text-gray-600 transition-colors"
            >
              {templateForm.showJson ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
              高级：JSON 编辑
            </button>
            {templateForm.showJson && (
              <div className="mt-2 flex gap-2 items-start">
                <textarea
                  value={templateForm.layerJson}
                  onChange={(e) => setTemplateForm({ ...templateForm, layerJson: e.target.value })}
                  rows={6}
                  className="flex-1 px-3 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-xs font-mono resize-y"
                />
                <Button
                  variant="outline"
                  size="sm"
                  icon={FileJson2}
                  onClick={() => {
                    try {
                      const parsed = JSON.parse(templateForm.layerJson)
                      if (!Array.isArray(parsed)) throw new Error('not array')
                      setTemplateForm((f) => ({ ...f, layers: parsed, showJson: false }))
                      setSelectedLayerIdx(-1)
                      toast.success('JSON 已导入到图层编辑器')
                    } catch {
                      toast.error('JSON 格式错误，应为图层数组')
                    }
                  }}
                >
                  导入
                </Button>
              </div>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={() => setTemplateModal(false)}>
            取消
          </Button>
          <Button
            variant="gradient"
            icon={templateModal === 'edit' ? Check : Plus}
            loading={templateSaving}
            onClick={handleSaveTemplate}
          >
            {templateModal === 'edit' ? '保存修改' : '创建模板'}
          </Button>
        </div>
      </Modal>

      {/* 模板背景图选择 Modal */}
      <Modal
        open={!!showTemplateBgPicker}
        onClose={() => setShowTemplateBgPicker(false)}
        title="选择背景图（铺满画布，可用暗化调节文字对比度）"
        size="2xl"
      >
        {images.length === 0 ? (
          <Empty icon={ImageIcon} title="图片库为空" description="请先上传或生成图片" />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {images.map((img) => {
              const picked = templateForm.background_image === absUrl(img.url)
              return (
                <button
                  key={img.filename}
                  onClick={() => {
                    setTemplateForm((f) => ({ ...f, background_image: absUrl(img.url) }))
                    setShowTemplateBgPicker(false)
                  }}
                  className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                    picked ? 'border-violet-500' : 'border-gray-200 hover:border-violet-400'
                  }`}
                >
                  <img
                    src={absUrl(img.thumb_url || img.url)}
                    alt={img.filename}
                    className="w-full h-32 object-contain bg-gray-50"
                    loading="lazy"
                  />
                  <div className="absolute bottom-0 left-0 right-0 bg-black/50 px-2 py-1">
                    <p className="text-xs text-white truncate">{img.filename}</p>
                  </div>
                  {picked && (
                    <div className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-violet-500 text-white flex items-center justify-center shadow">
                      <Check className="w-3.5 h-3.5" />
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        )}
      </Modal>

      {/* 套版图片多选弹窗 */}
      <Modal
        open={showTemplatePicker}
        onClose={() => setShowTemplatePicker(false)}
        title="选择套版图片（可多选）"
        size="2xl"
      >
        {images.length === 0 ? (
          <Empty icon={ImageIcon} title="图片库为空" description="请先上传或生成图片" />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {images.map((img) => {
              const picked = templateImages.some((x) => x.filename === img.filename)
              return (
                <button
                  key={img.filename}
                  onClick={() => {
                    setTemplateImages((prev) =>
                      picked
                        ? prev.filter((x) => x.filename !== img.filename)
                        : [...prev, { url: absUrl(img.url), filename: img.filename }]
                    )
                  }}
                  className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                    picked ? 'border-violet-500' : 'border-gray-200 hover:border-violet-400'
                  }`}
                >
                  <img
                    src={absUrl(img.thumb_url || img.url)}
                    alt={img.filename}
                    className="w-full h-32 object-contain bg-gray-50"
                    loading="lazy"
                  />
                  <div className="absolute bottom-0 left-0 right-0 bg-black/50 px-2 py-1">
                    <p className="text-xs text-white truncate">{img.filename}</p>
                  </div>
                  {picked && (
                    <div className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-violet-500 text-white flex items-center justify-center shadow">
                      <Check className="w-3.5 h-3.5" />
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        )}
        <div className="flex items-center justify-between mt-5">
          <button
            onClick={() => setTemplateImages([])}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors"
          >
            清空选择
          </button>
          <Button variant="gradient" onClick={() => setShowTemplatePicker(false)}>
            确定（已选 {templateImages.length} 张）
          </Button>
        </div>
      </Modal>

      {/* Excel 批量套版弹窗（商业化：对标跨境卖家批量出图工具） */}
      <Modal open={batchOpen} onClose={() => setBatchOpen(false)} title="Excel 批量生成图片" size="2xl">
        <div className="space-y-5">
          {/* 当前模板信息 */}
          <div className="flex items-start gap-3 rounded-xl bg-violet-50 border border-violet-100 px-4 py-3">
            <LayoutTemplate className="w-4 h-4 text-violet-500 mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-gray-900">
                {templates.find((x) => x.id === selectedTemplate)?.name || '未选择模板'}
              </div>
              <div className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">
                表格每行数据生成一张图片（自动套用模板变量），完成后打包 zip 下载，单次最多 500 行
              </div>
            </div>
          </div>

          {/* 步骤 1：上传表格 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">① 上传 Excel/CSV 表格</label>
            <button
              onClick={() => batchFileRef.current?.click()}
              className="w-full rounded-xl border-2 border-dashed border-gray-200 hover:border-emerald-400 hover:bg-emerald-50/50 transition-all px-4 py-6 text-center"
            >
              {batchFile ? (
                <span className="flex items-center justify-center gap-2 text-sm text-emerald-600 font-medium">
                  <FileSpreadsheet className="w-5 h-5" />
                  {batchFile.name}
                </span>
              ) : (
                <span className="flex flex-col items-center gap-1 text-sm text-gray-400">
                  <Upload className="w-6 h-6" />
                  点击上传 .xlsx / .csv（首行为表头，如：商品名、价格、折扣）
                </span>
              )}
            </button>
            <input
              ref={batchFileRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleBatchFile}
              className="hidden"
            />
          </div>

          {/* 步骤 2：字段映射（表格列 → 模板变量） */}
          {batchColumns.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-gray-700">② 字段映射（表格列 → 模板变量）</label>
                <button
                  onClick={() => {
                    const tmpl = templates.find((t) => t.id === selectedTemplate)
                    setBatchFieldMap(autoMapColumns(batchColumns, tmpl))
                  }}
                  className="text-xs text-violet-600 hover:text-violet-700"
                >
                  ↺ 自动匹配
                </button>
              </div>
              <div className="rounded-xl border border-gray-200 divide-y divide-gray-100 max-h-56 overflow-y-auto">
                {(templates.find((t) => t.id === selectedTemplate)?.layers || [])
                  .filter((l) => l.key)
                  .map((l) => (
                    <div key={l.key} className="flex items-center gap-3 px-3 py-2">
                      <span className="text-xs font-medium text-gray-700 w-36 truncate flex-shrink-0">
                        {l.type === 'image' ? '🖼' : '🔤'} {l.key}
                      </span>
                      <select
                        value={Object.entries(batchFieldMap).find(([, v]) => v === l.key)?.[0] || ''}
                        onChange={(e) => {
                          const nm = { ...batchFieldMap }
                          Object.keys(nm).forEach((c) => {
                            if (nm[c] === l.key) delete nm[c]
                          })
                          if (e.target.value) nm[e.target.value] = l.key
                          setBatchFieldMap(nm)
                        }}
                        className="flex-1 px-3 py-1.5 rounded-lg border border-gray-200 text-sm outline-none focus:border-violet-500 bg-white"
                      >
                        <option value="">— 不映射 —</option>
                        {batchColumns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
              </div>
              <p className="mt-1.5 text-[11px] text-gray-400">
                🔤 文字变量填入文本；🖼 图片变量填入图片 URL（http）或图库相对路径
              </p>
            </div>
          )}

          {/* 步骤 3：批次名称 */}
          {batchColumns.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">③ 批次名称（可选）</label>
              <input
                value={batchName}
                onChange={(e) => setBatchName(e.target.value)}
                placeholder="如：8月大促主图"
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none text-sm"
              />
            </div>
          )}

          {/* 任务进度 */}
          {batchTask && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-100 px-3 py-2">
              <div className="flex items-center gap-2 text-xs text-emerald-700">
                <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                <span className="flex-1 truncate">{batchTask.stage || '任务执行中…'}</span>
                <span className="font-medium">{Math.round(batchTask.progress || 0)}%</span>
              </div>
              <div className="mt-1.5 h-1.5 bg-emerald-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-teal-600 rounded-full transition-all"
                  style={{ width: `${batchTask.progress || 0}%` }}
                />
              </div>
            </div>
          )}

          {/* 完成结果 */}
          {batchResult && (
            <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
                <Check className="w-4 h-4" /> 已生成 {batchResult.count} 张图片
              </div>
              <div className="flex items-center gap-3 mt-2">
                <a
                  href={absUrl(batchResult.zip)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 transition-colors"
                >
                  <DownloadCloud className="w-3.5 h-3.5" /> 下载全部（zip）
                </a>
                <span className="text-[11px] text-emerald-600/70">图片已保存到图片库，可关闭弹窗在预览区查看</span>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => setBatchOpen(false)}>
              关闭
            </Button>
            <Button
              variant="gradient"
              icon={FileSpreadsheet}
              loading={batchBusy}
              disabled={
                !batchFile ||
                (batchColumns.length > 0 && Object.values(batchFieldMap).filter(Boolean).length === 0)
              }
              onClick={handleBatchStart}
            >
              {batchBusy ? '提交中…' : '开始批量生成'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* 一键发布弹窗（商业化：图片 → 公众号/抖音/快手账号） */}
      <Modal open={pubOpen} onClose={() => setPubOpen(false)} title="一键发布到平台">
        <div className="space-y-4">
          {pubTarget && (
            <div className="flex items-center gap-3 rounded-xl bg-gray-50 border border-gray-100 p-3">
              <img
                src={pubTarget.url}
                alt="待发布"
                className="w-16 h-16 rounded-lg object-cover border border-gray-200 flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 truncate">
                  发布图片：{pubTarget.filename || 'AI 生成图片'}
                </p>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  后端将按平台规格自动裁切封面、改写文案并生成话题标签
                </p>
              </div>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">目标平台</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {[
                ['wechat', '公众号'],
                ['douyin', '抖音'],
                ['kuaishou', '快手'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setPubPlatform(id)}
                  className={`px-3 py-2 rounded-xl border text-sm font-medium transition-all ${
                    pubPlatform === id
                      ? 'border-rose-500 bg-rose-50 text-rose-600'
                      : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">标题</label>
            <input
              value={pubTitle}
              onChange={(e) => setPubTitle(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">文案</label>
            <textarea
              value={pubContent}
              onChange={(e) => setPubContent(e.target.value)}
              rows={4}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 outline-none text-sm resize-none"
            />
          </div>
          <div className="flex justify-end gap-3 pt-1">
            <Button variant="outline" onClick={() => setPubOpen(false)}>
              取消
            </Button>
            <Button variant="gradient" icon={Send} loading={pubBusy} onClick={handlePublish}>
              {pubBusy ? '发布中…' : '确认发布'}
            </Button>
          </div>
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

/* eslint-disable react-refresh/only-export-components -- 画布动画引擎：导出常量供其他组件复用 */
import React, {
  useRef,
  useEffect,
  useCallback,
  useImperativeHandle,
  forwardRef,
  useState,
} from 'react'

/**
 * AI数字人动画引擎 v3.0 — AI写真增强版
 *
 * 新特性：
 * - AI 写真肖像模式：使用 AI 生成的真人照片作为角色形象
 * - 口型同步动画覆盖层（在写真上叠加嘴部动画）
 * - 5 种表情（自然/开心/惊讶/思考/悲伤）
 * - 场景背景
 * - Canvas 录制导出（WebM 视频）
 * - 零外部依赖
 *
 * 模式切换：
 * - portraitUrl 存在 → 写真模式（图片 + 口型动画覆盖层）
 * - portraitUrl 不存在 → 经典卡通模式（完整 canvas 绘制）
 */

// ═══════════════════════════════════════════════════════════
// 卡通模式配色方案
// ═══════════════════════════════════════════════════════════
const STYLES = {
  'business-female': {
    skin: '#FFDAB9',
    hair: '#2C1810',
    hairHi: '#4A3728',
    eye: '#4A90D9',
    outfit: {
      formal: ['#1a1a2e', '#2d2d44'],
      casual: ['#f093fb', '#db2777'],
      tech: ['#667eea', '#5a67d8'],
      cute: ['#fbbf24', '#f59e0b'],
    },
  },
  'business-male': {
    skin: '#F5D5B8',
    hair: '#1a1a2e',
    hairHi: '#2d2d44',
    eye: '#3d5a80',
    outfit: {
      formal: ['#374151', '#1f2937'],
      casual: ['#f59e0b', '#d97706'],
      tech: ['#4a5568', '#2d3748'],
      cute: ['#34d399', '#059669'],
    },
  },
  'casual-female': {
    skin: '#FFD1C1',
    hair: '#8B4513',
    hairHi: '#A0522D',
    eye: '#6B8E23',
    outfit: {
      formal: ['#78716c', '#57534e'],
      casual: ['#f472b6', '#db2777'],
      tech: ['#818cf8', '#6366f1'],
      cute: ['#fbbf24', '#f59e0b'],
    },
  },
  'casual-male': {
    skin: '#FDEBD0',
    hair: '#34495E',
    hairHi: '#5D6D7E',
    eye: '#2980B9',
    outfit: {
      formal: ['#475569', '#334155'],
      casual: ['#fb923c', '#ea580c'],
      tech: ['#06b6d4', '#0891b2'],
      cute: ['#a78bfa', '#7c3aed'],
    },
  },
  'tech-female': {
    skin: '#FFE4D6',
    hair: '#1a0033',
    hairHi: '#2d0055',
    eye: '#9b59b6',
    outfit: {
      formal: ['#374151', '#1f2937'],
      casual: ['#ec4899', '#be185d'],
      tech: ['#8B5CF6', '#7C3AED'],
      cute: ['#06b6d4', '#0891b2'],
    },
  },
  'sexy-goddess': {
    skin: '#FFDAB9',
    hair: '#1a0a0a',
    hairHi: '#3a2020',
    eye: '#8B0000',
    outfit: {
      formal: ['#8B0000', '#600000'],
      casual: ['#FF1493', '#C71585'],
      tech: ['#9400D3', '#6A0DAD'],
      cute: ['#FF69B4', '#FF1493'],
    },
  },
  'sweet-girl': {
    skin: '#FFF0E6',
    hair: '#8B4513',
    hairHi: '#D2691E',
    eye: '#FF69B4',
    outfit: {
      formal: ['#FFB6C1', '#FF69B4'],
      casual: ['#FFC0CB', '#FF91A4'],
      tech: ['#DDA0DD', '#BA55D3'],
      cute: ['#FFE4E1', '#FFC0CB'],
    },
  },
  'cool-queen': {
    skin: '#F5F0EB',
    hair: '#0a0a0a',
    hairHi: '#2a2a2a',
    eye: '#4169E1',
    outfit: {
      formal: ['#1a1a2e', '#0d0d1a'],
      casual: ['#2d1b69', '#1a0f3c'],
      tech: ['#191970', '#0f0f40'],
      cute: ['#4B0082', '#2E0854'],
    },
  },
  'charming-mature': {
    skin: '#FFE4D6',
    hair: '#4A0E17',
    hairHi: '#6B1D23',
    eye: '#8B4513',
    outfit: {
      formal: ['#722F37', '#4A1B20'],
      casual: ['#C41E3A', '#8B1525'],
      tech: ['#800020', '#500015'],
      cute: ['#E32636', '#B22222'],
    },
  },
  'educator-male': {
    skin: '#FAE5D3',
    hair: '#3E2723',
    hairHi: '#5D4037',
    eye: '#2E7D32',
    outfit: {
      formal: ['#1e3a5f', '#15294a'],
      casual: ['#14b8a6', '#0d9488'],
      tech: ['#0d9488', '#0f766e'],
      cute: ['#f59e0b', '#d97706'],
    },
  },
  'cartoon-cute': {
    skin: '#FFF5E6',
    hair: '#FFE0B2',
    hairHi: '#FFCC80',
    eye: '#4FC3F7',
    outfit: {
      formal: ['#9ca3af', '#6b7280'],
      casual: ['#fbbf24', '#f59e0b'],
      tech: ['#38bdf8', '#0ea5e9'],
      cute: ['#f472b6', '#ec4899'],
    },
  },
  'anime-style': {
    skin: '#FCE4EC',
    hair: '#E91E63',
    hairHi: '#F06292',
    eye: '#CE93D8',
    outfit: {
      formal: ['#4a1942', '#2d0f26'],
      casual: ['#f472b6', '#db2777'],
      tech: ['#c084fc', '#a855f7'],
      cute: ['#fb7185', '#e11d48'],
    },
  },
}

// 表情参数
const EXPRESSIONS = {
  neutral: { ea: 0, es: 1, mc: 0.5, blush: 0.3, sparkle: 1 },
  happy: { ea: -0.25, es: 0.85, mc: 0.9, blush: 0.6, sparkle: 1.5 },
  surprised: { ea: 0.4, es: 1.35, mc: 0.2, blush: 0.1, sparkle: 1.3 },
  sad: { ea: 0.3, es: 0.9, mc: 0.3, blush: 0.15, sparkle: 0.5 },
  thinking: { ea: -0.15, es: 0.95, mc: 0.35, blush: 0.2, sparkle: 0.8 },
}

// 口型形状
const PHONEME_SHAPES = {
  a: { mw: 1.3, mh: 1.1 },
  e: { mw: 1.6, mh: 0.6 },
  i: { mw: 0.7, mh: 0.8 },
  o: { mw: 0.85, mh: 1.0 },
  u: { mw: 0.5, mh: 0.9 },
}

// 场景背景绘制
const SCENE_BG = {
  office: (ctx, w, h) => {
    const bg = ctx.createLinearGradient(0, 0, 0, h)
    bg.addColorStop(0, '#1a1a2e')
    bg.addColorStop(0.5, '#16213e')
    bg.addColorStop(1, '#0f3460')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = 'rgba(255,255,255,0.08)'
    ctx.fillRect(w * 0.15, h * 0.1, w * 0.25, h * 0.3)
    ctx.strokeStyle = 'rgba(255,255,255,0.15)'
    ctx.lineWidth = 2
    ctx.strokeRect(w * 0.15, h * 0.1, w * 0.25, h * 0.3)
    ctx.fillStyle = '#2d1810'
    ctx.fillRect(0, h * 0.75, w, h * 0.3)
    ctx.fillStyle = '#3d2818'
    ctx.fillRect(0, h * 0.75, w, 4)
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(w * 0.55, h * 0.45, w * 0.3, h * 0.25)
    ctx.fillStyle = '#5a67d8'
    ctx.fillRect(w * 0.57, h * 0.47, w * 0.26, h * 0.18)
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(w * 0.63, h * 0.73, w * 0.14, 8)
  },
  studio: (ctx, w, h) => {
    const bg = ctx.createLinearGradient(0, 0, 0, h)
    bg.addColorStop(0, '#1e1b4b')
    bg.addColorStop(0.5, '#312e81')
    bg.addColorStop(1, '#3730a3')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
    ctx.strokeStyle = 'rgba(255,255,255,0.12)'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(w * 0.75, h * 0.3, 40, 0, Math.PI * 2)
    ctx.stroke()
    ctx.strokeStyle = 'rgba(255,255,255,0.06)'
    ctx.beginPath()
    ctx.arc(w * 0.75, h * 0.3, 55, 0, Math.PI * 2)
    ctx.stroke()
    ctx.strokeStyle = 'rgba(255,255,255,0.1)'
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.moveTo(w * 0.75, h * 0.3 + 55)
    ctx.lineTo(w * 0.75, h)
    ctx.stroke()
  },
  nature: (ctx, w, h) => {
    const bg = ctx.createLinearGradient(0, 0, 0, h)
    bg.addColorStop(0, '#4ade80')
    bg.addColorStop(0.4, '#22c55e')
    bg.addColorStop(1, '#166534')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.beginPath()
    ctx.arc(w * 0.2, h * 0.15, 30, 0, Math.PI * 2)
    ctx.arc(w * 0.27, h * 0.12, 25, 0, Math.PI * 2)
    ctx.arc(w * 0.33, h * 0.15, 28, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.arc(w * 0.65, h * 0.1, 22, 0, Math.PI * 2)
    ctx.arc(w * 0.7, h * 0.08, 18, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#3f6212'
    ctx.fillRect(0, h * 0.82, w, h * 0.3)
    for (let i = 0; i < 6; i++) {
      const x = w * 0.1 + i * w * 0.15
      ctx.fillStyle = ['#fbbf24', '#f472b6', '#ffffff', '#fbbf24', '#818cf8', '#f472b6'][i]
      ctx.beginPath()
      ctx.arc(x, h * 0.84, 4, 0, Math.PI * 2)
      ctx.fill()
    }
  },
  tech: (ctx, w, h) => {
    const bg = ctx.createLinearGradient(0, 0, w, h)
    bg.addColorStop(0, '#0f0c29')
    bg.addColorStop(0.5, '#302b63')
    bg.addColorStop(1, '#24243e')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
    ctx.strokeStyle = 'rgba(99,102,241,0.2)'
    ctx.lineWidth = 1
    for (let i = 0; i < 8; i++) {
      ctx.beginPath()
      ctx.moveTo(0, h * 0.1 + i * h * 0.1)
      ctx.lineTo(w, h * 0.15 + i * h * 0.1)
      ctx.stroke()
    }
    for (let i = 0; i < 12; i++) {
      ctx.fillStyle = ['rgba(99,102,241,0.3)', 'rgba(16,185,129,0.3)'][i % 2]
      ctx.beginPath()
      ctx.arc(
        w * 0.1 + Math.random() * w * 0.8,
        h * 0.1 + Math.random() * h * 0.4,
        3,
        0,
        Math.PI * 2
      )
      ctx.fill()
    }
  },
}

function lerp(a, b, t) {
  return a + (b - a) * t
}

const AnimatedAvatar = forwardRef(function AnimatedAvatar(
  {
    avatarId = 'business-female',
    width = 480,
    height = 400,
    audioElement = null,
    talking = false,
    expression = 'neutral',
    outfit = 'formal',
    scene = 'office',
    glasses = false,
    hat = false,
    portraitUrl = null, // ★ 新增：AI 写真图片 URL
    className = '',
  },
  ref
) {
  const canvasRef = useRef(null) // 主画布（卡通模式：角色 + 背景；写真模式：口型动画覆盖层）
  const bgCanvasRef = useRef(null) // 背景画布
  const animFrame = useRef(null)
  const analyserRef = useRef(null)
  const audioCtxRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)
  const [portraitLoaded, setPortraitLoaded] = useState(false)
  const [portraitError, setPortraitError] = useState(false)

  const stateRef = useRef({
    time: 0,
    breathPhase: 0,
    blinkTimer: 0,
    nextBlink: 100,
    isBlinking: false,
    blinkProgress: 0,
    mouthOpen: 0,
    mouthTarget: 0,
    audioLevel: 0,
    headTilt: 0,
    headTiltTarget: 0,
    exprCurrent: { ea: 0, es: 1, mc: 0.5, blush: 0.3, sparkle: 1 },
    exprTarget: { ea: 0, es: 1, mc: 0.5, blush: 0.3, sparkle: 1 },
    phonemeTarget: 'a',
    phonemeCurrent: { mw: 1, mh: 1 },
    handPhase: 0,
    gestureType: 0,
    gestureProgress: 0,
    nodAmount: 0,
    nodTarget: 0,
    hairTouchTimer: 0,
    hairTouchProgress: 0,
    isHairTouching: false,
  })

  const style = STYLES[avatarId] || STYLES['business-female']
  const topColor = style.outfit[outfit]?.[0] || style.outfit.formal[0]
  const bottomColor = style.outfit[outfit]?.[1] || style.outfit.formal[1]

  // 是否使用写真模式
  const usePortrait = !!(portraitUrl && portraitLoaded && !portraitError)

  // ── Web Audio ──
  useEffect(() => {
    if (!audioElement) return
    let ctx, source, analyser
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)()
      analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      analyser.smoothingTimeConstant = 0.25
      source = ctx.createMediaElementSource(audioElement)
      source.connect(analyser)
      analyser.connect(ctx.destination)
      audioCtxRef.current = ctx
      analyserRef.current = analyser
    } catch (e) {
      console.warn('Web Audio 不可用', e)
    }
    return () => {
      if (ctx) ctx.close().catch(() => {})
    }
  }, [audioElement])

  const getAudioData = useCallback(() => {
    const a = analyserRef.current
    if (!a) return { level: 0, freq: new Uint8Array(0) }
    const d = new Uint8Array(a.frequencyBinCount)
    a.getByteFrequencyData(d)
    let sum = 0
    for (let i = 2; i < Math.min(40, d.length); i++) sum += d[i]
    return { level: sum / (38 * 255), freq: d }
  }, [])

  const detectPhoneme = useCallback((freq) => {
    if (!freq || freq.length < 40) return 'a'
    const low = freq.slice(2, 10).reduce((a, b) => a + b, 0)
    const mid = freq.slice(10, 25).reduce((a, b) => a + b, 0)
    const high = freq.slice(25, 40).reduce((a, b) => a + b, 0)
    const total = low + mid + high
    if (total < 100) return 'a'
    const lr = low / total
    const mr = mid / total
    if (lr > 0.5) return 'u'
    if (mr > 0.55) return 'o'
    if (high / total > 0.4) return 'i'
    if (mr > 0.4) return 'e'
    return 'a'
  }, [])

  // ── 录制 ──
  const startRecording = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const stream = canvas.captureStream(30)
    streamRef.current = stream
    chunksRef.current = []
    const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' })
    recorder.ondataavailable = (e) => {
      if (e.data.size) chunksRef.current.push(e.data)
    }
    recorderRef.current = recorder
    recorder.start()
    return recorder
  }, [])

  const stopRecording = useCallback(() => {
    return new Promise((resolve) => {
      const rec = recorderRef.current
      if (!rec) {
        resolve(null)
        return
      }
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'video/webm' })
        resolve(blob)
      }
      rec.stop()
    })
  }, [])

  useImperativeHandle(ref, () => ({ startRecording, stopRecording, canvas: canvasRef.current }), [
    startRecording,
    stopRecording,
  ])

  // ══ 写真模式：口型动画覆盖层 ══
  const drawPortraitOverlay = useCallback(
    (ctx, w, h, state) => {
      ctx.clearRect(0, 0, w, h)

      if (!talking || state.mouthOpen < 0.02) return

      const cx = w * 0.5
      const mouthY = h * 0.68 // 口部大致位置（写真模式下，嘴部在画面中下位置）
      const p = state.phonemeCurrent
      const open = state.mouthOpen

      // 半透明黑色椭圆 — 模拟说话嘴部动画
      const mh = Math.max(3, open * 28) * p.mh
      const mw = Math.max(10, 16 * p.mw)

      // 嘴部外光晕
      const glowGrad = ctx.createRadialGradient(cx, mouthY, mw * 0.3, cx, mouthY, mw * 1.2)
      glowGrad.addColorStop(0, 'rgba(255, 100, 100, 0.25)')
      glowGrad.addColorStop(0.5, 'rgba(255, 80, 80, 0.08)')
      glowGrad.addColorStop(1, 'rgba(255, 80, 80, 0)')
      ctx.fillStyle = glowGrad
      ctx.beginPath()
      ctx.ellipse(cx, mouthY, mw * 1.2, mh * 1.4, 0, 0, Math.PI * 2)
      ctx.fill()

      // 嘴唇动画线
      ctx.strokeStyle = `rgba(255, 100, 120, ${0.35 + open * 0.5})`
      ctx.lineWidth = 2.5
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.ellipse(cx, mouthY, mw, mh, 0, Math.PI * 0.1, Math.PI * 0.9)
      ctx.stroke()
    },
    [talking]
  )

  // ══ 卡通模式：完整角色绘制 ══

  const drawFace = (ctx, cx, cy, s, state, st) => {
    const e = state.exprCurrent
    const fg = ctx.createRadialGradient(cx - 10 * s, cy * 0.52, 5 * s, cx, cy * 0.55, 50 * s)
    fg.addColorStop(0, '#FFFFFF')
    fg.addColorStop(0.5, st.skin)
    fg.addColorStop(
      1,
      st.skin.replace('FF', 'E6').replace('D1', 'B0').replace('FA', 'E0').replace('FD', 'E0')
    )
    ctx.fillStyle = fg
    ctx.beginPath()
    ctx.ellipse(cx, cy * 0.55, 48 * s, 52 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = `rgba(255, 150, 150, ${e.blush})`
    ctx.beginPath()
    ctx.ellipse(cx - 28 * s, cy * 0.58, 10 * s, 6 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.ellipse(cx + 28 * s, cy * 0.58, 10 * s, 6 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = st.skin.replace('FF', 'E6').replace('D1', 'B0')
    ctx.beginPath()
    ctx.arc(cx, cy * 0.54, 3 * s, 0, Math.PI * 2)
    ctx.fill()
  }

  const drawEyes = (ctx, cx, cy, s, state, st) => {
    const e = state.exprCurrent
    const eyeY = cy * 0.48 - e.ea * 8 * s
    const blinkH = state.isBlinking ? lerp(14, 1.5, state.blinkProgress) : 14 * e.es
    const eyeW = 14 * s
    const irisW = 9 * s
    const pupilW = 5 * s
    for (const side of [-1, 1]) {
      const ex = cx + side * 18 * s
      ctx.fillStyle = '#FFF'
      ctx.beginPath()
      ctx.ellipse(ex, eyeY, eyeW, blinkH * s, 0, 0, Math.PI * 2)
      ctx.fill()
      if (blinkH > 3) {
        ctx.fillStyle = st.eye
        ctx.beginPath()
        ctx.ellipse(ex, eyeY, irisW, Math.min(blinkH * s, irisW), 0, 0, Math.PI * 2)
        ctx.fill()
        const pupilH = Math.min(blinkH * s * 0.55, pupilW)
        ctx.fillStyle = '#1a1a2e'
        ctx.beginPath()
        ctx.ellipse(ex, eyeY, pupilW, pupilH, 0, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = '#FFF'
        ctx.beginPath()
        ctx.arc(
          ex + 4 * s * e.sparkle * side,
          eyeY - 3 * s * e.sparkle,
          3 * s * e.sparkle,
          0,
          Math.PI * 2
        )
        ctx.fill()
        if (e.sparkle > 0.6) {
          ctx.beginPath()
          ctx.arc(ex - 3 * s * side, eyeY + 2 * s, 1.5 * s, 0, Math.PI * 2)
          ctx.fill()
        }
      }
    }
  }

  const drawEyebrows = (ctx, cx, cy, s, state, st) => {
    const e = state.exprCurrent
    ctx.strokeStyle = st.hair
    ctx.lineWidth = 2.5 * s
    ctx.lineCap = 'round'
    const by = cy * 0.36 - e.ea * 15 * s
    ctx.beginPath()
    ctx.moveTo(cx - 28 * s, by + e.ea * 8 * s)
    ctx.quadraticCurveTo(cx - 18 * s, by, cx - 10 * s, by + e.ea * 2 * s)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(cx + 10 * s, by + e.ea * 2 * s)
    ctx.quadraticCurveTo(cx + 18 * s, by, cx + 28 * s, by + e.ea * 8 * s)
    ctx.stroke()
  }

  const drawMouth = (ctx, cx, cy, s, state) => {
    const e = state.exprCurrent
    const open = state.mouthOpen
    const mouthY = cy * 0.65
    const p = state.phonemeCurrent
    if (open < 0.015) {
      ctx.strokeStyle = '#CC7777'
      ctx.lineWidth = 2 * s
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.arc(
        cx,
        mouthY + 2 * s,
        lerp(10, 14, e.mc) * s,
        0.1 + (1 - e.mc) * 0.3,
        Math.PI - 0.1 - (1 - e.mc) * 0.3,
        false
      )
      ctx.stroke()
    } else {
      const mh = Math.max(2.5, open * 38) * s * p.mh
      const mw = Math.max(8, 14 * s * p.mw)
      ctx.fillStyle = '#8B3333'
      ctx.beginPath()
      ctx.ellipse(cx, mouthY + mh * 0.3, mw, mh, 0, 0, Math.PI * 2)
      ctx.fill()
      if (open > 0.25) {
        ctx.fillStyle = '#E57373'
        ctx.beginPath()
        ctx.ellipse(cx, mouthY + mh * 0.5, mw * 0.55, mh * 0.45, 0, 0, Math.PI)
        ctx.fill()
      }
    }
  }

  const drawHair = (ctx, cx, cy, s, state, st) => {
    ctx.fillStyle = st.hairHi
    ctx.beginPath()
    ctx.ellipse(cx, cy * 0.55, 62 * s, 70 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = st.hair
    ctx.beginPath()
    ctx.moveTo(cx - 42 * s, cy * 0.25)
    ctx.quadraticCurveTo(cx - 50 * s, cy * 0.0, cx - 20 * s, cy * 0.05)
    for (let i = 0; i < 5; i++) {
      const bx = cx - 35 * s + i * 18 * s
      ctx.lineTo(bx - 8 * s, cy * 0.12)
      ctx.lineTo(bx + 8 * s, cy * 0.0)
    }
    ctx.lineTo(cx + 45 * s, cy * 0.15)
    ctx.quadraticCurveTo(cx + 58 * s, cy * 0.4, cx + 48 * s, cy * 0.7)
    ctx.lineTo(cx - 48 * s, cy * 0.7)
    ctx.quadraticCurveTo(cx - 58 * s, cy * 0.4, cx - 42 * s, cy * 0.25)
    ctx.fill()
    for (const side of [1, -1]) {
      ctx.fillStyle = st.hair
      ctx.beginPath()
      ctx.moveTo(cx + side * 46 * s, cy * 0.55)
      ctx.quadraticCurveTo(cx + side * 52 * s, cy * 0.8, cx + side * 42 * s, cy * 1.05)
      ctx.quadraticCurveTo(cx + side * 38 * s, cy * 0.85, cx + side * 48 * s, cy * 0.55)
      ctx.fill()
    }
  }

  const drawBody = (ctx, cx, cy, s, state, w, h) => {
    const breath = Math.sin(state.breathPhase) * 3 * s
    ctx.fillStyle = style.skin
    ctx.beginPath()
    ctx.roundRect(cx - 12 * s, cy * 0.85, 24 * s, 30 * s, 6 * s)
    ctx.fill()
    ctx.fillStyle = topColor
    ctx.beginPath()
    ctx.moveTo(cx - 55 * s, cy * 1.05 + breath)
    ctx.quadraticCurveTo(cx - 30 * s, cy * 0.9, cx - 10 * s, cy * 1.02)
    ctx.lineTo(cx + 10 * s, cy * 1.02)
    ctx.quadraticCurveTo(cx + 30 * s, cy * 0.9, cx + 55 * s, cy * 1.05 + breath)
    ctx.lineTo(cx + 70 * s, h * 1.1)
    ctx.lineTo(cx - 70 * s, h * 1.1)
    ctx.closePath()
    ctx.fill()
    ctx.fillStyle = bottomColor
    ctx.beginPath()
    ctx.moveTo(cx - 20 * s, cy * 0.95)
    ctx.quadraticCurveTo(cx, cy * 1.08, cx + 20 * s, cy * 0.95)
    ctx.quadraticCurveTo(cx, cy * 0.88, cx - 20 * s, cy * 0.95)
    ctx.fill()
    ctx.fillStyle = style.outfit[outfit]?.[1] || '#f5576c'
    ctx.beginPath()
    ctx.moveTo(cx, cy * 0.92)
    ctx.lineTo(cx - 6 * s, cy * 0.98)
    ctx.lineTo(cx, cy * 1.05)
    ctx.lineTo(cx + 6 * s, cy * 0.98)
    ctx.closePath()
    ctx.fill()
  }

  const drawArm = (ctx, cx, cy, s, state, side) => {
    const gPhase = state.handPhase
    const gType = state.gestureType
    ctx.save()
    const shoulderX = cx + side * 48 * s
    const shoulderY = cy * 0.98
    ctx.translate(shoulderX, shoulderY)
    let armAngle = side * 0.3
    let forearmAngle = side * 0.5
    if (gType === 0) {
      armAngle = side * 0.2 + Math.sin(gPhase * 0.7) * 0.1
      forearmAngle = side * 0.4 + Math.sin(gPhase * 0.8) * 0.08
    } else if (gType === 1) {
      armAngle = side * -0.4 + Math.sin(gPhase * 1.5) * 0.5
      forearmAngle = side * -0.6 + Math.cos(gPhase * 1.3) * 0.4
    } else if (gType === 2) {
      armAngle = side * -0.7 + Math.sin(gPhase * 0.5) * 0.2
      forearmAngle = side * -1.0 + Math.cos(gPhase * 0.6) * 0.15
    }
    ctx.strokeStyle = topColor
    ctx.lineWidth = 14 * s
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(0, 0)
    const armX = Math.sin(armAngle) * 35 * s
    const armY = Math.cos(armAngle) * 35 * s
    ctx.lineTo(armX, armY)
    ctx.stroke()
    ctx.translate(armX, armY)
    const faX = Math.sin(forearmAngle) * 30 * s
    const faY = Math.cos(forearmAngle) * 30 * s
    ctx.lineWidth = 10 * s
    ctx.beginPath()
    ctx.moveTo(0, 0)
    ctx.lineTo(faX, faY)
    ctx.stroke()
    ctx.fillStyle = style.skin
    ctx.beginPath()
    ctx.arc(faX, faY, 7 * s, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }

  // ══ 卡通模式主绘制 ══
  const drawCartoonCharacter = useCallback(
    (ctx, w, h, state, st, t) => {
      const s = Math.min(w, h) / 480
      const cx = w / 2
      const cy = h / 2
      ctx.clearRect(0, 0, w, h)
      const tilt = state.headTilt * 0.04
      ctx.save()
      ctx.translate(cx, cy * 0.7)
      ctx.rotate(tilt)
      ctx.translate(-cx, -cy * 0.7)
      const nod = state.nodAmount * 0.08
      ctx.translate(0, nod * s * 5)
      drawBody(ctx, cx, cy, s, state, w, h, t)
      drawArm(ctx, cx, cy, s, state, -1, t)
      drawArm(ctx, cx, cy, s, state, 1, t)
      ctx.fillStyle = st.hairHi
      ctx.beginPath()
      ctx.ellipse(cx, cy * 0.55, 62 * s, 70 * s, 0, 0, Math.PI * 2)
      ctx.fill()
      drawFace(ctx, cx, cy, s, state, st)
      drawEyes(ctx, cx, cy, s, state, st)
      drawEyebrows(ctx, cx, cy, s, state, st)
      drawMouth(ctx, cx, cy, s, state)
      drawHair(ctx, cx, cy, s, state, st, t)
      ctx.restore()
    },
    [style, topColor, bottomColor, outfit]
  )

  // ══ 动画循环 ══
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)

    const state = stateRef.current
    let last = performance.now()
    state.exprTarget = EXPRESSIONS[expression] || EXPRESSIONS.neutral

    const loop = (now) => {
      const dt = Math.min((now - last) / 1000, 0.1)
      last = now
      state.time += dt
      state.breathPhase += dt * 2.5

      // 眨眼
      state.blinkTimer += dt * 60
      if (!state.isBlinking && state.blinkTimer > state.nextBlink) {
        state.isBlinking = true
        state.blinkProgress = 0
        state.blinkTimer = 0
        state.nextBlink = 80 + Math.random() * 200
      }
      if (state.isBlinking) {
        state.blinkProgress += dt * 12
        if (state.blinkProgress >= 1) {
          state.isBlinking = false
          state.blinkProgress = 0
        }
      }

      // 表情过渡
      const et = state.exprTarget
      state.exprCurrent.ea = lerp(state.exprCurrent.ea, et.ea, dt * 5)
      state.exprCurrent.es = lerp(state.exprCurrent.es, et.es, dt * 5)
      state.exprCurrent.mc = lerp(state.exprCurrent.mc, et.mc, dt * 5)
      state.exprCurrent.blush = lerp(state.exprCurrent.blush, et.blush, dt * 5)
      state.exprCurrent.sparkle = lerp(state.exprCurrent.sparkle, et.sparkle, dt * 5)

      // 头部
      state.headTiltTarget += (Math.sin(state.time * 0.7) * 0.15 - state.headTiltTarget) * dt * 2
      state.headTilt += (state.headTiltTarget - state.headTilt) * dt * 3

      // 点头
      state.nodTarget += (Math.sin(state.time * 1.8) * 0.5 - state.nodTarget) * dt * 2
      state.nodAmount += (state.nodTarget - state.nodAmount) * dt * 4

      // 手势
      state.handPhase += dt
      if (state.handPhase > 8) {
        state.handPhase = 0
        state.gestureType = Math.floor(Math.random() * 3)
      }

      // 撩头发
      state.hairTouchTimer += dt
      if (!state.isHairTouching && state.hairTouchTimer > 5 + Math.random() * 10) {
        state.isHairTouching = true
        state.hairTouchProgress = 0
        state.hairTouchTimer = 0
      }
      if (state.isHairTouching) {
        state.hairTouchProgress += dt * 2
        if (state.hairTouchProgress > 1) {
          state.isHairTouching = false
          state.hairTouchTimer = 0
        }
      }

      // 口型 + 音素
      if (talking) {
        const { level, freq } = getAudioData()
        state.audioLevel = lerp(state.audioLevel, level, dt * 15)
        const ph = detectPhoneme(freq)
        state.phonemeTarget = ph
        const ps = PHONEME_SHAPES[ph] || PHONEME_SHAPES.a
        state.phonemeCurrent.mw = lerp(state.phonemeCurrent.mw, ps.mw, dt * 12)
        state.phonemeCurrent.mh = lerp(state.phonemeCurrent.mh, ps.mh, dt * 12)
        state.mouthTarget = Math.pow(state.audioLevel, 0.7) * 0.9
      } else {
        state.mouthTarget = 0
        state.phonemeCurrent.mw = lerp(state.phonemeCurrent.mw, 1, dt * 8)
        state.phonemeCurrent.mh = lerp(state.phonemeCurrent.mh, 1, dt * 8)
      }
      state.mouthOpen = lerp(state.mouthOpen, state.mouthTarget, dt * 20)

      // ★ 绘制模式切换
      if (usePortrait) {
        // 写真模式：只画口型动画覆盖层
        drawPortraitOverlay(ctx, width, height, state, state.time)
      } else {
        // 卡通模式：完整角色绘制
        const st = STYLES[avatarId] || STYLES['business-female']
        drawCartoonCharacter(ctx, width, height, state, st, state.time)
      }

      animFrame.current = requestAnimationFrame(loop)
    }
    animFrame.current = requestAnimationFrame(loop)
    return () => {
      if (animFrame.current) cancelAnimationFrame(animFrame.current)
    }
  }, [
    width,
    height,
    avatarId,
    talking,
    expression,
    outfit,
    scene,
    glasses,
    hat,
    usePortrait,
    getAudioData,
    detectPhoneme,
    drawCartoonCharacter,
    drawPortraitOverlay,
  ])

  // ══ 背景绘制 ══
  useEffect(() => {
    const bg = bgCanvasRef.current
    if (!bg) return
    const ctx = bg.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    bg.width = width * dpr
    bg.height = height * dpr
    ctx.scale(dpr, dpr)
    const drawFn = SCENE_BG[scene]
    if (drawFn) drawFn(ctx, width, height)
  }, [width, height, scene])

  // ══ 写真图片预加载 ══
  useEffect(() => {
    if (!portraitUrl) {
      setPortraitLoaded(false)
      setPortraitError(false)
      return
    }
    setPortraitLoaded(false)
    setPortraitError(false)
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => setPortraitLoaded(true)
    img.onerror = () => setPortraitError(true)
    img.src = portraitUrl
  }, [portraitUrl])

  return (
    <div className="relative overflow-hidden rounded-2xl" style={{ width, height }}>
      {/* 背景层 */}
      <canvas ref={bgCanvasRef} className="absolute inset-0" style={{ width, height }} />

      {/* ★ 写真层：AI 生成的真人肖像图片 */}
      {usePortrait && (
        <img
          src={portraitUrl}
          alt="AI数字人写真"
          className="absolute inset-0 w-full h-full object-cover"
          style={{ objectPosition: 'center 20%' }}
          crossOrigin="anonymous"
        />
      )}

      {/* 动画层：口型同步覆盖（写真模式）或 完整角色（卡通模式） */}
      <canvas
        ref={canvasRef}
        className={`absolute inset-0 ${className}`}
        style={{ width, height }}
      />

      {/* 写真模式的状态标签 */}
      {usePortrait && talking && (
        <div className="absolute top-2 right-2 bg-black/40 backdrop-blur-sm rounded-full px-2.5 py-0.5 text-[10px] text-emerald-300 font-medium animate-pulse">
          ● LIVE 口型同步
        </div>
      )}

      {/* 无写真时的提示（卡通模式） */}
      {!usePortrait && portraitUrl && !portraitLoaded && !portraitError && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-sm">
          <div className="text-white/80 text-xs animate-pulse">写真加载中...</div>
        </div>
      )}
    </div>
  )
})

export { AnimatedAvatar as default, EXPRESSIONS, SCENE_BG }
export const SCENE_NAMES = {
  office: '商务办公',
  studio: '虚拟演播室',
  nature: '自然户外',
  tech: '科技蓝幕',
}
export const OUTFIT_NAMES = { formal: '正装', casual: '休闲', tech: '科技', cute: '可爱' }
export const EXPRESSION_NAMES = {
  neutral: '自然',
  happy: '开心',
  surprised: '惊讶',
  sad: '悲伤',
  thinking: '思考',
}

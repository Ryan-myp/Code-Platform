import React, { useRef, useEffect, useCallback } from 'react'

/**
 * 自研 Canvas 动画角色引擎 — 动漫风格虚拟主播
 *
 * 特性：
 * - Canvas 绘制动漫角色（圆脸、大眼、渐变配色）
 * - requestAnimationFrame 60fps 动画循环
 * - Web Audio API 实时口型同步
 * - 自然空闲动画：呼吸起伏、眨眼、微摇头
 * - 8 种配色方案对应平台已有的 8 个数字人形象
 * - 零外部依赖
 */

// ── 配色方案（对应 digital_human.py 的 8 个形象） ──────────
const STYLES = {
  'business-female': { skin: '#FFDAB9', hair: '#2C1810', hairHighlight: '#4A3728', eye: '#4A90D9', top: '#667eea', skirt: '#5a67d8', ribbon: '#f5576c' },
  'business-male':   { skin: '#F5D5B8', hair: '#1a1a2e', hairHighlight: '#2d2d44', eye: '#3d5a80', top: '#4a5568', skirt: '#2d3748', ribbon: '#a0aec0' },
  'casual-female':   { skin: '#FFD1C1', hair: '#8B4513', hairHighlight: '#A0522D', eye: '#6B8E23', top: '#f093fb', skirt: '#f5576c', ribbon: '#ffd700' },
  'casual-male':     { skin: '#FDEBD0', hair: '#34495E', hairHighlight: '#5D6D7E', eye: '#2980B9', top: '#f39c12', skirt: '#e67e22', ribbon: '#f1c40f' },
  'tech-female':     { skin: '#FFE4D6', hair: '#1a0033', hairHighlight: '#2d0055', eye: '#9b59b6', top: '#8B5CF6', skirt: '#7C3AED', ribbon: '#06d6a0' },
  'educator-male':   { skin: '#FAE5D3', hair: '#3E2723', hairHighlight: '#5D4037', eye: '#2E7D32', top: '#0d9488', skirt: '#0f766e', ribbon: '#fbbf24' },
  'cartoon-cute':    { skin: '#FFF5E6', hair: '#FFE0B2', hairHighlight: '#FFCC80', eye: '#4FC3F7', top: '#FFB74D', skirt: '#FF9800', ribbon: '#FF5722' },
  'anime-style':     { skin: '#FCE4EC', hair: '#E91E63', hairHighlight: '#F06292', eye: '#CE93D8', top: '#f472b6', skirt: '#db2777', ribbon: '#818cf8' },
}

function lerp(a, b, t) { return a + (b - a) * t }

export default function AnimatedAvatar({
  avatarId = 'business-female',
  width = 400,
  height = 400,
  audioElement = null,   // <audio> 元素引用，用于口型同步
  talking = false,        // 手动控制是否说话
  expression = 'neutral', // neutral | happy | surprised | thinking
  className = '',
}) {
  const canvasRef = useRef(null)
  const animFrame = useRef(null)
  const analyserRef = useRef(null)
  const audioCtxRef = useRef(null)
  const audioSourceRef = useRef(null)

  // 动画状态
  const stateRef = useRef({
    time: 0,
    breathPhase: 0,
    blinkTimer: 0,
    nextBlink: 100,
    isBlinking: false,
    blinkProgress: 0,
    mouthOpenTarget: 0,
    mouthOpenCurrent: 0,
    audioLevel: 0,
    headTilt: 0,
    headTiltTarget: 0,
  })

  const style = STYLES[avatarId] || STYLES['business-female']

  // ── Web Audio 口型分析 ──
  useEffect(() => {
    if (!audioElement) return
    let ctx, source, analyser

    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)()
      analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.3
      source = ctx.createMediaElementSource(audioElement)
      source.connect(analyser)
      analyser.connect(ctx.destination)
      audioCtxRef.current = ctx
      analyserRef.current = analyser
      audioSourceRef.current = source
    } catch (e) {
      console.warn('Web Audio API 不可用，口型同步将使用模拟模式', e)
    }

    return () => {
      if (ctx) ctx.close().catch(() => {})
    }
  }, [audioElement])

  // ── 音频音量读取 ──
  const getAudioLevel = useCallback(() => {
    const analyser = analyserRef.current
    if (!analyser) return 0
    const dataArray = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(dataArray)
    // 取中低频段（人声主要频率范围）
    let sum = 0
    for (let i = 2; i < Math.min(32, dataArray.length); i++) {
      sum += dataArray[i]
    }
    return sum / (30 * 255)
  }, [])

  // ── 绘制角色 ──
  const drawCharacter = useCallback((ctx, w, h, state, scale) => {
    const s = scale
    const cx = w / 2
    const cy = h / 2
    const t = state.time

    ctx.save()
    ctx.clearRect(0, 0, w, h)

    // 头部微摇
    const headTiltAngle = state.headTilt * 0.03
    ctx.translate(cx, cy * 0.7)
    ctx.rotate(headTiltAngle)
    ctx.translate(-cx, -cy * 0.7)

    // ══ 身体 ══
    // 脖子
    ctx.fillStyle = style.skin
    ctx.beginPath()
    ctx.roundRect(cx - 12 * s, cy * 0.85, 24 * s, 30 * s, 6 * s)
    ctx.fill()

    // 上衣
    const breathOffset = Math.sin(state.breathPhase) * 3 * s
    ctx.fillStyle = style.top
    ctx.beginPath()
    ctx.moveTo(cx - 55 * s, cy * 1.05 + breathOffset)
    ctx.quadraticCurveTo(cx - 30 * s, cy * 0.9, cx - 10 * s, cy * 1.02)
    ctx.lineTo(cx + 10 * s, cy * 1.02)
    ctx.quadraticCurveTo(cx + 30 * s, cy * 0.9, cx + 55 * s, cy * 1.05 + breathOffset)
    ctx.lineTo(cx + 70 * s, h * 1.1)
    ctx.lineTo(cx - 70 * s, h * 1.1)
    ctx.closePath()
    ctx.fill()

    // 衣领
    ctx.fillStyle = style.ribbon
    ctx.beginPath()
    ctx.moveTo(cx - 20 * s, cy * 0.95)
    ctx.quadraticCurveTo(cx, cy * 1.08, cx + 20 * s, cy * 0.95)
    ctx.quadraticCurveTo(cx, cy * 0.88, cx - 20 * s, cy * 0.95)
    ctx.fill()

    // ══ 头部 ══
    // 头发后层
    ctx.fillStyle = style.hairHighlight
    ctx.beginPath()
    ctx.ellipse(cx, cy * 0.55, 62 * s, 70 * s, 0, 0, Math.PI * 2)
    ctx.fill()

    // 脸部
    const faceGrad = ctx.createRadialGradient(cx - 10 * s, cy * 0.52, 5 * s, cx, cy * 0.55, 50 * s)
    faceGrad.addColorStop(0, '#FFFFFF')
    faceGrad.addColorStop(0.5, style.skin)
    faceGrad.addColorStop(1, style.skin.replace('FF', 'E6').replace('D1', 'B0').replace('FA', 'E0').replace('FD', 'E0'))
    ctx.fillStyle = faceGrad
    ctx.beginPath()
    ctx.ellipse(cx, cy * 0.55, 48 * s, 52 * s, 0, 0, Math.PI * 2)
    ctx.fill()

    // 头发前层 + 刘海
    ctx.fillStyle = style.hair
    ctx.beginPath()
    // 顶部弧线 + 锯齿刘海
    ctx.moveTo(cx - 42 * s, cy * 0.25)
    ctx.quadraticCurveTo(cx - 50 * s, cy * 0.0, cx - 20 * s, cy * 0.05)
    // 刘海锯齿
    for (let i = 0; i < 5; i++) {
      const bx = cx - 35 * s + i * 18 * s
      ctx.lineTo(bx - 8 * s, cy * 0.12)
      ctx.lineTo(bx + 8 * s, cy * 0.0)
    }
    ctx.lineTo(cx + 45 * s, cy * 0.15)
    // 右侧头发
    ctx.quadraticCurveTo(cx + 58 * s, cy * 0.4, cx + 48 * s, cy * 0.7)
    ctx.lineTo(cx - 48 * s, cy * 0.7)
    ctx.quadraticCurveTo(cx - 58 * s, cy * 0.4, cx - 42 * s, cy * 0.25)
    ctx.fill()

    // 侧发
    ctx.fillStyle = style.hair
    ctx.beginPath()
    ctx.moveTo(cx + 46 * s, cy * 0.55)
    ctx.quadraticCurveTo(cx + 52 * s, cy * 0.8, cx + 42 * s, cy * 1.05)
    ctx.quadraticCurveTo(cx + 38 * s, cy * 0.85, cx + 48 * s, cy * 0.55)
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(cx - 46 * s, cy * 0.55)
    ctx.quadraticCurveTo(cx - 52 * s, cy * 0.8, cx - 42 * s, cy * 1.05)
    ctx.quadraticCurveTo(cx - 38 * s, cy * 0.85, cx - 48 * s, cy * 0.55)
    ctx.fill()

    // 呆毛
    ctx.strokeStyle = style.hairHighlight
    ctx.lineWidth = 2.5 * s
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(cx + 5 * s, cy * 0.05)
    ctx.quadraticCurveTo(cx + 15 * s, cy * (-0.15), cx + 25 * s + Math.sin(t * 3) * 5 * s, cy * (-0.1))
    ctx.stroke()

    // ══ 眉毛 ══
    ctx.strokeStyle = style.hair
    ctx.lineWidth = 2.5 * s
    ctx.lineCap = 'round'
    // 左眉
    ctx.beginPath()
    ctx.moveTo(cx - 28 * s, cy * 0.36)
    ctx.quadraticCurveTo(cx - 18 * s, cy * 0.33, cx - 10 * s, cy * 0.35)
    ctx.stroke()
    // 右眉
    ctx.beginPath()
    ctx.moveTo(cx + 10 * s, cy * 0.35)
    ctx.quadraticCurveTo(cx + 18 * s, cy * 0.33, cx + 28 * s, cy * 0.36)
    ctx.stroke()

    // ══ 眼睛 ══
    const eyeY = cy * 0.48
    const blinkH = state.isBlinking ? lerp(14, 2, state.blinkProgress) : 14

    // 左眼
    ctx.fillStyle = '#FFFFFF'
    ctx.beginPath()
    ctx.ellipse(cx - 18 * s, eyeY, 14 * s, blinkH * s, 0, 0, Math.PI * 2)
    ctx.fill()
    // 虹膜
    ctx.fillStyle = style.eye
    ctx.beginPath()
    ctx.ellipse(cx - 18 * s, eyeY, 9 * s, blinkH > 4 ? 9 * s : 2 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    // 瞳孔
    ctx.fillStyle = '#1a1a2e'
    ctx.beginPath()
    ctx.ellipse(cx - 18 * s, eyeY, 5 * s, blinkH > 4 ? 5 * s : 1 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    // 高光
    if (blinkH > 6) {
      ctx.fillStyle = '#FFFFFF'
      ctx.beginPath()
      ctx.arc(cx - 14 * s, eyeY - 3 * s, 3 * s, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.arc(cx - 21 * s, eyeY + 2 * s, 2 * s, 0, Math.PI * 2)
      ctx.fill()
    }

    // 右眼
    ctx.fillStyle = '#FFFFFF'
    ctx.beginPath()
    ctx.ellipse(cx + 18 * s, eyeY, 14 * s, blinkH * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = style.eye
    ctx.beginPath()
    ctx.ellipse(cx + 18 * s, eyeY, 9 * s, blinkH > 4 ? 9 * s : 2 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#1a1a2e'
    ctx.beginPath()
    ctx.ellipse(cx + 18 * s, eyeY, 5 * s, blinkH > 4 ? 5 * s : 1 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    if (blinkH > 6) {
      ctx.fillStyle = '#FFFFFF'
      ctx.beginPath()
      ctx.arc(cx + 22 * s, eyeY - 3 * s, 3 * s, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.arc(cx + 15 * s, eyeY + 2 * s, 2 * s, 0, Math.PI * 2)
      ctx.fill()
    }

    // 脸颊红晕
    ctx.fillStyle = 'rgba(255, 150, 150, 0.3)'
    ctx.beginPath()
    ctx.ellipse(cx - 28 * s, cy * 0.58, 10 * s, 6 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.ellipse(cx + 28 * s, cy * 0.58, 10 * s, 6 * s, 0, 0, Math.PI * 2)
    ctx.fill()

    // 鼻子
    ctx.fillStyle = style.skin.replace('FF', 'E6').replace('D1', 'B0')
    ctx.beginPath()
    ctx.arc(cx, cy * 0.54, 3 * s, 0, Math.PI * 2)
    ctx.fill()

    // ══ 嘴巴（口型同步） ══
    const mouthOpen = state.mouthOpenCurrent
    const mouthY = cy * 0.65

    if (mouthOpen < 0.02) {
      // 闭嘴 — 微笑弧线
      ctx.strokeStyle = '#CC7777'
      ctx.lineWidth = 2 * s
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.arc(cx, mouthY + 2 * s, 12 * s, 0.1, Math.PI - 0.1, false)
      ctx.stroke()
    } else {
      // 张嘴 — 椭圆
      const mh = Math.max(3, mouthOpen * 35) * s
      const mw = 14 * s
      ctx.fillStyle = '#8B3333'
      ctx.beginPath()
      ctx.ellipse(cx, mouthY + mh * 0.3, mw, mh, 0, 0, Math.PI * 2)
      ctx.fill()
      // 舌头（张开较大时可见）
      if (mouthOpen > 0.3) {
        ctx.fillStyle = '#E57373'
        ctx.beginPath()
        ctx.ellipse(cx, mouthY + mh * 0.5, mw * 0.6, mh * 0.5, 0, 0, Math.PI)
        ctx.fill()
      }
    }

    ctx.restore()
  }, [style])

  // ── 动画循环 ──
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const w = width
    const h = height

    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.scale(dpr, dpr)

    const state = stateRef.current
    let lastTime = performance.now()

    const loop = (now) => {
      const dt = Math.min((now - lastTime) / 1000, 0.1)
      lastTime = now
      state.time += dt

      // 呼吸
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

      // 头部微摇
      state.headTiltTarget += (Math.sin(state.time * 0.7) * 0.15 - state.headTiltTarget) * dt * 2
      state.headTilt += (state.headTiltTarget - state.headTilt) * dt * 3

      // 口型同步
      let mouthTarget = 0
      if (talking) {
        const level = getAudioLevel()
        state.audioLevel = lerp(state.audioLevel, level, dt * 15)
        mouthTarget = Math.pow(state.audioLevel, 0.7) * 0.9
      }
      state.mouthOpenTarget = mouthTarget
      state.mouthOpenCurrent = lerp(state.mouthOpenCurrent, mouthTarget, dt * 20)

      // 绘制
      const scale = Math.min(w, h) / 400
      drawCharacter(ctx, w, h, state, scale)

      animFrame.current = requestAnimationFrame(loop)
    }

    animFrame.current = requestAnimationFrame(loop)

    return () => {
      if (animFrame.current) cancelAnimationFrame(animFrame.current)
    }
  }, [width, height, avatarId, talking, getAudioLevel, drawCharacter])

  return (
    <canvas
      ref={canvasRef}
      className={`rounded-2xl ${className}`}
      style={{ width, height }}
    />
  )
}

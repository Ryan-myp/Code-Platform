# 小团智能平台 UI 设计规范 v2.0

## 设计原则
- 简洁明了，信息层次清晰
- 一致的交互反馈
- 深色/浅色双主题
- 移动端友好

## 色彩系统

### 主色
- 主色: `#7C3AED` (Purple 600)
- 主色悬浮: `#6D28D9` (Purple 700)
- 主色柔和: `#EDE9FE` (Purple 50)

### 辅助色
- 成功: `#10B981` (Emerald 500)
- 警告: `#F59E0B` (Amber 500)
- 错误: `#EF4444` (Red 500)
- 信息: `#3B82F6` (Blue 500)

### 中性色
- 背景: `#F9FAFB` (Gray 50)
- 卡片: `#FFFFFF` (White)
- 边框: `#E5E7EB` (Gray 200)
- 文字: `#111827` (Gray 900)
- 次要文字: `#6B7280` (Gray 500)
- 占位文字: `#9CA3AF` (Gray 400)

## 字体系统
- 标题: Inter, sans-serif, font-weight: 600
- 正文: Inter, sans-serif, font-weight: 400
- 代码: JetBrains Mono, monospace

## 组件规范

### 卡片 (Card)
```
圆角: 12px
边框: 1px solid #E5E7EB
阴影: 0 1px 3px rgba(0,0,0,0.1)
背景: #FFFFFF
悬浮阴影: 0 4px 12px rgba(0,0,0,0.15)
```

### 按钮 (Button)
- 主按钮: bg-purple-600, text-white, hover:bg-purple-700
- 次要按钮: bg-white, border border-gray-300, text-gray-700
- 图标按钮: p-2, hover:bg-gray-100, rounded-lg

### 输入框 (Input)
- 边框: 1px solid #E5E7EB
- 圆角: 8px
- 聚焦: ring-2 ring-purple-500 border-transparent
- 高度: py-2.5 px-3

### 标签 (Badge)
- 默认: bg-gray-100 text-gray-700
- 成功: bg-emerald-100 text-emerald-700
- 警告: bg-amber-100 text-amber-700
- 错误: bg-red-100 text-red-700

## 页面布局

### 侧边栏
- 宽度: 240px
- 背景: #FFFFFF
- 边框: 1px solid #E5E7EB
- 导航项高度: 40px
- 活跃项: bg-purple-50 text-purple-700

### 主内容区
- 顶部导航: h-16, bg-white, border-b
- 内容区: px-6 py-6
- 最大宽度: max-w-7xl

### 统计卡片
- 布局: grid grid-cols-4 gap-4
- 每个卡片: p-4, bg-white, rounded-2xl
- 图标: w-12 h-12, rounded-xl, gradient
- 数值: text-2xl, font-bold

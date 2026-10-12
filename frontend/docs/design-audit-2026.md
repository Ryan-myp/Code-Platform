# 全站设计走查报告（2026-07-10）

> 范围：79 个页面。方法：CDP 1440×900 截图扫描 12 代表页 + 代码模式审计。
> 原则：不替换现有设计身份（紫 brand / 渐变 tile / rounded-xl 卡片），只做「统一 + 提质」。
> 纪律：baseline-ui（单一 accent / 空态必有下一步 / tabular-nums / 200ms 内反馈 / h-dvh）。

## 一、发现的确定性问题（截图证据）

### P0 视觉缺陷（用户一眼可见）
| # | 页面 | 问题 | 证据 |
|---|------|------|------|
| V1 | 图片工厂 | Tab 双行标签断词换行（"文生图/像"、"AI 润/色"、"随机提/词"） | d1_image.png |
| V2 | 需求看板 | 卡片头部不一致：标题位置两卡不同；`in_progress` 原文未中文化；标题与描述同句重复 | d1_board.png |
| V3 | 收藏中心 | 空态文案窄容器断词（"快捷访/问"） | d1_favorites.png |
| V4 | 股票分析 | 全宽紫色「创建定时任务」按钮过强，主 CTA 层级混乱 | d1_stock.png |
| V5 | 多页 | PageHeader 两种形态混用：有的带渐变图标 tile，有的纯文字；24 页完全不用 PageHeader | d1_*.png 对比 |

### P1 系统性问题（代码审计）
| # | 问题 | 规模 |
|---|------|------|
| S1 | Token 漂移：`gray-*` 直用而非 `ink-*`/品牌 token | 73/78 页 |
| S2 | 空态不统一：有的无 CTA（违反「空态必须有一个清晰下一步」） | ~15 页 |
| S3 | 手写 StatCard 样式不一致（text-2xl font-bold 各自实现） | ~20 页 |
| S4 | 表格/列表页无统一 Toolbar（筛选+搜索+批量操作各写各的） | ~12 页 |
| S5 | 数据区未用 `tabular-nums`（数字列跳动） | 数字密集页 |

## 二、分批方案

- **Batch A 设计语言标准化**（全局）：ui 原语补强（StatCard/SectionTitle/Toolbar/统一 Empty）→ 修 V1–V5 → 24 页 PageHeader 归一 → 空态全量补 CTA
- **Batch B 研发系**：board 卡片规范（V2）/ sandbox / pipelines / evolution / agent-execute
- **Batch C 工坊系**：image-factory（V1）/ ppt / video / game / meme / music / short-drama / translation / dubbing —— 统一「左侧参数 + 右侧结果」骨架
- **Batch D 工具数据系**：stock（V4）/ data-analyzer / doc-qa / excel / forecast / dashboard / ab-testing / usage / strategy / monitor / pdf / batch / web-search / code-interpreter / mindmap / digital-human / voice
- **Batch E 社区会员系**：publish / gallery / membership / tasks / records / notifications / favorites（V3）/ projects / api-platform / scheduler / plugins / admin / audit / search

每批交付：截图 QA → 构建 + 121 测试全绿 → 提交。

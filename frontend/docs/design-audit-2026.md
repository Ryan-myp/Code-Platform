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

## 三、执行结果（2026-07-10 全量走查完成）

| 批次 | 提交 | 修复 |
|------|------|------|
| Batch A 设计语言 | `187f943` | V1 tab 断词 / V2 看板卡片 / V3 空态 CTA / V5 头部归一 PageHeader（stock·tasks·membership·records·favorites·notifications） |
| Batch B+C 研发/工坊 | `f9fedcf` | 沙箱状态 ready 裸露 / 停止启动按钮降权 / 流水线断词 / 进化中心任务类型中文化 / 小游戏·小程序按钮竖排 |
| Batch D+E 工具数据/社区会员 | `0455d33` | **P0: 仪表盘布局事故（旧版 JSX 块插入新卡片循环中间）/ 数字人页 Sliders 未导入崩溃** / PDF done 裸露 / 用量模块英文 key / 发布 chip 断词 / 作品广场缩略图 4:3 |
| 收尾 | `13fbe3d` | 数字人卡片头 nowrap 防护 / 作品广场视频 4:3 |
| P0 功能批 | 本次 | **/chat teams.filter 崩溃（/api/teams 返回包装结构 {teams,total}）/ TeamsPage 同款解包 / 工作流卡片日期统一绝对格式 / Skills chip nowrap** |

已达标未动（截图验证）：tool-hub / stock(布局) / agents / knowledge / ppt / video / meme / music / copy / translate / excel / pdf(布局) / batch / doc-qa / forecast / ab / usage(数值) / web-search / digital(布局) / voice / mind-map / strategy / monitor / api-platform / scheduler / templates / gallery(卡片) / publish(布局) / projects / help / seo。

### 系统性沉淀
- `/tmp/check_missing.py`：扫描 79 页「用了但未导入/定义」大写标识符（lucide 漏导），已发现并修复 DigitalHuman(Sliders/ChevronDown)；建议纳入 CI pre-commit。
- 已知遗留（低优先）：token 漂移 gray-*→ink-*（73 页，无视觉差）；仪表盘快捷搜索/快捷入口旧卡片被删后未在新版补回（新版只有统计卡+趋势图，功能已由 ⌘K + 首页承接）。


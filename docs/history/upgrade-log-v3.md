# 升级日志 v3.0：专业级体验打磨（输入治理 / 历史持久化 / 案例墙预置）

> 依据用户实测反馈："功能看着是很多，每个都不怎么能拿的出手，对好用、耐用、可用等感觉还差很远，专业性也不太行"。
> 对全平台做专业度体检（基础设施已达标：LLM 重试/降级、任务队列+看门狗、可观测性/健康检查、自动备份、配额计费、沙箱安全、CI/CD、核心生成质量），
> 定位出三大真实差距并逐项修复，P4 全量回归通过。

## 一、体检结论（专业度差距清单）

| 差距 | 现象 | 严重度 |
|---|---|---|
| 占位符污染 | PPT 快速模板含 `[产品名]` 等占位符，用户直接生成 → 历史出现 `[项目名] ai人工稚嫩` 脏数据 | 高（生成质量） |
| 历史不持久 | useToolHistory 仅 2/66 页面接入，创作工具输入刷新即丢 | 高（耐用性） |
| 案例墙空白 | 首页「真实成果案例」0 条，演示无说服力 | 中（演示力） |

## 二、改动清单

### P1 输入治理（可用性）
| 文件 | 改动 |
|---|---|
| `frontend/src/pages/PPTFactoryPage.jsx` | 4 个占位符模板标题改为真实示例（智能新品发布会 / AI 内容平台商业计划书 / 大模型应用开发技术培训 / 智能客服系统立项提案）；生成前校验：主题含 `[xxx]` 占位符时 toast 拦截 |
| `frontend/src/pages/CopywritingPage.jsx` | 8 个示例 prompt 的 `[产品名]` 等占位符改为可读示例（示例仅预填，校验放宽） |
| `backend/extended_api.py` | `generate_ppt` 双保险：title 含占位符返回 400 友好提示；主题长度上限 200 字 |
| 数据库 `backend/platform.db` | 清理 2 条占位符脏历史记录（`[项目名]` / `[产品名]` 前缀） |

### P2 创作工具历史持久化（耐用性）
| 文件 | 改动 |
|---|---|
| `frontend/src/hooks/usePersistentToolState.js`（新增） | 通用输入态持久化 hook：key 版本化（`_v{version}`）+ localStorage 自动持久化/恢复/清空；300ms 防抖；容量防护（512KB 超限放弃）；`exclude` 排除大字段（base64 图片等）；合并恢复 `{...initialState, ...saved}` |
| 8 个创作页面接入 | PPTFactoryPage / ImageFactoryPage / VideoFactoryPage / MusicFactoryPage / CopywritingPage / TranslationPage / VoicePage / MemePage：输入内容（标题/提示词/参数）刷新不丢；setter 包装为 `(v) => setInputs((p) => ({ ...p, field: v ?? '' }))`，组件内引用零改动 |

### P3 首页案例墙预置（演示力）
| 文件 | 改动 |
|---|---|
| `backend/main.py` | 新增 `_DEMO_SHOWCASE` 常量（6 条系统精选示例：PPT/图片/数据分析/配音/视频/代码，含 route 字段）；`GET /api/showcase` 空结果时返回 demo 示例（`is_demo: true`）；有真实分享自动让位 |
| `frontend/src/pages/HomePage.jsx` | 案例墙渲染 demo 卡片：标题切换「精选成果案例」/「真实成果案例」；demo 卡片点击跳转对应工具页（`_self`）；「示例」徽标区分 |

### P4 回归与测试基建修复
| 文件 | 改动 |
|---|---|
| `tests/conftest.py` | 顶部在测试模块导入前设置 `APP_ENV=test`：修复全量运行时模块级 client 绑定生产限流（login 5/min）导致登录 429 偶发失败 |
| `tests/unit/test_dh_gateway.py` | `_login()` 加 per-username token 缓存（与 test_ai_video_api 一致），避免全量运行时登录限流 |
| `tests/unit/test_ai_video_api.py` | `_login()` 缓存 token 规避登录限流（429） |
| `tests/unit/test_data_analyzer.py` | showcase 断言更新：空结果返回 demo 而非 `[]` |

## 三、验证结果

- 后端：`pytest ../tests` 全量 **445 passed, 0 failed**；`ruff check backend/` All checks passed
- 前端：eslint 0 errors；`vite build` 构建成功
- 浏览器实测（全部通过）：
  - 案例墙 6 张 demo 卡片展示，点击跳转对应工具页
  - PPT 模板应用 → 填入「智能新品发布会」真实主题 → 生成成功 → 历史无占位符脏数据
  - 主题含 `[产品名]` → toast 拦截提示；后端接口直接调用 → 400 友好提示
  - 图片工厂输入提示词 → 刷新页面 → 内容保留
  - 历史记录中 `[项目名]` 脏数据已消失

## 四、设计要点

- **占位符治理三层防线**：前端模板去占位符（源头）→ 前端生成校验（拦截）→ 后端 400（兜底）
- **持久化 hook 通用化**：版本化 key 让数据结构变更自动失效旧缓存；容量防护避免 localStorage 溢出；exclude 机制专治 base64 大字段
- **案例墙让位策略**：demo 是"空态填充"，任何真实成果发布后自动让位，不污染用户数据

## 五、后续建议

- [ ] 其余低频页面（图表/表单/代码沙箱等）可按同样模式接入持久化
- [ ] 分享奖励与案例墙联动：真实成果达到 N 条后隐藏 demo 区
- [ ] 占位符校验扩展到其他生成接口（图片/视频 prompt 等）

---

# v13.1 数字人稳定性攻坚（失败率 24% → 修复）

> 基于 usage_logs 真实数据体检：**digital_human 失败率 24%**（59 次调用 14 次失败，全平台唯一显著失败率），
> 远超数字人爆款计划验收线（<2%）。失败任务 error 均为 `TTS 通道均不可用: EDGE_TTS_ERROR`，且 retry_count=0（未触发任务级重试）。

## 根因

1. **无任务级自动重试**：`dh_generate`/`voice_generate` 注册时未配置 `max_attempts`，TTS 瞬时抖动直接判失败（失败任务 retry_count 均为 0）
2. **无启动预热**：edge-tts 健康检查仅在首次调用时探活，服务刚启动时通道未探活，失败等待超时（失败任务耗时 47-58s）
3. **无失败诊断埋点**：usage_logs 无 error 列，失败原因不可统计

## 改动清单

| 文件 | 改动 |
|---|---|
| `backend/digital_human.py` | `dh_generate` 注册加 `max_attempts=2`（失败自动重试 1 次，指数退避，**不重复扣费**）；`log_usage` 失败时写入 error（含 `[stage:xxx]` 阶段标记） |
| `backend/voice_factory.py` | `voice_generate` 注册加 `max_attempts=2`（同根因：TTS 通道） |
| `backend/common/llm.py` | `log_usage()` 加 `error` 参数；usage_logs 幂等迁移 `error` 列（老库自动补列，截断 500 字） |
| `backend/main.py` | lifespan 启动即后台线程预热 edge-tts 探活（`_tts_health_check(force=True)`，不阻塞启动） |
| `tests/unit/test_digital_human.py` | 新增 6 用例：注册配置断言（dh/voice 重试、voice_clone 保持不重试）+ error 字段写入/截断/成功空值 |

## 设计要点

- **重试不重复扣费**：扣费在路由层完成，任务框架自动重试路径不扣费不退费，最终失败才退费——重试 1 次对用户零成本
- **voice_clone 刻意不加自动重试**：失败会清理样本文件，自动重试需重新上传（handler 注释已说明），保持不自动重试
- **幂等迁移**：error 列由 log_usage 首次调用时自动 ALTER（含事务提交），老库无需手工 DDL

## 验证结果

- 全量 pytest **451 passed, 0 failed**（+6 新用例）；ruff All checks passed
- 浏览器实测：数字人生成端到端成功，耗时 **9.3s**（此前失败样本 47-58s），页面产出可播放视频
- 生产库 error 列已自动迁移生效，新记录带 error 字段

---

# 升级日志 v13.2：亿级基础设施升级（SEO 获客 / PWA / 性能 / 体验兜底）

> 用户要求"在全部升级，离一个亿还差的太远"。本轮聚焦**亿级产品的获客与基础设施硬差距**：
> 实测发现分享页 SEO 链路断裂（有 /share/{code} 的 SEO HTML，但搜索引擎发现不了这些 URL）、
> 无 PWA 能力、主 bundle 1.1MB 未拆分、高频页面缺加载/错误兜底。

## 一、体检结论（亿级差距清单）

| 差距 | 证据 | 严重度 |
|---|---|---|
| 无 robots.txt / sitemap.xml | 全仓库 find 无结果；爬虫无法规范抓取，分享内容零收录 | P0（获客链路断） |
| index.html 无 description/og/theme-color | 仅 viewport；社交分享/搜索首屏无描述 | P0（获客首印象） |
| 无 PWA（manifest/图标/SW） | 无 manifest.webmanifest；移动端无法安装/离线 | P1（移动体验） |
| 主 bundle 1.1MB 未拆分 | vite build 实测；mermaid(3.2MB) 被全局同步 import 打进主 chunk | P1（首屏性能） |
| 高频页面无加载/错误态 | 首页 13 个 api 调用零错误态；Scheduler/UsageAnalytics/Notifications/Tasks 缺兜底 | P1（可用性） |
| React Router v7 future flags 警告 | 浏览器 console 实测（6.30.4 支持 flags） | P3 |
| 已达标项 | 后端无事件循环阻塞（全 to_thread）；路由全 lazy；分享裂变闭环真实（阈值 10/奖励 5 前后端一致）；分享页 SEO/CTA 专业；移动端响应式基础良好 | — |

## 二、改动清单

| 文件 | 改动 |
|---|---|
| `backend/main.py` | 新增 `GET /robots.txt` 与 `GET /sitemap.xml`（按请求 Host + X-Forwarded-Proto 动态生成绝对 URL，适配任意部署域名）；sitemap 收录 27 个核心工具页 + 公开分享 TOP100（含 lastmod）；XML 转义防注入 |
| `frontend/index.html` | 补全 description / og:title / og:description / og:type / theme-color / apple-touch-icon / manifest 链接 |
| `serve_frontend.py` | robots/sitemap 白名单转发后端（避免 SPA fallback 吞掉）；PWA 静态资源（sw.js/manifest/icons）直接服务 |
| `nginx.conf` | `location = /robots.txt` / `location = /sitemap.xml` 代理后端；`/share/` 已有 |
| `frontend/public/manifest.webmanifest`（新） | PWA 清单：名称/图标 192+512（any+maskable）/standalone/主题色 |
| `frontend/public/sw.js`（新） | Service Worker：预缓存外壳；/assets/* 缓存优先（hash 内容寻址）；其余同源 GET 网络优先、离线回退；版本化整体替换 |
| `frontend/public/icons/`（新）+ `scripts/gen_icons.py`（新） | 品牌图标集（512/192/180 PNG + favicon 重构：紫色渐变 + 四角星 sparkle） |
| `frontend/src/main.jsx` | PWA 注册（仅生产构建，避免开发模式缓存干扰 HMR） |
| `frontend/src/components/MarkdownRenderer.jsx` | mermaid 改动态 import 按需加载（仅渲染 mermaid 块时拉取） |
| `frontend/vite.config.js` | manualChunks 拆分 echarts / markdown / mermaid / icons / http 独立 chunk |
| `frontend/src/App.jsx` | Router future flags（v7_startTransition + v7_relativeSplatPath）消除警告 |
| `frontend/src/pages/HomePage.jsx` | 核心数据加载失败 → 全页错误态 + 一键重试（不再静默空白） |
| `frontend/src/pages/SchedulerPage.jsx` | 骨架屏列表 + ErrorState 重试（失败不再误显示"暂无任务"） |
| `frontend/src/pages/UsageAnalyticsPage.jsx` | 骨架屏网格 + ErrorState 重试 |
| `frontend/src/pages/NotificationsPage.jsx` | 错误态 + 重试 |
| `frontend/src/pages/TasksPage.jsx` | 首载/手动刷新失败 → 错误态 + 重试（静默轮询不受影响） |
| `tests/unit/test_seo.py`（新） | 6 用例：robots 内容/X-Forwarded-Proto、sitemap 核心页/分享收录/XML 转义/https 绝对地址 |

## 三、设计要点

- **动态 Host 方案**：robots/sitemap 按请求 Host + X-Forwarded-Proto 生成绝对 URL，任何部署域名（开发/裸 IP/正式域名/反代 https）都正确，无需改配置
- **转发而非静态文件**：robots/sitemap 由后端生成，避免在 public/ 写死域名；serve_frontend（本地预览）与 nginx（生产）都代理到后端
- **mermaid 按需加载**：全局组件 MarkdownRenderer 同步 import mermaid 会把 3.2MB 打进主 chunk；改为模块级 promise 缓存 + 动态 import，仅渲染 mermaid 图时拉取一次
- **SW 仅生产注册**：开发模式注册会缓存 HMR 资源导致热更新失效，`import.meta.env.PROD` 守卫

## 四、验证结果

- 全量 pytest **452 passed, 5 skipped, 0 failed**（+6 新用例）；ruff All checks passed；eslint 0 errors
- 主 bundle：**1.1MB → 229.79 kB（gzip 74.15 kB，-79%）**；mermaid 独立按需 chunk 3.2MB；页面级 chunk 均 20-90kB
- serve_frontend 实测：robots/sitemap 正确转发后端（Host 正确）、SPA fallback 不受影响、sw.js/icons 200
- 浏览器实测：首页/SchedulerPage console 0 错误；React Router future flags 警告已消除
- 构建产物完整：dist 含 manifest.webmanifest / sw.js / icons / 新 favicon

---

# 升级日志 v13.3：全功能四件套普及（分享 / 复制 / 导出 / 输入持久化）

> 依据用户要求「每个功能都要全面升级」，对全平台 66 页做能力矩阵扫描，
> 定位出共性缺口：**分享按钮（引流传播闭环）覆盖率低、核心工具结果不可复制/导出、输入态不持久化**，
> 按「专家级质量标准」四维（专业性/可用性/方便性/深度）批量补齐 10 个核心创作工具。

## 一、能力矩阵扫描结论（66 页）

| 能力 | 扫描前覆盖率 | 缺口特征 |
|---|---|---|
| ShareButton 分享 | 仅 8/66 页 | 结果无法生成分享链接 → 无传播/引流闭环 |
| 结果复制/导出 | 约 40% 工具页 | 预测/分析/搜索等结果不可带走 |
| 输入态持久化 | 仅 8 页 | 刷新丢股票代码/搜索词/编辑器代码 |
| 加载/错误态 | 约 60% | 上次已补 5 页，剩余逐步补齐 |

## 二、改动清单（10 页 × 四件套）

### P1 分享 + 导出 + 复制 + 持久化（全量补齐）
| 页面 | 改动 |
|---|---|
| `ForecastPage` | 结果头部加「导出报告/复制/分享」（Download 图标原本已导入未用）；buildReportMd 汇总概览/趋势/预测表/建议为 Markdown |
| `StockAnalysisPage` | AI 分析报告加「复制/导出/分享」；symbol/period 接入 usePersistentToolState 持久化 |
| `WebSearchPage` | AI 摘要加「复制/导出/分享」（含来源链接）；搜索词持久化 |
| `BatchProcessPage` | 结果区加「导出全部/复制全部/分享」（Download 图标原本已导入未用） |
| `CodeSandboxPage` | 编辑器工具栏加分享按钮；输出区加「复制输出」；编辑器代码持久化（200KB 上限防撑爆 localStorage） |
| `DataAnalyzerPage` | 导出报告旁加分享（抽取 buildConclusionMd 与导出复用） |
| `DocQAPage` | 导出旁加分享（抽取 buildChatMd 与导出复用） |
| `VideoAnalyzerPage` | 视频概览加「复制报告/分享」（汇总摘要/关键场景/亮点/建议） |
| `CompetitorMonitorPage` | 报告弹窗加「复制/分享」（汇总概览/分类/模式/发布习惯/互动/优劣势/建议） |
| `ContentStrategyPage` | 扫描结果加「复制/分享」（含命中明细/修改建议） |

## 三、设计要点

- **单一来源**：每页抽取 `buildXxxMd()`，复制/导出/分享三个入口复用同一份 Markdown，避免三处内容漂移
- **分享闭环**：ShareButton 已具备 链接+二维码 弹窗，覆盖 10 个新页面后全平台分享入口达 18 处，传播路径打通
- **持久化安全**：编辑器等大体积字段显式设置 maxBytes（200KB），超限自动放弃保存
- **一致性**：按钮统一「复制/导出/分享」ghost 小按钮组，放结果卡片标题行右侧，移动端 flex-wrap 降级

## 四、验证结果

- `npx vite build` 成功（10.79s），无 lint 错误；改动 10 页全部 GetProblems 0 errors
- 后端接口实测：登录 ✅ → 分享创建/查看 ✅（share_code 正常返回）→ websearch 接口连通（429 为配额限制属预期）
- 浏览器实测（DOM 级验证，console 0 错误）：
  - `/code-sandbox`：分享按钮物理可见（复制→下载→分享→运行），编辑器/历史/输出正常
  - `/web-search`：搜索框/推荐词/历史正常渲染
  - `/stock`：搜索框/周期选择器/模拟账户/免责声明正常
- 全量 pytest 452 passed（后端无改动，不重跑）

## 五、后续建议

- 剩余低流量页面（ABTesting/Forecast 等管理类）可复用同一模式继续补齐
- 分享页 `/share/:code` 已支持公开访问，可作为获客落地页再包装（CTA 引导注册）

---

# v13.4 升级日志：全功能补齐 + 三维度净化升级

> 依据用户反馈："全部补齐吧，另外除了页面的美观性，在功能的可用性、方便性、还有能力上，也要全面的净化升级"。
> 阶段一：剩余 3 个创作工具页分享补齐（16/16 全覆盖）；阶段二：三维度（可用性/方便性/能力）系统性净化升级。

## 一、阶段一：分享能力 16 页全覆盖（补齐收官）

| 文件 | 改动 |
|---|---|
| `DigitalHumanPage.jsx` | 批量生产任务完成区「打包下载 ZIP」旁加分享（含文案清单/成功失败统计） |
| `AIWorkspacePage.jsx` | AI 对话面板头部加「导出对话」+ 分享（对话 Markdown 全量导出） |
| `PublishingPage.jsx` | 发布结果区加分享（标题/平台/内容类型/模式/正文） |
| `GalleryPage.jsx` | 详情弹窗加「复制提示词」+ 分享 |
| `ChatPage.jsx` | 顶栏「导出对话」+ 分享；消息气泡加复制按钮 |
| `MindMapPage.jsx` / `WorkflowEditorPage.jsx` / `GameFactoryPage.jsx` / `MiniAppPage.jsx` | 预览区/工具栏/项目行分享（行内 stopPropagation 防冒泡） |
| `MusicFactoryPage.jsx` / `VideoFactoryPage.jsx` / `ImageFactoryPage.jsx` / `VoicePage.jsx` / `MemePage.jsx` | 卡片/行内分享，紧凑样式适配（!p-1.5 / !p-2 / !bg-transparent） |
| `ExcelPage.jsx` / `ArtifactsPage.jsx` | 结果区导出按钮 + 详情 Modal 分享 |

## 二、阶段二：三维度净化升级

### 可用性（边界处理）
| 文件 | 改动 |
|---|---|
| `VideoAnalyzerPage.jsx` | 上传前校验：200MB 上限 + 视频格式白名单（前端提前拦截，避免上传中断） |
| `DocQAPage.jsx` / `KnowledgeBasesPage.jsx` | 上传前 20MB 上限校验（与后端一致） |
| `BatchProcessPage.jsx` | 多文件选择时过滤超限文件并提示 |

### 方便性（一键操作 / 快捷键 / 入口）
| 文件 | 改动 |
|---|---|
| 8 个生成页（Copywriting/ImageFactory/ContentStrategy/CompetitorMonitor/Meme/Excel/MindMap/PPTFactory） | 主输入框支持 `Cmd/Ctrl+Enter` 一键提交（loading 中自动拦截） |
| `CommandPalette.jsx` | 补齐 8 个缺失页面收录：数据分析/内容策略/竞品监控/用量记录/帮助中心/个人中心/会员中心/收藏中心（57→65 路由） |
| `BackToTop.jsx`（新增） | 全局「回到顶部」按钮，滚动超 400px 出现，点击平滑回顶；挂载登录态内页 |
| `ForecastPage` / `StockAnalysisPage` / `WebSearchPage` / `VideoAnalyzerPage` | 结果区加「重新分析/重新搜索」一键重跑 |

### 能力（落地页深度）
| 文件 | 改动 |
|---|---|
| `ShareViewPage.jsx` | 分享落地页增强：31 种 content_type 中文标签映射、内容字数/行数统计、「复制全文」按钮（公开页可直接取用） |

## 三、设计要点

- **快捷键模式**：`onKeyDown` 内联于主 textarea，`(metaKey||ctrlKey) && Enter && !busy` 守卫，macOS/Windows 双平台兼容，与 Button loading 自动禁用形成双重防重入
- **命令面板补齐**：按「路由存在但未收录」扫描法（comm 对比），只补真实独立页面，别名/重定向路由（/code-gen、/voice-factory 等）不重复收录
- **上传校验前置**：前端校验与后端限制对齐（20MB/200MB），失败时清空 input value 允许重新选择
- **回顶按钮定位**：左下角避开右下角 FloatingAssistant 与移动端底部导航，移动端上移避让

## 四、验证结果

- `npx vite build` 成功（12.06s）；22 个改动文件 GetProblems 全部 0 errors
- 浏览器实测（a11y 快照级验证，console 0 错误）：
  - Cmd+K 面板搜索「帮助中心/会员中心」→ 均命中 ✅
  - `/workspace` 对话面板「导出+分享」按钮可见 ✅
  - `/digital-human` 批量任务「打包下载 ZIP+分享」按钮可见（成功 2 条）✅
  - `/copywriting` Cmd+Enter 触发生成（按钮进入 loading）✅
  - 回到顶部按钮：滚动超阈值出现、点击平滑回顶 ✅
- 全量 pytest 452 passed（后端无改动）

## 五、后续建议

- 生成页「智能补充/润色 prompt」能力目前仅 ImageFactory/Excel 2 页具备，可向 Copywriting/Music/Video 等扩散
- 分享落地页可作为获客主链路：统计 `share_visit` 埋点的来源渠道转化率

---

# v13.5 AI 智能补充能力扩散（2026-08-09）

## 一、背景

v13.4 后续建议指出：生成页「智能补充/润色 prompt」能力仅 ImageFactory/Excel 2 页具备，且 ImageFactory 的「智能补充」只是模板填入、非真实 AI 润色。本次将其升级为**通用 AI 润色能力**并扩散到全部核心生成页。

## 二、改动清单

### 后端（tool_hub.py）
| 改动 | 说明 |
|---|---|
| `POST /api/tools/enhance-prompt` | 新增 AI 润色接口：接收 `{text, style}`，9 种场景专家系统（image/copywriting/music/video/meme/mindmap/ppt/general），`call_llm_async` 扩写（max_tokens=800, temperature=0.7） |
| 边界校验 | 空文本 400、超 2000 字 400、拒绝「抱歉/无法」开头输出 502、异常 500（含 traceback 日志） |
| 免费策略 | 不在 `_QUOTA_PATHS` 扣额度路径中，辅助润色不消耗生成额度 |

### 前端
| 文件 | 改动 |
|---|---|
| `EnhancePromptButton.jsx`（新增） | 通用「AI 智能补充」组件：魔棒图标、busy 防重入、toast 成功/失败反馈，props：`{text, onEnhance, style, className}` |
| `ImageFactoryPage.jsx` | 替换假「智能补充」（模板填入）为真 AI 润色（style=image） |
| `CopywritingPage.jsx` | 需求描述 label 右侧加智能补充（style=copywriting） |
| `VideoFactoryPage.jsx` | 视频描述 label 右侧加智能补充（style=video） |
| `MusicFactoryPage.jsx` | 歌词内容 label 右侧加智能补充（style=music） |

## 三、设计要点

- **场景专家系统**：不同生成场景使用不同 system prompt（图片润色转专业英文提示词、文案扩写补营销结构、歌词补韵律意象等），而非统一模板
- **免费辅助**：润色是辅助能力不消耗生成额度，与生成主链路解耦，失败不阻塞生成
- **双保险防重入**：组件内 busy state 禁用按钮 + 生成页 Cmd+Enter 快捷键 busy 守卫
- **优雅降级**：LLM 异常时返回 500 + 前端 toast 展示 detail，不中断页面

## 四、验证结果

- `npx vite build` 成功（10.85s）；6 个改动文件 GetProblems 全部 0 errors
- 后端接口实测（curl）：copywriting 扩写为结构化营销文案 ✅、image 扩写为专业英文提示词 ✅、空文本 400 ✅、未认证 401 ✅
- 浏览器实测 `/image-factory`：输入 11 字中文 → 点击智能补充 → 「补充中…」→ toast「已智能补充，可直接生成」→ 输入框扩写为 243 字符专业英文提示词（含 golden hour/backlighting/cinematic/8k 等细节），控制台 0 错误 ✅
- 修复部署问题：8888 端口后端（前端默认 API）未加载新路由返回 405 → 重启 8888 加载新代码，清理 8000 冗余进程

## 五、后续建议

- 智能补充可继续扩散到 Mindmap/PPT/Excel 等输入型页面（组件已支持对应 style）
- 可考虑在润色时附带「扩写/精简/改写」模式选择，适配不同输入习惯

---

# v13.6 智能补充剩余页扩散 + 新场景专家（2026-08-09）

## 一、背景

v13.5 已为核心 4 个生成页接入 AI 智能补充。经扫描（textarea 存在但无 EnhancePromptButton 的 34 个页面中筛选「创作/生成型输入」），剩余 MindMap/PPT/Excel/Game 4 个生成页仍缺此能力；且后端专家系统缺 game/excel 场景。

## 二、改动清单

### 后端（tool_hub.py）
| 改动 | 说明 |
|---|---|
| `_ENHANCE_SYSTEMS` 新增 2 场景 | `game`：游戏策划专家（核心玩法/操作/关卡/美术音效/目标人群）；`excel`：Excel 公式专家（列结构假设/计算规则/边界条件/输出格式） |
| 专家系统总数 | 9 → 11 种场景（image/copywriting/music/video/meme/mindmap/ppt/game/excel/general） |

### 前端（4 页接入）
| 文件 | 改动 |
|---|---|
| `MindMapPage.jsx` | 「生成导图」标题右侧加智能补充（style=mindmap，紫色） |
| `PPTFactoryPage.jsx` | 「大纲要点」label 右侧加智能补充（style=ppt，橙色） |
| `ExcelPage.jsx` | 「公式需求」label 右侧加智能补充（style=excel，绿色） |
| `GameFactoryPage.jsx` | 「玩法需求」label 右侧加智能补充（style=game，品红） |

## 三、设计要点

- **筛选原则**：只给「创作/生成型输入」接入，扫描/配置/批量格式输入（ContentStrategy 正文、Meme 批量文案）不接入，避免破坏输入格式语义
- **标题内嵌模式**：无独立 label 的卡片（MindMap）将 h3 改为 flex justify-between，右侧内嵌按钮，不额外占行
- **场景对齐**：每页传对应 style 让后端走领域专家系统，而非统一 general

## 四、验证结果

- `npx vite build` 成功（10.39s）；5 个改动文件 GetProblems 全部 0 errors
- 后端接口实测（curl）：game 扩写为游戏设计需求说明书 ✅、excel 扩写为精确公式需求描述（列结构/阶梯规则/边界条件）✅
- 浏览器实测 `/mindmap`：输入主题 → 智能补充 → 扩写为 77 行三级树形大纲（PEST/产业链/竞争格局等维度）✅；`/games` 页玩法需求按钮存在 ✅；控制台 0 错误

## 五、后续建议

- 智能补充已覆盖 8 个创作生成页（Image/Copywriting/Music/Video/MindMap/PPT/Excel/Game），可收尾该能力线
- 可考虑给智能补充加「扩写/精简/改写」模式参数，适配不同输入习惯

---

# v13.7 随机提示词灵感入口（2026-08-09）

## 一、背景

扫描发现 9 个创作生成页中仅 Music/Video 有「随机/示例」入口，其余 7 页新手用户不知写什么时无处下手。新增通用「随机提示词」组件并接入 6 个生成页，与智能补充形成「灵感 + 精修」完整输入链。

## 二、改动清单

### 前端
| 文件 | 改动 |
|---|---|
| `RandomPromptButton.jsx`（新增） | 通用随机按钮组件：从预设数组随机取一条填入输入框，props：`{prompts, onPick, className}` |
| `ImageFactoryPage.jsx` | 提示词 label 右侧加随机按钮（6 条专业英文图片提示词预设） |
| `CopywritingPage.jsx` | 需求描述右侧加随机按钮（6 条中文营销场景预设） |
| `MindMapPage.jsx` | 生成导图标题右侧加随机按钮（6 个热门主题预设） |
| `PPTFactoryPage.jsx` | 主题 label 右侧加随机按钮（6 个职场汇报主题预设） |
| `ExcelPage.jsx` | 公式需求右侧加随机按钮（6 条公式/数据处理场景预设） |
| `GameFactoryPage.jsx` | 玩法需求右侧加随机按钮（6 条游戏玩法创意预设） |

## 三、设计要点

- **双按钮布局**：label 右侧 `flex gap-3` 并排「随机提示词 + 智能补充」，随机取灵感 → 智能补充精修，两键形成完整输入链
- **筛选原则**：只接「创作/生成型输入」；Meme 双栏（上/下文案）结构特殊不接，避免破坏批量格式语义
- **预设质量**：每页 6 条高价值预设，覆盖主流使用场景（如 Excel 的提成阶梯/重复值统计/工龄计算），非凑数内容

## 四、验证结果

- `npx vite build` 成功（10.66s）；7 个改动文件 GetProblems 全部 0 errors
- 浏览器实测：
  - `/image-factory` 连续点击 3 次随机 → 填入 3 条不同英文提示词 ✅
  - `/copywriting` 点击随机 → 填入中文营销需求 ✅
  - `/mindmap` 标题右侧双按钮可见 ✅
  - 三页控制台均 0 错误 ✅

## 五、后续建议

- 随机预设可考虑接入云端（类似 Video 的 cloudPrompts），运营可远程更新
- Meme 页可加「随机梗文案」双栏填充（需单独设计）

---

# v13.8 Meme 随机梗 + MindMap 一键重跑（2026-08-09）

## 一、背景

v13.7 遗留两项建议落地：①Meme 页双栏（顶部/底部文案）结构特殊未接随机入口；②扫描发现 9 个创作生成页中 8 个结果区缺「重新生成/一键重跑」。

## 二、改动清单

### 前端
| 文件 | 改动 |
|---|---|
| `MemePage.jsx` | 「表情文字」标题右侧加「随机梗文案」（从 SUGGESTS 随机取一条填入上/下双栏）；「批量文案」label 右侧加「随机批量」（随机取 3-4 条不重复 SUGGESTS 拼成批量格式） |
| `MindMapPage.jsx` | 结果区「导出PNG」旁加「重新生成」按钮（RefreshCw，复用 generate()，task 进行中禁用） |

## 三、设计要点

- **双栏随机**：Meme 随机梗直接复用既有 applySuggest 机制，一次点击同时填顶部+底部，保持双栏语义一致
- **批量随机去重**：随机批量用池子 splice 保证同次生成的 3-4 条不重复，避免批量里出现相同梗
- **一键重跑复用**：重新生成直接调用现有 generate()（表单已是当前输入），不新增后端逻辑；task 非空时禁用防重复提交

## 四、验证结果

- `npx vite build` 成功（12.60s）；2 个改动文件 GetProblems 全部 0 errors
- 浏览器实测：
  - `/meme` 随机梗点击后双栏填入（好的呢/微笑中透露着疲惫）✅
  - `/meme` 随机批量填入 4 行不重复「顶部/底部」文案 ✅
  - `/mindmap` 重新生成按钮可见，点击后历史 1→2 条 ✅
  - 两页控制台 0 错误 ✅

## 五、后续建议

- 「一键重跑」可继续扩散到 Music/PPT/Excel/Game/Image/Video 等任务式生成页（需逐页评估结果区结构）
- Meme 随机梗素材库（SUGGESTS）可扩充到 20+ 条，提升新鲜感

# v13.9 游戏工坊全面升级：策略/回合制/模拟全品类 + wx 完整性门禁（2026-08-09）

## 一、背景

用户反馈："不能只是搞简单的游戏，什么策略类的、回合制的等等全面小游戏都要支持的"。此前游戏工坊 8 个模板全部是即时休闲类（贪吃蛇/2048/飞机大战/打砖块/记忆翻牌/俄罗斯方块/扫雷/三消），策略、回合制、模拟、益智等品类缺失；且回合制等复杂游戏生成时微信版偶发缺失/为空仍能通过 QC。

## 二、改动清单

### 后端（game_factory.py）
| 改动 | 说明 |
|---|---|
| 新增 6 个模板 | 策略塔防（策略）、回合制RPG（回合制）、回合制卡牌（回合制）、五子棋（回合制）、放置经营（模拟）、答题闯关（益智），全部带完整 play 玩法描述 |
| 旧模板补 category | 8 个旧模板全部标注品类（休闲×7/益智×1），模板总数 8→15 |
| 回合制/策略专项 prompt | `_GENERATE_SYSTEM` 追加 A-G 七条：回合状态机（phase）、AI 决策函数（禁止随机乱动+思考延迟）、资源经济闭环（禁止负资源）、Canvas 按钮面板、棋盘格坐标换算、数值平衡（单局 3-8 分钟）、双版本一致（wx.onTouchStart） |
| wx 完整性硬门禁 | `_validate_files` 缺失 wx 或 game.js 为空直接 ValueError 触发自动重试；`_qc_check` 强制检查 wx 三件套（game.js/game.json/project.config.json），删除原 `if wx:` 跳过逻辑 |
| max_tokens 提升 | 首轮/QC 重试 16000→22000、精简重试 14000、evolve 20000，避免复杂双版本输出被截断 |

### 前端（GameFactoryPage.jsx）
| 改动 | 说明 |
|---|---|
| TEMPLATES 同步 | 15 个模板全部带 category 字段 |
| 分类分组展示 | 模板区按 休闲/益智/策略/回合制/模拟/自定义 分组，每组 emoji 图标 + 小标题 + 4 列网格，兼容无 category 的云端模板（归入"其他"） |
| RANDOM_REQUIREMENTS 扩充 | 6→12 条，新增策略塔防/回合制战斗/卡牌对战/五子棋/放置经营/答题闯关随机需求 |

## 三、设计要点

- **品类即 prompt**：新增模板的 play 描述即完整玩法规格（炮塔种类/技能列表/波次系统/棋盘规格），LLM 按规格落地，避免"策略游戏做成即时游戏"
- **专项 prompt 兜底**：A-G 七条对任何回合制/策略/模拟模板强制生效，即使用户只写一句话需求也能产出带状态机的完整游戏
- **wx 三件套即交付**：微信小游戏版与网页版同为交付核心，缺失即触发 3 轮自动重试直至补全

## 四、验证结果

- 模板接口实测：15 个模板全部返回且 category 正确 ✅
- 回合制RPG 实测生成（sync 模式，76.8s）：web index.html 414 行 + wx 三件套齐全（game.js 374 行非空），QC 全部通过 ✅
- 浏览器实测 `/games`：
  - 分类分组模板区正常（🎮休闲 7 / 🧩益智 2 / ♟️策略 1 / 🔄回合制 3 / 🏪模拟 1 / ✨自定义 1）✅
  - 点击「策略塔防」模板，描述区切换为"策略塔防：布塔防守，升级炮塔…" ✅
  - 「勇者斗恶龙」（回合制RPG）试玩：iframe 内 canvas 正常渲染、标题正确、控制台 0 错误 ✅
  - 游戏列表标注"· 双版本 ·"（wx 三件套齐全）✅

## 五、后续建议

- 模板可继续扩充：经营养成（模拟）、战棋走格（策略）、猜词聚会（多人）等
- 塔防等复杂模板生成耗时较长（~77s），可考虑拆分为"先 web 后 wx"两阶段任务回报进度
- 下一轮：图片生成全面升级（艺术风格预设 + 负面提示词）

# v13.10 图片工厂全面升级：艺术风格预设 + 负面提示词（2026-08-09）

## 一、背景

用户反馈："不止游戏哈，图片生产、视频生成、其他的都有搞，需要全面的升级的"。图片工厂此前只有基础提示词输入，缺少风格控制与排除项能力，专业设计场景（电商图/海报/插画）难以一次到位。

## 二、改动清单

### 后端（image_factory.py）
| 改动 | 说明 |
|---|---|
| text-to-image 加 negative 参数 | `negative: str = Form("")`，worker 内非空时透传 `negative_prompt` 给 AGNES API |
| image-to-image 加 negative 参数 | 图生图接口同步支持，`data["negative_prompt"]` 透传 |

### 前端（ImageFactoryPage.jsx）
| 改动 | 说明 |
|---|---|
| ART_STYLES 艺术风格预设 | 10 种风格：写实摄影/动漫/3D渲染/油画/水彩/像素/赛博朋克/极简/国风水墨/蒸汽波，各带 emoji 图标与英文风格关键词（title 悬浮可见） |
| 风格选择交互 | 5 列网格卡片，点击选中（高亮+当前风格提示），再次点击取消；选择后生成时自动追加风格关键词到 prompt |
| 负面提示词输入 | 提示词下方新增负面词输入框（支持中英文），生成时随请求提交；非空时提示词区显示"已启用负面提示词" |
| 双 tab 接入 | 文生图 + 图生图均提交 negative 参数 |
| 输入持久化 | artStyle / negativePrompt 纳入 usePersistentToolState，刷新不丢 |

## 三、设计要点

- **风格即关键词**：每种风格对应一组高质量英文关键词（如国风水墨 = Chinese ink wash painting, shuimo style, elegant brushwork, rice paper），追加到 prompt 末尾，不覆盖用户描述
- **负面词双保险**：前端可选填；后端空值不发送，避免无效请求体
- **可取消选择**：风格卡片再次点击即取消，回到"无（自由发挥）"，不强制用户选风格

## 四、验证结果

- `npx vite build` 成功（10.34s）；GetProblems 0 errors；后端语法检查通过
- 后端重启后 /api/health 正常
- 浏览器实测 `/image-factory`：
  - 10 种风格卡片全部渲染，悬浮显示英文关键词 ✅
  - 点击「国风水墨」→ 当前风格提示更新 + 按钮高亮 ✅
  - 负面提示词填入 low quality, blurry, watermark, text ✅
  - 生成任务提交成功（200），任务完成 100% ✅
  - 生成图片 prompt 实测包含 "Chinese ink wash painting, shuimo style, elegant..." 风格关键词 ✅
  - 结果图正常展示 ✅

## 五、后续建议

- 风格预设可扩充：胶片摄影/莫奈印象派/浮世绘/低多边形等
- 图生图/试衣 tab 可复用同一套风格选择器
- 下一轮：视频生成全面升级（提示词模板 + 预设场景）

# v13.11 视频工厂全面升级：结构化导演控制 + 死控件修复（2026-08-09）

## 一、背景

用户反馈："视频生成...需要全面的升级的"。扫描发现视频页两个严重问题：①视频风格/镜头语言下拉框是**死控件**（defaultValue 无 state 绑定，选中后根本不参与生成）；②提示词模板仅 5 类、缺少运镜/情绪等导演级控制项。

## 二、改动清单

### 前端（VideoFactoryPage.jsx）
| 改动 | 说明 |
|---|---|
| 死控件修复 | 视频风格/镜头语言接入持久化 state（videoStyle/cameraAngle），提交时拼入 prompt |
| 运镜方式 | 新增 CAMERA_MOTIONS 7 种：固定/推近/拉远/横移/环绕/手持/升降，各带英文关键词 |
| 情绪氛围 | 新增 MOODS 7 种：默认/温暖治愈/史诗宏大/梦幻唯美/赛博冷峻/暗黑悬疑/欢乐活泼 |
| 画面比例快捷切换 | ASPECTS 4 种：16:9 横屏/9:16 竖屏/1:1 方形/4:3 经典，一键设置宽高并高亮当前比例 |
| 提示词模板扩充 | PRESET_CATEGORIES 5→7 类（新增影视剧情 🎬、科幻未来 🚀），各 4 条预设 |
| 结构化组合提交 | handleCreate 将 风格/镜头/运镜/情绪 关键词按序拼入 prompt（逗号分隔），不再丢失控制项 |

## 三、设计要点

- **导演四要素**：风格（画面质感）+ 镜头（景别角度）+ 运镜（运动方式）+ 情绪（氛围基调），构成专业视频 prompt 结构
- **关键词即效果**：每个控制项映射到英文生成关键词（如 环绕 = orbit around the subject, 360 rotation），中文选项 + 英文关键词双展示
- **竖屏支持补全**：9:16/1:1 一键切换补上分辨率下拉没有的竖屏/方形比例，适配抖音/小红书场景

## 四、验证结果

- `npx vite build` 成功（11.88s）；GetProblems 0 errors
- 浏览器实测 `/video-factory`：
  - 7 类提示词模板（新增影视剧情/科幻未来）✅
  - 视频风格/镜头语言/运镜/情绪 4 下拉全部可用 ✅
  - 9:16 竖屏按钮高亮，宽高 state 更新为 1080×1920 ✅
  - 创建任务成功（200），任务 payload prompt 实测：
    `A majestic dragon flying over a mountain valley, 电影感, aerial/drone, orbit around the subject, 360 rotation, epic scale, dramatic lighting, grandiose atmosphere` ✅
  - width/height = 1080/1920 ✅

## 五、后续建议

- 视频风格可加"胶片/黑白/赛璐璐"等美术风格；运镜可加"第一人称/FPS 视角"
- 图生视频/关键帧模式可展示参考图预览与关键帧编辑器
- 下一轮：其余创作页全面体检（音频/文档/PPT/Excel 等按同类标准升级）

# v13.12 语音工厂升级：场景文案模板 + 场景联动填充（2026-08-09）

## 一、背景

"其他的都有搞，需要全面的升级的"持续落地。语音工厂（AI 配音）此前只有空白文本框，用户需自己组织口播/旁白文案；且新用户对"场景 × 文案风格"无感知，上手成本高。

## 二、改动清单

### 前端（VoicePage.jsx）
| 改动 | 说明 |
|---|---|
| SCENE_TEXT_TEMPLATES 场景文案库 | 6 大场景（短视频旁白/广告口播/有声书/新闻播报/儿童故事/自定义）各 2-3 条专业示例文案 |
| 场景联动填充 | 点击场景卡片且文本框为空时，自动填入该场景首条示例文案（不覆盖已有输入） |
| 随机文案按钮 | 「配音文本」标题右侧新增，从当前场景模板池随机抽取一条填入（custom 时从全场景池抽取） |

## 三、设计要点

- **场景即风格**：文案模板与场景语义强绑定（新闻=字正腔圆口播、故事=童趣开场），示范正确的内容组织方式
- **空文本才联动**：仅当用户未输入时自动填充，避免覆盖用户草稿
- **随机池降级**：custom 场景无专属模板时自动降级为全场景池，保证按钮永远可用

## 四、验证结果

- `npx vite build` 成功（11.07s）；GetProblems 0 errors
- 浏览器实测 `/voice-dubbing`：
  - 点击「新闻播报」场景 → 文本框自动填入"各位听众朋友，大家好，这里是午间新闻…" ✅
  - 点击「随机文案」→ 随机抽取"今日要闻播报：受冷空气影响…" ✅
  - 场景卡片选中态高亮正常 ✅

## 五、后续建议

- 文案模板可扩充到每场景 5 条，覆盖更多细分内容（带货/知识付费/睡前故事）
- 「智能补充」可接入配音文本（润色口播文案）
- 下一轮：音乐/PPT/Excel/文案等剩余创作页按同类标准体检

# v13.13 音乐工厂修复与扩充：歌词情绪联动 + 主题池 6 类（2026-08-09）

## 一、背景

"其他的都有搞，需要全面的升级的"持续落地。扫描发现：①歌词生成接口漏传情感基调（mood），后端 /lyrics/generate 支持 mood 且会注入"情感基调"提示，但前端 generateLyrics 只提交 theme/style/language/length → 歌词情绪永远是默认"欢快"；②主题池仅 4 类，节日/国风等高频题材缺失。

## 二、改动清单

### 前端（MusicFactoryPage.jsx）
| 改动 | 说明 |
|---|---|
| generateLyrics 补 mood | 歌词生成 form 追加 mood，歌词情绪与「情感基调」选择保持一致 |
| 主题池扩充 | PRESET_CATEGORIES 4→6 类：新增「节日庆典 🎉」（春节/圣诞/毕业季/生日）与「国风古韵 🏮」（江南烟雨/长安月下/山河故人/琴瑟和鸣），均带风格联动 |

## 三、设计要点

- **情绪贯穿全链路**：主题→歌词→音乐 三段生成共享同一 mood，避免"主题悲伤、歌词欢快"的割裂
- **题材即流量**：节日与国风是内容创作高频题材，主题池直接服务爆款选题

## 四、验证结果

- `npx vite build` 成功（11.09s）；GetProblems 0 errors
- 浏览器实测 `/music-factory`：
  - 主题池 6 类完整展示（新增节日庆典/国风古韵）✅
  - 随机主题从新池抽取：「圣诞雪夜」填入主题框（style 联动 classical）✅

## 五、后续建议

- 歌词结果区可加「换一版」按钮（同参数再生成一次）
- 音乐生成可增加 BPM/乐器选择等专业控制项

# v13.14-v13.19 剩余创作模块深度升级（2026-08-09）

## 一、背景

"按这个思路，再深度的优化我们的功能"持续落地。上轮已完成 游戏/图片/视频/语音/音乐 五大工厂，本轮对剩余创作模块（PPT/Excel/Meme/MindMap/数字人/文案）做同类深度升级：**池子扩充 + 一键重跑 + 场景联动 + 前后端一致性**。

## 二、改动清单

### v13.14 PPT 工厂（PPTFactoryPage.jsx）
| 改动 | 说明 |
|---|---|
| 演示类型 5→8 | 新增：学术论文/营销策划/个人述职 |
| 设计主题 5→8 | 新增：清新薄荷/复古金棕/梦幻紫粉（themeColorMap 同步） |
| 快速模板 6→10 | 新增：学术答辩/电商大促/政府汇报/文旅策划 |
| 随机主题 6→12 | 新增：数字化转型/校园招聘/乡村振兴/电商大促/AIGC 白皮书/安全生产 |
| 结果区一键重跑 | 「重新生成」按钮复用当前参数直接再跑 |

### v13.15 Excel 助手（ExcelPage.jsx）
| 改动 | 说明 |
|---|---|
| 随机公式 6→10 | 新增：库存预警/季度环比/手机号脱敏/加班调休 |
| 快速模板 6→12 | 新增：人事考勤/库存周转/成绩统计/销售提成/多表合并 |
| 结果区一键重跑 | 「重新执行」按钮 |
| 历史回填增强 | reuseHistory 补回填 prompt（此前只回填操作类型） |

### v13.16 表情包工坊（MemePage.jsx + meme_factory.py）
| 改动 | 说明 |
|---|---|
| AI 风格 5→8（前后端同步） | 新增：油画质感/赛璐璐动漫/电影写实；后端 AI_STYLES 字典 + API 描述同步，杜绝前端可选后端 fallback 的"选择不生效"缺陷 |
| 灵感梗文案 6→12 | 新增：周五了/甲方说/开工/体检报告/早起失败/开会两小时 |
| AI 场景智能补充 | 场景描述输入框右侧加 EnhancePromptButton |

### v13.17 AI 思维导图（MindMapPage.jsx）
| 改动 | 说明 |
|---|---|
| 配色主题切换 5 套 | 经典多彩/清新薄荷/暖阳橙红/科技蓝紫/暗夜深邃；canvas 覆色渲染（根/一/二/三级联动透明度），不依赖后端节点自带色，一键全局换肤 |
| 随机主题 6→12 | 新增：私域流量/Scrum/职业规划/理财配置/短视频冷启动/智能家居 |

### v13.18 AI 数字人（DigitalHumanPage.jsx）
| 改动 | 说明 |
|---|---|
| 场景台词联动 | SCENE_SCRIPTS 5 场景 × 2 条示例口播；点击场景卡片且文案为空时自动填入对应示例 |
| 随机台词按钮 | 口播文案头部按钮组新增「随机台词」，优先当前场景池抽取 |

### v13.19 AI 文案创作（CopywritingPage.jsx）
| 改动 | 说明 |
|---|---|
| 随机需求 6→12 | 新增：SaaS 落地页/宠物寄养/校园墙/知识付费/读书日/健身房开工 |
| 快速模板 8→12 | 新增：短视频口播/招聘 JD/年会致辞/直播话术 |
| 结果区一键重跑 | 「重新生成」按钮（修复 RefreshCw 未导入遗漏） |

## 三、设计要点

- **池子扩充 = 素材即内容**：所有模板/主题/风格池扩充一倍以上，直接扩大 AI 的输入覆盖度
- **结果区一键重跑**：同参数再生成一版，成为创作页标配（PPT/Excel/文案已补齐，至此全部创作页统一）
- **前后端选择一致性**：前端新增风格选项必须同步后端字典，避免静默 fallback
- **场景联动**：语音/数字人场景点击 → 自动填充该场景示例内容，降低空输入门槛

## 四、验证结果

- `npx vite build` 成功；GetProblems 0 errors；后端 ast 检查通过并重启
- 浏览器实测 5 页全部通过：
  - PPT：10 模板/8 主题完整、学术答辩模板一键填入标题+大纲 ✅
  - MindMap：5 套配色按钮、生成后切「暖阳橙红」canvas 像素级验证变橙红系 ✅
  - Meme：AI 风格 8 个完整、智能补充按钮存在（lucide-wand2）✅
  - 数字人：场景「故事讲述」空文案自动填示例、随机台词内容变化 ✅
  - 文案：12 模板完整、统计卡同步 12 ✅

## 五、后续建议

- 音乐/图片/视频结果区可补「换一版」快速重跑（目前有重新生成但部分缺）
- 数字人可增加「口播文本朗读预览」轻量试听（TTS 短句预览）

---

### v13.20 开源 AI 生成引擎集成（阶段① CosyVoice + 阶段② ACE-Step + 短剧管线）

> 目标：引入 GitHub 优秀开源生成项目替代/增强自研 DSP 链路（用户需求："github 不是有很多开源的，比较优秀的，视频、音频、短剧等生成的开源项目吗，你看看能不能集成到我们项目里来"）。
> 约束：Mac M4 Pro 24GB 统一内存；独立推理服务模式（业务层不动，HTTP 调用 + 引擎抽象/开关 + 失败自动降级）。

## 一、阶段① CosyVoice 2（语音 + 歌声，已完成）

| 改动 | 说明 |
|---|---|
| `backend/voice_engine/`（独立服务 9888） | CosyVoice 2 推理服务：`/tts/sft` `/tts/zero_shot` `/sing` 三接口（MPS 加速）；平台侧探活防抖 + 失败自动回退 edge-tts |
| `backend/voice_factory.py` | 4 个 AI 克隆音色接入（中文女/男/童声/粤语女），前端 VoicePage 同步 |
| `backend/music_factory.py` | 人声轨接入 CosyVoice 真歌声（`/sing` + ffmpeg atempo 时间拉伸对齐谱曲时长，ratio 夹 0.7~1.35），失败自动回退 edge-tts 变调链路 |
| 验证 | 配音 8.9s（-14.9dB 母带）、整首歌 22.2s（人声频段能量 51.1%） |

## 二、阶段② ACE-Step 1.5 音乐大模型（已完成）

| 改动 | 说明 |
|---|---|
| `~/ai-models/ACE-Step-1.5/`（独立 venv） | ACE-Step 1.5 仓库 + 依赖（torch 2.12.1 + mlx + mlx-lm）；模型：DiT acestep-v15-turbo（4.79G）+ LM acestep-5Hz-lm-1.7B（3.71G）+ VAE，modelscope 源下载 |
| `acestep.api_server`（独立服务 9889） | 官方 FastAPI：`/release_task`（异步）`/query_result` `/v1/audio` `/health`；MLX 后端（官方 macOS 支持），Flash Attention 不可用自动回退 SDPA |
| `backend/music_factory.py` | 引擎开关 `MUSIC_ENGINE=auto\|acestep\|local`；auto 模式 ACE-Step 可用优先（探活防抖），失败自动回退 CosyVoice 人声 + numpy 伴奏链路；产物 metadata 标记 `engine:"acestep"`；stats 接口加 engine 状态 |
| `frontend MusicFactoryPage.jsx` | 统计卡加「AI 引擎」标识（ACE-Step 大模型 / 本地真歌声 / 降级中） |
| 推理性能 | MLX 一首 30s 歌：LM 阶段 84s + DiT 阶段 51s ≈ 135s（RTF≈4.5，符合计划预期 2-5） |
| 验证 | 直接调用：30.0s / 128kbps / 人声频段能量 55.0%；平台端到端：engine=acestep / 30.0s / 52.8% ≥ 45% 达标 |
| 下载踩坑 | `uv sync` 会解析跨平台 flash-attn wheel 卡死 → 必须 `uv pip install -r`；requirements 的 `--extra-index-url cu128` 会污染 darwin torch 解析 → 剔除后固定 `torch>=2.9.1; sys_platform=='darwin' and platform_machine=='arm64'` |

## 三、阶段④前置：短剧本地管线（backend/short_drama.py）

| 改动 | 说明 |
|---|---|
| `backend/short_drama.py`（新增，注册 main.py） | LLM 剧本（分幕/分镜/台词/旁白 JSON）→ 每镜 CosyVoice 配音 → PIL 渐变背景图 → ffmpeg 逐镜合成 → concat 拼接 → 字幕烧录 → mp4 产物；`POST /api/drama/generate`（sync 可选）+ 视频/字幕/封面/列表接口；任务注册 `drama_generate`（长任务池） |
| 验证 | 5 镜 24.7s 竖屏短剧（720x1280 / 25fps / h264+aac），SRT 字幕时间轴对齐，LLM 剧本起承转合完整 |
| ffmpeg libass 坑 | 本机 ffmpeg 8.1.1 未编译 libass（`subtitles` 滤镜不可用）→ 安装 `imageio-ffmpeg`（自带 libass 的 7.1 二进制）优先使用，系统 ffmpeg 兜底；环境检查脚本同步探测 |
| requirements.txt | 新增 `imageio-ffmpeg>=0.5.0` |

## 四、环境自检脚本更新（scripts/check_environment.sh）

- 12 项 → 13 项：新增 [13] 本地 AI 引擎检查（仅 macOS：voice_engine 9888 / acestep 9889 / 模型目录，缺失仅警告不阻塞部署，平台自动降级）
- [8] Python 依赖 MAPPING 加 `imageio-ffmpeg`；[9] 加 subtitles 滤镜（libass）探测：系统 ffmpeg 缺失时警告并提示 imageio-ffmpeg 兜底
- 本机验证：13 项中 12 通过（唯一失败为端口 8888 被后端占用，属预期）

## 五、后续（阶段③④）

- 阶段④ 短剧素材增强：云 API 文生视频（阿里云百炼/硅基流动 failover）+ 数字人说话头替代静态背景图
- start_all.sh / stop_all.sh 统一编排 voice_engine(9888) / acestep(9889) / avatar_engine(9890)

### v13.21 开源 AI 生成引擎集成（阶段③ 数字人：SadTalker 单图口播）

> 目标：照片 + 音频 → 自然口播视频（3DMM 系数驱动，头部运动 + 口型同步），作为平台现有 Wav2Lip 照片数字人的高级引擎（引擎链：sadtalker → live_portrait(Wav2Lip) → 2d 自动降级）。

| 改动 | 说明 |
|---|---|
| `~/ai-models/SadTalker/`（独立 venv py3.10） | SadTalker 仓库 + 权重（mapping_00109/00229 ~155MB×2 + SadTalker_V0.0.2_256.safetensors 725MB + BFM_Fitting 404MB，GitHub Releases 直连）；依赖用 `req_arm64.txt` 放宽版本（官方 requirements 为 py3.8+CUDA 时代） |
| `backend/avatar_engine/`（独立服务 9890） | SadTalker 推理封装（sad_engine.py）+ FastAPI 服务（server.py）：`/release_task`（multipart）`/query_result`（data list + stage 阶段字段）`/v1/video` `/health`；ThreadPoolExecutor(1) 串行推理（24GB 内存限制）、模型懒加载、CPU 8 线程优化（Face Renderer Conv3D 在 MPS 不可用） |
| `backend/digital_human_sadtalker.py`（新增） | 平台侧客户端：探活防抖（30s 缓存，同时记录引擎 busy 排队数）→ 提交任务 → 轮询（stage→进度映射：排队 58 / 加载 60 / 3DMM 62 / 音频系数 66 / 渲染 72+）→ 下载回传 → 分辨率统一缩放（256x256 → 720p/1080p lanczos）→ 平台水印 overlay；超时上限 7200s（覆盖排队+推理两段）；失败抛错触发上层引擎降级 |
| `backend/digital_human.py` | GenerateRequest engine 加 `sadtalker`（单条 + 批量）；引擎链 `sadtalker→live_portrait→2d`（live_portrait 失败降 2d 不变）；照片形象校验覆盖 sadtalker |
| `frontend DigitalHumanPage.jsx` | 引擎选项加「数字人高级版（3D 口型·头部运动）」，提示推理 20-50 分钟；build 通过（10.45s） |
| `scripts/start_all.sh` | 编排加 avatar_engine(9890)（SadTalker venv + uvicorn）；`scripts/check_environment.sh` [13] 加 avatar_engine 探活 + SadTalker 模型目录检查 |
| 推理性能 | CPU 21s 音频（133 帧 @256 分辨率）：Face Renderer ≈28s/帧，总时长 ≈60 分钟（RTF≈170，符合 Apple Silicon CPU 预期；优化报告基线 4-8s/帧为 60s 视频分块版，本机未做分块优化）；平台端到端实测：15.7s 音频（99 帧）≈41 分钟 |
| 平台端到端验证 | ✅ 任务 `task_5e4da34f4b0d` → 平台记录 `dh_384e698580f1`：status=done、**engine=sadtalker（未降级）**、video_url 可下载；产物 256x256/25fps/15.7s（口型量化：嘴部/全脸帧间差异比 3.01、嘴部时间方差 6.9，PASS）；分辨率缩放 256x256→1280x720 单测通过 |
| 超时竞态修复（v13.21 补丁） | ① 客户端 `_AVATAR_MAX_WAIT` 3600→7200s：首次 e2e 因排队（前一任务 62 分钟）+ 推理（46 分钟）超 60 分钟 → 降级 live_portrait；② 任务框架看门狗 `TASK_TIMEOUT_SECONDS` 默认 7200→10800s：worker 写 success 与看门狗标记 failed 均带 `WHERE status='running'` 保护，若看门狗先触发则降级链完成后的 success 被丢弃 → 看门狗阈值必须大于业务客户端超时，给降级链留执行窗口；③ 探活返回 busy 计数，排队时进度提示「引擎繁忙（N 个任务排队）」避免误判卡死 |
| 依赖踩坑 | ① numba 0.66→llvmlite 0.48 无 arm64 py310 wheel → 固定 numba 0.61.2（llvmlite 0.44）；② torch 2.2.2 与 numpy 2.x 不兼容（_ARRAY_API）→ numpy 1.26.4；③ basicsr 1.4.2 需 torchvision 已移除的 `functional_tensor` → 兼容 shim；④ SadTalker 用 np.float 等老别名 → sad_engine 注入；⑤ numpy≥1.24 拒绝嵌套数组（lstsq k 为 (8,1)，t[0] 为 (1,)）→ 修复 POS 返回真标量；⑥ gfpgan/basicsr 为 animate 模块级 import（enhancer 关闭也要装）；⑦ facexlib 模型自动下载慢（GitHub 42kB/s）→ 手动 curl 直连 40s 完成 |

## 六、后续（阶段④）

- 阶段④ 短剧素材增强：云 API 文生视频（阿里云百炼/硅基流动 failover）+ 数字人说话头替代静态背景图
- 数字人增强候选：EchoMimic v2（2B 说话+唱歌口型，MPS 需实测）｜SadTalker 512 分辨率 + GFPGAN 增强器｜Face Renderer 分块优化（4-8s/帧）

### v13.22 全模块打磨（阶段④：音视频/游戏/小程序/图片）

> 目标：参照音乐模块成功模式（开源引擎接入 + 独立服务 + 引擎开关/降级链 + 客观指标验证），对图片、视频、游戏、小程序全面打磨：真抠图与背景替换、多通道 failover、ffmpeg 后期增强、模板与封面扩充、全模块一键验证脚本。

#### 一、图片工厂：rembg 真抠图 + 背景替换重做 + 模板渲染增强

| 改动 | 说明 |
|---|---|
| `backend/image_edit_engine.py`（新增） | ① rembg ONNX 语义分割封装（u2net 人像模型懒加载 + 探活防抖，不可用抛错由上层降级）；② `make_scene_background`：9 场景渐变背景（beach/city/space/studio/forest/snow/sunset/night/pastel，多层渐变 + 装饰元素，按图尺寸自适应）；③ `make_gradient` 垂直渐变工具 |
| `backend/image_factory.py` | ① `/edit/personal-segmentation`：rembg 真抠图（feather 0-8 羽化半径，透明背景 PNG），失败自动降级旧椭圆近似；② `/edit/replace-background`：三级背景合成（AI 描述 > 纯色 > 场景渐变），AI 背景用 Agnes 文生图并按原图分辨率重采样；③ 模板渲染增强：渐变背景简写 `#A→#B`、圆角矩形图层（radius/opacity）、文字阴影（shadow="dx,dy"）、max_width 自动换行、key/overrides 动态文本 |
| 前端 `ImageFactoryPage.jsx` | 图片编辑 Tab 新增「人像分割」（羽化滑块 0-8 + 一键分割按钮）与「背景替换」（9 场景下拉 / 纯色 #RRGGBB / AI 背景描述，优先级提示）两个区块 |

#### 二、视频工厂：多通道 failover + ffmpeg 后期增强

| 改动 | 说明 |
|---|---|
| `backend/video_factory.py` | ① 多通道 failover 框架：`AI_VIDEO_CHANNELS` 环境变量（默认 `agnes,dashscope`），`_available_channels()` 按配置顺序过滤未配 key 的通道，`_create_video_task`/`_poll_video_result` 按通道分派，单通道失败自动切备用通道并汇报进度，全部失败聚合报错；dashscope 通道预留实现（wan2.2-t2v-plus 视频合成，i2vid 抛 400 跳过）；stats 接口新增 channels 字段 ② 后期工具三个端点：`/tools/concat`（统一分辨率等比缩放+黑边补齐、无音轨片段自动补静音、concat filter）、`/tools/music`（原声+BGM 混音 `amix=inputs=2:duration=first:dropout_transition=2`，bg_volume 0-1，BGM 支持 URL/本地路径）、`/tools/subtitle`（SRT 文本烧录进画面，libass 滤镜，路径转义） |
| `backend/common/config.py` | `DASHSCOPE_API_KEY` / `AI_VIDEO_CHANNELS` 预留配置位（不配 key 自动从通道列表剔除） |
| 前端 `VideoFactoryPage.jsx` | 「视频后期工具」区块三入口：多视频拼接（勾选列表 + 顺序提示）/ 背景音乐混音（目标视频下拉 + BGM 地址 + 音量滑块）/ 字幕烧录（目标视频 + SRT 编辑器），处理结果自动入视频库 |
| 踩坑记录 | ① ffmpeg stdin 为 TTY 时进入交互模式挂起（CPU 0%）→ 所有 ffmpeg 调用必须加 `-nostdin`；② concat filter 输入必须视频/音频交替排列 `[v0][a0][v1][a1]…`（先视频后音频报 Media type mismatch）；③ 系统 ffmpeg 8.1.1 无 libass → `_pick_ffmpeg()` 优先 imageio-ffmpeg v7.1 二进制，`_pick_video_encoder()` h264_videotoolbox 优先回退 libx264 |

#### 三、小游戏工坊：模板扩充 + AI 封面

| 改动 | 说明 |
|---|---|
| `backend/game_factory.py` | 新增 runner（跑酷）/ whack（打地鼠）/ pong（弹球）/ sudoku（数独）4 模板，模板总数 19（含 custom）；新增 `POST /{proj_id}/ai-cover`：Agnes 文生图封面（1024x1024，prompt 留空自动按游戏名+模板拼商用封面描述），失败降级 `_fallback_game_cover`（PIL 渐变底 + 装饰圆环 + textbbox 居中的游戏名/玩法说明） |

#### 四、小程序工坊：模板扩充 + 商用级生成质量

| 改动 | 说明 |
|---|---|
| `backend/miniapp.py` | 新增 food（外卖点餐）/ community（社区论坛）/ fitness（健身打卡）/ travel（旅行攻略）4 模板，模板总数 9；生成 prompt 追加商用级交互规则：规则 13（加载态/空状态/toast/onShareAppMessage/下拉刷新+触底加载）、规则 14（真实图片 URL/安全间距/统一圆角配色） |

#### 五、脚本补齐：全模块一键验证

| 改动 | 说明 |
|---|---|
| `scripts/verify_all_factories.py`（新增，~340 行） | 全模块一键验证脚本，零第三方依赖（urllib + 手工 multipart）：冒烟模式（21 项只读检查：模板/列表/stats/接口参数校验）+ `--deep` 深度模式（真实生成：文生图→下载→分割→背景替换→模板创建渲染、视频生成→拼接→配乐→字幕、音乐、配音、表情、游戏双版本+AI 封面、小程序 QC）；退出码 0=全过 / 1=有失败；`PLATFORM_BASE/USER/PASS` 环境变量可配 |
| 脚本踩坑 | ① 多处接口直接返回数组而非包对象（模板/列表）→ 断言 `isinstance(data, list)`；② `/template/render` 需先 `/template/create` 拿 id（且 rect 图层参数是 width/height 而非 w/h）；③ `/api/meme/generate` 需 `?sync=true` 才同步返回产物 URL |

#### 六、验证结果

| 项目 | 结果 |
|---|---|
| 前端 build | ✅ 通过（ImageFactoryPage +166 行、VideoFactoryPage +314 行，无 lint 错误） |
| 前端 UI 实测 | ✅ 图片编辑 Tab：人像分割（羽化滑块）/背景替换（9 场景+纯色+AI 描述）渲染正常；视频工厂：后期工具三入口 + 拼接 Modal（勾选/禁用逻辑）正常；无 Console 错误 |
| 冒烟 | ✅ 21/21 |
| 深度验证（最终轮） | ✅ **37/37 全部通过**（397.5s）：图片 5 项（文生图/分割/背景替换/模板创建/模板渲染）、视频 4 项（生成/拼接/配乐/字幕）、音乐、配音、表情、游戏双版本+AI 封面、小程序 QC 全过 |


### v13.23 平台整体能力升级（2026-08-10）：短剧工厂 + 数字人提速 + 商业化闭环 + 研发底座

> 目标：① 上线短剧工厂（经典动画卡 / 数字人播报双模式，本地管线端到端出片）；② 数字人提速（SadTalker 512 分辨率 + Face Renderer 分块批处理）；③ 商业化闭环（新工坊配额覆盖 + API Key 使用报表 + 邀请激励 UI 对齐）；④ 研发底座（Agent 执行历史 + 全模块验证脚本扩展）。

#### 一、短剧工厂（T1.1/T1.2/T1.3）

| 改动 | 说明 |
|---|---|
| `backend/short_drama.py`（新增，~526 行） | `POST /api/drama/generate`（Form：theme/title/duration/scenes_json/avatar_mode/avatar_id/dh_engine/sync）：剧本（LLM 生成 4-8 镜或自定义分镜 JSON `[{shot,narrator,dialogue,sec}]`）→ 逐镜配音（CosyVoice 降级链）→ 画面 → ffmpeg 拼接 → SRT 字幕烧录；产物 mp4 + srt + 封面（首镜帧）入 `drama_factory/` 与 artifacts；`GET /list`、`/videos/{name}`、`/srt/{name}`、`/covers/{name}`；异步任务注册 `drama_generate`（user_limit=1, pool=long） |
| 数字人说话头模式（T1.2） | `avatar_mode=true` 时每镜调 `_dh_scene_video`（digital_human 引擎链：2d/live_portrait，sadtalker 耗时过长不适用），数字人失败自动回退背景图卡片模式；**配额设计：worker 内扣费而非 `_QUOTA_PATHS` 中间件**（数字人模式每镜由 digital_human 内部扣费，中间件再扣会双重计费），超限返回 402 分层引导（免费促升级 / 会员提示明日恢复） |
| 配额覆盖（T1.3/T3.1） | 短剧/数字人走「worker 内 consume_quota」设计（注释明确不进 `_QUOTA_PATHS`）；`_QUOTA_PATHS` 已有 games/miniapp/video-factory/tools，覆盖全部新工坊端点；402 文案与会员体系对齐 |
| 前端 `ShortDramaPage.jsx`（新增） | 主题输入 + 时长选择 + 画面模式切换（经典动画卡 / 数字人播报）+ 自定义分镜 JSON 编辑；作品列表（封面/时长/播放/字幕下载）；路由 `/drama` + Sidebar 导航 + `permissions.PAGES` 注册（访问控制对齐） |

#### 二、数字人提速（T2.1/T2.2）

| 改动 | 说明 |
|---|---|
| SadTalker 512 分辨率（T2.1） | `backend/digital_human_sadtalker.py`：`_pick_render_size()` 探测可用内存（≥10GB 用 512，否则 256 防 OOM）；提交任务时把 render_size 写入任务参数，引擎按 512/256 推理；产物 metadata `render_size` 记录**真实推理分辨率**；`_scale_to_resolution`（lanczos）统一缩放至用户选择的 720p/1080p，平台缩放链路不变；`digital_human.py` 记录 `render_size` 字段（修复 TTS 失败路径 UnboundLocalError：初始化移出引擎循环） |
| Face Renderer 分块（T2.2） | `~/ai-models/SadTalker/src/facerender/modules/make_animation.py`：`_auto_chunk()` 按可用内存选分块（256 分辨率内存 ≥12G→8、≥6G→4、否则 1；512 分辨率 ≥16G→4 否则 1），分块对齐 batch_size 倍数后合并推理（Conv3D 内核加载/线程调度摊销），内存受限自动回退逐帧串行（行为与原版一致）；**实跑验证（真实模型 16 帧）：chunk 与串行输出逐元素一致（max_diff=0），每帧 7.56s vs 33.6s（4.45x），375 帧场景 ~47 分钟 vs 串行 ~210 分钟** |

#### 三、创作体验（T2.3/T2.4）

| 改动 | 说明 |
|---|---|
| 口播试听（T2.3） | `backend/voice_factory.py`：`POST /api/voice/preview`（voice+text，≤80 字，未知音色 400）复用 `_tts_one` 全降级链；`DigitalHumanPage.jsx`「试听语音」按钮（仅系统音色，自定义/克隆声音提示不支持），生成前先验证音频效果 |
| 「换一版」快速重跑（T2.4） | `ImageFactoryPage.jsx` / `VideoFactoryPage.jsx` / `MusicFactoryPage.jsx` 结果区「换一版」按钮（RefreshCw 图标）：同参数重新生成，复用 submitTask，生成中禁用防重复提交 |

#### 四、商业化闭环（T3.2/T3.3）

| 改动 | 说明 |
|---|---|
| API Key 使用报表（T3.2） | `openai_gateway.py` 调用成功/失败写 usage_logs 时标记 `api_key`（带前缀截断）；`apikey_api.py`：`GET /api/api-keys/usage` 按天聚合（请求数/成功数/错误数/消耗 LLM token，近 30 天 + 每 Key 明细 + 总计）；`ApiDocsPage.jsx` 展示统计卡片 + 按天趋势 + 每 Key 明细 + 限流说明 |
| 邀请激励对齐（T3.3） | 后端 `/api/invite`、`/api/invite/leaderboard` 已有；`MembershipPage.jsx` 补「我的邀请」区块（邀请码/链接复制/已邀请用户列表，每邀请双方各 +5 次额度，与 /api/invite 数据结构对齐） |

#### 五、研发底座（T4.1）

| 改动 | 说明 |
|---|---|
| Agent 执行历史 | `chat_engine.py`：`agent_executions` 表记录（agent_id/user_id/message/status/elapsed/error，失败静默）；`GET /api/agent-executions`（agent_id/user_id 过滤 + limit，按时间倒序）；`AgentExecutePage.jsx` 右侧面板「执行历史」（最近 20 次：时间/任务/结果状态/耗时，失败可点开看错误） |

#### 六、验证（T4.2）

| 项目 | 结果 |
|---|---|
| `scripts/verify_all_factories.py` 扩展 | 冒烟 +4 项（短剧作品列表 / 口播试听参数校验 / API Key 报表结构 / **配额 402 分层引导**：注册临时用户→DB 置超限→drama sync 应 402→清理）；深度 +2 项（短剧同步生成含字幕+下载成片 / 口播试听真实音频 >1KB） |
| 冒烟 | ✅ **25/25**（1.0s） |
| 深度回归 | ✅ **44/44**（705.6s）：图片 5 / 视频 4 / 音乐 / 配音 / 表情 / 游戏双版本+AI 封面 / 小程序 QC / 短剧生成+下载 / 口播试听 |
| pytest | ✅ **457 passed, 0 failed**（修复：① `digital_human.py` sadtalker_render_size TTS 失败路径 UnboundLocalError；② `permissions.py` 补 drama 页面注册（Sidebar/AccessGuard 对齐）；③ `test_game_factory_qc.py` 单 web 版用例对齐 v13.9 双版本硬门禁设计） |
| ruff | ✅ backend/ + scripts/ 全部通过（存量 19 项清零：F401/I001 自动修复、B904 `raise from None`、B023 lambda 默认值绑定、C901 noqa 按项目约定） |
| 前端 build | ✅ 10.7s 成功（仅 chunk 体积警告） |
| Browser UI 实测 | ✅ 5 页面零 console 错误：短剧工厂（双模式+作品列表+播放/字 幕下载）、数字人试听（真实播放 11.7s，`/api/voice/preview` 200）、图片工厂换一版（真实生成 1024px 图）、API Key 报表（请求 2/成功 2/token 106 真实数据）、视频工厂换一版（任务完成） |

### v13.24 数字人情绪系统（2026-08-10）：声音 → 表情 → 渲染全链路情绪化

## 一、背景

用户实测反馈「AI 数字人基本上成型了，但情绪还不够、很模糊」。根因：TTS 无情绪发音风格、2D 渲染无情绪表情（只有字级嘴型/眨眼/律动）、SadTalker `expression_scale` 硬编码 1.0、文案无情绪标注。本版建立**统一情绪模型**贯穿声音、表情、渲染全链路，并支持 LLM 自动标注。

**统一情绪模型**：`neutral 自然 / happy 欢快 / sad 悲伤 / angry 激昂 / gentle 温柔 / serious 严肃`，请求层额外支持 `auto`（LLM 判断后落盘到 6 类之一，失败回退 neutral 不阻塞生成）。TTS style 映射：happy→cheerful、sad→sad、angry→angry、gentle→gentle、serious→serious、neutral→无 style。前端默认 `auto`。

## 二、改动清单

### T1 声音情绪通道（voice_factory.py + edge_tts_worker.py）
| 文件 | 改动 |
|---|---|
| `backend/edge_tts_worker.py` | 新增可选 style 参数（argv[7]）：非空时用 `<speak><voice name=...><mstts:express-as style=...>` SSML 包裹（文本 `html.escape` 转义 `& < > " '` 防 XML 破坏），否则走原文；旧调用方（音乐工厂 6 参）向后兼容 |
| `backend/voice_factory.py` | `_tts_one`/`_tts_edge` 增加 `emotion=""` 参数（第 5 参）；带风格合成失败自动降级无风格重试 2 次（部分音色不支持 style）；CosyVoice 通道不支持情绪，保留参数但忽略不报错 |

### T2 数字人后端参数链（digital_human.py）
| 改动 | 说明 |
|---|---|
| 请求模型 | `GenerateRequest`/`BatchGenerateRequest` 加 `emotion: str = Field("auto", pattern="^(auto\|neutral\|happy\|sad\|angry\|gentle\|serious)$")`，非法值 422 |
| 缓存分区 | `_tts_cache_key`/`_tts_cached` 加 emotion：同文案不同情绪不同音频缓存（实测 happy/sad 各自独立合成） |
| 自动标注 | `_detect_emotion(text)`：call_llm 低 token（max_tokens=16, temperature=0.3, timeout=30），输出白名单 + 中文别名模糊匹配（「悲伤」→sad 等），异常/非法回退 neutral 绝不阻塞生成 |
| 全链路透传 | TTS 调用 style；sadtalker 分支传 emotion；2d 渲染 `_render_video(..., emotion=...)`；live_portrait 忽略（Wav2Lip 无表情控制，降级链兜底） |
| DB 落库 | `digital_human_records` 补 emotion 列（TEXT DEFAULT 'auto'，与 template_id 同补列模式）；返回体带 emotion |
| 批量任务 | items/DB `digital_human_batches` 持久化 emotion；worker 逐条透传；**重试失败项保持原情绪**（修复：重试重建请求曾丢 emotion 回落 auto 重新 LLM 判断） |

### T3 2D 情绪表情渲染（digital_human.py 渲染层）
| 元素 | 实现 |
|---|---|
| 情绪参数表 | `_EMOTION_FACE` 模块级 dict（brow 眉形/brow_k 透明度/squint 眯眼/smile 嘴角/cheek 腮红/move 动作幅度/head 头姿），帧级直接查表无状态（多线程并发安全） |
| 眉毛贴图 | `_get_eyebrow_template(eye_w, pose)`：程序化眉形（弧线渐变+羽化，半透明深棕），4 种 pose（flat/rise 上挑/droop 下垂/knit 皱眉），按 (eye_w, pose) 缓存；happy 上挑、sad 八字下垂、angry 下压皱眉 |
| 眯眼叠加 | 眼睑深度取 `max(blink_close, emotion_squint)`：happy 0.35 / angry 0.5 恒定轻微下压 |
| 嘴角 | `_get_mouth_template` 增加 smile 维度（-1~+1 五档缓存）：嘴角端点上移（微笑）/下移（撇嘴），椭圆中部保持 |
| 颊彩/体态 | 腮红 alpha 乘情绪系数（happy ×1.35 / sad ×0.7）；tilt/breath 幅度乘 move 系数；头姿偏移 ±1~2° |

### T4 照片数字人表情增强（avatar_engine + digital_human_sadtalker.py）
| 文件 | 改动 |
|---|---|
| `backend/avatar_engine/server.py` | `release_task` 加 `expression_scale: float = Form(1.5)` 透传 opts |
| `backend/avatar_engine/sad_engine.py` | `run_inference` 加 expression_scale（clamp 0.5~2.5）替换硬编码 1.0 |
| `backend/digital_human_sadtalker.py` | `EMOTION_EXPRESSION_SCALE` 映射：neutral/serious→1.3、happy/sad→1.8、angry→2.0、gentle→1.5（默认 1.5 比旧版 1.0 生动），提交 release_task 透传 |
| 生效 | 需重启 avatar_engine（9890） |

### T5 短剧情绪自动标注（short_drama.py）
| 改动 | 说明 |
|---|---|
| 剧本 prompt | `_SCRIPT_SYSTEM` 每镜 scene JSON 增加 `"emotion"` 字段（6 类之一），要求台词口吻与情绪一致 |
| 解析清洗 | `_parse_script` 白名单清洗：非法值/中文标签（悲伤→sad 等）统一映射，缺省补 neutral |
| 透传 | `_dh_scene_video`→`_generate_one` 与 `_tts_scene`（情绪镜自动切 Azure 音色 zh-CN-XiaoxiaoNeural + style；neutral 镜保持 CosyVoice「中文女」现状） |
| UI | 短剧不开放手动情绪（LLM 全自动） |

### T6 前端（DigitalHumanPage.jsx）
| 改动 | 说明 |
|---|---|
| 情绪选择器 | 生成区新增 7 个情绪卡片横排（自动✨/自然🙂/欢快😄/悲伤😢/激昂🔥/温柔😊/严肃🧐，默认自动），选中 violet 高亮；auto 时提示「AI 自动分析文案情绪（声音 + 表情联动）」；单条/批量 payload 均带 emotion |
| 记录回显 | 记录行 + 结果面板回显情绪标签（复用记录接口已返回的 emotion 字段）；复用历史记录时回填情绪 |

## 三、验证结果

| 项目 | 结果 |
|---|---|
| 单测（新增 `tests/unit/test_dh_emotion.py`，14 用例） | ✅ 全通过：SSML style 参数透传（mock worker 断言 args）、无情绪不追加 style（兼容旧调用方）、缓存 key 情绪分区、请求白名单非法值 422、`_detect_emotion` 中文别名/非法输出/异常三路回退 neutral、`_EMOTION_FACE` 表完整、嘴部 smile 五档/眉毛 4 pose 输出差异、`_parse_script` 情绪清洗 |
| 全量 pytest | ✅ **471 passed, 0 failed**（修复：① 批量重试 `retry_batch_failed` 重建请求丢失 emotion→回落 auto 触发 LLM（测试环境不可达拖垮 15s 超时），补 `digital_human_batches.emotion` 列 + 内存 task 持久化 + 重试透传；② 测试 mock 适配 `_tts_one` 第 5 参；③ `_generate_one` getattr 防御旧请求对象无 emotion 字段） |
| ruff | ✅ backend/ + tests/ + scripts/ 全部通过 |
| 前端 build | ✅ 12.4s 成功（仅 chunk 体积警告） |
| 冒烟 | ✅ **27/27**（新增：数字人形象列表 + 情绪参数白名单 emotion=bogus → 4xx） |
| 深度回归 | ✅ 47/47（新增：`emotion=happy` 2D 全链路生成断言 video_url + emotion 落库） |
| 真实链路验证 | ✅ happy vs sad 双生成对比：TTS 情绪缓存分区独立合成（cheerful 42.7s/256KB vs sad 41.3s/248KB）；视频帧像素分析显示表情差异显著（眉毛区域差 32.7 / 腮红 34.2，远高于全帧平均 15.5），happy 上挑眉+腮红增强 vs sad 下垂眉+腮红减弱 |
| 服务重启 | ✅ 8888 主服务 + 9890 avatar_engine（expression_scale 生效）；9888/9889 未改代码不重启 |

## 四、设计要点

- **统一情绪模型贯穿全链路**：请求层 auto → LLM 标注落盘 6 类 → TTS style 发音 → 2D 表情参数表 → SadTalker expression_scale，一条情绪值驱动所有表现层
- **降级链保证可用性**：LLM 标注失败回退 neutral、TTS style 失败降级无风格、CosyVoice 忽略情绪参数、live_portrait 不控制表情——任何环节失败都不阻塞生成
- **无状态渲染**：情绪表情全部用模块级参数表 + 模板缓存（眉毛 4 pose / 嘴部 5 档 smile），帧级直接查表，多线程并发渲染安全
- **缓存分区防串味**：emotion 进 TTS 缓存 key，不同情绪的同一文案不会命中同一音频；批量任务 emotion 持久化（DB 列 + 内存 task），重启后重试仍保持原情绪
- **向后兼容**：emotion 默认值（"" / "auto" / "neutral"）设计，旧调用方（音乐工厂、voice preview 等）零改动；`_generate_one` getattr 防御旧请求对象

---

### v13.25 短剧工厂开源化升级（2026-08-10）：素材库管线 + 导航归位

#### 一、背景
用户反馈「短剧做得太差」。根因：镜头画面仅是 PIL 渐变背景 + 文字卡片（图文卡片播放器），无真实画面感。
调研 GitHub 开源方案（MoneyPrinterTurbo 56K★ / ShortGPT / MoneyPrinterPlus）核心管线：LLM 生成脚本时同步输出
**素材搜索关键词** → 按镜从 Pexels/Pixabay 免费素材库拉真实竖屏视频素材 → 配音 + 字幕 + BGM 合成。

#### 二、改动清单
| 模块 | 改动 |
| --- | --- |
| 导航 | 短剧工厂从「应用与社区」移至「内容创作」（视频工厂之后） |
| 剧本 | LLM 剧本 JSON 新增 `search` 字段（每镜英文素材关键词 2-4 词），`_parse_script` 清洗（限长 60/去引号），缺失回退 shot 前 30 字符 |
| 素材层 | Pexels API 搜索（竖屏优先 + 720~1920 宽选材）→ 流式下载 + URL 哈希缓存 → 本地 `drama_factory/materials/` 关键词模糊匹配 |
| 渲染 | 新 `_material_scene_video`：视频素材 cover 裁剪无黑边 + `-stream_loop` 循环补时长 + 混入配音；图片素材 2x 放大 zoompan Ken Burns 缓慢推近 |
| 回退链 | 三级回退：数字人播报（avatar_mode）→ 素材模式 → 渐变卡片兜底（逐镜独立） |
| BGM | `drama_factory/music/` 扫描随机选曲，音量 12% + 首尾 2s 淡入淡出，与字幕烧录合并一次 re-encode |
| 转场 | 每镜统一 fade in/out 0.25s（视觉柔和过渡，避免 xfade 全局重编码） |
| 接口 | 新增 `GET /api/drama/config`（pexels_configured / local_materials / music_tracks）；`GET /list` 补 title（从 artifacts 表 metadata 读取） |
| 前端 | 画面模式改为「素材模式（默认，AI 自动匹配真实视频素材）/ 数字人播报」两卡；素材源状态徽章 + Pexels key 注册提示 |

#### 三、验证结果
- 单测：`tests/unit/test_drama_material.py` 13 用例全过（search 清洗/回退、Pexels 选材策略、本地匹配、BGM、config 接口）
- 全量 pytest：**479 passed, 5 skipped**；ruff 全过；前端 build 成功
- ffmpeg 链路实测：图片 Ken Burns 5s 出片、2s 素材视频循环 cover 到 5s（720x1280 h264+aac）
- 真实生成：主题「程序员深夜加班」→ 《代码之夜》5 镜 177s 出片，字幕/封面/列表齐全
- Browser UI 验证：导航归位、素材模式默认高亮、amber 徽章与注册提示、零 console 错误、作品 hover 播放

#### 四、Pexels Key 启用指引（3 步）
1. 打开 https://www.pexels.com/api/ 注册账号（免费）→ 创建 API Key
2. 将 Key 填入 `backend/.env` 的 `PEXELS_API_KEY=`
3. 重启服务（`kill` 8888 后 `nohup python3 main.py`）→ 前端徽章变为「Pexels 素材库已启用」

无 Key 时自动回退：本地素材目录 `backend/drama_factory/materials/`（文件名含关键词，如 `city_rain.mp4`、`sunset_sky.jpg`）→ 渐变卡片兜底。

#### 五、设计要点
- **素材获取零阻塞**：Pexels 超时 10s/下载 60s，任何失败静默回退，不阻塞整条生成链路
- **缓存防重复下载**：素材按 `sha256(关键词|URL)` 缓存到 `drama_factory/cache/`，同镜重复生成秒级复用
- **编码对齐可拼接**：素材镜头与卡片镜头统一 libx264 fast + yuv420p + aac 128k + 25fps，concat demuxer 直接拼接
- **每镜独立回退**：不再整体切换模式（旧版数字人配额超限后全部变卡片），失败镜头单镜降级，其余镜头保持高质量
- **画质优先选材**：竖屏优先 + 720~1920 宽，兼顾清晰度与下载体积；短素材自动循环补足镜头时长

---

## v13.26 产物统一命名体系（2026-08-10）

### 一、背景
图片/视频/音乐工厂的列表与下载名此前展示随机时间戳 ID（`img_1786337267291.png`、`video_bGl0…mp4`、`music_1786337492230`），用户无法辨识产物内容，下载到本地也是随机名。

### 二、改动清单
| 模块 | 改动 |
|---|---|
| `common/artifacts.py` | 新增 `derive_title()`：统一标题派生（metadata.title → theme → content 的 prompt/topic/text → lyrics 首行，截断 30 字） |
| `image_factory.py` | `_save_artifact` 登记时自动写 title；`/images` 列表合并 prompt/title；空 title 兜底 `图片 · MM-DD HH:MM`（文件名时间戳转日期） |
| `video_factory.py` | `_save_artifact` 登记时自动写 title；`/list` 合并 title；空 title 按前缀兜底（字幕合成视频/配乐视频/视频拼接合成/AI 视频作品），消除 base64 长名展示 |
| `music_factory.py` | `/list` 返回 title（metadata.title → theme → 歌词首行，含 `\n` 字面转义还原与引号清洗） |
| `VideoFactoryPage.jsx` | 卡片/拼接勾选/视频选择器显示 title；分享文案与下载名语义化（`标题.mp4`） |
| `ImageFactoryPage.jsx` | 网格/列表显示 title；下载名语义化；搜索扩展匹配 title/prompt |
| `MusicFactoryPage.jsx` | 列表显示歌词首行/theme 标题（原仅时间戳数字） |
| `tests/unit/test_artifact_titles.py` | 新增 14 用例（派生规则/工厂写入/存量兜底） |

### 三、验证结果
- 单测：14/14 通过；全量 pytest **489 passed, 5 skipped**（+10）；ruff 全过
- 接口实测：视频 35/35、图片 105/105、音乐 14/14 全部返回非空 title（存量数据经兜底全覆盖）
- Browser UI 验证（强制刷新后）：视频页 6 类语义标题可见、零裸文件名、0 console 错误；图片页提示词/日期标题全覆盖；音乐页歌词首行标题全覆盖

### 四、命名优先级（三层覆盖）
1. `metadata.title`（用户改名/生成时显式标题）→ 2. 内容派生（prompt/topic/theme/歌词首行，截断 30 字）→ 3. 存量兜底（视频按前缀语义化、图片转日期）

### 五、说明
- 文件系统内部仍用时间戳 ID（稳定、避免存量文件名变更），语义名仅作用于展示层与下载名
- 语音工厂/表情包/短剧此前已有 title + 改名能力，本次未改动

---

## v13.27 短剧长剧能力（2026-08-10）

### 一、背景
用户反馈短剧应支持 10 分钟以上时长。原链路限制：剧本场次硬限 4-8 场、duration_hint 截断 120s、单镜 sec≤15s、max_tokens 3000，前端最长 2 分钟档。

### 二、改动清单
| 模块 | 改动 |
|---|---|
| `short_drama.py` | `_SCRIPT_SYSTEM` 场次规则公式化：场次数 ≈ 目标秒数 ÷ 每场 25-30 秒（300s→10-12 场；600s→20-24 场），台词 60-100 字/场撑 20-30 秒口播，总时长贴近目标 ±20% |
| `short_drama.py` | `_parse_script` 单镜 sec clamp 2-45s（原 ≤15）；duration_hint 放宽到 1800s（30 分钟）；max_tokens 3000→8000、剧本超时 180→300s；防御截断 32 场 |
| `ShortDramaPage.jsx` | 时长档位 [30,45,60,120,300,600]（5/10 分钟档显示中文）；文案改「支持 10 分钟长剧」；自定义分镜 sec 提示 2-45 |
| `tests/unit/test_drama_material.py` | +3 用例：sec clamp 45 / 下限 2 / 28 场长剧本解析 |

### 三、真实生成验证（Pexels 素材模式）
| 档位 | 场次 | 实际时长 | 偏差 | 结论 |
|---|---|---|---|---|
| 300s（旧提示 60-160 字） | 18 镜 | 735s（12分15秒） | +145% | 台词过长 |
| 600s（60-100 字） | 12 镜 | 436s（7分16秒） | -27% | 场次偏少 |
| 600s（公式化场次） | 12 镜 | 651s（10分51秒） | **+8.6%** | ✅ 达标 |

- 生成耗时约 4-8 分钟（素材缓存复用后更快）；看门狗 180 分钟无超时风险
- 作品：《雨夜追凶》（18 镜 12 分 15 秒）、《剑问苍穹：十年一梦》（12 镜 7 分 16 秒，LLM 实际起名）、《代码帝国：从宿舍到纳斯达克》（12 镜 10 分 51 秒）

### 四、设计要点
- **时长由配音文本量决定**：单镜时长 = max(配音, sec)，素材循环补足画面；控制台词 60-100 字/场即可让总时长贴合目标 ±20%
- **场次公式化优于区间提示**：LLM 对「目标秒数 ÷ 每场 25-30 秒」的计算比区间更精准（实测 651s vs 目标 600s）
- **32 场防御截断**：防 LLM 失控超长剧本导致任务无限拉长（约 12-15 分钟内容上限，如需要可再放宽）

---

## v13.28 短剧自定义时长 + 真封面缩略图（2026-08-10）

### 一、背景
用户反馈两点：① 时长只能选固定档位（30s/45s/60s/120s/5分钟/10分钟），无法输入任意时长；② 短剧生成后没有封面缩略图。排查发现「封面」是把首镜 MP4 原样复制改名 `.jpg`（file 识别为 ISO Media MP4），列表用 `<video>` 能播，但素材库/分享等 `<img>` 场景必然裂图。

### 二、改动清单
| 模块 | 改动 |
|---|---|
| `short_drama.py` | 新增 `_extract_cover`（ffmpeg 抽帧首镜 720x1280 真 JPG）+ `_make_preview`（首镜前 6 秒 preview.mp4，`-movflags +faststart`）；worker 封面段替换；list 过滤 `_preview.mp4` 并新增 `preview_url` 字段 |
| `short_drama.py` | 新增 `_enforce_duration` 时长硬校验：场次数上限 `min(32, max(4, ceil(hint/20)))` + 台词预算 `hint×2.5 字/秒` 比例截断 + 单镜 sec 双向收敛（均场值 base 的 ±25% 窗口内不动，超出收敛到 base，base 上限 45s） |
| `short_drama.py` | 剧本解析重试 3 次（LLM 偶发坏 JSON）；三处 ffmpeg `-shortest` → `-af apad`（防短音频截断 sec 画面保底） |
| `voice_factory.py` | `_tts_edge` 情绪改 pitch 映射：emotion 不再传 SSML express-as（实测强制 0.63 字/s 语速黑洞），改为 pitch 叠加（happy +15Hz / sad -15Hz / angry +12Hz / gentle -5Hz / serious 0），语速恢复 4.76 字/s |
| `digital_human.py` | `_tts_cache_key` 加 `v28|` 前缀，使旧 SSML style 慢速音频缓存失效 |
| `ShortDramaPage.jsx` | 自定义时长输入框（分钟，0.5-30 步进 0.5，提交转秒；档位点击清空自定义）；列表封面 `<video>` 改 `<img>`（真 JPG）+ hover 播放 preview |
| 存量迁移 | 11 个假 jpg 全部 PIL 验证 → ffmpeg 抽帧重建真封面（18MB → 23-199KB）；补生成 11 个存量 preview.mp4 |
| `tests/unit/test_drama_material.py` | 新增 TestEnforceDuration 6 用例（场次截断/短目标保底/32 上限/台词预算/预算内不动/sec 双向收敛） |

### 三、真实生成验证（时长精度七轮迭代）
目标 210s 档位，最初 LLM 直接出片 **1049s（+400%）**，逐轮加防御与实测修复：
| 轮次 | 成片 | 偏差 | 根因与修复 |
|---|---|---|---|
| ① | 1049s | +400% | LLM 场次/台词失控 → `_enforce_duration` 三重防御（场次 + 台词预算 + sec 归一） |
| ② | 390s | +86% | LLM 单镜 sec 写 30-40s → sec 上限 1.5 倍压缩 |
| ③ | - | 坏 JSON | 剧本解析重试 3 次 |
| ④⑤ | 367/371s | +75% | **TTS 情绪 SSML express-as 实测 0.63 字/s 语速黑洞**（sad/happy/serious 24 字 38s，rate/prosody 嵌套无效）→ 情绪改 pitch 表达，语速 4.76 字/s |
| ⑥ | 105s | -50% | LLM 单镜 sec 写小 → sec 双向收敛（<0.75 倍抬回 base） |
| ⑦ | 117s | -44% | **`-shortest` 被短音频截断，sec 兜底失效** → 三处改 `-af apad`（5s 音频+素材冒烟验证输出恰 20s） |
| ⑧ | 264s | +26% | sec 收敛窗口 1.5 → 1.25 收紧 |
| ⑨ | **211s** | **+0.5%** | ✅ 达标 |

600s 长剧回归（base=45 上限路径）：**586s（-2.3%）**，优于 v13.27 同档 651s（+8.6%），长剧能力未被破坏。

### 四、设计要点
- **单镜时长公式**：`dur = max(probe(音频), sec)`——配音与画面秒数取大，素材循环补足；sec 是 LLM 唯一能控制的画面保底量，必须收敛到均场值附近
- **TTS 情绪必须用 pitch 表达**：SSML express-as 强制极慢语速（0.63 字/s）且无法用 rate/prosody 修正（实测 speed 2.0/3.0 均输出固定 20s）；pitch 不影响语速，是情绪化的安全通道
- **`-shortest` 是画面保底的敌人**：短配音会提前截断输出流，使 sec 兜底失效；`-af apad` + `-t` 才能保证画面时长由 sec 控制
- **真封面收益**：抽帧 JPG（23-199KB）替代假封面（18MB），列表/素材库/分享全场景可用，且 hover preview 提供 6 秒动态预览
- **预览文件命名 `_preview.mp4` 后缀**：list 的 `glob("drama_*.mp4")` 必须过滤该后缀，否则被当成独立作品

---

## v13.29 短剧内容对齐 + AI 剧本工作台（2026-08-10）

### 一、背景
用户反馈：① 剧情跟字幕/画面"不太搭嘎"，像瞎拼接；② 短剧工厂要不要加 AI 写剧本。排查确认四个根因：卡片兜底画面是把整段台词印在渐变底上的"大字报"；Pexels 素材首条竖屏即用且同关键词永远同画面；SRT 字幕显示整镜时长导致配音结束后"有字无声"；LLM 剧本黑盒（用户看不到也改不了，只能手写 JSON）。

### 二、改动清单
| 模块 | 改动 |
|---|---|
| `short_drama.py` | 新增 `POST /api/drama/script`：主题+时长 → 剧本 JSON；抽公共 `_generate_script`（LLM 重试 3 次 + 时长防御），worker 与接口共用，返回即最终成片剧本（所见即所得） |
| `short_drama.py` | `_make_scene_card` 升级：新增 `_generate_scene_image`（AGNES 文生图 `agnes-image-2.1-flash`，768x1024→裁 720x1280，14s/镜），shot 描述 → 竖屏分镜插画；失败回退渐变海报（去掉整段台词大字报，只留剧名/序号/短标题） |
| `short_drama.py` | `_pexels_search_video` 相关性增强：per_page 5→15、时长过滤 8-40s、按 (关键词+日期) 哈希轮换 top 5（打破同词同画面死锁） |
| `short_drama.py` | `_make_srt` 字幕时序收敛：字幕显示时长 = min(画面时长, 配音时长+0.6s)，时间轴按画面推进；worker 收集各镜配音时长（素材/卡片镜 probe 音频，数字人镜整镜有声） |
| `short_drama.py` | `_SCRIPT_SYSTEM` 编剧强化：shot 必须"画面里能拍到的东西"（禁抽象概念）；search 与 shot 完全对应（禁 dream/hope/life 等搜不到素材的词）；台词/旁白必须提到本镜画面里的具体元素（画面有雨才能说雨） |
| `ShortDramaPage.jsx` | AI 剧本工作台："AI 写剧本"按钮 → 剧本编辑面板（剧名 + 每镜 shot/search/narrator/dialogue/emotion/sec 可编辑，加镜/删镜/重新生成）→ "确认并生成短剧"走 scenes_json 链路；原 JSON 折叠区降级为高级选项 |
| `tests/unit/test_drama_material.py` | +11 用例：字幕时序 3 / 插画回退 3 / _generate_script 重试 2 / Pexels 轮换 3；旧 Pexels 测试适配时长过滤 |

### 三、验证结果
- 全量 pytest **520 passed**（+11）；eslint 干净
- `/api/drama/script` 实测：剧本 4 镜，shot 具体可拍（"深夜城市街道，空无一人，路灯昏黄，细雨蒙蒙"）、search 强呼应（night city street rain neon convenience store exterior）、台词提到画面元素
- 真实生成《深夜便利店的微光》65.35s（目标 60s，+8.9%）：SRT 每镜画面 15s 而字幕在配音结束（~10s）即消失，无"有字无声"
- 插画实测：220KB / 720x1280 / 14.3s 每镜，shot 描述驱动
- Browser UI 全过：AI 写剧本 → 4 镜面板字段齐全 → 编辑台词/加镜/删镜生效 → 确认生成 → 成片《深夜面馆》恰 1 分 0 秒（60s 目标），用户编辑的台词真实出现在字幕中，封面/字幕/MP4 全部 200，0 功能错误

### 四、设计要点
- **所见即所得剧本流**：`/script` 返回的剧本已过时长防御，与最终成片完全一致；用户编辑提交走既有 `scenes_override` 链路，无需新生成通道
- **画面三段式对齐**：数字人（人像口播）→ 素材（Pexels 关键词+时长过滤+日期轮换）→ 插画（AGNES 文生图 shot 驱动）→ 渐变（仅兜底且不再印台词）
- **字幕是配音的影子**：字幕时长应跟随配音而非画面（素材循环补足段无声，字幕应消失）；时间轴仍按画面推进保证全局同步
- **编剧 prompt 决定素材命中率**：search 具体化（元素/天气/道具）比抽象词（梦想/希望）的 Pexels 命中率与相关性高一个量级
- **插画成本可控**：14s/镜 × 22 镜 ≈ 5 分钟，仅素材不可用时触发，失败静默回退渐变不阻塞主链路

## v13.30 AI 插画模式角色一致性（2026-08-10）

### 一、背景

短剧质量第一痛点：同一角色跨镜漂移。素材模式是真实拍摄（同一演员无法保证），AI 插画模式此前纯文生图（同角色每镜脸型/发型/服装凭 prompt 自由发挥）。v13.30 引入**角色表 + 角色参考图链路**：先定妆、后出场必沿用，实现同角色全剧同脸同装。

### 二、改动清单

| 文件 | 改动 |
| --- | --- |
| `short_drama.py` | `_SCRIPT_SYSTEM` 编剧强化：先定义全剧 1-3 个主要角色（性别/年龄/发型/发色/服装全剧固定）；每镜 `chars` 列出场角色（1-2 个为宜）；首个出场安排单人镜定妆，后续出场必须沿用外貌服装；shot 必须点名出场角色并沿用其形象；search 以该镜主角英文特征词开头 |
| `short_drama.py` | `_parse_characters` 角色表解析（v13.30）：id 规范化（非字母数字下划线清洗）去重；每角色产出 `anchor`（姓名+性别+年龄+外貌+服装，插画 prompt 文字锚定）与 `search`（英文特征词，素材搜索同性别/同特征锚定） |
| `short_drama.py` | `_parse_script` 每镜 `chars` 解析：兼容旧 `char` 单值；与角色表同一规范化后白名单过滤，无效引用丢弃 |
| `short_drama.py` | `_anchor_search` 素材搜索锚定：主角英文特征词前缀 → Pexels 尽力搜索同性别/同特征素材 |
| `short_drama.py` | 插画模式角色参考图链路：`char_refs` 记录每角色最近一张单人插画 → 后续该角色出场镜走图生图（顶层 `image` 参数传 Data URI 数组，多角色同镜多图），配合 anchors 文字锚定；无参考图 → 纯文生图兜底 |
| `short_drama.py` | `/api/drama/generate` 新增 `characters_json`（角色表 JSON）+ `illust_mode`（AI 插画模式）参数 |
| `ShortDramaPage.jsx` | 角色编辑区（添加/删除角色，删除时同步清理各镜引用）+ 每镜出场角色多选 + AI 插画模式选项 + 插画模式 Badge |
| `tests/unit/test_drama_material.py` | +14 用例：TestCharactersParse 角色表解析 4 / TestAnchorSearch 锚定 3 / TestSceneImageRefs 参考图请求与回退 2 等 |

### 三、验证结果

- 全量 pytest **506 passed**（unit）+ **23 passed**（integration）；eslint 干净
- AGNES 图生图 API 实测：参考图走顶层 `image` 参数（Data URI 数组）生效，`size=1K` + `ratio=9:16` 竖屏分镜
- 真实生成《深夜面馆的暖汤》44.04s / 4 镜 / 插画模式（sync 链路）：角色表「老板娘陈姨（55 岁银灰盘发）+ 常客阿杰（黑短发深灰西装）」全链路生效
- **agnes-vision 一致性判定（4 帧跨镜对比，三项全「是」）**：A) 定妆镜 vs 后续镜主角同一人 ✅；B) 镜 2/3/4 中年女性同一人 ✅；C) 镜 2/3/4 主角相互同一人 ✅；连衬衫污渍、眼红肿等细节跨镜连续，角色一致性达成

### 四、设计要点

- **定妆即锁定**：首个单人镜完成定妆，其插画成为该角色参考图；后续出场全部图生图锚定，杜绝每镜重新发明形象
- **多模态锚定双保险**：图生图（像素级参考）+ anchors 中文文字锚定（语义级），参考图缺失时文字锚定兜底，链路不中断
- **素材模式尽力而为**：真实素材无法保证同一演员，用主角英文特征词前缀提升同性别/同特征命中率，UI 明示「追求角色一致请用 AI 插画模式」
- **兼容优先**：`chars` 新字段兼容旧 `char` 单值；未传角色表时行为与 v13.29 完全一致，零破坏

## v13.31 插画模式流畅度（2026-08-10）

### 一、背景

v13.30 角色一致性达成后，成片观感暴露两个流畅度问题：① 插画镜是纯静帧，画面长时间静止呆滞；② 每镜末尾 fade 到全黑再淡入，镜间黑场闪烁，拼接后观感一顿一顿。

### 二、改动清单

| 文件 | 改动 |
| --- | --- |
| `short_drama.py` | `_scene_video` 升级：Ken Burns 运镜（`motion` 参数，zoom_in/zoom_out/pan_in/pan_out 四式交替：推近/拉远/横摇，2x 放大防抖 + zoompan 平滑插值，短镜自动减速）；fade_in/fade_out 参数化 |
| `short_drama.py` | **zoompan 修复：`in` → `on`**。实测 `in`（输入帧计数）写法在按需求值拉流时全部输出帧共享 in=0，画面静止（素材模式旧代码的 Ken Burns 从未真正生效）；改用 `on`（输出帧计数）后运动量提升千倍（diff 0.029 → 36~45） |
| `short_drama.py` | 镜序 fade 控制：首镜淡入、末镜淡出、中间镜硬切（电影标准），消除镜间黑场闪烁；`_material_scene_video` 同步参数化 + 图片分支 zoompan 一并修复 |
| `tests/unit/test_drama_material.py` | +6 用例 TestSceneVideoMotion：zoompan 必须用 on / 中间镜无 fade / 首镜仅淡入 / 4 式运镜交替断言 / still 无 zoompan / 真实编码 2s 产物校验 |

### 三、验证结果

- 全量 pytest **512 passed**（unit，+6）；eslint 干净
- 命令级单测：4 式运镜 z 表达式、fade 组合全部断言通过
- 合成验证（真实帧图 4 镜 × 3s）：4 式运镜运动量 36~45（旧写法 0.029），拼接 12.04s 精确，镜间亮度全部 >30 无黑场
- 真实生成《深夜面馆的暖汤（v13.31 流畅版）》44.04s / 720x1280 / 25fps / 1100 帧：每镜运动量 27~42（Ken Burns 生效），镜间衔接亮度 57~87 无黑场闪烁
- agnes-vision 一致性复查：A/B/C 三项全「是」（v13.31 未破坏 v13.30 角色一致性）

### 四、设计要点

- **zoompan 必须用 `on`**：`in` 是输入帧计数，滤镜按需求值只拉 1 个输入帧时全部输出帧共享 in=0 → 画面静止；`on` 是输出帧计数，平滑递增
- **镜序 fade 优于每镜 fade**：全剧只在首镜淡入、末镜淡出，中间硬切（电影标准），黑场闪烁消失且拼接仍可 `-c copy` 零重编码
- **短镜减速**：<10s 镜运镜幅度 0.10→0.06，避免急促；横摇 ±17px 在 2x 放大余量内无黑边
- **卡片兜底 still**：渐变海报不运镜（文字不放大移动），保持旧行为

## v13.32 数字人镜流畅度：模糊填充背景 + 镜序 fade 对齐（2026-08-10）

### 一、背景

v13.31 短剧插画/素材镜流畅度升级后，数字人镜（avatar_mode）成片观感掉队：① 竖屏化是纯色 pad（0x101018 深色底）上下大黑边，与插画镜全屏风格割裂；② 无 fade，首镜硬开场、末镜硬结束，与其他镜风格不一致。

### 二、改动清单

| 文件 | 改动 |
| --- | --- |
| `short_drama.py` | `_dh_scene_video` 竖屏化升级：纯色 pad → 模糊填充背景（split 放大模糊底 gblur=25 + 压暗 10% + 原画居中 overlay，无黑边）；新增 fade_in/fade_out 参数按镜序控制 |
| `short_drama.py` | worker 数字人镜调用点传镜序 fade（首镜淡入、末镜淡出、中间镜硬切），与插画/素材镜统一 |
| `digital_human.py` | 2D 引擎运镜越界保护注释补全（x/y 双向） |
| `tests/unit/test_drama_material.py` | +3 用例 TestDhSceneVideo：模糊填充替代 pad / fade 按镜序控制 / 音频保留 |

### 三、验证结果

- 短剧单测 **53 passed**（+3）；eslint 干净
- 真实转码验证（模拟 1280x720 横屏数字人视频 → 竖屏化）：产物 720x1280、3.02s，四角亮度 22~194 无黑边，淡入（t=0.1s 亮度 54）→ 全亮（112）→ 淡出（91）曲线正确

### 四、设计要点

- **模糊填充优于纯色 pad**：放大模糊底 + 压暗 + 降饱和，视觉上“有景深”且不抢主体，与插画镜全屏风格统一；overlay 原画保持完整不变形
- **2D 引擎本身已有 Ken Burns**（PIL 逐帧裁剪：推近 5% + 呼吸 ±1.2% + sin 平移），v13.31 思路在 2D 数字人已内置，无需重复加 zoompan（真实人物视频叠加二次运镜反而乱）
- **fade 只作用于视频流**：数字人镜音频是 TTS 人声，不做 fade（避免吃掉字头），与 _scene_video 行为一致


---

# 升级日志 v14.0：工厂商业化发布升级（发布就绪包 + 内容质量层）

> 目标：每个工厂输出"发布就绪包"——**内容质量达标（安全/成套/美观）+ 平台规格合规 + 配套物料 + zip 打包 + 预留自动发布接口位**，
> 生成的成果基本不用改就能上架发布。

## 一、横向基础设施（所有模块复用）

| 文件 | 改动 |
|---|---|
| `backend/publish_kit.py`（新增） | `build_publish_zip`（统一 zip 打包：UTF-8 文件名、目录化组织、zip slip 路径穿越防护）；`license_text`（AI 生成内容商用授权说明）；`platform_spec_text`（平台规格说明模板）；`pack_dir_name`；`PublishProvider` 抽象基类 + `publish_registry`（预留自动发布接口位，未注册 provider 静默返回未配置消息，不阻塞主流程） |
| `backend/content_safety.py`（新增） | `check_text`（6 类违规词库：政治/色情/暴力/违禁/诈骗/辱骂，高危拒绝 + 中危警告 + 分类 + 整改建议）；`quality_check_image`（美观度自检：分辨率/Laplacian 清晰度/颜色方差对比度/RGB 色偏 → 0-100 分 + 等级 + 建议）；`quality_report`（质量自检报告.md，随发布包附带） |

## 二、六个工厂改动

| 工厂 | 改动 |
|---|---|
| 表情包 `meme_factory.py` | 生成前 top/bottom/AI prompt 全量 check_text 拦截；**成套生成** `POST /api/meme/generate-set`（一次 16 条文案，前置审核任一违规拒绝整包，AI 模式注入角色设定保持一致）；**发布包** `POST /api/meme/publish-pack`（微信规格：主图 240/缩略图 120/图标 50/横幅 750x400 + 表情说明 + 上传指南 + 规格说明 + LICENSE + 质量报告） |
| 音乐 `music_factory.py` | 歌词/主题/发布入口 check_text 审核；**发布包** `POST /api/music-factory/publish-pack`（mp3 + wav 母带 44.1kHz/16bit + flac 无损 + 封面 + lrc/txt 歌词 + 网易云/腾讯/抖音音乐人规格说明 + 上传指南 + LICENSE + 质量报告） |
| 图片 `image_factory.py` | prompt 审核；平台规格预设（小红书 1242x1660 / 抖音 1080x1920 / 淘宝 800x800 / 公众号 900x383，cover 模式居中裁剪不变形）；lanczos 2x + 锐化高清放大；**发布包** `POST /api/image-factory/publish-pack`（规格成品 + 2x 高清版 + 上架文案 + 规格说明 + LICENSE + 质量报告） |
| 视频 `video_factory.py` | prompt 审核；平台规格预设（抖音 1080x1920 / B站 1920x1080 / 视频号 1080x1230，ffmpeg cover 转码 + 抽帧封面）；**发布包** `POST /api/video-factory/publish-pack`（规格成片 + 封面 + 发布文案 + LICENSE + 质量报告） |
| 游戏 `game_factory.py` | **发布包** `GET /api/games/{proj_id}/publish-pack`（web/wx 成品 + 封面 + README + 上线清单 + LICENSE + 质量报告） |
| 小程序 `miniapp.py` | export-zip 增强：发布物料（介绍.md + 审核清单.md + LICENSE.txt + 质量自检报告.md） |

## 三、前端

| 页面 | 改动 |
|---|---|
| 表情包页 | 勾选工具栏新增「微信发布包」按钮（标题/介绍输入 → 打包下载）；生成区新增「成套生成」入口（批量文案 textarea + 角色设定 → 16 张成套任务） |
| 音乐页 | 每首歌曲操作区新增「发布包」按钮（标题/歌手/流派 → mp3+wav+flac 成套物料下载） |
| 图片页 | 画廊工具栏新增「发布包」按钮（选平台规格 + 标题 + 2x 高清开关 → 全部打包） |
| 视频页 | 每个视频新增「发布包」按钮（选平台规格 + 标题/描述 → 规格成片下载） |
| 游戏页 | 项目详情新增「发布包」按钮（成品 + 封面 + 上线清单 + 质量报告） |
| 小程序页 | 「下载 ZIP」升级为「下载发布包」（含介绍/审核清单/质量报告） |

## 四、质量保障

- 内容安全：生成前对 prompt/文案/歌词/标题全量审核，高风险拒绝生成；图像 NSFW 深度检测需专用模型，本次以文本审核 + 基础图像自检为主（质量报告中注明局限）
- 成套一致性：AI 模式注入"角色设定（全套必须完全一致）"prompt 约束，不引入训练/参考图
- 单测：`tests/unit/test_publish_pack.py`（新增 31 例：打包结构/磁盘路径契约/规格尺寸/审核拦 截/成套一致性/美观度自检/游戏·小程序发布包结构断言）
- 回归：全量 pytest **569 passed**；eslint 0 errors

## 五、验证结果（真实生成）

- 表情包：成套生成 3 张 + 违规文案拦截（单张 400 / 成套整包拒绝）✓；微信横幅 750x400 ✓
- 图片：cover 适配 123x456 → 1242x1660 不变形 ✓；2x 高清放大 ✓
- 视频：真实 ffmpeg cover 转码 1088x1920 → 1080x1920 ✓；发布包抽帧封面真实 JPEG ✓
- 音乐：真实 ffmpeg 转码 wav 母带（RIFF/WAVE + 44.1kHz 16bit）与 flac（fLaC）✓；lrc 头与时间轴 ✓
- 游戏/小程序：真实库内项目打包，README/上线清单/审核清单/质量报告齐全 ✓
- 路由：openapi 确认 25 个发布相关路由全部注册 ✓
- 脚本：`scripts/verify_publish_packs.py`（真实发布包 8 项校验，可随时重跑）

## 六、设计要点

- **发布就绪 = 规格合规 + 物料齐全 + 质量自证**：zip 内含上传指南、平台规格、商 用授权、质量自检报告，用户拿到即可按指南提交
- **PublishProvider 接口位**：平台自动发布需企业资质，本次只做发布就绪包 + provider 扩展点，注册实现类后即可触发真实发布
- **质量报告随包自证**：安全审核结果 + 美观度评分 + 规格合规写入 md，发布前人工 复核一目了然

---

# 升级日志 v15.0：全模块深度进化（四维升级：功能深度 / AI 专业度 / 前端体验 / 稳定性能）

> 目标：四大类模块（平台底座 / 效率工具 / 业务分析 / 创作工厂）逐模块执行四维升级，
> 功能补齐参数维度与模板库、Prompt 专业化 + 结构化输出、前端三态体验（骨架屏/错误重试/空状态）、
> 异常兜底 + 防重复提交 + 单测覆盖，杜绝 demo 级模块。

## 一、阶段一：公共体验底座（全部模块复用）

| 文件 | 改动 |
|---|---|
| `frontend/src/components/ui/Loading.jsx` | `ErrorState` 新增「重试」按钮回调（onRetry）；空状态引导组件齐备 |
| `frontend/src/components/ui/PageHeader.jsx` | 统一「标题+副标题+右侧操作区」规范，各页面逐一对齐 |
| `frontend/src/hooks/useRequest.js` | 统一「加载→成功/错误(可重试)→空」三态封装（loading/data/error + refresh），消除各页面手写样板 |
| `backend/common/safe_guard.py`（新增） | 统一异常兜底装饰器：记录日志 + 返回友好错误，避免 500 裸抛 |

## 二、阶段二：平台底座类（12 模块）

| 模块 | 改动 |
|---|---|
| AB 测试 | 后端新增「运行实验」`POST /api/ab-tests/{tid}/run`（LLM 分别产出 A/B 方案 + 打分对比）+「结果统计」`GET /api/ab-tests/{tid}/results`（胜出方/置信度/各维度评分），ab_tests 表加 results 列；前端运行按钮接入真实执行 + 结果卡片（A/B 内容对比 + 评分条形图 + 结论建议），创建表单加「目标维度」；单测断言 run/results 逻辑 |
| 定时任务 Scheduler | 执行历史落库（scheduler_runs 表：状态/开始结束时间/输出摘要/错误）；失败自动重试（最多 3 次指数退避）；job_type 扩展（report/notify/backup）；前端任务列表「最近执行状态」徽标 + 执行历史抽屉（时间线+日志）；单测覆盖 cron 解析边界（非法表达式/每月最后一天）与重试逻辑 |
| 通知中心 | 新增「站内信」落库（notifications 表）+ 已读/未读管理（SMTP/webhook 基础上补齐）；前端未读角标 + 全部已读 + 分页，通知设置页与 config 打通；单测断言站内信写入/已读 |
| 收藏/记录/用量/帮助/插件 | 统一三态体验（useRequest）+ 错误重试 + 空状态引导；用量分析「按用户/按模块筛选 + 趋势区间切换（7/30/90天）」；帮助页按模块索引搜索 |
| 权限 + API Key + Admin | 角色-权限矩阵可视化（管理端展示权限来源）；API Key「最后使用时间/用量统计」+ 密钥过期时间；Admin 健康体检；单测断言权限矩阵 |
| realtime/sessions/backup/gallery/drafts | 稳定性体检：异常兜底 + 单测抽查 |

## 三、阶段三：效率工具类（10 个）

| 工具 | 改动 |
|---|---|
| PDF 全家桶 | 合同审查输出升级为「风险分级表格（高/中/低）+ 修改建议 + 责任条款标注」；新增「压缩 PDF」功能；单测 |
| PPT 工厂 | 模板库补齐 4 类（商务汇报/路演/教学课件/营销方案）+ 大纲→成稿段落级结构化输出 + 导出 pptx 主题色/字体统一；单测 |
| Excel 助手 | 公式生成输出增加「公式说明+参数表」；数据清洗增加「异常值检测」结果可视化；单测 |
| 翻译 | 新增「术语表记忆」（用户自定义术语 → 翻译时强制应用）+ 双语对照导出 md/docx；单测 |
| 文案创作 | 模板库扩充 + 「平台适配」参数（公众号/小红书/抖音标题风格差异）；单测 |
| 思维导图 | 节点批量编辑 + 导出增强（md 大纲/思维导图图）+ PNG 导出；单测 |
| 文档问答 DocQA | 会话增加「引用溯源」（回答附原文片段定位）+ 多文档联合问答；单测 |
| 代码沙箱 | 常用包白名单提示 + 运行超时/资源上限明确提示 + 结果导出；单测 |
| Web 搜索 | 结果增加「时间筛选（近24h/7d/30d）+ 来源域过滤」；单测 |
| 批处理 BatchProcess | 任务模板（批量翻译/批量总结/批量改写）+ 进度条 + 失败项单独重试；单测 |

## 四、阶段四：业务分析类（8 个）

| 模块 | 改动 |
|---|---|
| SEO 分析 | 拆分独立 Tab/页面；输出升级「关键词分组+难度分级+优先级矩阵」 |
| 数据分析 | 结论输出升级为「洞察/异常/建议」三段式 + 数据概览图表 |
| 数据预测 | 增加「预测区间（上下界）」可视化 + 模型选择说明；单测 |
| 股票 | 增加「风险提示卡片」（波动率/回撤/流动性）+ 导出报告；单测 |
| 竞争监控 | 监控项增加「变化摘要」diff 高亮 + 频率设置；单测 |
| 内容策略 | 日历视图 + 主题库（标签筛选）；单测 |
| 视频分析 | 分析报告分段输出（画面/音频/文本）+ 导出；单测 |
| AB 测试分析 | 分析输出升级（与底座阶段联动）；单测 |

## 五、阶段五：创作工厂类增强（8 个）

| 工厂 | 改动 |
|---|---|
| 表情包 | 成套生成增加「风格预览图」；发布包支持多套合并；后端+单测+前端+eslint |
| 音乐 | 歌词生成增加「押韵/分段」参数；发布包封面可自定义上传；单测 |
| 图片 | 批量生成参数（数量/比例）上限优化 + 生成历史缩略图墙；单测 |
| 视频 | 文案生成模板库（口播/剧情/科普）+ 批量转码；单测 |
| 游戏 | 模板库扩充 + 迭代历史对比视图；单测 |
| 小程序 | 模板库扩充（12 个，新增问卷投票/活动报名/二手闲置）+ 提审材料自动生成（app.json 字段核对：pages 注册完整性/导航栏标题/tabBar 图标/权限声明；隐私接口扫描 requiredPrivateInfos；服务类目建议 + md 提审清单）；单测 |
| 短剧 | 分镜表导出 Excel（openpyxl：镜号/时长/情绪/角色/画面/关键词/旁白/台词 8 列）+ 批量生成素材清单（汇总 + 关键词回退链）；单测 |
| 数字人 | 行业模板库 5→8（新增生活记录/企业宣传/情感语录），每模板补可直接填充的 script_sample 示例文案（含{占位符}，前端一键填入）；「口播文案体检」`POST /api/digital-human/script-check`：长句无停顿（>35 字 warn / >60 字 error）/ emoji / 长数字串（≥3 位自动转中文）/ 长英文词 / 连续空行 / 全文无标点 8 项检查 + 预估朗读时长（4字/秒）+ 自动修复版文案一键应用；单测 |

## 六、质量保障

- 单测：新增 `tests/unit/test_*_v15.py` 系列（数字人/短剧/小程序/游戏/图片/表情/音乐/视频 + 平台底座/工具/分析模块各增量断言），纯函数级断言结构化输出与参数校验边界
- 回归：全量 pytest 全绿；eslint 0 errors
- 真实生成验证：每模块关键路径复用 `scripts/verify_publish_packs.py` 模式抽查

## 七、设计要点

- **纯函数 + 端点薄封装**：业务逻辑（build_*/check_*）写成可单测纯函数，端点只做校验与转发，问题易定位、回归成本低
- **模板库 = 场景配置 + 文案示例**：行业模板除场景/背景/音色/字幕样式外，补可直接填充的 script_sample（占位符由用户替换），一键成稿
- **文案层体检先行**：长句无停顿/emoji/长数字等会导致 TTS 读岔与字级口型时间轴错位，生成前体检 + 自动修复，从源头降低返工率

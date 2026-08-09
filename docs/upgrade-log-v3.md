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

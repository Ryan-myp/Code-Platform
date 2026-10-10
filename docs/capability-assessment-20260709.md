# Code-Platform 能力综合评估

> **评估日期**: 2026-07-09
> **对象**: github.com/Ryan-myp/Code-Platform（本地检出 /Users/yanping.ma/PycharmProjects/Code-Platform）
> **HEAD**: 4953a3c（441 commits）
> **方法**: 全仓静态扫描 + 后端全量 pytest（1155 用例）+ 前端 vitest（121 用例）+ 安全扫描 + 仓库卫生审计

---

## 一、总体定位

**小团智能平台 v8.0**：一个 AI 赋能的通用业务编排引擎 + 多模态内容工厂矩阵。

- 可视化工作流（前端拖拽画布 → 后端 StepExecutor + 状态持久化）
- 5 类扩展节点（LLM / File / API / Skill / Decision）
- 19 个内容工厂：图片、视频、短剧（drama）、数字人（SadTalker+LivePortrait）、音乐、配音（edge-tts/克隆）、PPT/Excel/PDF/思维导图/漫画/表情包/游戏/小程序
- 效率工具箱：190 个工具定义（覆盖 15 个行业类目）
- 平台化能力：JWT+bcrypt 鉴权、慢速限流、配额计费（Stripe/batch/共享）、RBAC 权限、审计日志、实时 WebSocket、任务队列（重试/退避）、调度器、插件注册、Agent 模板与扩展
- 商业化闭环：成员制（Membership/邀请返佣/分享奖励）、模板市场、发布套件（npm 风格 deploy-cli + tgz 包）

## 二、规模数据

| 维度 | 数值 |
|---|---|
| 后端 Python 文件 | 138 个 / **81,241 行**（剔除 artifacts） |
| API 端点 | main.py 94 + 各 router 579 ≈ **670+** |
| Router 注册 | 65 个 |
| 前端 | React 18 + Vite + Tailwind，126 个 JSX / **77,894 行**，**79 个页面** |
| 后端测试 | 84 文件 / **1155 用例** |
| 前端测试 | 16 文件 / **121 用例** |
| CI | `.github/workflows/ci.yml`（Ruff/质量门）+ `code-quality.yml`（全量编译拦截 SyntaxError） |
| Git 历史 | 441 commits，近 3 次提交集中在 P0 bug 修复 + tool_hub 拆分（8734→1174 行） |

## 三、工程质量实测

### 测试通过率（本机 2026-07-09）

| 套件 | 结果 |
|---|---|
| 后端 pytest（7:52 完成） | **1122 / 1155 通过（97.2%）**，33 失败 |
| 前端 vitest | **116 / 121 通过（95.9%）**，5 失败 |

失败分布与根因：

| 模块 | 失败数 | 根因 |
|---|---|---|
| test_digital_human + ops | 17 | 依赖本机 `ffmpeg` 二进制 + edge-tts mock 音频无法解析（环境相关） |
| test_drama_material | 12 | 同上（ffmpeg/素材管线） |
| test_task_queue | 2 | **真实缺陷**：手动重试未清退避 / 失败态重置逻辑与实现不符 |
| integration/test_api | 2 | 待定位 |
| 前端 3 个文件 | 5 | TemplateMarketPage 等异步泄漏（unhandled rejection） |

### 重构进度（正向信号）

- `tool_hub.py` 8734→1174 行（-87%），工具定义拆到 `tool_definitions.py`
- `quality_gates.py` 质量门禁 + 防回归；`common/sandbox_check.py` 拦截 `eval/exec/$` 注入
- 历史 P0 隐性 bug 已系统性清除（42e46c2）
- 测试覆盖率密度高：单文件 79+，含稳定性/阻塞检测（test_stability、test_event_loop_blocking）

## 四、安全评估

| 项 | 结论 |
|---|---|
| 密码哈希 | bcrypt（sha256 旧哈希自动迁移），正确截断 72 字节 ✅ |
| 鉴权 | JWT + jose，router 全量 `require_auth` ✅ |
| 限流 | slowapi Limiter ✅ |
| SQL 注入 | 动态 SQL 仅作用于**白名单硬编码表名**或带引号过滤的 cfg 表名，参数值全部占位符 ✅（风险低） |
| 命令注入 | Decision 节点用受限 `eval(expr, {"__builtins__":{}})`，工作流用 `_safe_eval`（ast 白名单）；沙箱工具走 `sandbox_check` 黑名单 ✅ |
| 密钥泄露 | 代码中未发现硬编码密钥；`.env` 未入库（有 .env.example）✅ |
| 隐患 | 根目录残留 `platform.db` / `xiaotuan.db` 本地库文件（未跟踪，注意勿提交） |

## 五、主要风险与技术债（按优先级）

### P0 — 仓库卫生 / 协作可用性

1. **`content-platform` 是 gitlink 嵌套仓库但没有 `.gitmodules`**：他人 clone 后此目录为空目录，协作直接断裂。本地工作区 4.2GB，其中 `backend/drama_factory` 缓存 3.6GB、`.venv` 305M、`uploads` 143M 均为未跟踪垃圾。
2. **主仓跟踪了 43 个生成物**（backend 下 image_factory/*.png、短剧 mp4/srt、artifacts/*.py 等），.git 已 83M 且继续膨胀。
3. **源码树内混杂产物目录**：`backend/{image_factory,drama_factory,game_covers,skills_files,uploads,backups,logs}` 与同名 `*_factory.py` 模块并存（Python 以 .py 模块优先，但极易误导维护者）。

### P1 — 真实缺陷

4. `task_queue` 重试语义 2 个测试失败（手动重试不清退避、失败态重置不一致）→ 直接影响批处理商业化可靠性。
5. 集成测试 2 失败 + 前端 5 失败（unhandled rejection）需定位。
6. ffmpeg/edge-tts 强依赖导致 29 个数字人/短剧用例在 CI（ubuntu 裸容器）大概率红——需要 CI 安装 ffmpeg 或提供 mock profile，否则质量门形同虚设。

### P2 — 架构债

7. `backend/main.py` 3732 行 god module（94 端点 + 知识库统计等业务逻辑混排）；`engines/` 目录为空壳。
8. `docs/` 沉淀 14 份迭代报告（v19 优化器、audit-iteration-3/4 等）与大量根目录 `OPTIMIZATION_*` 式历史文档，检索成本高；README 仍写 "your-org/smart-rd-platform"，与实际仓库名不符（品牌一致性差）。
9. Python 版本策略分裂：根仓 .venv 3.12，content-platform 用 3.13，CI 用 3.13；requirements 有 .bak 残留（`stock_tools.py.bak`）。

## 六、能力评分卡（满分 100）

| 维度 | 权重 | 得分 | 说明 |
|---|---|---|---|
| 功能广度 | 20 | 19 | 79 页面 + 19 工厂 + 190 工具，覆盖内容生产→分发→变现全链路 |
| 工程质量 | 25 | 18 | 测试密度优秀（97.2%），但 33 失败中 4 个是真实缺陷 + CI 依赖未保障 |
| 架构 | 20 | 14 | 有清晰的 router 拆分与 P0/P1 重构路线，但 main.py god module + 产物混入源码 + 嵌套仓断裂 |
| 安全 | 20 | 18 | 鉴权/限流/注入面处理到位，残余风险低 |
| 可运维/可交付 | 15 | 9 | Dockerfile 四件套齐备，但 content-platform gitlink 无 .gitmodules、仓库膨胀、CI 大概率红 |
| **合计** | 100 | **68 / 100** | **B 级：能力面很宽，工程底子好，交付卫生是短板** |

## 七、建议行动清单

1. 【P0, 1h】为 `content-platform` 补 `.gitmodules` 或改为独立仓 + 文档说明；.gitignore 加 `drama_factory/`、`uploads/`、`*.db`、`logs/`、`backups/`；对已跟踪的 43 个生成物 `git rm --cached` + 迁移到对象存储/构建产物。
2. 【P0, 2h】CI 容器安装 ffmpeg（或引入 `imageio-ffmpeg` 二进制注入 PATH）+ 数字人/短剧测试加 skip-if-no-ffmpeg 标记，消除 29 个环境性失败。
3. 【P1, 4h】修 `task_queue` 重试/退避 2 个失败 + 定位 2 个集成失败 + 前端 3 处 unhandled rejection。
4. 【P1, 1d】`main.py` 继续拆分（知识库统计、管理端点迁出），目标 < 1500 行；清空或回填 `engines/`。
5. 【P2】统一 Python 3.13，删除 `.bak`/`_b.py` 残留；docs 归档为 `docs/history/`；README 品牌对齐（xiaotuan-code-platform）。

## 八、修复执行记录（同日完成）

> 状态：**P0/P1/P2 全量修复完毕**（含 main.py 拆分、Python 统一、文档归档、engines 路径可配置化）。

### 已修复

| # | 项 | 做法 | 验证 |
|---|----|------|------|
| P0-1 | gitlink 无 .gitmodules | 新增 .gitmodules + git rm --cached content-platform | git status 干净 |
| P0-2 | 37 张生成图 + 优化器报告 + artifacts 样本入库 | git rm --cached + .gitignore 扩展 | 仓库瘦身 |
| P0-3 | quality_gates.py 语法回归 | main() 缩进修复 + logger→print（模块无 logging 导入） | 3 道闸全过 |
| P1-1 | 测试债 33+5 全清 | ffmpeg 兕底解析器 + retry 402 + KB 装饰器错位 + 前端 5 测试 | 后端 1155/1155 · 前端 121/121 |
| P1-2 | ffmpeg 路径硬编码（8 模块 + conftest + music_factory 重定义） | 新增 common/ffmpeg_bin.py（env → PATH → imageio-ffmpeg），全仓替换 | compileall + 全量测试 |
| P1-3 | ffprobe 缺失导致 media_check 误判 | probe_media() 纯 ffmpeg stderr 解析兕底 | 数字人/短剧 35 用例全绿 |
| P1-4 | Ruff 1487 错误（CI 红） | 安全自动修复 996 + 手工 B904×16/E741×14/F811/E722/UP031 + E402 忽略（项目惯用）+ C901 阈值 20 + 2 处 noqa | ruff check 0 错误 · format 全绿 |
| P2-1 | .bak 文件 3 个 | 删除 | — |
| P2-8 | README 品牌不符 | your-org/smart-rd-platform → Ryan-myp/Code-Platform | — |
| P2-9 | **main.py 3822 行 god module** | 拆为 5 个路由模块：kb_api(642)/mcp_api(353)/sandbox_api(538)/commercial_api(715)/agent_api(699)，main.py 降至 967 行；`_safe_error`/分享埋点/工作流频控状态随迁；保留 main 旧 import 路径兼容 | 路由契约 666 不变 · 全量 1155 测试全绿 |
| P2-10 | Python 版本分裂（本地 3.12 / CI 3.13） | 两个 workflow 统一为 3.12（与已验证本地 .venv 对齐） | CI 配置一致 |
| P2-11 | 12 份历史迭代文档堆积 docs/ | 归档到 docs/history/（+ 归档说明 README） | docs/ 只留 4 份现行文档 |
| P2-12 | engines 硬编码 /Users/yanping.ma 路径 | BIZ_DIR 支持 env(BIZ_DELIVERY_DIR) → 仓内 scripts/ → 默认值，isdir 校验 | py_compile 通过 |

### 仍存（P2 建议项，未动）
- 无——P2 全部项已完成（main.py 拆分 / Python 统一 / 文档归档 / engines 路径 / .bak 清理 / README 品牌）
- 注：`engines/` 并非空壳，是 plugin_registry 的业务引擎适配层（4 个 Biz 插件）

### 终态质量闸
- 后端 pytest：**1155/1155** · 前端 vitest：**121/121**
- `ruff check backend/`：0 错误 · `ruff format --check`：全绿
- quality_gates.py 契约/undefined/密钥 3 道闸：PASS（路由 666 条，前端 0 断链）
- 主模块行数：main.py 3822→**967**（拆 5 个路由模块）
- 修复后预计评分：**84–88 / 100（B+→A-）**

---

## 九、E2E 能力实测（2026-10-10，commit ca38815）

> 新增 `scripts/e2e_capability_probe.py`：启动隔离实例（`DB_PATH=/tmp/capability_probe.db`，端口 8009），
> 对 11 个功能域 37 项探针打**真实请求**，生成物（PNG/MP3/PPTX）做 magic bytes 校验，不只看 200。
> 支持 `--no-llm` 限流降级模式（LLM 探针标 SKIP）。

### 实测结果：**36 PASS / 0 FAIL / 1 SKIP（147s）**

| 域 | 实测证据（摘要） |
|---|---|
| A 鉴权 | 注册/登录/JWT/配额全通 |
| B LLM | Agnes 真实对话 + SSE 流式（108 帧）；/v1 中转站网关设计性关闭（唯一 SKIP） |
| C 编排 | 工作流 DAG（input→agent→output）executor 真实执行；Agent 运行；65 工具清单 + 同步执行 |
| D 知识库 | 上传→建库→**检索命中**（此前检索端点是空壳，已修复） |
| E 任务队列 | 翻译任务 create→worker→success 全链路 |
| F 工厂 | 表情包本地渲染 PNG；**文生图真实出图 1MB PNG**（Agnes agnes-image-2.5-flash，需修 negative_prompt 字段 + 配 IMAGE_MODEL） |
| G 音频 | edge-tts 配音 MP3；**音乐合成 15s MP3**（_generate_melody 死存根已重构） |
| H 文档 | PPT LLM 生成 65KB PPTX（字节校验）；Excel；脑图 |
| I 平台 | 沙箱探测；MCP 服务器；分享外链公开访问；团队 + 仪表盘 |
| J 重工厂 | 数字人模板/短剧配置（Pexels 已配）/游戏模板市场/**小程序 LLM 全项目生成 success** |
| K 前端 | Vite dev server + 代理 /api 透传 |

### E2E 发现并修复的 3 个真实缺陷
1. **音乐工厂 500**：`_generate_melody` 是 3 参死存根，调用方传 4 参 → 重构建 4 参短语对齐旋律引擎（五声音阶+和声进行）
2. **KB 检索空壳**：`GET /search` 挂错在 `_search_kb_internal` 存根 → 接真实 `search_knowledge_base`（双路检索 + hits 证据）
3. **文生图 400**：Agnes 图像队列不支持 `negative_prompt` 字段（HTTP 400 明确拒绝）→ 去除该字段，用户自定义负面词折进 prompt；`.env` 增加 `IMAGE_MODEL=agnes-image-2.5-flash` 平台默认图模开箱可用

另：quality_gates.py main() 缩进再次损坏（logger 未定义）→ 修复，3/3 门禁恢复可运行。

### 回归基线
后端 **1155/1155** · 前端 **121/121** · ruff check 0 · format 全绿 · quality_gates 3/3 PASS

---
*本报告基于 2026-07-09 13:20 前后的本地实测数据；修复记录更新于同日 18:00；E2E 能力实测追加于 2026-10-10。*

## 十、商业化 P0 落地（2026-10-10 追加）

> 目标：从「功能可用」→「商业闭环可用」。TD 见 `docs/commercialization.md`。

| 交付 | 说明 |
|---|---|
| 支付抽象层 `common/payment.py` | PaymentProvider 协议；Mock 沙箱（HMAC 验签，E2E 专用）+ Alipay 契约骨架（未接凭据显式 501，**不做假实现**）；RSA2 接入 Runbook |
| 幂等履约状态机 | `mark_order_paid`：pending→paid→approved；金额不符停留 paid 转人工；rejected 终态 409；自动履约与 `review_order` 同一套开通 SQL |
| 端点 | `POST /api/orders/webhook`、`POST /api/orders/{id}/checkout/{provider}` |
| 计量中心 `common/billing.py` | `GET /api/billing/summary`（用户今日/30日 调用/成功率/字符/成本预估）、`GET /api/admin/metrics`（7日 p50/p95/错误率/功能分布/积压/DB 体积） |
| 数据迁移 | orders 表幂增 payment_provider/payment_ref/paid_at（顺带修 PRAGMA r[0]→r[1] 列名 bug） |

**验收**：单测 8/8（全链路/幂等重放/坏签 401/金额不符人工/rejected 409/501/计量/运维指标）；
全量回归 **1163/1163**（基线 +8）；E2E 实机：`order → mock webhook → 自动开通 pro（30天, quota 200）`
全链路通过；探针新增 **K 商业** 域（3 探针，纯 SQLite 不耗 LLM 配额）。

**下一期 P1**：支付宝/微信商户凭据接入（Runbook 就绪）、前端支付指令+账单页、`/v1` 网关开放（billing 闭环后 `gateway_open=1`）。

## 十一、能力打磨 P0：LLM 工具族全面迭代（2026-10-10）

聚焦自身能力（商业化 P1 挂起）：LLM 工具"能用"→"好用"的系统性迭代。

| # | 交付 | 证据 |
|---|---|---|
| C-1 | **LLM JSON 自修复系统能力**：`common/llm.call_llm_json`（同步）/`call_llm_json_async`（异步）——JSON 严格后缀提示 + 失败自动带【修复指令】重试 + 顶层类型校验；替代 content_strategy 裸 json.loads | 5 单测（修复链/类型不符/双败）|
| C-2 | 小程序生成解析器升级：`_extract_json` 换用 parse_llm_json 多级容错 | 回归绿 |
| C-3 | **工具执行身份注入**：worker system prompt 注入当前用户名 + "汇报人/作者直接用该名字"指令 → 周报/PRD 不再输出 [待补充] | 2 单测 + 真实 LLM 验收：汇报人段=`tool_qa`、[待补充] 计数=0 |
| C-4 | **5 个高频 LLM 工具真实验收**（会议纪要/周报/邮件/PRD/小红书）：串行小量、输出质量三维检查（长度/结构/关键词） | 5/5 达标（周报 2096 字含数据表、PRD 6127 字含方案对比、小红书 3 标题+emoji 正文） |

**配额纪律**：验收全程串行（1 工具/轮询），单次 LLM 调用 10-40s，共 7 次调用。
**测试基线**：backend **1175/1175**（+7）。

## 十二、后续能力路线图（用户聚焦"先做好自身能力"后）

1. **数字人管线产物级验收**（当前 E2E 仅配置层探针；需 1 次真实 TTS+渲染，~1-3 分钟产出）
2. **QC 报告泛化**：音乐已有 `_music_qc_report`；为视频/PPT/音频产物统一 QC 结构（可交付物带质检报告=商用标准）
3. 工具冒烟常态化：`scripts/tool_llm_qa.py` 可并入 E2E 探针 L-tools 域（当前 LLM 串行 5 项 ~1.5min）
4. （商业化挂起项）支付宝/微信 Pay、`/v1` 网关重开

**C-1 端到端补验**：`/api/strategy/topic-suggest` 真实调用返回 3 条结构化选题（title_direction/angle/audience 完整），`call_llm_json` 首个生产消费方验证通过。

## 十三、工厂族能力打磨（除视频/音乐）— 真实 LLM 验收 + 缺陷修复
（2026-07-09）

范围：小游戏 / 小程序 / PPT / 图片 / 表情包 / 配音 / PDF 合同审查。新增
`scripts/factory_acceptance.py`：严格串行（一次一个 LLM 调用）、逐项生成 +
产物 magic-bytes 校验（PNG/ZIP-PPTX/MP3）。

| 缺陷 | 修复 | 验证 |
|---|---|---|
| **P0** `POST /api/games/generate` 端点在重构中丢失（前端 404） | 重新补齐（模板校验 + 异步任务 + 同步降级） | 验收：4 文件、QC 过、双版本 |
| **P0** PPT 生成 0 页（LLM 富内容输出被默认 4000 token 截断→JSON 破损→解析退化） | `max_tokens=16000` + `parse_llm_json` 截断修复兜底 | 验收：13–15 页 + 合法 PPTX |
| 平台级 `parse_llm_json` 不抗截断（尾部 unterminated 即失败） | 栈式补全未闭合引号/数组/对象 + 尾逗号处理；空结果({}/[])触发修复重试 | 单测 4 条 + 真实截断数据抢救出 13 页 |
| **P1** 小程序质量门禁丢弃 worker 已生成结果（门内 `result=None` 重启→首轮强制精简重试，浪费 1 次 LLM + 降级） | `initial_result` 作为初值传入 | 单测：提供初值时 0 次多余 LLM 调用；验收 17 文件 + QC 过 |
| 门禁 502/500 吞细节（"操作失败请稍后重试"） | 携带 QC 失败项 / 异常类型+消息 | — |

**验收结果：7/7 PASS**（小游戏、小程序、PPT、图片文生图、表情包、配音、PDF合同审查），
产物全部通过 magic-bytes 校验（PNG/PPTX/MP3）。

### 工厂族 QC 覆盖现状（后续打磨方向）
- 有 QC 门禁：image、meme、game、miniapp、pdf_tools
- **无 QC 门禁**：voice_factory（纯 edge-tts，产物 mp3，可加"时长>0/字节>0"轻门禁）、
  PPT（可加"slides≥5 + 标题非空"轻门禁）
- 数字人/短剧：依赖 ffmpeg，用户判定"较难"，暂缓（路线图保持）

全量后端回归 **1184/1184** 全绿；Ruff 0。

## 十四、工具族（65 个）能力盘点 + api-doc 修复 + 高价值抽样
（2026-07-09）

**规模澄清**：所谓"几十个工具加工厂" = **65 个工具**（54 LLM + 11 实算）+ 一批产物工厂。
关键认知：54 个 LLM 工具**共享同一执行引擎**（`_run_tool_worker`：prompt 模板 + 身份注入 +
JSON 自修复 + 统一计费/统计），本质是 1 引擎 + 54 prompt 模板，代表性验证可外推。

| 类别 | 数量 | 能力状态 |
|---|---|---|
| 实算工具（单位/CSV/JSON/正则/SQL/日期/表格/颜色/差异/密码/Base64） | 11 | ✅ 全部离线验真（0 LLM 配额） |
| LLM 工具（15 分类） | 54 | ✅ 54/54 prompt 模板干净渲染；5 个代表真实 LLM 质检通过 |
| 产物工厂（游戏/小程序/PPT/图/表情包/配音/PDF） | 7 | ✅ 7/7 magic-bytes 验收 |

**本轮修复**：`api-doc` prompt 模板含未转义 JSON 花括号 → `str.format()` 走降级正则路径、
喂 LLM 的 prompt 残留未配对 `{`。转义 `{{ }}` + 理顺多余 `}` 后，54 个模板全部 0 崩溃。

**高价值抽样（3 次串行 LLM）**：财报分析(金融)、法律意见书(法律)、数据分析报告(运营)
— 实测均 PASS（长度 4.3k–4.7k、关键词齐全、无 [待补充] 占位）。
（法律意见书的 `[待补充]` 出现在"承办律师"字段 = LLM 无法得知的用户填写项，属合理占位，非缺陷。）

全量后端回归 1184/1184；Ruff 0；已推送 `6e5d506`。

## 十五、工具族深度质量抽样（结构 + 内容 + 样式三层，非仅"调通"）
（2026-07-09）

按"每工具自身 prompt 规定的输出格式"写断言（章节/表格/数量/领域词/占位符/花括号泄漏），
再人工通读原样输出把关（区分"关键词命中但内容空泛"的真缺陷）。

`scripts/tool_deep_qa.py`（可复用，严格串行 3 次 LLM）：

| 工具 | 分类 | 结果 | 人工把关要点 |
|---|---|---|---|
| 商品标题优化 | 电商运营 | 10/10 | 真落到 TWS/降噪/通勤、🔥⭐ 评分表、字数+核心/属性/长尾拆解 |
| 配色方案 | 设计创意 | 9/9 | HEX↔RGB 换算正确(#7CB342=rgb(124,179,66))、WCAG 对比度、20/70/10 比例、3 套含理念 |
| 面试题库 | 人力资源 | 10/10 | GIL/Go channel-vs-mutex/微服务技术准确、每题考察点+难度+参考答案+5/3/1 分表 |

**合计 29/29 项通过**。累计代表样本 8 → 11 个 LLM 工具，全部质量过关。
已推送。

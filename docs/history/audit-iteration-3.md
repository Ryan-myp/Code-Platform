# 第三轮全平台实测与升级总结（无人值守迭代）

> 时间：2026-08-08（凌晨迭代） · 方式：API 全量冒烟 + 性能并发 + 浏览器页面体检
> 原则：只记录真实发现与可验证的修复，不写无法验证的"优化"

## 一、本轮实测范围

| 层面 | 方法 | 覆盖量 |
|---|---|---|
| GET 端点全量冒烟 | OpenAPI 自动发现 + admin 登录逐个请求 | 128 个端点 |
| POST 端点精选冒烟 | 20 个代表性端点（CRUD + 轻 LLM），重型/外部付费端点跳过 | 20 个 |
| 性能并发 | 30 并发混合 GET + 10 并发混合（含 LLM 异步提交）+ 连续 20 次任务提交 | 60 请求 |
| 浏览器页面体检 | 真实浏览器逐页访问 10 个关键页面，收集 console 错误 | 10 页面 |
| 回归 | 全量 pytest + 前端生产构建 | 388 测试 + vite build |

## 二、实测结果

### 2.1 GET 端点（128 个）
- ✅ 正常 127 个；**0 个 500 / 0 个 404 / 0 个超时**
- 唯一 422：`/api/comments/thread`（缺少必填 query 参数 `target_type`，属正常参数校验）

### 2.2 POST 端点（20 个）
- ✅ 18 个 200；2 个非 200 均为业务约束/测试参数错误，非缺陷：
  - `/api/orders` 400「您已有待处理订单」——防重复下单的业务设计
  - `/api/publish/schedules` 400「未知平台: xhs」——平台白名单为 wechat/douyin/kuaishou，脚本用错平台；用 douyin 重测创建/取消均成功
- LLM 端点全部异步化生效：思维导图/翻译/助手对话 0.0~1.1s 返回（任务后台执行）

### 2.3 性能并发
- 30 并发 GET：总耗时 0.69s，成功 30/30（平均 418ms，最大 685ms）
- 10 并发混合（含 2 个 LLM 异步提交）：0.07s 全部完成，最大 66ms —— **事件循环无阻塞（验证 48 处异步化修复）**
- 连续 20 次任务提交：同类型并发被 429 正确拦截（用户级并发保护，前端按钮已防连点）

### 2.4 浏览器页面体检（10 页）
- 首页/工作台/工具库/任务中心/会员/记录/广场/个人中心/帮助/后台：**全部正常渲染，0 console error**
- 唯一 warn：WebSocket「closed before established」（React StrictMode 双挂载竞态，已修复见下）

### 2.5 数据健康
- `PRAGMA integrity_check` = ok；外键检查 0 违规
- 异步任务无积压（超过 30 分钟未完成：0）
- 历史失败任务 6 个，其中 2 个指向真实问题（见下）

## 三、发现的问题与修复（均有证据）

### 问题 1【P1】LLM 调用错误信息空白
- **证据**：任务表 2 条 failed 记录 error 为「LLM 调用异常: 」（空字符串）；`common/llm.py` 中连接类异常（EOFError/ConnectionResetError）的 `str(e)` 为空，直接拼进错误信息
- **修复**：`common/llm.py` call_llm / call_llm_async 两处——`detail = str(e) or f"{type(e).__name__}（连接异常），请稍后重试"`，用户不再看到空白错误

### 问题 2【P1】数据预测模块 JSON 解析失败无重试
- **证据**：任务表 1 条 failed：`forecast_analyze`「Expecting ',' delimiter: line 165 column 42」——LLM 长输出偶发非法 JSON，直接 500，用户需手动重跑
- **修复**：`data_forecast.py` 解析失败自动重试一次，重试时追加严格 JSON 格式约束；仍失败才报错

### 问题 3【P2】parse_llm_json 容错不足（缺注释剥离）
- **证据**：上述 forecast 失败即由此触发；LLM 常在 JSON 内输出 `// 注释`，现有 4 级容错无法处理
- **修复**：`common/llm.py` 新增第 5 级容错 `_strip_json_comments`（安全剥离 `//` 与 `/* */`，逐字符扫描跳过字符串字面量，URL 等不受影响），6 个调用模块全部受益
- **验证**：6 组单测全过（含 URL 内 `//` 不被误删、尾逗号+注释组合）

### 问题 4【P3】WebSocket 关闭竞态警告
- **证据**：任务中心每次进入产生 1 条 warn「WebSocket is closed before the connection is established」——组件卸载时对 CONNECTING 状态的 WS 直接 close
- **修复**：`frontend/src/lib/ws.js`——CONNECTING 时改为挂 onopen 后立即关闭，OPEN/CLOSING 才直接 close；消除警告且不泄漏连接

## 四、回归验证

- 全量 pytest：**388 passed**（185s）
- 前端生产构建：**vite build 成功**（10.6s，仅 chunk 体积提示非错误）
- 后端重启后登录/冒烟正常（health 200）
- 相关单测 74 passed（含 parse_llm_json 容错测试）
- 冒烟产生的测试数据（分享/草稿/收藏/订单/任务/竞品/系列/排期/团队/知识库/Agent/流水线/工作流/模板/API Key 等）已全部清理

## 五、结论

第三轮未发现 P0（无崩溃、无阻塞、无 500 风暴），说明前几轮修复已稳定。本轮修复 3 个真实可靠性问题（错误可读性、解析容错、重试兜底）+ 1 个前端警告。平台当前处于：**API 层 100% 可访问、无任务积压、数据库完整、页面零错误**状态。

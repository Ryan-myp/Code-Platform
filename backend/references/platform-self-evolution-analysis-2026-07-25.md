# 智能研发平台 v6.2 自进化分析报告
**分析时间**: 2026-07-25 | **平台版本**: v6.2 | **数据来源**: platform.db + 代码审计

---

## 1. 📊 使用统计

### 1.1 模块使用频率（usage_logs）

| 模块 | 调用次数 | 成功 | 失败 | 成功率 | 平均响应时间 | 平均输入长度 | 平均输出长度 |
|------|---------|------|------|--------|------------|------------|------------|
| agent_run | 30 | 15 | 15 | 50% | 1.8s | 0 | 2,769 |
| review (PRD审查) | 20 | 20 | 0 | 100% | 3.06s | 1,531 | 10,857 |
| generate (PRD生成) | 11 | 11 | 0 | 100% | 4.02s | 13 | 3,788 |
| code (代码生成) | 5 | 5 | 0 | 100% | 0.23s | 1 | 3,405 |
| test (测试用例) | 3 | 3 | 0 | 100% | 0.15s | 1 | 3,354 |
| td (技术方案) | 3 | 3 | 0 | 100% | 0.16s | 1 | 3,388 |
| biz_review (biz-delivery) | 2 | 2 | 0 | 100% | 1.46s | 4 | 4,993 |
| **合计** | **74** | **59** | **15** | **79.7%** | - | - | - |

### 1.2 按天使用趋势

| 日期 | agent_run | review | generate | code | test | td | biz_review |
|------|-----------|--------|----------|------|------|----|-----------|
| 07-22 | 6 | 3 | 3 | 2 | - | - | - |
| 07-23 | 2 | 6 | 2 | 2 | 2 | 2 | - |
| 07-24 | - | 3 | 1 | 1 | 1 | 1 | - |
| 07-25 | 22 | 8 | 5 | - | - | - | 2 |

### 1.3 Agent 配置分析

| Agent 名称 | 工具配置 | Memory | Reasoning | 活跃状态 | 创建日期 |
|-----------|---------|--------|-----------|---------|---------|
| 测试助手 | [] (空) | ✅ | ❌ | 活跃 | 07-22 |
| 高级研发助手 | [web_search, python] | ✅ | ❌ | 活跃(×3) | 07-22 |
| 测试绑定Agent | [web_search, python] | ✅/❌ | ❌/✅ | 活跃(×2) | 07-22 |
| 全功能测试Agent | [web_search, python] | ❌ | ❌ | 活跃 | 07-22 |
| 集成测试Agent | [] (空) | ❌ | ❌ | 活跃(×3) | 07-25 |
| 列表测试Agent | [] (空) | ❌ | ❌ | 活跃(×3) | 07-25 |
| 已更新Agent | [] (空) | ❌ | ❌ | 活跃(×3) | 07-25 |
| 待删除Agent | [] (空) | ❌ | ❌ | **不活跃** | 07-25 |

### 1.4 Plugin 注册情况

| 插件名称 | 分类 | 版本 | 健康状态 | 执行日志 |
|---------|------|------|---------|---------|
| biz-code-scan | code_analysis | 1.0.0 | ✅ 已修复 | 0次调用 |
| biz-review | prd_review | 1.0.0 | ✅ 已修复 | 2次调用 |
| biz-technical-design | tech_design | 1.0.0 | ✅ 已修复 | 0次调用 |
| biz-test-cases | testing | 1.0.0 | ✅ 已修复 | 0次调用 |

### 1.5 知识库 & Skills & MCP

| 类型 | 总数 | 活跃 | 详情 |
|------|------|------|------|
| 知识库 | 5 | 3 | 技术文档库(/Users/yanping.ma/docs), 测试知识库 |
| Skills | 4 | 2 | 代码规范(skill_1784703803111), test(skill_1784897716785) |
| MCP Servers | 2 | 1 | 文件系统(stdio) |
| Teams | 0 | - | 未创建 |

### 1.6 Requirements 工作流

| 需求ID | 名称 | 状态 | 优先级 | PRD长度 | Review长度 |
|-------|------|------|--------|--------|-----------|
| req_1784964426298 | 电商下单功能 | reviewed | P0 | 4,137字符 | 22,326字符 |

---

## 2. 🔧 关键发现与优化建议

### 2.1 🚨 CRITICAL: Plugin适配层方法名不匹配 — 已修复

**问题**: `engines/__init__.py` 中调用了不存在的旧方法名：
- `ReviewEngine.auto_review()` → 实际方法: `ReviewEngine.review()`
- `TDEngine.auto_design()` → 实际方法: `TDEngine.generate_td()`  
- `TestEngine.auto_test()` → 实际方法: `TestEngine.generate_tests()`

**影响**: 所有通过 Plugin 界面执行的 biz-delivery 引擎都会静默 fallback 到简单 LLM Agent（无证据注入、无22+预检查维度）。

**已修复**: 2026-07-25 完成修复，重启后端即可生效。

### 2.2 🚨 CRITICAL: 磁盘空间告警

**当前磁盘使用率: 94%** (460Gi总量, 30Gi可用)

**建议**: 
1. 立即清理 `/tmp/execution_*` 临时文件
2. 清理 Python 缓存(`__pycache__`, `.pyc`)
3. 设置磁盘监控阈值告警

### 2.3 agent_run 100% 失败模式

15次失败的agent_run全部特征：input_length=0, output_length=0, response_time<0.02s。根因是Agent配置了空工具数组但instructions非空，导致初始化崩溃。

**建议**: 为所有Agent配置有效工具，或实现空工具时的降级逻辑。

### 2.4 biz-delivery 引擎集成现状

**两条调用路径对比**:

| 路径 | 函数 | 方法名 | 状态 |
|------|------|--------|------|
| extensions.py `run_biz_*()` | `engine.review()` | ✅ 正确 | 已使用(biz_review: 2次) |
| engines/__init__.py Plugin | `engine.review()` | ✅ 已修复 | 之前fallback到简单LLM |
| main.py `/api/prd/*` | 简单Agent() | N/A | 前端主要调用此路径 |

**关键洞察**: 前端ReviewPage/TDPage/TestPage全部调用`/api/prd/*`路由（简单LLM Agent），不走biz-delivery。而requirements workflow中的`/api/requirements/{id}/review`使用biz-delivery，生成了22,326字符的详细审查报告（vs 简单LLM的~10,857字符）。

### 2.5 Prompt Templates 质量

| 模块 | 主模板长度(main.py) | biz-delivery引擎长度 | 差距 |
|------|-------------------|-------------------|------|
| review | ~1,513字符 | ~10,000+字符 | 6.6x |
| technical_design | ~2,401字符 | ~5,000+字符 | 2.1x |
| test_cases | ~2,980字符 | ~8,000+字符 | 2.7x |
| code_generation | ~3,660字符 | ~5,000+字符 | 1.4x |

v6.0模板已从v1(106-399字符)升级到v2(730-3,660字符)，但仍显著短于biz-delivery引擎。

---

## 3. ⚠️ 需要关注的问题

### 3.1 代码沙箱安全审计 (v5.0遗留)

| 风险项 | 严重程度 | 现状 |
|-------|---------|------|
| 无网络隔离 | 🔴 Critical | subprocess.run直接执行，可自由调用urllib/requests |
| 无资源限制 | 🟡 Medium | 仅有timeout，无CPU/memory cgroups |
| 无进程隔离 | 🔴 Critical | 无chroot/namespaces/seccomp |

**结论**: v6.0已移除`/api/code-execution`端点。**不建议启用**。如需代码执行能力，应开发基于Docker的隔离沙箱。

### 3.2 双后端架构

v5.0(intelligent-rd-platform)数据在内存中不持久，v6.0(Code-Platform)使用SQLite持久化。v5.0已废弃但未彻底清理。

### 3.3 低使用率组件

- teams: 0个（表存在但为空）
- workflows: 表存在但为空
- 集成测试知识库: 已禁用
- 集成测试MCP: 已禁用

---

## 4. 📋 优化行动计划

### P0 (已完成/立即)
- ✅ **修复Plugin适配层方法名** — engines/__init__.py 中 auto_review→review, auto_design→generate_td, auto_test→generate_tests
- ⏳ **磁盘清理** — 需手动执行
- ⏳ **前端PRD路由切换到biz-delivery** — 修改/api/prd/*路由调用run_biz_*函数

### P1 (本周)
- 修复空工具Agent配置
- 清理测试数据（待删除Agent、禁用的知识库/Skills/MCP）
- Prompt模板版本管理同步

### P2 (后续)
- Docker沙箱替代当前不安全实现
- Teams/Workflows多Agent协作支持
- 磁盘监控告警

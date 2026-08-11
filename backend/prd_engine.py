#!/usr/bin/env python3
"""研发流程引擎 - PRD 生成/审查/技术方案/测试用例/代码生成 + 需求/项目/成果/配置/自进化 API"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from common.auth import decode_access_token, get_user_profile, require_auth
from common.config import BIZ_DELIVERY_DIR, DEFAULT_MODELS, load_config
from common.db import get_db
from common.llm import call_llm, call_llm_async, log_usage, stream_llm_async

logger = logging.getLogger(__name__)
router = APIRouter(tags=["研发流程"])

PROJECT_DIR = Path(__file__).parent
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# biz-delivery 引擎路径（由 config.BIZ_DELIVERY_DIR 控制，留空则禁用 biz 引擎走 LLM fallback）
BIZ_DIR = BIZ_DELIVERY_DIR
if BIZ_DIR and BIZ_DIR not in sys.path:
    sys.path.insert(0, BIZ_DIR)

# 模块加载时从 config 表加载 LLM 配置（覆盖环境变量）
load_config()


# ══════════════════════════════════════════════════════════════
# PRD 流程
# ══════════════════════════════════════════════════════════════

PRD_SYSTEM = """你是一位资深产品经理，擅长编写高质量 PRD（产品需求文档）。

## 角色定位
- 5年+ 互联网产品经验，熟悉广告/电商/社交领域
- 精通用户研究、需求分析、产品设计方法论
- 能够将模糊需求转化为可执行的产品方案

## PRD 结构要求
1. **文档信息**：版本、作者、日期、 reviewer
2. **背景与目标**：
   - 业务背景（为什么做）
   - 目标用户画像
   - 核心指标（北极星指标 + 过程指标）
   - 成功标准（量化）
3. **用户故事**（采用 Given-When-Then 格式）：
   - 按角色分组（管理员/运营/用户/系统）
   - 标注优先级 P0/P1/P2
4. **功能需求**：
   - 用表格列出：功能点 | 描述 | 优先级 | 验收标准
   - 包含：核心流程、边界情况、异常处理
5. **非功能需求**：
   - 性能：QPS、延迟、并发数
   - 安全：鉴权、加密、合规
   - 可用性：SLA、容灾、监控
6. **数据需求**：
   - 数据流向图
   - 数据模型（核心实体）
   - 数据埋点需求
7. **接口需求**：
   - 外部依赖接口
   - 内部模块接口
8. **项目计划**：
   - 里程碑
   - 风险与应对
   - 资源需求

## 输出规范
- 直接输出 PRD 正文，不要解释
- 使用 Markdown 格式
- 表格用 Markdown 表格
- 流程图用 Mermaid 语法
- 关键决策用表格对比
- 语言简洁专业，避免废话

## 广告领域特别注意
- 竞价流程：RTB、pCPM、oCPM、智能出价
- 归因模型：Last Click、Linear、Time Decay、Markov
- 反作弊：设备指纹、行为分析、规则引擎
- 创意审核：OCR、内容安全、版权检测

## 参考排障案例
- 竞态条件：创建任务时并发导致重复 → 加分布式锁
- 数据不一致：MQ 消费失败未补偿 → 加死信队列+重试
- 性能瓶颈：N+1 查询 → 批量查询+缓存
"""

REVIEW_SYSTEM = """你是一位资深架构师兼技术评审专家，擅长审查 PRD。

## 审查思维框架
- **全局优先**：先理解系统架构 → 定位 PRD 功能位置 → 判断合理性
- **数据流优先**：用户请求 → API → Service → DAO → DB，每层检查数据来源和去向
- **异常 > 正常**：必查网络超时/校验失败/权限不足/并发冲突/幂等性/重试/降级
- **性能意识**：QPS 预估、数据库压力（索引/N+1）、缓存策略、外部依赖超时处理
- **向后兼容**：不破坏旧功能、不突然下线旧接口、DDL 变更考虑迁移
- **安全底线**：SQL 注入/XSS/越权/敏感数据加密/接口鉴权
- **可观测性**：结构化日志(traceId)/Prometheus 指标/健康检查/告警规则

## 审查维度（22+ 项）

### 一、需求完整性检查
1. 目标是否清晰可量化
2. 用户范围是否明确
3. 边界条件是否定义
4. 成功标准是否可测量
5. 依赖项是否识别

### 二、逻辑一致性检查
6. PRD 内部术语是否一致
7. 流程步骤是否闭环
8. 数据流向是否合理
9. 状态转换是否完整
10. 异常分支是否覆盖

### 三、技术可行性检查
11. 现有架构是否支持
12. 性能需求是否可达
13. 第三方依赖是否可控
14. 数据量预估是否合理
15. 技术选型是否合适

### 四、兼容性检查
16. API 版本兼容性
17. 数据库迁移方案
18. 前端影响范围
19. 第三方回调兼容
20. 降级策略

### 五、安全与合规检查
21. 敏感数据处理
22. 权限模型设计
23. 审计日志需求
24. 数据隐私合规（GDPR/PIPL）

### 六、可测试性检查
25. 验收标准是否可测试
26. 测试数据是否可构造
27. 边界条件是否可验证

## 输出格式
1. **总体评价**（含评分 /100）
2. **问题清单表格**（编号 | 级别 P0/P1/P2 | 问题描述 | 修改建议 | 检查维度）
3. **亮点与风险**
4. **修改建议总结**
5. **P0 问题必须处理才能进入开发**

## 广告领域审查重点
- 竞价流程：出价策略、流量分配、归因逻辑
- 创意审核：审核标准、时效性、人工复审
- 数据上报：实时性、准确性、去重
- 反作弊：设备指纹、IP 代理、行为异常
"""

TD_SYSTEM = """你是一位资深技术架构师，擅长编写技术设计方案。

## 设计方案要求

### 1. 架构总览
- 系统架构图（Mermaid）
- 模块划分说明
- 技术选型及理由
- 部署架构（容器化/云原生）

### 2. 核心场景流程
- 主流程时序图（Mermaid）
- 关键步骤说明表
- 异常处理流程
- 异步/事件驱动流程

### 3. 详细设计
#### 3.1 模块设计
- 模块职责划分
- 模块间依赖关系
- 接口定义（REST/RPC/MQ）

#### 3.2 数据模型
- ER 图（Mermaid）
- 核心表结构设计
- 索引设计
- 数据迁移方案

#### 3.3 接口设计
- API 端点定义表
- 请求/响应结构
- 错误码定义
- 限流策略

#### 3.4 状态机设计
- 状态转换图（Mermaid）
- 状态转换规则
- 并发控制策略

### 4. 关键技术决策
| 决策项 | 选项A | 选项B | 选择 | 理由 |
|--------|-------|-------|------|------|
| 缓存策略 | Redis | 本地缓存 | Redis | 分布式一致 |

### 5. 文件/代码结构
- 包结构设计
- 核心文件清单
- 配置项说明

### 6. 风险与演进
- 技术风险识别
- 应对方案
- 演进路线
- 监控告警设计

## 输出规范
- 直接输出完整技术方案 Markdown
- 架构图用 Mermaid
- 表格用 Markdown
- 代码用代码块标注语言
- 关键决策必须有理由
"""

TEST_SYSTEM = """你是一位资深测试工程师，擅长设计测试用例。

## 测试用例设计原则
- **正向流程**：覆盖 PRD 主流程，每个节点有对应用例
- **异常分支**：权限不足/数据校验失败/业务异常/系统异常
- **边界条件**：空数据/极值/并发/分页/超时
- **兼容性**：旧接口不受影响/旧数据可读/灰度策略正确
- **性能**：QPS 要求/缓存策略/DB 索引

## 测试用例格式
| 编号 | 级别 | 类型 | 前置条件 | 测试步骤 | 预期结果 | 备注 |
|------|------|------|----------|----------|----------|------|
| TC001 | P0 | 正向 | 已登录 | 1. 点击创建... | 创建成功 | 核心链路 |

## 测试维度覆盖要求

### 1. 功能测试
- 核心流程：P0 级别，必须覆盖
- 边界条件：P1 级别
- 异常处理：P1 级别

### 2. 接口测试
- 请求参数校验（必填/类型/长度）
- 响应结构校验（字段/类型/枚举）
- 错误码校验（状态码/错误码/错误信息）
- 鉴权校验（未登录/无权限）

### 3. 性能测试
- 核心接口响应时间
- 并发处理能力
- 数据库查询性能

### 4. 安全测试
- SQL 注入
- XSS 攻击
- 越权访问
- 敏感数据泄露

### 5. 兼容性测试
- 新旧版本兼容
- 数据迁移兼容
- 第三方依赖兼容

## 输出规范
- 直接输出测试用例文档
- P0 用例必须覆盖核心链路
- 包含接口测试和场景测试
- 注明测试数据和预期结果
- 使用 Markdown 表格格式
"""

CODE_SYSTEM = """你是一位高级开发工程师，擅长编写高质量可运行代码。

## 代码质量要求
1. **可运行**：代码必须能直接运行，包含必要的 import 和入口
2. **错误处理**：完善错误处理，返回友好的错误信息
3. **代码注释**：每个文件开头注释说明文件用途，关键函数有注释
4. **日志记录**：关键操作记录日志，便于排查问题
5. **性能考虑**：避免 N+1 查询、大 Key、内存泄漏

## 输出规范

### 单文件项目
```python main.py
# 文件用途说明
import ...

if __name__ == "__main__":
    # 入口逻辑
```

### 多文件项目
```python main.py
# 主入口文件
```

```python config/settings.py
# 配置管理
```

```python models/user.py
# 数据模型
```

## 具体要求
1. 监听 0.0.0.0:8000，根路径返回 200
2. 多文件输出：每个文件单独一个 Markdown 代码块
3. 块头格式：\`\`\`语言 文件路径
4. Python 项目需输出 requirements.txt
5. Go 项目需输出 go.mod
6. 支持目录层级：\`\`\`python src/utils.py

## 代码风格
- 变量命名清晰有意义
- 函数职责单一
- 避免过长的函数（>50行拆分）
- 使用类型注解（Python/Go）
- 错误处理优先使用返回而非异常

## 广告领域特别注意
- 竞价接口需要高精度（DECIMAL）
- 时间处理用 UTC，展示用本地时区
- 金额计算避免浮点误差
- 高并发场景考虑分布式锁
"""


# ══════════════════════════════════════════════════════════════
# v12.0 流式输出（SSE）：PRD 端点 stream: true 时返回打字机增量
# ══════════════════════════════════════════════════════════════


def _sse_event(event: str, data: dict) -> str:
    """序列化 SSE 事件：``event: {event}\ndata: {json}\n\n``。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def stream_llm_response(system_prompt: str, user_prompt: str, max_tokens: int, usage_key: str) -> StreamingResponse:
    """把 LLM 流式调用包装为 SSE 响应（事件 delta/done/error），复用重试与模型降级。"""

    async def gen():
        start = time.time()
        try:
            full = ""
            async for delta, full in stream_llm_async(system_prompt, user_prompt, max_tokens=max_tokens):  # noqa: B007 — full 为累计文本，循环结束后用于 done 事件
                yield _sse_event("delta", {"text": delta})
            log_usage(usage_key, len(user_prompt), len(full), time.time() - start)
            yield _sse_event("done", {"full": full, "elapsed": round(time.time() - start, 2)})
        except HTTPException as e:
            yield _sse_event("error", {"detail": e.detail})
        except Exception as e:
            logger.exception(f"{usage_key} stream failed")
            yield _sse_event("error", {"detail": f"流式调用异常: {e}"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/api/prd/generate")
async def generate_prd(req: dict):
    """AI 生成 PRD（v12.0：stream: true 走 SSE 流式）"""
    prd_text = (req.get("prd_text") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入需求描述")

    if req.get("stream"):
        return stream_llm_response(PRD_SYSTEM, prd_text, 4000, "prd_generate")

    start = time.time()
    try:
        # 尝试用 biz-delivery 的 prompt 模板增强（若有）
        result = await call_llm_async(PRD_SYSTEM, prd_text, max_tokens=4000)
        log_usage("prd_generate", len(prd_text), len(result), time.time() - start)
        return {"result": result}
    except Exception as e:
        logger.error(f"PRD generate failed: {e}")
        raise HTTPException(500, f"PRD 生成失败: {str(e)}") from e


@router.post("/api/prd/review")
async def review_prd(req: dict):
    """PRD 审查 - 优先用 biz-delivery ReviewEngine，失败 fallback LLM；stream: true 直接 LLM 流式"""
    prd_text = (req.get("prd_text") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入 PRD 内容")

    repo_path = req.get("repo_path") or ""
    if req.get("stream"):
        return stream_llm_response(REVIEW_SYSTEM, prd_text, 4000, "prd_review")

    start = time.time()
    fallback = False

    # 尝试 biz-delivery 引擎
    try:
        from review_engine import ReviewEngine

        profile = {
            "name": "platform",
            "repositories": [repo_path] if repo_path else [],
            "ir_cache": None,
            "kb_dir": "",
            "business_rules": {},
        }
        engine = ReviewEngine(profile, output_dir=str(PROJECT_DIR / "cache"))
        result = engine.review(prd_text)
        output = result.get("report", "") if isinstance(result, dict) else str(result)
        if not output:
            raise ValueError("empty review result")
        log_usage("prd_review", len(prd_text), len(output), time.time() - start)
        return {"result": output, "engine": "biz-delivery"}
    except Exception as e:
        logger.warning(f"biz-delivery review unavailable, fallback LLM: {e}")
        fallback = True

    result = await call_llm_async(REVIEW_SYSTEM, prd_text, max_tokens=4000)
    log_usage("prd_review", len(prd_text), len(result), time.time() - start)
    return {"result": result, "engine": "llm", "fallback": fallback}


@router.post("/api/prd/technical-design")
async def technical_design(req: dict):
    """技术方案生成 - 优先用 biz-delivery TDEngine；stream: true 直接 LLM 流式"""
    prd_text = (req.get("prd_text") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入 PRD 内容")

    repo_path = req.get("repo_path") or ""
    if req.get("stream"):
        return stream_llm_response(TD_SYSTEM, prd_text, 6000, "prd_td")

    start = time.time()
    fallback = False

    try:
        from td_engine import TDEngine

        profile = {
            "name": "platform",
            "repositories": [repo_path] if repo_path else [],
            "ir_cache": None,
        }
        engine = TDEngine(profile, output_dir=str(PROJECT_DIR / "cache"))
        result = engine.generate_td(prd_text)
        output = result.get("design", "") if isinstance(result, dict) else str(result)
        if not output:
            raise ValueError("empty td result")
        log_usage("prd_td", len(prd_text), len(output), time.time() - start)
        return {"result": output, "engine": "biz-delivery"}
    except Exception as e:
        logger.warning(f"biz-delivery TD unavailable, fallback LLM: {e}")
        fallback = True

    result = await call_llm_async(TD_SYSTEM, prd_text, max_tokens=6000)
    log_usage("prd_td", len(prd_text), len(result), time.time() - start)
    return {"result": result, "engine": "llm", "fallback": fallback}


@router.post("/api/prd/test-cases")
async def test_cases(req: dict):
    """测试用例生成 - 优先用 biz-delivery TestEngine；stream: true 直接 LLM 流式"""
    prd_text = (req.get("prd_text") or "").strip()
    tech_design = (req.get("tech_design") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入 PRD 内容")

    if req.get("stream"):
        user_prompt = f"PRD:\n{prd_text}\n\n技术方案:\n{tech_design}" if tech_design else f"PRD:\n{prd_text}"
        return stream_llm_response(TEST_SYSTEM, user_prompt, 4000, "prd_test")

    start = time.time()
    fallback = False

    try:
        from test_engine import TestEngine

        profile = {"name": "platform", "repositories": [], "ir_cache": None}
        engine = TestEngine(profile, output_dir=str(PROJECT_DIR / "cache"))
        result = engine.generate_tests(prd_text, tech_design or None)
        output = result.get("cases", "") if isinstance(result, dict) else str(result)
        if not output:
            raise ValueError("empty test result")
        log_usage("prd_test", len(prd_text), len(output), time.time() - start)
        return {"result": output, "engine": "biz-delivery"}
    except Exception as e:
        logger.warning(f"biz-delivery test unavailable, fallback LLM: {e}")
        fallback = True

    user_prompt = f"PRD:\n{prd_text}\n\n技术方案:\n{tech_design}" if tech_design else f"PRD:\n{prd_text}"
    result = await call_llm_async(TEST_SYSTEM, user_prompt, max_tokens=4000)
    log_usage("prd_test", len(user_prompt), len(result), time.time() - start)
    return {"result": result, "engine": "llm", "fallback": fallback}


@router.post("/api/prd/generate-code")
async def generate_code(req: dict):
    """根据技术方案生成代码（stream: true 走 SSE 流式）"""
    tech_design = (req.get("tech_design") or "").strip()
    language = (req.get("language") or "python").strip()
    task_type = req.get("task_type", "code")
    if not tech_design:
        raise HTTPException(400, "请输入技术方案")

    user_prompt = f"语言: {language}\n任务类型: {task_type}\n\n技术方案:\n{tech_design}"
    if req.get("stream"):
        return stream_llm_response(CODE_SYSTEM, user_prompt, 8000, "prd_code")

    start = time.time()
    result = await call_llm_async(CODE_SYSTEM, user_prompt, max_tokens=8000)
    log_usage("prd_code", len(user_prompt), len(result), time.time() - start)
    return {"result": result, "language": language}


@router.post("/api/prd/code-chat")
async def code_chat(req: dict):
    """代码对话 - 追问/修改代码（stream: true 走 SSE 流式）"""
    message = (req.get("message") or "").strip()
    language = (req.get("language") or "python").strip()
    if not message:
        raise HTTPException(400, "请输入消息")

    system = (
        f"你是一位高级 {language} 开发工程师。根据用户对话上下文，继续完善或修改代码。直接输出最新完整代码，不要解释。"
    )
    if req.get("stream"):
        return stream_llm_response(system, message, 8000, "prd_code_chat")

    start = time.time()
    result = await call_llm_async(system, message, max_tokens=8000)
    log_usage("prd_code_chat", len(message), len(result), time.time() - start)
    return {"result": result}


# ══════════════════════════════════════════════════════════════
# 需求 / 项目 / 成果 管理
# ══════════════════════════════════════════════════════════════


@router.get("/api/requirements")
async def list_requirements():
    """获取需求列表"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM requirements WHERE active=1 ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [_parse_req(r) for r in rows]


def _parse_req(row):
    """需求行转 dict，并把 pipeline_status JSON 字符串解析为对象。"""
    r = dict(row)
    try:
        r["pipeline_status"] = json.loads(r.get("pipeline_status") or "{}")
    except Exception:
        r["pipeline_status"] = {}
    return r


@router.post("/api/requirements")
async def create_requirement(req: dict):
    """创建需求"""
    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    req_id = f"req_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO requirements (id, name, description, status, priority, project_id, creator, version, created_at, updated_at, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            req_id,
            name,
            req.get("description", ""),
            req.get("status", "draft"),
            req.get("priority", "P1"),
            req.get("project_id", ""),
            req.get("creator", "admin"),
            1,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return {"id": req_id, "name": name}


@router.get("/api/requirements/{req_id}")
async def get_requirement(req_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM requirements WHERE id=?", (req_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "需求不存在")
    return _parse_req(row)


@router.get("/api/requirements/{req_id}/test-runs")
async def get_test_runs(req_id: str):
    """查询需求的自动化测试执行记录（部署流水线测试门禁/修复循环写入）。

    cases 字段为逐条用例结果 JSON（[{name, path, status, message}]），解析后返回。
    """
    conn = get_db()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS test_runs (id TEXT PRIMARY KEY, requirement_id TEXT, pipeline_id TEXT, "
            "status TEXT, summary TEXT, log TEXT, cases TEXT, created_at TEXT)"
        )
        # 旧库无 cases 列：安全追加（SQLite 不支持 ADD COLUMN IF NOT EXISTS）
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(test_runs)").fetchall()}
        if "cases" not in cols:
            conn.execute("ALTER TABLE test_runs ADD COLUMN cases TEXT")
        rows = conn.execute(
            "SELECT id, requirement_id, pipeline_id, status, summary, log, cases, created_at FROM test_runs "
            "WHERE requirement_id=? ORDER BY created_at DESC LIMIT 20",
            (req_id,),
        ).fetchall()
        runs = []
        for r in rows:
            item = dict(r)
            try:
                item["cases"] = json.loads(item.get("cases") or "[]")
            except Exception:
                item["cases"] = []
            runs.append(item)
        return runs
    finally:
        conn.close()


@router.put("/api/requirements/{req_id}")
async def update_requirement(req_id: str, req: dict):
    conn = get_db()
    fields = [
        "name",
        "description",
        "status",
        "priority",
        "project_id",
        "prd_text",
        "review_report",
        "tech_design",
        "test_cases",
        "code",
    ]
    updates = []
    vals = []
    for f in fields:
        if f in req:
            updates.append(f"{f}=?")
            vals.append(req[f])
    if not updates:
        raise HTTPException(400, "无更新字段")
    updates.append("updated_at=?")
    vals.append(datetime.now().isoformat())
    vals.append(req_id)
    conn.execute(f"UPDATE requirements SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": req_id}


@router.delete("/api/requirements/{req_id}")
async def delete_requirement(req_id: str):
    conn = get_db()
    conn.execute("UPDATE requirements SET active=0 WHERE id=?", (req_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/api/requirements/{req_id}/pipeline-output")
async def save_pipeline_output(req_id: str, req: dict):
    """保存流水线阶段输出（AI 工作台调用）。

    同时更新 pipeline_status：当前阶段标记 fresh，下游阶段标记 stale（需求变更传播）。
    """
    stage = req.get("stage") or ""
    content = req.get("content") or ""
    field_map = {
        "prd": "prd_text",
        "review": "review_report",
        "td": "tech_design",
        "test": "test_cases",
        "code": "code",
        "code_review": "code_review",
        "review_code": "code_review",
    }
    field = field_map.get(stage)
    if not field:
        raise HTTPException(400, f"未知阶段: {stage}")
    conn = get_db()
    conn.execute(
        f"UPDATE requirements SET {field}=?, updated_at=? WHERE id=?", (content, datetime.now().isoformat(), req_id)
    )
    # 流水线状态：当前阶段 fresh，下游全部 stale（上游变更后下游产物需重新生成）
    STAGE_ORDER = ["prd", "review", "td", "test", "code", "review_code"]
    row = conn.execute("SELECT pipeline_status FROM requirements WHERE id=?", (req_id,)).fetchone()
    ps = {}
    if row and row["pipeline_status"]:
        ps = json.loads(row["pipeline_status"])
    now = datetime.now().isoformat()
    ps[stage] = {"status": "fresh", "updated_at": now}
    if stage in STAGE_ORDER:
        for s in STAGE_ORDER[STAGE_ORDER.index(stage) + 1 :]:
            ps[s] = {"status": "stale", "updated_at": ps.get(s, {}).get("updated_at", "")}
    conn.execute("UPDATE requirements SET pipeline_status=? WHERE id=?", (json.dumps(ps, ensure_ascii=False), req_id))
    conn.commit()
    conn.close()
    return {"success": True, "stage": stage}


# ── 项目管理 ────────────────────────────────────────────────


@router.get("/api/projects")
async def list_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects WHERE active=1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/projects")
async def create_project(req: dict):
    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    proj_id = f"proj_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO projects (id, name, description, status, team_id, created_at, updated_at, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
        (proj_id, name, req.get("description", ""), req.get("status", "active"), req.get("team_id", ""), now, now),
    )
    conn.commit()
    conn.close()
    return {"id": proj_id, "name": name}


@router.delete("/api/projects/{proj_id}")
async def delete_project(proj_id: str):
    conn = get_db()
    conn.execute("UPDATE projects SET active=0 WHERE id=?", (proj_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── 成果仓库 ────────────────────────────────────────────────


@router.get("/api/artifacts")
async def list_artifacts(project_id: str = ""):
    """成果列表，支持按 project_id 过滤（query 参数 ?project_id=xxx）。

    - 不传 project_id：返回全部 active artifacts
    - 传 project_id：仅返回该项目的 artifacts（包括图片/视频/音频/文档等所有类型）
    """
    conn = get_db()
    if project_id:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE active=1 AND project_id=? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM artifacts WHERE active=1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/projects/{project_id}/artifacts")
async def list_project_artifacts(project_id: str):
    """项目空间：按 project_id 查询该项目下全部 artifacts（聚合图片/视频/音频/文档产物）。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM artifacts WHERE active=1 AND project_id=? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/artifacts")
async def create_artifact(req: dict):
    art_id = f"art_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    conn.execute(
        """INSERT INTO artifacts (id, project_id, requirement_id, type, content, version, author, created_at, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            art_id,
            req.get("project_id", ""),
            req.get("requirement_id", ""),
            req.get("type", "doc"),
            json.dumps(req.get("content", {})),
            req.get("version", "v1"),
            req.get("author", "admin"),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": art_id}


@router.delete("/api/artifacts/{art_id}")
async def delete_artifact(art_id: str):
    conn = get_db()
    conn.execute("UPDATE artifacts SET active=0 WHERE id=?", (art_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ══════════════════════════════════════════════════════════════
# 系统配置
# ══════════════════════════════════════════════════════════════


@router.get("/api/config")
async def get_config():
    conn = get_db()
    rows = conn.execute("SELECT * FROM config").fetchall()
    conn.close()
    cfg = {r["key"]: r["value"] for r in rows}
    # 脱敏 API Key
    if cfg.get("agnes_api_key"):
        cfg["agnes_api_key"] = "••••••••••••" + cfg["agnes_api_key"][-4:]
    # 兼容前端字段名
    cfg.setdefault("api_url", cfg.get("agnes_api_base", ""))
    cfg.setdefault("api_key", cfg.get("agnes_api_key", ""))
    cfg.setdefault("model_name", cfg.get("model_name", "agnes-2.5-flash"))
    # 模型列表（config 表未配置时返回内置默认）；api_key 脱敏
    models = _get_models()
    for m in models:
        if m.get("api_key"):
            m["api_key"] = _mask_key(m["api_key"])
    cfg["models"] = models
    return cfg


def _mask_key(key: str) -> str:
    """脱敏 API Key：保留前 6 / 后 4 位。"""
    key = key.strip()
    if len(key) <= 10:
        return "••••" + key[-2:]
    return key[:6] + "••••••" + key[-4:]


def _get_models() -> list[dict]:
    """读取模型列表（原文含 api_key）：config 表 model_list（JSON），空则回退内置默认。"""
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key='model_list'").fetchone()
    conn.close()
    raw = row["value"] if row else ""
    if raw:
        try:
            models = json.loads(raw)
            if isinstance(models, list) and models and all("name" in m for m in models):
                return models
        except (ValueError, TypeError):
            pass
    return [dict(m) for m in DEFAULT_MODELS]


@router.post("/api/config/models")
async def add_model(req: dict):
    """添加模型到模型列表（自动去重）；支持每个模型独立配置 base_url / api_key。"""
    name = (req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "模型名称不能为空")
    if len(name) > 100:
        raise HTTPException(400, "模型名称过长（最多 100 字符）")
    note = (req.get("note") or "").strip()[:50]
    base_url = (req.get("base_url") or "").strip()
    api_key = (req.get("api_key") or "").strip()
    models = _get_models()
    if any(m.get("name") == name for m in models):
        raise HTTPException(400, f"模型 {name} 已存在（如需修改请使用更新）")
    models.append({"name": name, "note": note, "base_url": base_url, "api_key": api_key})
    _save_models(models)
    return {"models": _mask_models(models)}


@router.put("/api/config/models/{name}")
async def update_model(name: str, req: dict):
    """更新模型配置（note / base_url / api_key）；api_key 传空 = 保持不变。"""
    models = _get_models()
    target = next((m for m in models if m.get("name") == name), None)
    if not target:
        raise HTTPException(404, f"模型 {name} 不存在")
    if "note" in req:
        target["note"] = (req.get("note") or "").strip()[:50]
    if "base_url" in req:
        target["base_url"] = (req.get("base_url") or "").strip()
    if req.get("api_key"):  # 留空 = 保持原样
        target["api_key"] = req["api_key"].strip()
    _save_models(models)
    return {"models": _mask_models(models)}


def _save_models(models: list[dict]) -> None:
    """持久化模型列表到 config 表。"""
    conn = get_db()
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('model_list', ?) ON CONFLICT(key) DO UPDATE SET value=?",
        (json.dumps(models, ensure_ascii=False), json.dumps(models, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def _mask_models(models: list[dict]) -> list[dict]:
    """返回脱敏副本（不修改原列表）。"""
    out = []
    for m in models:
        c = dict(m)
        if c.get("api_key"):
            c["api_key"] = _mask_key(c["api_key"])
        out.append(c)
    return out


@router.delete("/api/config/models/{name}")
async def delete_model(name: str):
    """从模型列表移除；若删除的是当前默认模型则自动回退到列表第一个。"""
    models = _get_models()
    if not any(m.get("name") == name for m in models):
        raise HTTPException(404, f"模型 {name} 不存在")
    models = [m for m in models if m.get("name") != name]
    conn = get_db()
    if models:
        conn.execute(
            "INSERT INTO config (key, value) VALUES ('model_list', ?) ON CONFLICT(key) DO UPDATE SET value=?",
            (json.dumps(models, ensure_ascii=False), json.dumps(models, ensure_ascii=False)),
        )
    else:
        # 删空 → 清空配置，回退内置默认列表
        conn.execute("DELETE FROM config WHERE key='model_list'")
    # 被删的是当前默认模型 → 自动回退（config 表未显式配置时按内置默认判断）
    row = conn.execute("SELECT value FROM config WHERE key='model_name'").fetchone()
    current_default = row["value"] if row and row["value"] else DEFAULT_MODELS[0]["name"]
    if current_default == name:
        fallback = models[0]["name"] if models else DEFAULT_MODELS[0]["name"]
        conn.execute(
            "INSERT INTO config (key, value) VALUES ('model_name', ?) ON CONFLICT(key) DO UPDATE SET value=?",
            (fallback, fallback),
        )
    conn.commit()
    conn.close()
    load_config()
    return {"models": _mask_models(models if models else [dict(m) for m in DEFAULT_MODELS])}


@router.post("/api/config/save")
async def save_config(req: dict):
    """保存系统配置"""
    conn = get_db()
    updates = []
    if req.get("api_key"):
        updates.append(("agnes_api_key", req["api_key"].strip()))
    if req.get("api_url"):
        updates.append(("agnes_api_base", req["api_url"].strip()))
    if req.get("model_name"):
        updates.append(("model_name", req["model_name"].strip()))
    for k, v in updates:
        conn.execute("INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?", (k, v, v))
    conn.commit()
    conn.close()
    # 重载配置
    load_config()
    return {"success": True}


# ══════════════════════════════════════════════════════════════
# 使用统计 + 自进化
# ══════════════════════════════════════════════════════════════


@router.get("/api/usage-stats")
async def usage_stats(
    request: Request,
    days: int = 7,
    module: str = "",
    user: str = "",
):
    """使用统计（v15 参数化）：趋势区间 days（7/30/90）+ 按模块/按用户筛选。

    筛选同时作用于总览卡片与趋势；模块分布不受 module 筛选影响（否则只剩一个模块）。
    """
    # 可选：从 Authorization 头解析当前用户，返回会员等级与今日剩余额度（未登录则返回 free）
    member_level, remaining_today = "free", None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_access_token(auth_header[7:])
            uid = payload.get("user_id")
            if uid:
                profile = get_user_profile(uid)
                member_level = profile.get("membership", "free")
                remaining_today = profile.get("remaining_today")
        except Exception:
            pass
    days = min(max(int(days), 1), 90)
    module = (module or "").strip()
    user = (user or "").strip()
    where, params = "", []
    if module:
        where += " AND task_type=?"
        params.append(module)
    if user:
        where += " AND user_id=?"
        params.append(user)
    conn = get_db()
    total = conn.execute(f"SELECT COUNT(*) c FROM usage_logs WHERE 1=1{where}", params).fetchone()["c"]
    success = conn.execute(f"SELECT COUNT(*) c FROM usage_logs WHERE 1=1{where} AND success=1", params).fetchone()["c"]
    avg_time = conn.execute(f"SELECT AVG(response_time) a FROM usage_logs WHERE 1=1{where}", params).fetchone()["a"]
    by_type = conn.execute(
        f"SELECT task_type, COUNT(*) c, AVG(response_time) a FROM usage_logs WHERE 1=1{where} GROUP BY task_type"
        , params
    ).fetchall()
    recent = conn.execute(
        f"SELECT * FROM usage_logs WHERE 1=1{where} ORDER BY timestamp DESC LIMIT 10", params
    ).fetchall()
    # 趋势区间：days 天窗口（按日聚合调用次数 + token 消耗）
    daily = conn.execute(
        f"SELECT substr(timestamp,1,10) d, COUNT(*) c, SUM(input_length + output_length) tokens "
        f"FROM usage_logs WHERE timestamp >= datetime('now', ?) AND 1=1{where} GROUP BY d ORDER BY d",
        [f"-{days} days"] + params,
    ).fetchall()
    # 模块分布（只受 user 筛选影响，展示全部模块占比）
    dist_where, dist_params = "", []
    if user:
        dist_where += " AND user_id=?"
        dist_params.append(user)
    module_agg = conn.execute(
        f"SELECT task_type module, COUNT(*) c FROM usage_logs WHERE 1=1{dist_where} GROUP BY task_type ORDER BY c DESC",
        dist_params,
    ).fetchall()
    # 今日统计
    today = conn.execute(
        f"SELECT COUNT(*) c, COALESCE(SUM(input_length + output_length), 0) tokens FROM usage_logs "
        f"WHERE substr(timestamp,1,10) = substr(date('now'),1,10) AND 1=1{where}",
        params,
    ).fetchone()
    total_tokens = conn.execute(
        f"SELECT COALESCE(SUM(input_length + output_length), 0) t FROM usage_logs WHERE 1=1{where}", params
    ).fetchone()["t"]
    conn.close()
    return {
        "total_calls": total,
        "success_rate": round(success / total * 100, 1) if total else 0,
        "avg_response_time": round(avg_time, 2) if avg_time else 0,
        "by_type": [dict(r) for r in by_type],
        "recent": [dict(r) for r in recent],
        "daily_breakdown": [{"date": r["d"], "count": r["c"], "tokens": r["tokens"] or 0} for r in daily],
        "module_breakdown": [{"module": r["module"], "count": r["c"]} for r in module_agg],
        "total_tokens": total_tokens,
        "today_calls": today["c"],
        "today_tokens": today["tokens"],
        "most_used": module_agg[0]["module"] if module_agg else "无",
        "member_level": member_level,
        "remaining_today": remaining_today,
    }


@router.get("/api/usage-stats/users")
async def usage_stats_users(current_user: dict = Depends(require_auth)):
    """用量分析可选用户列表：usage_logs 中有埋点 user_id 的去重（附用户名）。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT user_id FROM usage_logs WHERE user_id != '' ORDER BY user_id"
    ).fetchall()
    conn.close()
    if not rows:
        return []
    ids = [r["user_id"] for r in rows]
    ph = ",".join("?" * len(ids))
    conn = get_db()
    try:
        users = conn.execute(f"SELECT id, username FROM users WHERE id IN ({ph})", ids).fetchall()
    finally:
        conn.close()
    um = {r["id"]: r["username"] for r in users}
    return [{"id": u, "username": um.get(u, u)} for u in ids]


@router.get("/api/usage-stats/export")
async def usage_stats_export(current_user: dict = Depends(require_auth)):
    """导出使用统计 CSV（按 日期×模块 聚合，供审计/归档）。"""
    import csv
    import io

    conn = get_db()
    rows = conn.execute(
        "SELECT substr(timestamp,1,10) d, task_type, COUNT(*) c, "
        "SUM(input_length + output_length) tokens, ROUND(AVG(response_time),2) avg_ms, SUM(success) ok "
        "FROM usage_logs GROUP BY d, task_type ORDER BY d DESC, c DESC LIMIT 10000"
    ).fetchall()
    conn.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["日期", "模块", "调用次数", "Token消耗", "平均耗时(s)", "成功次数"])
    for r in rows:
        w.writerow([r["d"], r["task_type"], r["c"], r["tokens"] or 0, r["avg_ms"] or 0, r["ok"] or 0])
    return Response(
        content="\ufeff" + buf.getvalue(),  # BOM：Excel 直接打开中文不乱码
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=usage_stats.csv"},
    )


@router.get("/api/evolution/prompt-history")
async def prompt_history():
    conn = get_db()
    rows = conn.execute("SELECT * FROM prompt_versions ORDER BY optimized_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/evolution/optimize-prompts")
def optimize_prompts(req: dict):
    """自进化 - 优化提示词模板"""
    target = req.get("target") or "all"
    conn = get_db()
    rows = conn.execute("SELECT * FROM prompt_versions ORDER BY optimized_at DESC LIMIT 20").fetchall()
    conn.close()

    history_summary = ""
    if rows:
        history_summary = "\n".join(
            f"- [{r.get('module') or r.get('id')}] v{r.get('version') or '?'}: {(r.get('instructions') or '')[:200]}"
            for r in rows[-5:]
        )

    system = "你是一位提示词工程专家。根据历史 prompt 的使用效果，优化改进提示词模板。输出优化后的 prompt 版本。"
    user = f"优化目标: {target}\n\n历史 prompt 记录:\n{history_summary or '暂无历史记录'}\n\n请输出优化后的 prompt（直接给内容，标注优化点）。"
    result = call_llm(system, user, max_tokens=3000)

    conn = get_db()
    conn.execute(
        """INSERT INTO prompt_versions (module, version, instructions, optimized_at, created_by)
           VALUES (?, ?, ?, ?, ?)""",
        (target, 1, result, datetime.now().isoformat(), "platform_evolution"),
    )
    conn.commit()
    conn.close()
    return {"result": result}

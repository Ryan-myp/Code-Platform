#!/usr/bin/env python3
"""研发流程引擎 - PRD 生成/审查/技术方案/测试用例/代码生成 + 需求/项目/成果/配置/自进化 API"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from common.config import BIZ_DELIVERY_DIR, DEFAULT_MODELS, load_config
from common.db import get_db
from common.llm import call_llm, log_usage

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
要求：
1. 结构完整：背景与目标、用户故事、功能需求、非功能需求、验收标准、数据指标
2. 功能需求用表格或编号列出，注明优先级 P0/P1/P2
3. 语言简洁专业，直接输出 PRD 正文
4. 不要输出"以下是"之类的废话开头"""

REVIEW_SYSTEM = """你是一位资深架构师兼技术评审专家，擅长审查 PRD。
审查维度（22+ 项）：
- 需求完整性：目标、范围、边界是否清晰
- 逻辑一致性：前后矛盾、歧义、遗漏
- 技术可行性：依赖、性能、安全、兼容性
- 可测试性：验收标准是否可量化
- 优先级：P0/P1/P2 划分是否合理
输出格式：
1. 总体评价（含评分 /100）
2. 问题清单表格（编号 | 级别 P0/P1/P2 | 问题描述 | 修改建议）
3. 亮点与风险
4. 修改建议总结"""

TD_SYSTEM = """你是一位资深技术架构师，擅长编写技术设计方案。
要求：
1. 架构总览（含 Mermaid 架构图）
2. 核心场景流程（Mermaid 时序图 + 步骤表）
3. 详细设计：模块划分、数据模型（表结构）、接口定义（REST API 表）
4. 关键技术决策表（决策项 | 选项 | 选择 | 理由）
5. 文件/代码结构清单
6. 风险与演进
直接输出完整技术方案 Markdown。"""

TEST_SYSTEM = """你是一位资深测试工程师，擅长设计测试用例。
要求：
1. 覆盖正向流程、异常流程、边界条件
2. 用例格式：编号 | 级别 | 前置条件 | 步骤 | 预期结果
3. 包含接口测试（状态码/响应结构/错误码）和场景测试
4. 注明 P0 用例必须覆盖核心链路
直接输出测试用例文档。"""

CODE_SYSTEM = """你是一位高级开发工程师，擅长编写高质量可运行代码。
要求：
1. 直接输出完整代码，包含必要的 import 和 main 函数
2. 代码必须可运行，错误处理完善
3. 文件开头注释说明文件用途
4. 如需要多文件，用 Markdown 代码块标注文件名
直接输出代码，不要解释。"""


@router.post("/api/prd/generate")
async def generate_prd(req: dict):
    """AI 生成 PRD"""
    prd_text = (req.get("prd_text") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入需求描述")

    start = time.time()
    try:
        # 尝试用 biz-delivery 的 prompt 模板增强（若有）
        result = call_llm(PRD_SYSTEM, prd_text, max_tokens=4000)
        log_usage("prd_generate", len(prd_text), len(result), time.time() - start)
        return {"result": result}
    except Exception as e:
        logger.error(f"PRD generate failed: {e}")
        raise HTTPException(500, f"PRD 生成失败: {str(e)}") from e


@router.post("/api/prd/review")
async def review_prd(req: dict):
    """PRD 审查 - 优先用 biz-delivery ReviewEngine，失败 fallback LLM"""
    prd_text = (req.get("prd_text") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入 PRD 内容")

    repo_path = req.get("repo_path") or ""
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

    result = call_llm(REVIEW_SYSTEM, prd_text, max_tokens=4000)
    log_usage("prd_review", len(prd_text), len(result), time.time() - start)
    return {"result": result, "engine": "llm", "fallback": fallback}


@router.post("/api/prd/technical-design")
async def technical_design(req: dict):
    """技术方案生成 - 优先用 biz-delivery TDEngine"""
    prd_text = (req.get("prd_text") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入 PRD 内容")

    repo_path = req.get("repo_path") or ""
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

    result = call_llm(TD_SYSTEM, prd_text, max_tokens=6000)
    log_usage("prd_td", len(prd_text), len(result), time.time() - start)
    return {"result": result, "engine": "llm", "fallback": fallback}


@router.post("/api/prd/test-cases")
async def test_cases(req: dict):
    """测试用例生成 - 优先用 biz-delivery TestEngine"""
    prd_text = (req.get("prd_text") or "").strip()
    tech_design = (req.get("tech_design") or "").strip()
    if not prd_text:
        raise HTTPException(400, "请输入 PRD 内容")

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
    result = call_llm(TEST_SYSTEM, user_prompt, max_tokens=4000)
    log_usage("prd_test", len(user_prompt), len(result), time.time() - start)
    return {"result": result, "engine": "llm", "fallback": fallback}


@router.post("/api/prd/generate-code")
async def generate_code(req: dict):
    """根据技术方案生成代码"""
    tech_design = (req.get("tech_design") or "").strip()
    language = (req.get("language") or "python").strip()
    task_type = req.get("task_type", "code")
    if not tech_design:
        raise HTTPException(400, "请输入技术方案")

    start = time.time()
    user_prompt = f"语言: {language}\n任务类型: {task_type}\n\n技术方案:\n{tech_design}"
    result = call_llm(CODE_SYSTEM, user_prompt, max_tokens=8000)
    log_usage("prd_code", len(user_prompt), len(result), time.time() - start)
    return {"result": result, "language": language}


@router.post("/api/prd/code-chat")
async def code_chat(req: dict):
    """代码对话 - 追问/修改代码"""
    message = (req.get("message") or "").strip()
    language = (req.get("language") or "python").strip()
    if not message:
        raise HTTPException(400, "请输入消息")

    start = time.time()
    system = f"你是一位高级 {language} 开发工程师。根据用户对话上下文，继续完善或修改代码。直接输出最新完整代码，不要解释。"
    result = call_llm(system, message, max_tokens=8000)
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
        (req_id, name, req.get("description", ""), req.get("status", "draft"),
         req.get("priority", "P1"), req.get("project_id", ""), req.get("creator", "admin"),
         1, now, now),
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


@router.put("/api/requirements/{req_id}")
async def update_requirement(req_id: str, req: dict):
    conn = get_db()
    fields = ["name", "description", "status", "priority", "project_id", "prd_text", "review_report", "tech_design", "test_cases", "code"]
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
    field_map = {"prd": "prd_text", "review": "review_report", "td": "tech_design", "test": "test_cases", "code": "code", "code_review": "code_review", "review_code": "code_review"}
    field = field_map.get(stage)
    if not field:
        raise HTTPException(400, f"未知阶段: {stage}")
    conn = get_db()
    conn.execute(f"UPDATE requirements SET {field}=?, updated_at=? WHERE id=?", (content, datetime.now().isoformat(), req_id))
    # 流水线状态：当前阶段 fresh，下游全部 stale（上游变更后下游产物需重新生成）
    STAGE_ORDER = ["prd", "review", "td", "test", "code", "review_code"]
    row = conn.execute("SELECT pipeline_status FROM requirements WHERE id=?", (req_id,)).fetchone()
    ps = {}
    if row and row["pipeline_status"]:
        ps = json.loads(row["pipeline_status"])
    now = datetime.now().isoformat()
    ps[stage] = {"status": "fresh", "updated_at": now}
    if stage in STAGE_ORDER:
        for s in STAGE_ORDER[STAGE_ORDER.index(stage) + 1:]:
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
        (art_id, req.get("project_id", ""), req.get("requirement_id", ""), req.get("type", "doc"),
         json.dumps(req.get("content", {})), req.get("version", "v1"), req.get("author", "admin"),
         datetime.now().isoformat()),
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
        fallback = (models[0]["name"] if models else DEFAULT_MODELS[0]["name"])
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
async def usage_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) c FROM usage_logs").fetchone()["c"]
    success = conn.execute("SELECT COUNT(*) c FROM usage_logs WHERE success=1").fetchone()["c"]
    avg_time = conn.execute("SELECT AVG(response_time) a FROM usage_logs").fetchone()["a"]
    by_type = conn.execute("SELECT task_type, COUNT(*) c, AVG(response_time) a FROM usage_logs GROUP BY task_type").fetchall()
    recent = conn.execute("SELECT * FROM usage_logs ORDER BY timestamp DESC LIMIT 10").fetchall()
    conn.close()
    return {
        "total_calls": total,
        "success_rate": round(success / total * 100, 1) if total else 0,
        "avg_response_time": round(avg_time, 2) if avg_time else 0,
        "by_type": [dict(r) for r in by_type],
        "recent": [dict(r) for r in recent],
    }


@router.get("/api/evolution/prompt-history")
async def prompt_history():
    conn = get_db()
    rows = conn.execute("SELECT * FROM prompt_versions ORDER BY optimized_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/evolution/optimize-prompts")
async def optimize_prompts(req: dict):
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

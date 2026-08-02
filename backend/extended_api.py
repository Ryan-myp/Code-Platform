#!/usr/bin/env python3
"""Platform v9.0 Extended API - 研发增强/内容创作/运营分析/办公效率"""

import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from common.db import get_db
from common.auth import require_auth
from common.llm import call_llm

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# Phase 2: 研发增强
# ══════════════════════════════════════════════════════════════

class CodeGenRequest(BaseModel):
    language: str = "python"
    prompt: str
    model: str = ""

class CodeReviewRequest(BaseModel):
    language: str = "python"
    code: str
    model: str = ""

class PipelineCreate(BaseModel):
    name: str
    description: str = ""
    type: str = "ci"
    config: dict = {}


@router.post("/api/code/generate")
async def generate_code(data: CodeGenRequest, current_user: dict = require_auth()):
    """AI 代码生成"""
    conn = get_db()
    try:
        system_prompt = f"你是一个专业的{data.language}开发工程师。根据用户需求生成高质量代码。只返回代码，不要解释。"
        result = call_llm(system_prompt, data.prompt)
        
        gen_id = f"cg_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO code_generations (id, language, prompt, result, model) VALUES (?,?,?,?,?)",
            (gen_id, data.language, data.prompt, result, data.model)
        )
        conn.commit()
        return {"ok": True, "id": gen_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"代码生成失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/code/generations")
async def list_code_generations(current_user: dict = require_auth()):
    """获取代码生成历史"""
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM code_generations ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.post("/api/code/review")
async def review_code(data: CodeReviewRequest, current_user: dict = require_auth()):
    """AI 代码审查"""
    conn = get_db()
    try:
        system_prompt = f"你是一个资深的{data.language}代码审查专家。审查以下代码，给出改进建议，包括：1.代码质量 2.潜在bug 3.性能优化 4.安全建议。"
        result = call_llm(system_prompt, data.code)
        
        review_id = f"cr_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO code_reviews (id, language, code, result, model) VALUES (?,?,?,?,?)",
            (review_id, data.language, data.code, result, data.model)
        )
        conn.commit()
        return {"ok": True, "id": review_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"代码审查失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/code/reviews")
async def list_code_reviews(current_user: dict = require_auth()):
    """获取代码审查历史"""
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM code_reviews ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


# Pipeline CRUD
@router.get("/api/pipelines")
async def list_pipelines(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM pipelines WHERE active=1 ORDER BY created_at DESC").fetchall():
            p = dict(row)
            p["config"] = json.loads(p.get("config", "{}"))
            items.append(p)
        return items
    finally:
        conn.close()


@router.post("/api/pipelines")
async def create_pipeline(data: PipelineCreate, current_user: dict = require_auth()):
    conn = get_db()
    try:
        pid = f"pipe_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO pipelines (id, name, description, type, config, created_by) VALUES (?,?,?,?,?,?)",
            (pid, data.name, data.description, data.type, json.dumps(data.config), current_user["username"])
        )
        conn.commit()
        return {"ok": True, "id": pid}
    finally:
        conn.close()


@router.delete("/api/pipelines/{pid}")
async def delete_pipeline(pid: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("UPDATE pipelines SET active=0 WHERE id=?", (pid,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Phase 3: 内容创作增强
# ══════════════════════════════════════════════════════════════

class CopywritingRequest(BaseModel):
    type: str = "marketing"
    title: str = ""
    prompt: str
    model: str = ""

class TranslationRequest(BaseModel):
    source_lang: str = "中文"
    target_lang: str = "English"
    text: str
    model: str = ""


@router.post("/api/copywriting/generate")
async def generate_copywriting(data: CopywritingRequest, current_user: dict = require_auth()):
    """AI 文案生成"""
    conn = get_db()
    try:
        type_prompts = {
            "marketing": "营销文案专家，生成吸引眼球的营销文案",
            "social": "社交媒体运营专家，生成适合社交平台的文案",
            "seo": "SEO优化专家，生成搜索引擎友好的文案",
            "email": "邮件营销专家，生成高转化率的邮件内容",
            "ad": "广告创意专家，生成创意广告文案",
        }
        role = type_prompts.get(data.type, "专业文案写手")
        system_prompt = f"你是一位{role}。根据用户需求生成高质量文案。"
        result = call_llm(system_prompt, data.prompt)
        
        task_id = f"copy_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO copywriting_tasks (id, type, title, prompt, result, model) VALUES (?,?,?,?,?,?)",
            (task_id, data.type, data.title, data.prompt, result, data.model)
        )
        conn.commit()
        return {"ok": True, "id": task_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"文案生成失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/copywriting/history")
async def list_copywriting_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM copywriting_tasks ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.delete("/api/copywriting/{task_id}")
async def delete_copywriting(task_id: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("DELETE FROM copywriting_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/api/translation/translate")
async def translate_text(data: TranslationRequest, current_user: dict = require_auth()):
    """AI 翻译"""
    conn = get_db()
    try:
        system_prompt = f"你是专业翻译，将以下内容从{data.source_lang}翻译为{data.target_lang}。保持原文格式和语气，只返回翻译结果。"
        result = call_llm(system_prompt, data.text)
        
        trans_id = f"trans_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO translations (id, source_lang, target_lang, source_text, result, model) VALUES (?,?,?,?,?,?)",
            (trans_id, data.source_lang, data.target_lang, data.text, result, data.model)
        )
        conn.commit()
        return {"ok": True, "id": trans_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"翻译失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/translation/history")
async def list_translation_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM translations ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.delete("/api/translation/{task_id}")
async def delete_translation(task_id: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("DELETE FROM translations WHERE id = ?", (task_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Phase 4: 运营分析
# ══════════════════════════════════════════════════════════════

class ABTestCreate(BaseModel):
    name: str
    description: str = ""
    variant_a: str = ""
    variant_b: str = ""


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = require_auth()):
    """获取仪表盘统计数据"""
    conn = get_db()
    try:
        stats = {
            "agents": conn.execute("SELECT COUNT(*) FROM agents WHERE active=1").fetchone()[0],
            "workflows": conn.execute("SELECT COUNT(*) FROM workflows WHERE active=1").fetchone()[0],
            "projects": conn.execute("SELECT COUNT(*) FROM projects WHERE active=1").fetchone()[0],
            "tasks": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE active=1").fetchone()[0],
            "tasks_completed": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE status='done' AND active=1").fetchone()[0],
            "pipelines": conn.execute("SELECT COUNT(*) FROM pipelines WHERE active=1").fetchone()[0],
            "code_generations": conn.execute("SELECT COUNT(*) FROM code_generations").fetchone()[0],
            "translations": conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
            "artifacts": conn.execute("SELECT COUNT(*) FROM artifacts WHERE active=1").fetchone()[0],
        }
        return stats
    finally:
        conn.close()


@router.get("/api/analytics/overview")
async def get_analytics_overview(current_user: dict = require_auth()):
    """获取分析概览"""
    conn = get_db()
    try:
        return {
            "total_agents": conn.execute("SELECT COUNT(*) FROM agents WHERE active=1").fetchone()[0],
            "total_workflows": conn.execute("SELECT COUNT(*) FROM workflows WHERE active=1").fetchone()[0],
            "total_projects": conn.execute("SELECT COUNT(*) FROM projects WHERE active=1").fetchone()[0],
            "total_tasks": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE active=1").fetchone()[0],
            "completed_tasks": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE status='done'").fetchone()[0],
            "total_artifacts": conn.execute("SELECT COUNT(*) FROM artifacts WHERE active=1").fetchone()[0],
            "total_code_gens": conn.execute("SELECT COUNT(*) FROM code_generations").fetchone()[0],
            "total_translations": conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
        }
    finally:
        conn.close()


@router.get("/api/ab-tests")
async def list_ab_tests(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM ab_tests WHERE active=1 ORDER BY created_at DESC").fetchall():
            t = dict(row)
            t["result"] = json.loads(t.get("result", "{}"))
            items.append(t)
        return items
    finally:
        conn.close()


@router.post("/api/ab-tests")
async def create_ab_test(data: ABTestCreate, current_user: dict = require_auth()):
    conn = get_db()
    try:
        tid = f"ab_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO ab_tests (id, name, description, variant_a, variant_b, created_by) VALUES (?,?,?,?,?,?)",
            (tid, data.name, data.description, data.variant_a, data.variant_b, current_user["username"])
        )
        conn.commit()
        return {"ok": True, "id": tid}
    finally:
        conn.close()


@router.delete("/api/ab-tests/{tid}")
async def delete_ab_test(tid: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("UPDATE ab_tests SET active=0 WHERE id=?", (tid,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 办公效率: PPT + Excel
# ══════════════════════════════════════════════════════════════

class PPTGenerateRequest(BaseModel):
    title: str
    outline: str = ""
    model: str = ""

class ExcelRequest(BaseModel):
    operation: str = "create"
    title: str = ""
    data: dict = {}


@router.post("/api/ppt/generate")
async def generate_ppt(data: PPTGenerateRequest, current_user: dict = require_auth()):
    """AI PPT 大纲生成"""
    conn = get_db()
    try:
        system_prompt = """你是一个专业的PPT制作专家。根据用户提供的主题，生成PPT大纲。
请按以下JSON格式返回：
{
  "slides": [
    {"title": "幻灯片标题", "content": "要点1\\n要点2\\n要点3", "notes": "演讲备注"},
    ...
  ]
}
生成6-10页幻灯片，包含封面、目录、内容页和总结页。只返回JSON。"""
        
        prompt = f"主题：{data.title}"
        if data.outline:
            prompt += f"\n大纲：{data.outline}"
        
        result = call_llm(system_prompt, prompt)
        
        ppt_id = f"ppt_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO ppt_generations (id, title, outline, result, model) VALUES (?,?,?,?,?)",
            (ppt_id, data.title, data.outline, result, data.model)
        )
        conn.commit()
        return {"ok": True, "id": ppt_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"PPT生成失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/ppt/history")
async def list_ppt_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM ppt_generations ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.post("/api/excel/operate")
async def excel_operate(data: ExcelRequest, current_user: dict = require_auth()):
    """Excel 操作"""
    conn = get_db()
    try:
        op_id = f"excel_{uuid.uuid4().hex[:12]}"
        result = ""
        
        if data.operation == "analyze":
            system_prompt = "你是一个Excel数据分析专家。分析用户提供的数据，给出关键发现和建议。"
            result = call_llm(system_prompt, json.dumps(data.data, ensure_ascii=False))
        elif data.operation == "formula":
            system_prompt = "你是一个Excel公式专家。根据用户需求生成Excel公式，解释公式含义。"
            prompt = data.data.get("prompt", "")
            result = call_llm(system_prompt, prompt)
        else:
            result = json.dumps({"status": "created", "data": data.data})
        
        conn.execute(
            "INSERT INTO excel_operations (id, operation, title, data, result) VALUES (?,?,?,?,?)",
            (op_id, data.operation, data.title, json.dumps(data.data), result)
        )
        conn.commit()
        return {"ok": True, "id": op_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"Excel操作失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/excel/history")
async def list_excel_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM excel_operations ORDER BY created_at DESC LIMIT 50").fetchall():
            e = dict(row)
            e["data"] = json.loads(e.get("data", "{}"))
            items.append(e)
        return items
    finally:
        conn.close()

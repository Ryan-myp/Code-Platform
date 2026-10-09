#!/usr/bin/env python3
"""效率工具箱 API v2 - 专业级工具平台"""

import asyncio
import base64
import hashlib
import html
import io
import json
import logging
import os
import re
import traceback
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from difflib import unified_diff
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from common.auth import require_auth
from common.helpers import _notify_progress
from common.db import get_db
from common.llm import call_llm_async, _safe_exc_msg
from permissions import access_status, get_visibility_map, load_user_ctx
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# 工具定义 v2 - 支持高级参数、模板、导出
# ══════════════════════════════════════════════════════════════

from tool_definitions import TOOL_DEFINITIONS  # noqa: F401  # 工具定义数据(拆分自 tool_hub)



# ══════════════════════════════════════════════════════════════
# 请求模型
# ══════════════════════════════════════════════════════════════


class ToolRunRequest(BaseModel):
    tool_id: str
    input: str
    params: dict[str, Any] | None = {}
    model: str = ""


class EnhancePromptRequest(BaseModel):
    """AI 提示词润色请求：风格化扩写用户输入，供各生成页「智能补充」复用。"""

    text: str
    style: str = "general"  # image / copywriting / music / video / meme / mindmap / ppt / general

    # ══════════════════════════════════════════════════════════════


# API 端点
# ══════════════════════════════════════════════════════════════


# 各场景提示词润色专家系统（免费辅助能力，不扣减生成额度）
_ENHANCE_SYSTEMS = {
    "image": (
        "你是一位专业 AI 绘画提示词工程师。把用户的简要描述扩写为高质量英文绘图提示词："
        "包含主体、场景、光线、镜头、风格、画质等维度，用逗号分隔，不使用括号包裹。"
        "只输出润色后的提示词本身，不要解释。"
    ),
    "copywriting": (
        "你是一位资深营销文案专家。把用户的简要需求扩写为具体可执行的文案创作指令："
        "明确目标人群、核心卖点、语气基调、内容结构（开头-主体-结尾）与字数要求，"
        "让 AI 可直接按此生成高质量文案。只输出润色后的指令，不要解释。"
    ),
    "music": (
        "你是一位专业音乐制作人。把用户的简要描述扩写为结构化的音乐创作提示："
        "包含曲风、BPM 速度、乐器配置、情绪走向、段落结构（前奏-主歌-副歌-间奏-尾奏）。"
        "只输出润色后的提示，不要解释。"
    ),
    "video": (
        "你是一位短视频编导。把用户的简要主题扩写为完整的视频分镜提示："
        "包含画面描述、运镜方式、时长建议、旁白文案要点与情绪节奏。"
        "只输出润色后的提示，不要解释。"
    ),
    "meme": (
        "你是一位互联网表情包创作达人。把用户的一句话扩写为适合做表情包的文案："
        "保留幽默感与网络流行语风格，简短有力，适合黄底黑字或白底黑字大字报样式。"
        "可以给出 2-3 个候选，每个一行。只输出文案，不要解释。"
    ),
    "mindmap": (
        "你是一位知识结构整理专家。把用户的主题扩写为思维导图分支大纲："
        "用多级缩进结构输出，每行一个节点，子节点缩进表示层级，覆盖主要维度。"
        "只输出大纲，不要解释。"
    ),
    "ppt": (
        "你是一位 PPT 结构设计专家。把用户主题扩写为演示文稿大纲："
        "输出封面页、目录、3-6 个章节（每章节含要点），每行一个要点。"
        "只输出大纲，不要解释。"
    ),
    "game": (
        "你是一位游戏策划专家。把用户的简要玩法需求扩写为清晰完整的游戏设计需求说明："
        "补充核心玩法机制、操作方式、关卡/难度设计、美术与音效风格、目标玩家群体，"
        "让 AI 可直接据此实现小游戏。只输出润色后的需求说明，不要解释。"
    ),
    "excel": (
        "你是一位 Excel 公式专家。把用户的简要需求扩写为明确的 Excel 公式/数据处理需求描述："
        "补充数据列结构假设、计算规则、边界条件（空值/文本/负数）、期望输出格式，"
        "让 AI 可直接生成准确公式。只输出润色后的需求描述，不要解释。"
    ),
    "general": (
        "你是一位需求澄清专家。把用户的简要描述扩写为更完整、更具体、可执行的表达，"
        "保留原意，补充关键细节与边界条件，语气专业。只输出润色后的文本，不要解释。"
    ),
}


@router.post("/api/tools/enhance-prompt")
async def enhance_prompt(req: EnhancePromptRequest, current_user: dict = require_auth()):
    """AI 润色/扩写提示词：各生成页「智能补充」共用，免费不扣额度。"""
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "请先输入内容再使用智能补充")
    if len(text) > 2000:
        raise HTTPException(400, "内容过长（2000 字以内），请精简后重试")
    system_prompt = _ENHANCE_SYSTEMS.get(req.style, _ENHANCE_SYSTEMS["general"])
    try:
        enhanced = await call_llm_async(
            system_prompt, f"【原始内容】\n{text}", max_tokens=800, temperature=0.7
        )
        enhanced = enhanced.strip().strip('"\'`')
        if not enhanced or enhanced.lower().startswith(("抱歉", "sorry", "无法")):
            raise HTTPException(502, "智能补充暂不可用，请稍后重试")
        return {"ok": True, "enhanced": enhanced}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[enhance_prompt] {traceback.format_exc()}")
        raise HTTPException(500, "操作失败，请稍后重试") from e


@router.get("/api/tools")
async def list_tools(current_user: dict = require_auth()):
    """获取当前用户可见的效率工具列表（受内容权限控制）。"""
    vis_map = get_visibility_map("tool")
    user_ctx = load_user_ctx(current_user)
    tools = []
    for tool_id, tool in TOOL_DEFINITIONS.items():
        status = access_status(user_ctx, vis_map.get(tool_id, "all"))
        if not status["visible"]:
            continue
        item = {
            "id": tool_id,
            "name": tool["name"],
            "category": tool["category"],
            "icon": tool["icon"],
            "color": tool["color"],
            "description": tool["description"],
        }
        if status.get("locked"):
            item["locked"] = True
            item["requires"] = status["requires"]
        if tool.get("type") == "app":
            item["type"] = "app"
            item["path"] = tool["path"]
        else:
            item["type"] = "tool"
            item["placeholder"] = tool.get("placeholder", "")
            item["input_type"] = tool.get("input_type", "textarea")
            item["supports_file"] = tool.get("supports_file", False)
            item["templates"] = tool.get("templates", [])
            item["params"] = tool.get("params", {})
            item["export_formats"] = tool.get("export_formats", ["md"])
        tools.append(item)
    return tools


# ⚠️ 注意：/api/tools/stats 必须定义在 /api/tools/{tool_id} 之前，否则会被当作 tool_id 捕获（路由顺序陷阱）
@router.get("/api/tools/stats")
async def get_usage_stats(current_user: dict = require_auth()):
    """获取工具使用统计"""
    user_id = current_user.get("id", "default")
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT tool_id, use_count, last_used_at
               FROM tool_usage_stats WHERE user_id=?
               ORDER BY use_count DESC LIMIT 20""",
            (user_id,),
        ).fetchall()
        stats = []
        for row in rows:
            tool_id = row["tool_id"]
            if tool_id in TOOL_DEFINITIONS:
                tool = TOOL_DEFINITIONS[tool_id]
                stats.append(
                    {
                        "tool_id": tool_id,
                        "name": tool["name"],
                        "category": tool["category"],
                        "icon": tool["icon"],
                        "color": tool["color"],
                        "use_count": row["use_count"],
                        "last_used_at": row["last_used_at"],
                    }
                )
        return stats
    finally:
        conn.close()


@router.get("/api/tools/{tool_id}")
async def get_tool(tool_id: str, current_user: dict = require_auth()):
    """获取单个工具详情（无权限返回 404 防探测）。"""
    if tool_id not in TOOL_DEFINITIONS:
        raise HTTPException(404, "工具不存在")
    vis_map = get_visibility_map("tool")
    user_ctx = load_user_ctx(current_user)
    status = access_status(user_ctx, vis_map.get(tool_id, "all"))
    if not status["visible"]:
        raise HTTPException(404, "工具不存在")
    tool = TOOL_DEFINITIONS[tool_id]
    result = {
        "id": tool_id,
        **tool,
    }
    if status.get("locked"):
        result["locked"] = True
        result["requires"] = status["requires"]
    return result


@router.post("/api/tools/run")
async def run_tool(
    data: ToolRunRequest,
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务模式"),
    current_user: dict = require_auth(),
):
    """运行效率工具（默认异步任务：进度跟踪/失败自动重试/不阻塞事件循环；sync=true 兼容老客户端）"""
    if data.tool_id not in TOOL_DEFINITIONS:
        raise HTTPException(404, "工具不存在")

    # 内容权限兑底：不可见工具与不存在无异（404 防探测），锁定工具拒绝运行（403）
    vis_map = get_visibility_map("tool")
    user_ctx = load_user_ctx(current_user)
    status = access_status(user_ctx, vis_map.get(data.tool_id, "all"))
    if not status["visible"]:
        raise HTTPException(404, "工具不存在")
    if status.get("locked"):
        raise HTTPException(403, "该工具暂未对你开放")

    tool = TOOL_DEFINITIONS[data.tool_id]
    if tool.get("type") == "app":
        raise HTTPException(400, "该工具需要使用专属页面")

    payload = {
        "tool_id": data.tool_id,
        "input": data.input,
        "params": data.params or {},
        "model": data.model or "",
        "user_id": str(current_user.get("user_id", "")),
        "username": current_user.get("username", ""),
    }
    if sync:
        # 同步模式：直接执行（Long LLM 生成会阻塞本请求，仅供脚本/兼容场景）
        return await _run_tool_worker(payload)
    # 异步任务模式：提交即返回，慢 LLM（实测可达 300s+）不阻塞请求
    task = create_task(
        "tool_run",
        payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task["id"], "status": task["status"], "message": "工具执行任务已提交，可在任务中心或当前页面查看进度"}

# ══════════════════════════════════════════════════════════════
# v20 实算工具执行引擎（不消耗 LLM 额度）
# ══════════════════════════════════════════════════════════════

# ── 单位换算表 ─────────────────────────────────────────────────
_UNIT_CONVERSIONS = {
    "长度": {
        "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
        "mi": 1609.344, "yd": 0.9144, "ft": 0.3048, "in": 0.0254,
        "nmi": 1852.0, "ly": 9.461e15,
    },
    "重量": {
        "kg": 1.0, "g": 0.001, "mg": 1e-6,
        "t": 1000.0, "lb": 0.453592, "oz": 0.0283495, "ct": 0.0002,
    },
    "面积": {
        "m2": 1.0, "km2": 1e6, "cm2": 1e-4, "mm2": 1e-6,
        "ha": 10000.0, "ac": 4046.86, "ft2": 0.092903, "in2": 0.00064516,
    },
    "体积": {
        "l": 1.0, "ml": 0.001, "m3": 1000.0, "cm3": 0.001,
        "gal": 3.78541, "qt": 0.946353, "pt": 0.473176, "cup": 0.236588,
    },
    "速度": {
        "ms": 1.0, "kmh": 0.277778, "mph": 0.44704, "knot": 0.514444,
    },
    "数据量": {
        "b": 1.0, "kb": 1024.0, "mb": 1024**2, "gb": 1024**3,
        "tb": 1024**4, "pb": 1024**5,
    },
    "时间": {
        "s": 1.0, "ms": 0.001, "min": 60.0, "h": 3600.0, "d": 86400.0,
        "wk": 604800.0, "mo": 2592000.0, "yr": 31536000.0,
    },
}


async def _run_compute_tool(tool_id: str, input_text: str, params: dict, report) -> dict:
    """实算工具执行入口。"""
    report(10, "解析计算参数")

    if tool_id == "unit-converter":
        result = _compute_unit_converter(params)
    elif tool_id == "csv-analyzer":
        result = await _compute_csv_analyzer(input_text, params)
    elif tool_id == "json-formatter":
        result = _compute_json_formatter(input_text, params)
    elif tool_id == "regex-builder":
        result = _compute_regex_builder(input_text, params)
    elif tool_id == "sql-generator":
        result = _compute_sql_generator(input_text, params)
    elif tool_id == "date-calculator":
        result = _compute_date_calculator(input_text, params)
    elif tool_id == "markdown-table":
        result = _compute_markdown_table(input_text, params)
    elif tool_id == "color-converter":
        result = _compute_color_converter(input_text, params)
    elif tool_id == "diff-comparator":
        result = _compute_diff_comparator(input_text, params)
    elif tool_id == "password-generator":
        result = _compute_password_generator(params)
    elif tool_id == "base64-tool":
        result = _compute_base64_tool(input_text, params)
    else:
        raise HTTPException(404, "未知实算工具")

    report(90, "完成")
    return result


def _compute_unit_converter(params: dict) -> dict:
    """单位换算器。"""
    category = params.get("category", "长度")
    from_u = str(params.get("from_unit", "")).strip().lower()
    to_u = str(params.get("to_unit", "")).strip().lower()
    value = float(params.get("value", 1))

    # 温度特殊处理
    if category == "温度":
        temp_map = {"c": "c", "f": "f", "k": "k", "celsius": "c", "fahrenheit": "f", "kelvin": "k"}
        f_, t_ = temp_map.get(from_u, "c"), temp_map.get(to_u, "c")
        if f_ == "c" and t_ == "f":
            result = value * 9 / 5 + 32
        elif f_ == "f" and t_ == "c":
            result = (value - 32) * 5 / 9
        elif f_ == "c" and t_ == "k":
            result = value + 273.15
        elif f_ == "k" and t_ == "c":
            result = value - 273.15
        elif f_ == "f" and t_ == "k":
            result = (value - 32) * 5 / 9 + 273.15
        elif f_ == "k" and t_ == "f":
            result = (value - 273.15) * 9 / 5 + 32
        else:
            result = value
        return {
            "category": category,
            "from": f"{value} {from_u}",
            "to": f"{result:.2f} {to_u}",
            "formula": f"{value}°{f_.upper()} = {result:.2f}°{t_.upper()}",
        }

    rates = _UNIT_CONVERSIONS.get(category)
    if not rates:
        return {"error": f"不支持的换算类别: {category}"}

    if from_u not in rates or to_u not in rates:
        return {
            "error": "单位无法识别",
            "available": list(rates.keys()),
            "hint": f"从单位示例: {list(rates.keys())[:5]}",
        }

    base_value = value * rates[from_u]
    result = base_value / rates[to_u]

    # 智能精度
    if abs(result) >= 1000:
        result_str = f"{result:,.2f}"
    elif abs(result) < 0.001 and result != 0:
        result_str = f"{result:.6g}"
    else:
        result_str = f"{result:.6f}".rstrip('0').rstrip('.')

    return {
        "category": category,
        "from": f"{value} {from_u}",
        "to": f"{result_str} {to_u}",
        "formula": f"{value} {from_u} = {result_str} {to_u}",
    }


async def _compute_csv_analyzer(input_text: str, params: dict) -> dict:
    """CSV 数据分析（基础统计 + 类型推断）。"""
    import csv as _csv
    import io as _io

    depth = params.get("analysis_depth", "基础统计")
    lines = [l for l in input_text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        return {"error": "请输入至少包含表头的 CSV 数据（两行以上）"}

    reader = _csv.reader(_io.StringIO(input_text))
    headers = next(reader, [])
    if not headers:
        return {"error": "无法解析 CSV 表头"}
    rows = [row for row in reader if row and len(row) == len(headers)]

    if not rows:
        return {"error": "没有有效数据行"}

    # 类型推断
    col_types = {}
    for i, h in enumerate(headers):
        h = h.strip()
        nums = 0
        floats = 0
        total = 0
        for row in rows:
            v = row[i].strip()
            if not v:
                continue
            total += 1
            try:
                float(v)
                nums += 1
                if "." in v:
                    floats += 1
            except ValueError:
                pass
        if total > 0 and nums == total and floats > 0:
            col_types[h] = "float"
        elif total > 0 and nums == total:
            col_types[h] = "int"
        else:
            col_types[h] = "str"

    # 统计
    numeric_cols = {h: [] for h, t in col_types.items() if t in ("int", "float")}
    for row in rows:
        for i, h in enumerate(headers):
            h = h.strip()
            v = row[i].strip()
            if h in numeric_cols and v:
                try:
                    numeric_cols[h].append(float(v))
                except ValueError:
                    pass

    stats_lines = [f"📊 **数据概览**：{len(rows)} 行 × {len(headers)} 列"]
    for h in headers:
        h = h.strip()
        if col_types[h] in ("int", "float"):
            vals = numeric_cols[h]
            if vals:
                stats_lines.append(
                    f"  • `{h}`：均值 {sum(vals)/len(vals):.2f}，范围 [{min(vals):.2f} ~ {max(vals):.2f}]，共 {len(vals)} 个有效值"
                )
        else:
            unique = len(set(row[headers.index(h)].strip() for row in rows))
            stats_lines.append(f"  • `{h}`：{unique} 个唯一值，字符串类型")

    return {"summary": "\n".join(stats_lines), "column_types": col_types, "row_count": len(rows)}


def _compute_json_formatter(input_text: str, params: dict) -> dict:
    """JSON 格式化/校验。"""
    op = params.get("operation", "格式化")
    indent = 4 if params.get("indent") == "4" else (2 if params.get("indent") == "2" else 2)

    try:
        data = json.loads(input_text)
    except json.JSONDecodeError as e:
        return {"error": f"JSON 语法错误：{e}", "valid": False}

    if op == "校验":
        return {"valid": True, "type": type(data).__name__, "keys": list(data.keys()) if isinstance(data, dict) else f"array[{len(data)}]"}
    elif op == "压缩":
        compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return {"compact": compact, "savings": f"{(1 - len(compact)/max(len(input_text),1))*100:.1f}%"}
    else:
        formatted = json.dumps(data, ensure_ascii=False, indent=indent)
        return {"formatted": formatted, "original_size": len(input_text), "formatted_size": len(formatted)}


def _compute_regex_builder(input_text: str, params: dict) -> dict:
    """自然语言 → 正则表达式（规则引擎）。"""
    text = input_text.lower()
    patterns = []
    explanations = []

    rules = [
        ("邮箱", r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', "匹配标准邮箱格式"),
        ("手机号", r'^1[3-9]\d{9}$', "匹配中国大陆手机号"),
        ("身份证", r'^\d{17}[\dXx]$', "匹配18位身份证号"),
        ("网址", r'^https?://[^\s]+$', "匹配 HTTP/HTTPS 网址"),
        ("ipv4", r'^(\d{1,3}\.){3}\d{1,3}$', "匹配 IPv4 地址"),
        ("日期", r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', "匹配日期格式"),
        ("中文", r'[\u4e00-\u9fff]+', "匹配连续中文字符"),
        ("整数", r'^-?\d+$', "匹配整数（含负数）"),
        ("浮点", r'^-?\d+\.\d+$', "匹配浮点数"),
    ]
    for keyword, regex, desc in rules:
        if keyword in text:
            patterns.append(regex)
            explanations.append(desc)

    if not patterns:
        patterns.append(r'.*')
        explanations.append("通用匹配（未识别特定模式，可补充描述）")

    return {
        "patterns": [{"regex": p, "explanation": e} for p, e in zip(patterns, explanations)],
        "dialect": params.get("language", "Python/JavaScript"),
        "usage_tip": f"在 Python 中：re.match(r'{patterns[0]}', text)",
    }


def _compute_sql_generator(input_text: str, params: dict) -> dict:
    """自然语言 → SQL 模板。"""
    dialect = params.get("dialect", "PostgreSQL")
    text = input_text.lower()

    actions = []
    if any(k in text for k in ("查询", "查找", "select", "搜索")):
        actions.append("SELECT")
    if any(k in text for k in ("插入", "新增", "insert")):
        actions.append("INSERT")
    if any(k in text for k in ("更新", "修改", "update")):
        actions.append("UPDATE")
    if any(k in text for k in ("删除", "delete", "移除")):
        actions.append("DELETE")

    table_match = re.search(r'(从|表|table|来自)\s*(\w+)', text)
    table_name = table_match.group(2) if table_match else "your_table"

    sql = ""
    if "SELECT" in actions:
        sql = f"SELECT * FROM {table_name} WHERE /* 条件 */"
    elif "INSERT" in actions:
        sql = f"INSERT INTO {table_name} (col1, col2) VALUES (/* 值1 */, /* 值2 */)"
    elif "UPDATE" in actions:
        sql = f"UPDATE {table_name} SET col = /* 新值 */ WHERE /* 条件 */"
    elif "DELETE" in actions:
        sql = f"DELETE FROM {table_name} WHERE /* 条件 */"
    else:
        sql = f"-- 请描述具体操作，例如：\n-- '查询 {table_name} 表中所有数据'"

    return {
        "sql": sql,
        "dialect": dialect,
        "notes": "基于关键词模板生成，请根据实际表结构调整字段名与条件。",
    }


def _compute_date_calculator(input_text: str, params: dict) -> dict:
    """日期计算器。"""
    from datetime import datetime as _dt
    today = _dt.now().date()
    calc_type = params.get("calc_type", "日期加减")
    result = {"today": str(today), "calc_type": calc_type}

    def _parse_date(s: str):
        m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', s)
        if m:
            return _dt(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        return None

    if calc_type == "日期加减":
        base = _parse_date(input_text) or today
        m = re.search(r'([+-]?\d+)\s*(天|日|周|星期|月|年)', input_text)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit in ("周", "星期"):
                delta = timedelta(weeks=n)
            elif unit == "月":
                delta = timedelta(days=n * 30)
            elif unit == "年":
                delta = timedelta(days=n * 365)
            else:
                delta = timedelta(days=n)
            result["target"] = str(base + delta)
        else:
            result["target"] = "请指定天数和方向（如：2024-01-15 加 30 天）"
    elif calc_type == "年龄计算":
        birth = _parse_date(input_text)
        if birth:
            result["age"] = (today - birth).days // 365
            result["birth_date"] = str(birth)
        else:
            result["age"] = "请提供出生日期（YYYY-MM-DD）"
    elif calc_type == "时间差":
        dates = re.findall(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', input_text)
        if len(dates) >= 2:
            d1 = _dt(int(dates[0][0]), int(dates[0][1]), int(dates[0][2])).date()
            d2 = _dt(int(dates[1][0]), int(dates[1][1]), int(dates[1][2])).date()
            result["days_diff"] = abs((d2 - d1).days)
        else:
            result["days_diff"] = "请提供两个日期"
    elif calc_type == "工作日计算":
        m = re.search(r'(\d+)\s*个工作日', input_text)
        if m:
            n = int(m.group(1))
            current = today
            added = 0
            while added < n:
                current += timedelta(days=1)
                if current.weekday() < 5:
                    added += 1
            result["target_date"] = str(current)
        else:
            result["target_date"] = "格式：今天之后 N 个工作日"
    elif calc_type == "月份天数":
        m = re.search(r'(\d{4})[-/](\d{1,2})', input_text)
        if m:
            import calendar
            y, mo = int(m.group(1)), int(m.group(2))
            result["days"] = calendar.monthrange(y, mo)[1]
            result["month"] = f"{y}-{mo:02d}"
        else:
            result["days"] = "请指定年月（如：2024-02）"
    return result


def _compute_markdown_table(input_text: str, params: dict) -> dict:
    """Markdown 表格生成器。"""
    lines = [l.strip() for l in input_text.strip().split("\n") if l.strip()]
    if not lines:
        return {"error": "请输入表格数据"}

    rows = []
    for line in lines:
        if "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
        elif "\t" in line:
            cells = [c.strip() for c in line.split("\t")]
        else:
            cells = [c.strip() for c in line.split(",")]
        rows.append(cells)

    max_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < max_cols:
            r.append("")

    align = params.get("alignment", "左对齐")
    align_map = {"左对齐": ":---", "居中": ":---:", "右对齐": "---:"}
    separator = " | ".join(align_map.get(align, ":---") for _ in range(max_cols))
    header = " | ".join(rows[0][:max_cols])
    body = "\n".join(" | ".join(str(c)[:30] for c in r[:max_cols]) for r in rows[1:])
    table = f"| {header} |\n| {separator} |\n" + "\n".join(f"| {l} |" for l in body.split("\n") if l)

    return {"markdown_table": table, "rows": len(rows) - 1, "columns": max_cols}


def _compute_color_converter(input_text: str, params: dict) -> dict:
    """颜色格式转换（HEX ↔ RGB ↔ HSL）。"""
    text = input_text.strip().lstrip("#")
    inp_fmt = params.get("input_format", "HEX")

    try:
        if inp_fmt == "HEX":
            if len(text) == 6:
                r, g, b = int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
            elif len(text) == 3:
                r, g, b = int(text[0] * 2, 16), int(text[1] * 2, 16), int(text[2] * 2, 16)
            else:
                return {"error": "HEX 格式错误，支持 #RRGGBB 或 #RGB"}
        elif inp_fmt == "RGB":
            m = re.search(r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', text)
            if not m:
                return {"error": "RGB 格式错误，请使用 255, 128, 64 格式"}
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            return {"error": f"暂不支持 {inp_fmt} 输入，使用 HEX 或 RGB"}

        hex_val = f"#{r:02x}{g:02x}{b:02x}"
        r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
        c_max, c_min = max(r_n, g_n, b_n), min(r_n, g_n, b_n)
        delta = c_max - c_min
        l = (c_max + c_min) / 2.0
        if delta == 0:
            h = s = 0.0
        else:
            s = delta / (1 - abs(2 * l - 1))
            if c_max == r_n:
                h = ((g_n - b_n) / delta) % 6
            elif c_max == g_n:
                h = (b_n - r_n) / delta + 2
            else:
                h = (r_n - g_n) / delta + 4
            h = h * 60
            if h < 0:
                h += 360
        return {
            "hex": hex_val.upper(),
            "rgb": f"rgb({r}, {g}, {b})",
            "hsl": f"hsl({round(h, 1)}, {round(s * 100, 1)}%, {round(l * 100, 1)}%)",
            "brightness": "亮" if l > 0.5 else "暗",
        }
    except Exception as e:
        return {"error": f"转换失败：{e}"}


def _compute_diff_comparator(input_text: str, params: dict) -> dict:
    """文本差异对比。"""
    parts = input_text.split("---SEPARATOR---", 1)
    if len(parts) < 2:
        parts = input_text.split("\n---\n", 1)
    if len(parts) < 2:
        blank_idx = input_text.find("\n\n")
        if blank_idx > 0:
            parts = [input_text[:blank_idx], input_text[blank_idx + 2:]]
        else:
            lines = input_text.strip().split("\n")
            mid = len(lines) // 2
            parts = ["\n".join(lines[:mid]), "\n".join(lines[mid:])]

    text1, text2 = parts[0].strip(), parts[1].strip()
    diff = list(unified_diff(text1.splitlines(), text2.splitlines(), lineterm=""))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    return {
        "mode": params.get("comparison_mode", "逐行对比"),
        "added_lines": added,
        "removed_lines": removed,
        "diff_preview": "\n".join(diff[:30]) + ("\n...（更多差异已省略）" if len(diff) > 30 else ""),
    }


def _compute_password_generator(params: dict) -> dict:
    """密码生成器。"""
    import secrets
    length = int(params.get("length", 16))
    include_symbols = params.get("include_symbols", True)
    exclude_ambiguous = params.get("exclude_ambiguous", True)

    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    if include_symbols:
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?/"
    if exclude_ambiguous:
        for c in "0O1lI":
            chars = chars.replace(c, "")

    pwd_list = [
        secrets.choice("abcdefghijklmnopqrstuvwxyz"),
        secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        secrets.choice("0123456789"),
    ]
    if include_symbols:
        pwd_list.append(secrets.choice("!@#$%^&*()_+-="))
    while len(pwd_list) < length:
        pwd_list.append(secrets.choice(chars))

    for i in range(len(pwd_list) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        pwd_list[i], pwd_list[j] = pwd_list[j], pwd_list[i]

    password = "".join(pwd_list[:length])
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)
    score = sum([has_lower, has_upper, has_digit, has_symbol]) * 25
    if length >= 16:
        score += 10
    score = min(score, 100)

    return {
        "password": password,
        "length": length,
        "strength_score": score,
        "strength_label": "弱" if score < 50 else ("中" if score < 75 else "强"),
        "entropy_bits": round(length * 3.32, 1),
    }


def _compute_base64_tool(input_text: str, params: dict) -> dict:
    """Base64 编解码。"""
    op = params.get("operation", "编码")
    url_safe = params.get("url_safe", False)
    try:
        if op == "编码":
            raw = input_text.encode("utf-8")
            result = base64.urlsafe_b64encode(raw).decode("ascii") if url_safe else base64.b64encode(raw).decode("ascii")
            return {
                "operation": "编码",
                "input_length": len(input_text),
                "output": result,
                "output_length": len(result),
            }
        else:
            cleaned = input_text.replace("\n", "").replace(" ", "")
            result = base64.urlsafe_b64decode(cleaned).decode("utf-8", errors="replace") if url_safe else base64.b64decode(cleaned).decode("utf-8", errors="replace")
            return {"operation": "解码", "output": result, "output_length": len(result)}
    except Exception as e:
        return {"error": f"{op}失败：{e}"}



async def _run_tool_worker(payload: dict, progress: Callable | None = None) -> dict:
    """工具执行 worker：构建提示词 → LLM 生成 → 保存记录/统计（线程池执行，不阻塞事件循环）。

    v20 增强：支持 type=compute 实算工具（直接执行代码/计算，不消耗 LLM 额度）。
    """
    tool_id = payload.get("tool_id", "")
    tool = TOOL_DEFINITIONS.get(tool_id)
    if not tool:
        raise HTTPException(404, "工具不存在")
    if tool.get("type") == "app":
        raise HTTPException(400, "该工具需要使用专属页面")

    input_text = payload.get("input", "") or ""
    params = payload.get("params") or {}
    uid = payload.get("user_id") or "default"

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    # ── v20：实算工具分支（直接执行，不消耗 LLM）────────────────
    if tool.get("type") == "compute":
        return await _run_compute_tool(tool_id, input_text, params, _report)

    _report(10, "解析工具配置")

    # 合并默认参数和用户参数
    merged = {}
    for param_name, param_config in tool.get("params", {}).items():
        merged[param_name] = params.get(param_name, param_config.get("default", ""))

    # 渲染提示词（容错）：模板变量缺定义/未传参时不抛异常降级，
    # 缺失变量替换为空串（LLM 会据 input 推断），避免把 {xxx} 字面量喂给 LLM
    prompt_template = tool.get("prompt_template", tool.get("prompt", ""))
    try:
        prompt = prompt_template.format(input=input_text, **merged)
    except (KeyError, IndexError, ValueError):
        prompt = re.sub(r"\{(\w+)\}", lambda m: str(merged.get(m.group(1), "")), prompt_template)
        prompt = prompt.replace("{input}", input_text)

    _report(35, "构建提示词")
    # 注入真实当前日期：模板中的 [当前日期] 若不注入，LLM 会幻觉日期（实测出现 2024 年）
    system_prompt = (
        "你是一个专业的AI助手，请根据用户的要求生成高质量内容。输出格式要清晰、结构化的Markdown。\n"
        f"今天是 {datetime.now().strftime('%Y年%m月%d日')}（星期{'一二三四五六日'[datetime.now().weekday()]}）。"
    )
    _report(50, "AI 生成中")
    result = await call_llm_async(system_prompt, prompt, model=payload.get("model") or None)
    _report(85, "保存记录")

    # 保存记录
    conn = get_db()
    try:
        record_id = f"tool_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO tool_records (id, tool_id, input, result, model, created_at, user_id)
               VALUES (?,?,?,?,?,?,?) """,
            (
                record_id,
                tool_id,
                json.dumps({"input": input_text, "params": params}),
                result,
                payload.get("model") or "",
                datetime.now().isoformat(),
                uid,
            ),
        )
        # 更新使用统计
        stats_id = f"stat_{uuid.uuid4().hex[:12]}"
        existing_stat = conn.execute(
            "SELECT id, use_count FROM tool_usage_stats WHERE user_id=? AND tool_id=?", (uid, tool_id)
        ).fetchone()
        if existing_stat:
            conn.execute(
                "UPDATE tool_usage_stats SET use_count=use_count+1, last_used_at=? WHERE id=?",
                (datetime.now().isoformat(), existing_stat["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO tool_usage_stats (id, user_id, tool_id, use_count, last_used_at) VALUES (?,?,?,1,?)",
                (stats_id, uid, tool_id, datetime.now().isoformat()),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "id": record_id,
        "result": result,
        "metadata": {
            "tool_name": tool["name"],
            "params_used": merged,
        },
    }


async def _tool_run_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装工具执行，回报进度。"""
    return await _run_tool_worker(payload, progress=update)


@router.get("/api/tools/{tool_id}/history")
async def get_tool_history(tool_id: str, limit: int = 20, current_user: dict = require_auth()):
    """获取工具使用历史（仅当前用户）"""
    conn = get_db()
    try:
        uid = current_user.get("user_id") or "default"
        items = []
        for row in conn.execute(
            "SELECT * FROM tool_records WHERE tool_id=? AND user_id=? ORDER BY created_at DESC LIMIT ?",
            (tool_id, uid, limit),
        ).fetchall():
            item = dict(row)
            # 解析 input JSON
            try:
                input_data = json.loads(item.get("input", "{}"))
                item["input_text"] = input_data.get("input", "")
                item["params"] = input_data.get("params", {})
            except Exception:
                item["input_text"] = item.get("input", "")
                item["params"] = {}
            items.append(item)
        return items
    finally:
        conn.close()


@router.get("/api/records")
async def get_my_records(limit: int = 50, current_user: dict = require_auth()):
    """统一记录中心：工具使用记录 + 分享记录（仅当前用户）。"""
    conn = get_db()
    try:
        uid = current_user.get("user_id") or "default"
        tools = []
        for row in conn.execute(
            "SELECT * FROM tool_records WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (uid, min(limit, 100))
        ).fetchall():
            item = dict(row)
            item["tool_name"] = TOOL_DEFINITIONS.get(item.get("tool_id"), {}).get("name", item.get("tool_id"))
            try:
                input_data = json.loads(item.get("input", "{}"))
                item["input_text"] = input_data.get("input", "")
            except Exception:
                item["input_text"] = item.get("input", "")
            tools.append(item)
        shares = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM shares WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (uid,)
            ).fetchall()
        ]
        return {"tools": tools, "shares": shares}
    finally:
        conn.close()



def _extract_excel(tmp_path: str, filename: str) -> str:
    """Excel 内容提取为 Markdown 表格。"""
    NL = "\n"
    import openpyxl

    wb = openpyxl.load_workbook(tmp_path)
    sheets_data = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append([str(cell) if cell is not None else "" for cell in row])
        sheets_data.append({"name": sheet_name, "data": rows[:50]})
    out = "Excel 文件: " + filename + NL + "包含 " + str(len(wb.sheetnames)) + " 个工作表" + NL + NL
    for sheet in sheets_data:
        out += "## 工作表: " + sheet["name"] + NL + "行数: " + str(len(sheet["data"])) + NL
        if sheet["data"]:
            headers = sheet["data"][0]
            out += "| " + " | ".join(headers) + " |" + NL
            out += "| " + " | ".join(["---"] * len(headers)) + " |" + NL
            for row in sheet["data"][1:20]:
                out += "| " + " | ".join(row) + " |" + NL
        out += NL
    return out


def _extract_csv(tmp_path: str, filename: str) -> str:
    """CSV 内容提取为 Markdown 表格。"""
    NL = "\n"
    import csv

    with open(tmp_path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = list(reader)[:50]
    out = "CSV 文件: " + filename + NL + "总行数: " + str(len(rows)) + NL + NL
    if rows:
        headers = rows[0]
        out += "| " + " | ".join(headers) + " |" + NL
        out += "| " + " | ".join(["---"] * len(headers)) + " |" + NL
        for row in rows[1:30]:
            out += "| " + " | ".join(row) + " |" + NL
    return out


def _extract_pdf(tmp_path: str, filename: str) -> str:
    """PDF 内容提取（前10页）。"""
    NL = "\n"
    import PyPDF2

    with open(tmp_path, "rb") as fh:
        reader = PyPDF2.PdfReader(fh)
        out = "PDF 文件: " + filename + NL + "总页数: " + str(len(reader.pages)) + NL + NL
        for i, page in enumerate(reader.pages[:10]):
            text = page.extract_text()
            if text:
                out += "## 第 " + str(i + 1) + " 页" + NL + text + NL + NL
    return out


def _extract_text(tmp_path: str) -> str:
    """文本内容提取（限 50KB）。"""
    NL = "\n"
    with open(tmp_path, encoding="utf-8") as fh:
        content = fh.read()
    if len(content) > 50000:
        content = content[:50000] + NL + "...(内容已截断)"
    return content


def _extract_word(tmp_path: str, filename: str) -> str:
    """Word 内容提取（前100段）。"""
    NL = "\n"
    from docx import Document

    doc = Document(tmp_path)
    out = "Word 文档: " + filename + NL + NL
    for para in doc.paragraphs[:100]:
        if para.text.strip():
            out += para.text + NL
    return out


@router.post("/api/tools/upload")
async def upload_file(file: UploadFile = File(...), current_user: dict = require_auth()):  # noqa: C901
    """上传文件并提取内容"""
    import tempfile

    # 检查文件类型
    allowed_types = {
        ".xlsx": "excel",
        ".xls": "excel",
        ".csv": "csv",
        ".pdf": "pdf",
        ".txt": "text",
        ".md": "text",
        ".doc": "word",
        ".docx": "word",
    }

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_types:
        raise HTTPException(400, "操作失败，请稍后重试")

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        file_type = allowed_types[ext]
        extractors = {
            "excel": lambda: _extract_excel(tmp_path, file.filename),
            "csv": lambda: _extract_csv(tmp_path, file.filename),
            "pdf": lambda: _extract_pdf(tmp_path, file.filename),
            "text": lambda: _extract_text(tmp_path),
            "word": lambda: _extract_word(tmp_path, file.filename),
        }
        extracted_content = await asyncio.to_thread(extractors[file_type]) if file_type == "excel" else extractors[file_type]()
        return {"ok": True, "filename": file.filename, "content": extracted_content, "file_type": file_type}
    finally:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════


# 收藏与使用统计
# ══════════════════════════════════════════════════════════════


@router.get("/api/tools/favorites/list")
async def list_favorites(current_user: dict = require_auth()):
    """获取用户收藏的工具列表"""
    user_id = current_user.get("id", "default")
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT tool_id, created_at FROM tool_favorites WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        favorites = []
        for row in rows:
            tool_id = row["tool_id"]
            if tool_id in TOOL_DEFINITIONS:
                tool = TOOL_DEFINITIONS[tool_id]
                item = {
                    "id": tool_id,
                    "name": tool["name"],
                    "category": tool["category"],
                    "icon": tool["icon"],
                    "color": tool["color"],
                    "description": tool["description"],
                    "favorited_at": row["created_at"],
                }
                if tool.get("type") == "app":
                    item["type"] = "app"
                    item["path"] = tool["path"]
                else:
                    item["type"] = "tool"
                favorites.append(item)
        return favorites
    finally:
        conn.close()


@router.post("/api/tools/favorites/{tool_id}")
async def toggle_favorite(tool_id: str, current_user: dict = require_auth()):
    """切换工具收藏状态"""
    if tool_id not in TOOL_DEFINITIONS:
        raise HTTPException(404, "工具不存在")

    user_id = current_user.get("id", "default")
    fav_id = f"fav_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM tool_favorites WHERE user_id=? AND tool_id=?", (user_id, tool_id)
        ).fetchone()

        if existing:
            conn.execute("DELETE FROM tool_favorites WHERE id=?", (existing["id"],))
            conn.commit()
            return {"ok": True, "favorited": False}
        else:
            conn.execute("INSERT INTO tool_favorites (id, user_id, tool_id) VALUES (?,?,?)", (fav_id, user_id, tool_id))
            conn.commit()
            return {"ok": True, "favorited": True}
    finally:
        conn.close()


# ── 异步任务处理器注册 ──
register_handler("tool_run", _tool_run_handler, user_limit=2, max_attempts=1)

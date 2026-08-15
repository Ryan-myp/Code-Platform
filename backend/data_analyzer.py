#!/usr/bin/env python3
"""AI 数据分析沙箱 — 上传表格 → 自然语言提问 → LLM 生成 pandas 代码 → 受限执行 → 图表+结论。

安全模型与 /api/sandbox/execute 一致（common/sandbox_check.py）：
- LLM 生成的代码经过静态扫描（危险 token 黑名单 + import 白名单）
- 子进程受限执行（CPU/文件大小/fd 限制 + 超时 + 隔离工作目录）
- 代码只能读取沙箱内预置的 data.csv；图表由执行器自动收集，禁止代码内 open/网络
"""

import asyncio
import csv
import io
import re
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile

from common.auth import require_auth
from common.llm import call_llm_async, log_usage
from common.sandbox_check import MAX_CODE_LEN, check_sandbox_code, run_sandbox_python

router = APIRouter(tags=["AI 数据分析"])

# 数据文本上限：超过则截断（前端同步限制）
MAX_DATA_CHARS = 1_500_000
# 上传文件原始大小上限
MAX_FILE_BYTES = 8 * 1024 * 1024
# 转 CSV 时的最大行数
MAX_CSV_ROWS = 5000
# 预览给 LLM 的行数
PREVIEW_ROWS = 30

_CODE_BLOCK_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)

# v15：三段式结论解析（洞察/异常/建议）
_SECTION_RE = re.compile(r"\[(洞察|异常|建议)\]")
_SECTION_ORDER = ["insights", "anomalies", "suggestions"]
_SECTION_LABELS = {"洞察": "insights", "异常": "anomalies", "建议": "suggestions"}


def parse_conclusion(output: str) -> dict:
    """将沙箱输出解析为三段式结论（洞察/异常/建议）。

    规则：按行解析，仅行首的 [洞察]/[异常]/[建议] 标记切段；
    每段内去除编号前缀（1. 2.）与空行。无任何标记时整段视为洞察。
    """
    sections = {k: [] for k in _SECTION_ORDER}
    if not output:
        return sections
    current = "insights"
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SECTION_RE.match(line)
        if m:
            current = _SECTION_LABELS[m.group(1)]
            line = line[m.end():].strip()
        item = _strip_number(line)
        if item:
            sections[current].append(item)
    return sections


def _strip_number(line: str) -> str:
    """去除条目编号前缀：'1. xxx' / '1、xxx' → 'xxx'。"""
    import re as _re

    return _re.sub(r"^\s*\d+[.、．)]\s*", "", line)

_ANALYZER_SYSTEM_PROMPT = """你是资深数据分析师与 Python 工程师。用户会上传一个 CSV 表格（UTF-8，可能含中文表头）并提出数据分析问题。
请生成一段可直接执行的 Python 代码来回答用户的问题，代码必须遵守以下约束：

1. 数据读取：用 pandas 读取当前目录下的 data.csv：df = pd.read_csv('data.csv')。不要用 open() 读取任何文件。
2. 允许使用的库：pandas、numpy、matplotlib、json、math、statistics、collections、itertools、functools、re、datetime。禁止导入其他任何模块。
3. 图表：matplotlib 使用 Agg 后端，禁止 plt.show()。每张图保存为 chart1.png、chart2.png（plt.savefig('chart1.png')，dpi=100），最多 3 张。
4. 图表文字一律使用英文（服务器没有中文字体，中文会显示为方块）；图表标题、轴标签要清晰。
5. 文本结论：用 print() 输出中文结论。**结论必须按以下三段式结构输出**（每段用 [洞察]/[异常]/[建议] 标记开头，每条结论一行，用 1. 2. 3. 编号）：
   [洞察] 数据中最重要的事实、趋势与关键发现（含关键数字）
   [异常] 发现的异常值、突变、背离趋势的数据点（无异常则输出 [异常] 无显著异常）
   [建议] 基于数据的可执行业务建议（具体到动作与目标）
   示例：
   [洞察] 1. 华东区销售额 3.2 万居首，占总盘 28%
2. 2 月整体环比下滑 12%
[异常] 1. 3 月 6 日华南销量骤降至 8，仅为均值 1/4
[建议] 1. 对华南数码品类补货并加大促销
6. 绝对禁止的写法（会被沙箱直接拒绝）：open 函数、os 模块、subprocess、eval 与 exec 函数、import 非白名单模块、网络请求、文件删除。
7. 代码要健壮：先 df.head() 了解结构，处理缺失值与类型转换，避免除零。
8. 只输出代码本身，用 ```python 代码块包裹，不要输出任何解释文字。"""

# 分析深度 → 附加要求（专业基线：参数真实影响输出质量）
_DEPTH_REQUIREMENTS = {
    "quick": "快速分析：聚焦核心指标与最关键的 1-2 个发现，结论控制在 5 句以内，图表最多 1 张。",
    "standard": "标准分析：覆盖数据概览、关键指标、趋势/对比/占比维度，结论 8-12 句，图表最多 3 张。",
    "deep": "深度分析：多维度交叉（时间/分类/相关性）、异常值诊断、统计指标（均值/中位数/标准差）、可执行建议，结论 15 句以上，图表最多 4 张。",
}

# 图表风格 → 注入 matplotlib 样式
_CHART_STYLES = {
    "default": "",
    "dark": "plt.style.use('dark_background')\n",
    "business": "plt.rcParams.update({'figure.facecolor': 'white', 'axes.grid': True, 'grid.alpha': 0.3, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 11})\n",
}


def _extract_code(raw: str) -> str:
    """从 LLM 回复中提取 python 代码块（无代码块时整段视为代码）。"""
    m = _CODE_BLOCK_RE.search(raw or "")
    return (m.group(1) if m else (raw or "")).strip()


def _csv_info(text: str) -> dict:
    """解析 CSV 文本，返回列名/总行数/预览行（供 LLM 与前端使用）。"""
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except Exception:
        rows = []
    if not rows:
        return {"columns": [], "rows": 0, "preview": ""}
    columns = [c.strip() for c in rows[0] if c.strip()]
    total = max(len(rows) - 1, 0)
    preview_rows = rows[1 : PREVIEW_ROWS + 1]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(rows[0])
    writer.writerows(preview_rows)
    return {"columns": columns, "rows": total, "preview": buf.getvalue()}


def _bytes_to_csv(content: bytes) -> str:
    """文件字节转 CSV 文本（UTF-8/GBK 容错）。"""
    for enc in ("utf-8", "gbk"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


@router.post("/api/data-analyzer/upload")
async def data_analyzer_upload(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传表格文件（CSV/Excel），解析为 CSV 文本返回（前端预览与回传分析）。"""
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(400, "不支持的文件类型，仅支持CSV/Excel格式")

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(400, "文件过大（上限 8MB）")

    if ext == "csv":
        text = _bytes_to_csv(content)
    else:
        try:
            import openpyxl

            wb = await asyncio.to_thread(openpyxl.load_workbook, io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            out = io.StringIO()
            writer = csv.writer(out)
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= MAX_CSV_ROWS:
                    break
                writer.writerow(["" if c is None else c for c in row])
            text = out.getvalue()
        except Exception as e:
            raise HTTPException(400, "服务异常，请稍后重试") from e

    text = text[:MAX_DATA_CHARS]
    if not text.strip():
        raise HTTPException(400, "文件内容为空")

    info = _csv_info(text)
    if not info["columns"]:
        raise HTTPException(400, "无法识别表格结构（缺少表头？）")
    if info["rows"] < 1:
        raise HTTPException(400, "表格缺少数据行（至少需要表头 + 一行数据）")

    return {"csv": text, "filename": file.filename or "data.csv", **info}


def _validate_analyze_request(req: dict) -> tuple[str, str, dict]:
    """校验分析请求，返回 (question, data, csv_info)。非法时抛 400。"""
    question = (req.get("question") or "").strip()
    data = (req.get("data") or "").strip()
    if not question:
        raise HTTPException(400, "请描述你想分析的问题")
    if not data:
        raise HTTPException(400, "请先上传或粘贴数据（CSV 文本）")
    if len(question) > 2000:
        raise HTTPException(400, "问题过长（上限 2000 字）")
    if len(data) > MAX_DATA_CHARS:
        raise HTTPException(400, "数据过大（上限 1.5MB）")
    info = _csv_info(data)
    if not info["columns"]:
        raise HTTPException(400, "数据不是有效的 CSV（缺少表头？）")
    if info["rows"] < 1:
        raise HTTPException(400, "数据缺少数据行（至少需要表头 + 一行数据）")
    return question, data, info


@router.post("/api/data-analyzer/analyze")
async def data_analyzer_analyze(req: dict, current_user: dict = require_auth()):
    """AI 数据分析：自然语言提问 → LLM 生成 pandas 代码 → 沙箱执行 → 结论+图表。

    请求体：{question: str, data: CSV文本, filename?: str}
    """
    question, data, info = _validate_analyze_request(req)

    # 专业基线：分析深度 + 图表风格（真实影响生成质量）
    depth = (req.get("depth") or "standard").lower()
    if depth not in _DEPTH_REQUIREMENTS:
        depth = "standard"
    chart_style = (req.get("chart_style") or "default").lower()
    if chart_style not in _CHART_STYLES:
        chart_style = "default"
    depth_req = _DEPTH_REQUIREMENTS[depth]
    style_code = _CHART_STYLES[chart_style]

    # ── LLM 生成分析代码 ──
    user_prompt = (
        f"## 数据概览\n"
        f"- 文件名：{req.get('filename') or 'data.csv'}\n"
        f"- 列名：{', '.join(info['columns'])}\n"
        f"- 总行数（不含表头）：{info['rows']}\n\n"
        f"## 数据预览（前 {PREVIEW_ROWS} 行）\n"
        f"```\n{info['preview']}\n```\n\n"
        f"## 用户的问题\n{question}\n\n"
        f"## 分析要求\n{depth_req}\n"
    )
    start = datetime.now()
    raw_code = ""
    try:
        raw_code = await call_llm_async(
            _ANALYZER_SYSTEM_PROMPT, user_prompt, max_tokens=4000, temperature=0.2
        )
    except HTTPException as e:
        log_usage("data_analyzer", len(user_prompt), 0, 0.0, success=False)
        raise e

    code = _extract_code(raw_code)
    if not code:
        raise HTTPException(500, "模型未能生成分析代码，请重试")
    # 注入图表风格（Agg 后端已由沙箱强制）
    if style_code:
        code = style_code + "\n" + code
    if len(code) > MAX_CODE_LEN:
        raise HTTPException(500, "生成的代码过长，请简化问题后重试")

    # ── 安全检查 + 受限执行 ──
    blocked = check_sandbox_code(code)
    if blocked:
        log_usage("data_analyzer", len(user_prompt), len(code), 0.0, success=False)
        raise HTTPException(400, "代码未通过安全检查，请勿使用危险操作")

    result = run_sandbox_python(code, extra_files={"data.csv": data})
    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("data_analyzer", len(user_prompt), len(code), elapsed)

    charts = [{"name": k, "data": v} for k, v in result["files"].items()]
    return {
        "conclusion": result["output"],
        "conclusion_sections": parse_conclusion(result["output"]),
        "overview": {"columns": info["columns"], "rows": info["rows"]},
        "error": result["error"],
        "charts": charts,
        "code": code,
        "duration": result["duration"],
    }

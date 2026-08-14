#!/usr/bin/env python3
from common.helpers import _aggregate_compute_results, _execute_common_step, _execute_compute_step, _execute_single_step, _execute_step, _finalize_common_operation, _finalize_results, _finalize_step_results, _initialize_compute_context, _prepare_common_context, _prepare_context, _prepare_step_context


async def _create_dh_simple(dh_params: dict) -> dict:
    """简化版数字人视频创建。"""
    return {"status": "success", "video_url": dh_params.get("output_path", "")}

async def _prepare_dh_params_simple(request_data: dict) -> dict:
    """简化版准备数字人参数。"""
    return {
        "image_path": request_data.get("image", ""),
        "audio_path": request_data.get("audio", ""),
        "output_path": request_data.get("output_path", "")
    }


from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping, Iterable, Awaitable, Coroutine, Type
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import asyncio
from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
"""数字人按量计费 API 网关 — 对外开发者计费入口（Phase 5.1 商业化预留，最小实现）。

复用 openai_gateway 的 API Key 认证模式（api_keys 表 + Bearer xt-xxx）：
- POST /v1/dh/videos            按条计费生成数字人视频（异步任务，返回 task_id）
- GET  /v1/dh/videos/{task_id}  查询任务状态与账单（任务失败自动惰性退费）
- GET  /v1/dh/pricing           计费规则 + 我的余额
- POST /api/dh/billing/recharge 管理员充值（内部验证用，测试账号开通余额）

计费规则：
- config 表 key='dh_pricing' 存 JSON，未配置时用 DH_PRICING_DEFAULT：
  2D 基础 0.5 元/条、照片数字人 2 元/条、声音克隆 10 元/个（参考价）、1080p 加价 1 元
- 扣费走 users.balance 余额（充值由订单体系人工审核后管理员划拨，预留支付闭环）
- 免费/付费分层（5.2）：免费用户（membership=free 且非 admin）经网关强制
  2D 引擎 + 720p + 水印（水印由内部 membership 策略自动叠加），付费用户高清无水印
"""

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from common.auth import _auth_by_api_key, get_quota_info, require_auth
from common.db import get_db_context
from task_queue import create_task, get_task

logger = logging.getLogger(__name__)
router = APIRouter(tags=["数字人计费API"])

# 计费规则默认值（config 表 dh_pricing 可覆盖；单位：元）
DH_PRICING_DEFAULT = {
    "2d": 0.5,  # 2D 基础引擎：元/条
    "live_portrait": 2.0,  # 照片数字人：元/条
    "voice_clone": 10.0,  # 声音克隆服务：元/个（参考价，页面购买）
    "hd_1080p_extra": 1.0,  # 1080p 高清加价：元/条
}


# ── 表结构 ──────────────────────────────────────────────────


def _ensure_billing_tables(conn) -> None:
    """账单表 + users.balance 余额列（幂等，首次调用建表）。"""
    try:
        conn.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0")
    except Exception:
        pass  # 已存在
    conn.execute(
        """CREATE TABLE IF NOT EXISTS dh_billing_records (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            api_key_id TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            engine TEXT DEFAULT '2d',
            resolution TEXT DEFAULT '720p',
            price REAL DEFAULT 0,
            balance_before REAL DEFAULT 0,
            balance_after REAL DEFAULT 0,
            status TEXT DEFAULT 'charged',   -- charged / refunded
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dh_billing_task ON dh_billing_records(task_id)")


# ── 计费规则 ──────────────────────────────────────────────────


def _get_pricing() -> dict:
    """读取计费规则（config 表 dh_pricing JSON，未配置用默认值）。"""
    try:
        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='dh_pricing'").fetchone()
        if row and row["value"]:
            val = json.loads(row["value"])
            if isinstance(val, dict):
                return val
    except Exception:  # noqa: BLE001 — 配置损坏回退默认
        logger.warning("dh_pricing 配置读取失败，使用默认计费规则")
    return dict(DH_PRICING_DEFAULT)


def _price_for(engine: str, resolution: str, pricing: dict | None = None) -> float:
    """按引擎 + 分辨率计算单条价格（1080p 加价）。"""
    pricing = pricing or _get_pricing()
    price = float(pricing.get(engine, pricing.get("2d", 0.5)))
    if resolution == "1080p":
        price += float(pricing.get("hd_1080p_extra", 1.0))
    return round(price, 2)


# ── 认证（复用 openai_gateway 的 OpenAI 风格错误） ─────────────────


def _auth(request: Request):
    """Bearer API Key 认证（OpenAI 兼容网关，与 openai_gateway 一致）。"""
    from common.helpers import _auth_bearer

    return _auth_bearer(request, _auth_by_api_key)


def _err(status: int, message: str, code: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": message, "code": code, **extra}})


def _charge(auth: dict, billing_id: str, price: float, task_id: str = "") -> float:
    """扣款 + 写账单（独立事务）。返回扣款后余额。"""
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        row = conn.execute("SELECT balance FROM users WHERE id=?", (auth["user_id"],)).fetchone()
        balance = float(row["balance"] or 0) if row else 0.0
        new_balance = round(balance - price, 2)
        conn.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, auth["user_id"]))
        conn.execute(
            """INSERT INTO dh_billing_records
               (id, user_id, api_key_id, task_id, engine, resolution, price,
                balance_before, balance_after, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                billing_id,
                auth["user_id"],
                auth.get("api_key_id", ""),
                task_id,
                "",
                "",
                price,
                balance,
                new_balance,
                "charged",
                datetime.now().isoformat(),
            ),
        )
    return new_balance


def _refund(billing_id: str) -> float | None:
    """账单退费（任务失败/创建失败）：余额回补 + 账单标记 refunded。返回回补后余额。"""
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        row = conn.execute(
            "SELECT * FROM dh_billing_records WHERE id=? AND status='charged'", (billing_id,)
        ).fetchone()
        if not row:
            return None
        urow = conn.execute("SELECT balance FROM users WHERE id=?", (row["user_id"],)).fetchone()
        balance = float(urow["balance"] or 0) if urow else 0.0
        new_balance = round(balance + float(row["price"] or 0), 2)
        conn.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, row["user_id"]))
        conn.execute("UPDATE dh_billing_records SET status='refunded' WHERE id=?", (billing_id,))
        logger.info("数字人计费退费: billing=%s user=%s +%.2f -> %.2f", billing_id, row["user_id"], row["price"], new_balance)
        return new_balance


def _lazy_refund_failed(task: dict, auth: dict) -> float | None:
    """惰性退费：任务终态失败且账单仍 charged → 自动退费（用户查询状态时结算）。"""
    if task.get("status") not in ("failed", "interrupted", "canceled"):
        return None
    task_id = task.get("id", "")
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        rows = conn.execute(
            "SELECT id FROM dh_billing_records WHERE task_id=? AND user_id=? AND status='charged'",
            (task_id, auth["user_id"]),
        ).fetchall()
    refunded = None
    for r in rows:
        refunded = _refund(r["id"])
    return refunded


# ── 对外接口 ──────────────────────────────────────────────────


async def _validate_dh_inputs(text: str, voice_id: str, face_id: str) -> bool:
    """验证数字人输入参数。"""
    if not text or len(text) < 1:
        return False
    if not voice_id:
        return False
    if not face_id:
        return False
    return True

def _prepare_dh_request(params: dict) -> dict:
    """准备数字人请求参数。"""
    return {
        "text": params.get("text", ""),
        "voice_id": params.get("voice_id", ""),
        "face_id": params.get("face_id", ""),
        "resolution": params.get("resolution", "720p")
    }

def _parse_dh_response(response: dict) -> dict:
    """解析数字人响应。"""
    return {
        "video_url": response.get("video_url", ""),
        "duration": response.get("duration", 0),
        "status": response.get("status", "failed")
    }




def _prepare_dh_video_context(dh_params):
    """准备数字人视频生成上下文。"""
    return {
        "params": dh_params,
        "status": "prepared"
    }

def _validate_dh_video_params(params):
    """验证数字人视频参数。"""
    required = ["image", "audio", "speaker"]
    return all(p in params for p in required)

def _execute_dh_video_generation(params):
    """执行数字人视频生成。"""
    return {
        "status": "generating",
        "task_id": params.get("task_id")
    }

def _finalize_dh_video_result(result):
    """汇总数字人视频生成结果。"""
    return {
        "video_url": result.get("video_url"),
        "duration": result.get("duration"),
        "status": "completed"
    }


def _create_dh_simple(dh_params: dict) -> dict:
    """简化版数字人视频创建。"""
    return {
        "status": "success",
        "video_url": dh_params.get("output_path", ""),
        "duration": dh_params.get("duration", 0)
    }

def _prepare_dh_params_simple(request_data: dict) -> dict:
    """简化版准备数字人参数。"""
    return {
        "image_path": request_data.get("image", ""),
        "audio_path": request_data.get("audio", ""),
        "speaker": request_data.get("speaker", ""),
        "output_path": request_data.get("output_path", ""),
        "duration": request_data.get("duration", 0)
    }



def _build_dh_request(body: dict) -> tuple:
    """构建 GenerateRequest，校验文案与行业模板白名单。返回 (req, err_response|None)。"""
    from digital_human import INDUSTRY_TEMPLATES, GenerateRequest

    text = str(body.get("text") or "").strip()
    if len(text) < 5:
        return None, _err(400, "文案至少 5 个字", "invalid_text")
    if len(text) > 10000:
        return None, _err(400, "文案最多 10000 字", "invalid_text")
    try:
        req = GenerateRequest(
            text=text,
            avatar_id=str(body.get("avatar_id") or "business-female"),
            voice_id=str(body.get("voice_id") or "zh-CN-XiaoxiaoNeural"),
            background_id=str(body.get("background_id") or "tech"),
            scene_id=str(body.get("scene_id") or "product"),
            template_id=str(body.get("template_id") or ""),
            speed=float(body.get("speed") or 1.0),
            resolution=str(body.get("resolution") or "720p"),
            fps=int(body.get("fps") or 15),
            watermark=bool(body.get("watermark")),
            engine=str(body.get("engine") or "2d"),
        )
    except ValueError as e:
        return None, _err(400, f"参数不合法: {e}", "invalid_params")
    if req.template_id and req.template_id not in {t["id"] for t in INDUSTRY_TEMPLATES}:
        return None, _err(400, f"未知行业模板: {req.template_id}", "invalid_template")
    return req, None

def _apply_free_tier_downgrade(req, auth: dict) -> tuple:
    """免费档降级：非 admin 免费 Key 的高级引擎/分辨率静默降级为 2D+720p。"""
    qi = get_quota_info(auth["user_id"]) or {}
    membership = qi.get("membership", "free")
    forced = []
    if membership == "free" and auth.get("role") != "admin":
        if req.engine != "2d":
            req = req.model_copy(update={"engine": "2d"})
            forced.append("engine=2d")
        if req.resolution != "720p":
            req = req.model_copy(update={"resolution": "720p"})
            forced.append("resolution=720p")
    return req, forced


def _check_and_charge(auth: dict, price: float, billing_id: str) -> float | None:
    """余额校验并扣款；余额不足返回 None，成功返回扣款后余额。"""
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        row = conn.execute("SELECT balance FROM users WHERE id=?", (auth["user_id"],)).fetchone()
        balance = float(row["balance"] or 0) if row else 0.0
        if balance < price:
            return None
    _charge(auth, billing_id, price)
    return balance - price


def _create_billing_task(req, auth: dict, billing_id: str, price: float) -> dict:
    """创建数字人生成任务并关联账单；失败自动退款。"""
    try:
        task = create_task(
            "dh_generate",
            req.model_dump(),
            username=auth["username"],
            user_id=auth["user_id"],
            role=auth.get("role", ""),
        )
    except HTTPException as e:
        _refund(billing_id)
        raise
    with get_db_context() as conn:
        conn.execute(
            "UPDATE dh_billing_records SET task_id=?, engine=?, resolution=? WHERE id=?",
            (task["id"], req.engine, req.resolution, billing_id),
        )
    return task

@router.post("/v1/dh/videos")
def create_dh_video(request: Request, body: dict):  # noqa: C901 — 校验/分层/计费多分支，逐段可读
    """按量计费生成数字人视频（OpenAI 风格计费 API）。

    请求体（OpenAI 网关兼容白名单，多余字段忽略）：
    - text: 口播文案（必填，5-10000 字）
    - avatar_id / voice_id / background_id / scene_id / template_id
    - speed (0.5-2.0) / resolution (720p|1080p) / fps (10-30)
    - engine: 2d | live_portrait
    - watermark: 是否强制加水印（默认按会员等级自动）
    返回 task_id，用 GET /v1/dh/videos/{task_id} 轮询结果。
    """
    auth = _auth(request)
    if isinstance(auth, JSONResponse):
        return auth

    from digital_human import GenerateRequest, _precheck_generate

    req, param_err = _build_dh_request(body)
    if param_err:
        return param_err

    # 免费/付费分层（5.2）：免费 Key 高级引擎静默降级为 2D+720p
    req, forced = _apply_free_tier_downgrade(req, auth)

    # 素材/内容/配额预检（不扣费；与内部生成接口同规则）
    try:
        _precheck_generate(req, auth["user_id"], auth["username"])
    except HTTPException as e:
        return _err(e.status_code, str(e.detail), "precheck_failed")

    price = _price_for(req.engine, req.resolution)

    # 余额校验与扣款（不足 402 不创建任务）
    billing_id = f"dhb_{uuid.uuid4().hex[:12]}"
    balance_after = _check_and_charge(auth, price, billing_id)
    if balance_after is None:
        with get_db_context() as conn:
            _ensure_billing_tables(conn)
            row = conn.execute("SELECT balance FROM users WHERE id=?", (auth["user_id"],)).fetchone()
            balance = float(row["balance"] or 0) if row else 0.0
        return _err(
            402,
            f"余额不足（本条需 {price:.2f} 元，当前余额 {balance:.2f} 元），请联系平台充值",
            "insufficient_balance",
            price=price,
            balance=balance,
        )
    try:
        task = _create_billing_task(req, auth, billing_id, price)
    except HTTPException as e:
        return _err(e.status_code, str(e.detail), "task_create_failed")
    return {
        "task_id": task["id"],
        "status": "pending",
        "price": price,
        "balance": round(balance_after, 2),
        "billing_id": billing_id,
        "engine": req.engine,
        "resolution": req.resolution,
        "forced": forced,
        "message": f"任务已提交，预计扣费 {price:.2f} 元" + (f"（免费档已强制 {'、'.join(forced)}）" if forced else ""),
    }


@router.get("/v1/dh/videos/{task_id}")
async def get_dh_video(task_id: str, request: Request):
    """查询计费生成任务状态（含账单）；任务失败时自动退费。"""
    auth = _auth(request)
    if isinstance(auth, JSONResponse):
        return auth
    task = get_task(task_id)
    if not task:
        return _err(404, "任务不存在", "task_not_found")
    if str(task.get("created_by") or "") != auth["username"] and auth.get("role") != "admin":
        return _err(403, "无权访问该任务", "forbidden")
    refunded = _lazy_refund_failed(task, auth)
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        rows = conn.execute(
            "SELECT * FROM dh_billing_records WHERE task_id=? AND user_id=?",
            (task_id, auth["user_id"]),
        ).fetchall()
        urow = conn.execute("SELECT balance FROM users WHERE id=?", (auth["user_id"],)).fetchone()
    return {
        "task_id": task_id,
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "stage": task.get("stage", ""),
        "result": task.get("result"),
        "error": task.get("error"),
        "billing": [
            {
                "billing_id": r["id"],
                "price": r["price"],
                "balance_before": r["balance_before"],
                "balance_after": r["balance_after"],
                "status": r["status"],
            }
            for r in rows
        ],
        "balance": round(float(urow["balance"] or 0), 2) if urow else 0.0,
        "refunded": refunded is not None,
    }


@router.get("/v1/dh/pricing")
async def get_dh_pricing(request: Request):
    """计费规则 + 我的余额（供开发者查询价格后再下单）。"""
    auth = _auth(request)
    if isinstance(auth, JSONResponse):
        return auth
    pricing = _get_pricing()
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        row = conn.execute("SELECT balance FROM users WHERE id=?", (auth["user_id"],)).fetchone()
    return {
        "pricing": pricing,
        "balance": round(float(row["balance"] or 0), 2) if row else 0.0,
        "currency": "CNY",
        "note": "免费用户经 API 强制 2D+720p+水印；付费用户可高清无水印",
    }


# ── 内部管理：充值 / 对账（管理员） ─────────────────────────────


class RechargeRequest(BaseModel):
    user_id: str = Field(..., description="目标用户ID")
    amount: float = Field(..., gt=0, le=100000, description="充值金额（元）")
    remark: str = Field("", max_length=200, description="备注（如订单号）")


@router.post("/api/dh/billing/recharge")
async def admin_recharge(req: RechargeRequest, current_user: dict = require_auth()):
    """管理员为指定用户充值余额（内部验证用；正式上线由订单审核自动划拨）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可执行充值操作")
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        row = conn.execute("SELECT balance FROM users WHERE id=?", (req.user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "操作失败，请稍后重试")
        new_balance = round(float(row["balance"] or 0) + req.amount, 2)
        conn.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, req.user_id))
    logger.info("数字人余额充值: user=%s +%.2f -> %.2f（%s）", req.user_id, req.amount, new_balance, req.remark)
    return {"user_id": req.user_id, "amount": req.amount, "balance": new_balance, "message": f"充值成功，当前余额 {new_balance:.2f} 元"}


@router.get("/api/dh/billing/records")
async def admin_billing_records(limit: int = 50, current_user: dict = require_auth()):
    """账单流水（管理员对账用）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可查看账单")
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        rows = conn.execute(
            "SELECT * FROM dh_billing_records ORDER BY created_at DESC LIMIT ?", (min(limit, 200),)
        ).fetchall()
    return {"total": len(rows), "records": [dict(r) for r in rows]}

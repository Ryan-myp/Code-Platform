#!/usr/bin/env python3
"""中转站接入管理 — 平台作为客户端接入外部中转站（One API / new-api / 自建网关）。

能力：
- 添加中转站（名称 / base_url / api_key），存储到 config 表 relay_servers
- 测试连接：GET {base}/models 验证可达
- 一键拉取中转站模型列表 → 批量导入到平台模型列表（自动带上 base_url / api_key）
- 列表 / 删除 / 测试

接入后平台所有 LLM 调用（chat_engine / prd_engine / image_factory 等）
可通过模型路由自动走中转站（模型配置的 base_url 指向中转站）。
"""

import json
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from common.db import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/relay", tags=["中转站接入"])

_CONFIG_KEY = "relay_servers"


# ── 数据模型 ──────────────────────────────────────────────
class RelayServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="中转站名称")
    base_url: str = Field(..., min_length=5, description="中转站地址（如 https://xxx/v1）")
    api_key: str = Field(..., min_length=5, description="中转站 API Key")
    note: str = Field("", max_length=200, description="备注")


# ── 存储 ──────────────────────────────────────────────────
def _load_relays() -> list[dict]:
    """读取中转站列表。"""
    try:
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT value FROM config WHERE key=?", (_CONFIG_KEY,)
            ).fetchone()
        if row and row["value"]:
            data = json.loads(row["value"])
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_relays(relays: list[dict]) -> None:
    """保存中转站列表。"""
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=?",
            (_CONFIG_KEY, json.dumps(relays, ensure_ascii=False), json.dumps(relays, ensure_ascii=False)),
        )


def _mask_key(key: str) -> str:
    """脱敏 API Key（仅显示前后 4 位）。"""
    if not key:
        return ""
    if len(key) <= 10:
        return key[:2] + "***"
    return key[:4] + "***" + key[-4:]


# ── API ───────────────────────────────────────────────────
@router.get("")
async def list_relay_servers():
    """中转站列表（Key 脱敏）。"""
    relays = _load_relays()
    return {"items": [dict(r, api_key=_mask_key(r.get("api_key", ""))) for r in relays]}


@router.post("")
async def add_relay_server(req: RelayServerCreate):
    """添加中转站（去重按 base_url）。"""
    base_url = req.base_url.rstrip("/")
    if not base_url.endswith("/v1") and "/v1/" not in base_url:
        base_url = base_url.rstrip("/") + "/v1"
    relays = _load_relays()
    if any(r.get("base_url") == base_url for r in relays):
        raise HTTPException(400, "该中转站地址已存在，请直接更新或删除后重试")
    relays.append(
        {
            "id": f"relay_{int(datetime.now().timestamp() * 1000)}",
            "name": req.name.strip(),
            "base_url": base_url,
            "api_key": req.api_key.strip(),
            "note": req.note.strip(),
            "created_at": datetime.now().isoformat(),
        }
    )
    _save_relays(relays)
    return {"ok": True, "message": f"中转站「{req.name}」已添加"}


@router.delete("/{relay_id}")
async def delete_relay_server(relay_id: str):
    """删除中转站。"""
    relays = _load_relays()
    remaining = [r for r in relays if r.get("id") != relay_id]
    if len(remaining) == len(relays):
        raise HTTPException(404, "中转站不存在")
    _save_relays(remaining)
    return {"ok": True, "message": "中转站已删除"}


@router.post("/{relay_id}/test")
async def test_relay_server(relay_id: str):
    """测试中转站连接：GET {base}/models。"""
    relay = next((r for r in _load_relays() if r.get("id") == relay_id), None)
    if not relay:
        raise HTTPException(404, "中转站不存在")
    ok, data, err = await _probe_relay(relay)
    if not ok:
        raise HTTPException(502, f"连接失败：{err}")
    return {"ok": True, "models": data, "count": len(data)}


@router.post("/{relay_id}/import-models")
async def import_relay_models(relay_id: str, keep_global: bool = Query(False, description="base_url 继承全局(留空)")):
    """拉取中转站模型并批量导入到平台模型列表。

    导入后模型列表自动带上中转站 base_url + api_key，平台 LLM 调用可直接路由到该中转站。
    """
    relay = next((r for r in _load_relays() if r.get("id") == relay_id), None)
    if not relay:
        raise HTTPException(404, "中转站不存在")
    ok, models, err = await _probe_relay(relay)
    if not ok:
        raise HTTPException(502, f"拉取模型失败：{err}")

    # 读取当前模型列表
    from prd_engine import _get_models, _save_models

    current = _get_models()
    existing = {m.get("name") for m in current}
    imported = []
    for m in models:
        name = m.get("id", "")
        if not name or name in existing:
            continue
        current.append(
            {
                "name": name,
                "note": f"来自中转站 {relay['name']}",
                "base_url": "" if keep_global else relay["base_url"],
                "api_key": relay["api_key"],
            }
        )
        imported.append(name)
    if imported:
        _save_models(current)
    return {"ok": True, "imported": imported, "count": len(imported), "total": len(models)}


async def _probe_relay(relay: dict) -> tuple:
    """探测中转站：GET {base}/models，返回 (ok, models, error)。"""
    base = (relay.get("base_url") or "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {relay.get('api_key')}"},
            )
            if resp.status_code != 200:
                return False, [], f"HTTP {resp.status_code}: {resp.text[:200]}"
            data = resp.json()
            models = data.get("data") if isinstance(data, dict) else data
            if not isinstance(models, list):
                return False, [], "响应格式异常（期望 models 列表）"
            # OpenAI 兼容：data 数组，每项含 id
            return True, [{"id": m.get("id")} for m in models if isinstance(m, dict) and m.get("id")], ""
    except Exception as e:
        return False, [], str(e)

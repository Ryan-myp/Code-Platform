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

from common.auth import get_user_relay_config, require_auth
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
async def delete_relay_server(relay_id: str, provider: str = "", current_user: dict = require_auth()):
    """删除中转站。"""
    # /me 是「用户自己的中转站 key」路由，须先于动态段匹配（避免被 {relay_id} 吞掉）
    if relay_id == "me":
        return await clear_my_relay(provider=provider, current_user=current_user)
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
    try:
        from prd_engine import _get_models, _save_models
    except ImportError:
        from common.config import get_model_list

        def _get_models():
            return get_model_list()

        def _save_models(models):
            with get_db_context() as conn:
                import json as _json
                conn.execute(
                    "INSERT INTO config (key, value) VALUES ('model_list',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=?",
                    (_json.dumps(models, ensure_ascii=False), _json.dumps(models, ensure_ascii=False)),
                )


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


# ══════════════════════════════════════════════════════════════
# 用户级中转站配置（模式 B：用户自带中转站 Key，平台卖 token 盈利）
# 路径与平台管理中转站区分：/api/relay/me（用户自己的 key）
# ══════════════════════════════════════════════════════════════


class UserRelayRequest(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=200, description="API Key")
    provider: str = Field("aixinghuo", description="供应商：aixinghuo(爱星火中转站) / agnes(AGNES官方)")
    # 注意：供应商 base 由平台写死（防用户指向其他服务商绕开计费），用户只能选供应商填 key


def _load_user_relay_keys(uid: str) -> dict:
    """读取用户各供应商 key 映射 {provider: api_key}。"""
    from common.db import get_db

    if not uid:
        return {}
    try:
        conn = get_db()
        try:
            row = conn.execute("SELECT relay_keys, relay_api_key, relay_provider FROM users WHERE id=?", (uid,)).fetchone()
        finally:
            conn.close()
        if not row:
            return {}
        keys = {}
        try:
            keys = json.loads(row["relay_keys"] or "{}") if row["relay_keys"] else {}
            if not isinstance(keys, dict):
                keys = {}
        except Exception:
            keys = {}
        # 兼容旧数据：单列 relay_api_key 未迁移时补进 relay_keys
        old_key = (row["relay_api_key"] or "").strip()
        if old_key and not any(keys.values()):
            keys[row["relay_provider"] or "aixinghuo"] = old_key
        return {k: (v or "").strip() for k, v in keys.items() if k and v}
    except Exception:
        return {}


def _save_user_relay_key(uid: str, provider: str, api_key: str, activate: bool = True) -> None:
    """保存某供应商 key（不覆盖其他供应商）；activate=True 时同时设为当前激活供应商。"""
    keys = _load_user_relay_keys(uid)
    keys[provider] = api_key
    with get_db_context() as conn:
        conn.execute(
            "UPDATE users SET relay_keys=?, relay_api_key=?, relay_provider=?, relay_api_base='' WHERE id=?",
            (
                json.dumps(keys, ensure_ascii=False),
                api_key if activate else (keys.get(_active_provider(uid)) or ""),
                provider if activate else _active_provider(uid),
                uid,
            ),
        )


def _active_provider(uid: str) -> str:
    from common.db import get_db

    try:
        conn = get_db()
        try:
            row = conn.execute("SELECT relay_provider FROM users WHERE id=?", (uid,)).fetchone()
        finally:
            conn.close()
        return (row["relay_provider"] or "aixinghuo") if row else "aixinghuo"
    except Exception:
        return "aixinghuo"


def _save_provider_models(provider: str, model_list: list) -> None:
    """模型列表按供应商分存（model_list:{provider}），并同步到当前 model_list。"""
    import os

    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=?",
            (
                f"model_list:{provider}",
                json.dumps(model_list, ensure_ascii=False),
                json.dumps(model_list, ensure_ascii=False),
            ),
        )
        # 激活供应商时把该供应商模型设为当前生效列表
        conn.execute(
            "INSERT INTO config (key, value) VALUES ('model_list',?) ON CONFLICT(key) DO UPDATE SET value=?",
            (
                json.dumps(model_list, ensure_ascii=False),
                json.dumps(model_list, ensure_ascii=False),
            ),
        )


@router.get("/me")
async def get_my_relay(current_user: dict = require_auth()):
    """读取当前用户的中转站配置（key 脱敏；各供应商独立状态）。"""
    uid = current_user.get("user_id", "")
    keys = _load_user_relay_keys(uid)
    from common.config import AGNES_API_BASE as _DEFAULT_BASE, RELAY_PROVIDERS

    provider = _active_provider(uid)
    _base = RELAY_PROVIDERS.get(provider, _DEFAULT_BASE)
    _register = "https://aixinghuo.net/" if provider == "aixinghuo" else "https://apihub.agnes-ai.cn/"
    return {
        "configured": bool(keys.get(provider)),
        "api_key_masked": _mask_key(keys.get(provider, "")) if keys.get(provider) else "",
        "api_base": _base,
        "default_base": _DEFAULT_BASE,
        "provider": provider,
        "providers": list(RELAY_PROVIDERS.keys()),
        "providers_status": {
            p: {
                "configured": bool(keys.get(p)),
                "api_key_masked": _mask_key(keys[p]) if keys.get(p) else "",
            }
            for p in RELAY_PROVIDERS
        },
        "register_url": _register,
    }


@router.put("/me")
async def update_my_relay(req: UserRelayRequest, current_user: dict = require_auth()):
    """保存用户中转站 key（先校验 key 有效，再拉取该供应商模型列表；多供应商并存互不覆盖）。"""
    uid = current_user.get("user_id", "")
    if not uid:
        raise HTTPException(401, "请先登录")

    api_key = req.api_key.strip()
    provider = (req.provider or "aixinghuo").strip().lower()
    # 供应商 base 平台写死（防用户指向其他服务商绕开计费）
    from common.config import RELAY_PROVIDERS

    if provider not in RELAY_PROVIDERS:
        raise HTTPException(400, "不支持的供应商，请选择 aixinghuo 或 agnes")
    _DEFAULT_BASE = RELAY_PROVIDERS[provider]

    ok, err = await _verify_user_key(api_key, _DEFAULT_BASE)
    if not ok:
        raise HTTPException(400, f"{provider} Key 校验失败：{err}（请确认 Key 正确且对应供应商）")

    # 拉取该供应商的模型列表并保存（按供应商分存，不污染另一供应商的模型）
    models_saved = 0
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_DEFAULT_BASE}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get("data") if isinstance(data, dict) else data
                if isinstance(raw, list):
                    model_list = [
                        {"name": m.get("id")} for m in raw if isinstance(m, dict) and m.get("id")
                    ]
                    if model_list:
                        _save_provider_models(provider, model_list)
                        models_saved = len(model_list)
    except Exception:
        pass

    # 保存 key：只更新该供应商的 key，同时设为当前激活供应商（旧供应商 key 保留）
    _save_user_relay_key(uid, provider, api_key, activate=True)
    return {
        "success": True,
        "message": f"{provider} Key 已保存并设为当前使用，AI 功能将使用你的 Key 计费",
        "api_key_masked": _mask_key(api_key),
        "api_base": _DEFAULT_BASE,
        "provider": provider,
        "models": models_saved,
        "model_hint": "模型列表已从中转站同步" if models_saved else "已保存 Key（模型列表同步失败，请重试或检查中转站）",
    }


@router.post("/me/activate")
async def activate_my_relay(provider: str = Query(...), current_user: dict = require_auth()):
    """切换当前使用的供应商（该供应商须已保存过 key；切换时同步该供应商模型列表）。"""
    uid = current_user.get("user_id", "")
    provider = (provider or "").strip().lower()
    from common.config import RELAY_PROVIDERS

    if provider not in RELAY_PROVIDERS:
        raise HTTPException(400, "不支持的供应商，请选择 aixinghuo 或 agnes")
    keys = _load_user_relay_keys(uid)
    api_key = keys.get(provider, "")
    if not api_key:
        raise HTTPException(400, f"尚未保存 {provider} 的 Key，请先填写保存")

    # 同步该供应商模型列表为当前生效
    try:
        from common.db import get_db

        conn = get_db()
        try:
            row = conn.execute("SELECT value FROM config WHERE key=?", (f"model_list:{provider}",)).fetchone()
        finally:
            conn.close()
        if row and row["value"]:
            with get_db_context() as conn:
                conn.execute(
                    "INSERT INTO config (key, value) VALUES ('model_list',?) ON CONFLICT(key) DO UPDATE SET value=?",
                    (row["value"], row["value"]),
                )
    except Exception:
        pass

    _save_user_relay_key(uid, provider, api_key, activate=True)
    return {
        "success": True,
        "message": f"已切换到 {provider}，AI 功能将使用该供应商的 Key 计费",
        "provider": provider,
    }


@router.post("/verify")
async def verify_user_relay_key(req: UserRelayRequest, current_user: dict = require_auth()):
    """校验中转站 Key 是否有效（不保存）。"""
    api_key = req.api_key.strip()
    provider = (req.provider or "aixinghuo").strip().lower()
    from common.config import RELAY_PROVIDERS

    if provider not in RELAY_PROVIDERS:
        raise HTTPException(400, "不支持的供应商，请选择 aixinghuo 或 agnes")
    _DEFAULT_BASE = RELAY_PROVIDERS[provider]

    ok, err = await _verify_user_key(api_key, _DEFAULT_BASE)
    if not ok:
        raise HTTPException(400, f"{provider} Key 校验失败：{err}")
    return {"success": True, "message": f"{provider} Key 有效，可以正常使用", "provider": provider}


async def clear_my_relay(provider: str = "", current_user: dict = require_auth()):
    """清除用户中转站配置：默认清当前激活供应商的 key；全部清空时删除模型列表。

    注意：路由由 DELETE /{relay_id} 转发（relay_id == 'me'），
    因 /{relay_id} 注册更早会吞掉 /me，故不在本函数上直接挂路由。
    """
    uid = current_user.get("user_id", "")
    keys = _load_user_relay_keys(uid)
    target = (provider or "").strip().lower() or _active_provider(uid)
    if target in keys:
        del keys[target]
    with get_db_context() as conn:
        conn.execute(
            "UPDATE users SET relay_keys=?, relay_api_key=?, relay_provider=? WHERE id=?",
            (
                json.dumps(keys, ensure_ascii=False),
                keys.get(_active_provider(uid), "") if keys else "",
                _active_provider(uid) if keys else "aixinghuo",
                uid,
            ),
        )
        if not keys:
            conn.execute("DELETE FROM config WHERE key='model_list'")
            conn.execute("DELETE FROM config WHERE key LIKE 'model_list:%'")
    return {
        "success": True,
        "message": f"已清除 {target} 的中转站配置" + ("与模型列表" if not keys else "") + "，可重新配置 Key 后使用 AI 功能",
    }


async def _verify_user_key(api_key: str, api_base: str) -> tuple:
    """校验用户中转站 Key：GET {base}/models 探针。"""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{api_base}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                return True, ""
            if resp.status_code == 401:
                return False, "Key 无效或已过期（401）"
            if resp.status_code == 403:
                return False, "Key 无权限（403）"
            return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:120]

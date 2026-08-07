#!/usr/bin/env python3
"""资源可见性控制（v9.3 商业版：内容权限 / 灰度发布）。

- 工具（tool）：tool_hub 中的每个效率工具
- 页面（page）：PPT 工厂 / Excel / 股票 / 图片工厂等独立模块

可见范围 visible_to：
- all    所有登录用户可见
- pro    仅 pro/vip 会员可见（免费用户看到但锁定，引导开通会员）
- vip    仅 vip 会员可见（其余用户看到但锁定）
- admin  仅管理员可见（其他用户完全看不到）
- hidden 全站下线（列表不展示，仅管理后台可见）
"""

from datetime import datetime

from common.db import get_db

# 可见范围取值（用于接口校验）
VISIBLE_TO_VALUES = ("all", "pro", "vip", "admin", "hidden")

# 页面注册表：前端 Sidebar / 路由守卫按 page_id 对齐
PAGES = [
    {"id": "image-factory", "path": "/image-factory", "label": "图片工厂"},
    {"id": "video-factory", "path": "/video-factory", "label": "视频工厂"},
    {"id": "music-factory", "path": "/music-factory", "label": "音乐工厂"},
    {"id": "copywriting", "path": "/copywriting", "label": "文案工厂"},
    {"id": "translation", "path": "/translation", "label": "翻译中心"},
    {"id": "ppt-factory", "path": "/ppt-factory", "label": "PPT 工厂"},
    {"id": "excel", "path": "/excel", "label": "Excel 助手"},
    {"id": "stock", "path": "/stock", "label": "股票分析"},
    {"id": "agents", "path": "/agents", "label": "Agent 列表"},
    {"id": "workflows", "path": "/workflows", "label": "Workflow 管理"},
    {"id": "sandbox", "path": "/sandbox", "label": "沙箱运行"},
    {"id": "plugins", "path": "/plugins", "label": "插件市场"},
    {"id": "chat", "path": "/chat", "label": "智能协作"},
    {"id": "publish", "path": "/publish", "label": "发布中心"},
    {"id": "miniapp", "path": "/miniapp", "label": "小程序工坊"},
    {"id": "games", "path": "/games", "label": "小游戏工坊"},
    {"id": "voice-dubbing", "path": "/voice-dubbing", "label": "配音工坊"},
    {"id": "meme", "path": "/meme", "label": "表情包工坊"},
    {"id": "digital-human", "path": "/digital-human", "label": "AI数字人"},
    {"id": "voice-chat", "path": "/voice-chat", "label": "AI语音对话"},
    {"id": "video-analyzer", "path": "/video-analyzer", "label": "AI视频理解"},
    {"id": "mindmap", "path": "/mindmap", "label": "AI思维导图"},
    {"id": "forecast", "path": "/forecast", "label": "AI数据预测"},
    {"id": "doc-qa", "path": "/doc-qa", "label": "AI文档问答"},
    {"id": "pdf-tools", "path": "/pdf-tools", "label": "PDF工具集"},
    {"id": "gallery", "path": "/gallery", "label": "作品广场"},
    {"id": "templates", "path": "/templates", "label": "模板市场"},
    {"id": "web-search", "path": "/web-search", "label": "联网搜索"},
    {"id": "batch-process", "path": "/batch-process", "label": "批量处理"},
    {"id": "code-interpreter", "path": "/code-interpreter", "label": "代码解释器"},
    {"id": "api-platform", "path": "/api-platform", "label": "API开放平台"},
    {"id": "usage-analytics", "path": "/usage-analytics", "label": "用量分析"},
    {"id": "scheduler", "path": "/scheduler", "label": "定时任务"},
    {"id": "growth", "path": "/growth", "label": "增长工坊"},
    {"id": "strategy", "path": "/strategy", "label": "内容策略"},
    {"id": "monitor", "path": "/monitor", "label": "竞品监控"},
    {"id": "favorites", "path": "/favorites", "label": "收藏中心"},
    {"id": "data-analyzer", "path": "/data-analyzer", "label": "数据分析沙箱"},
]

# 会员等级权重：免费 < 专业 < 至尊
_MEMBERSHIP_LEVEL = {"free": 0, "pro": 1, "vip": 2}
_REQUIRE_LEVEL = {"pro": 1, "vip": 2}


def get_visibility_map(resource_type: str) -> dict[str, str]:
    """返回 {resource_id: visible_to}，未配置的资源默认 all。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT resource_id, visible_to FROM resource_visibility WHERE resource_type=?",
            (resource_type,),
        ).fetchall()
        return {r["resource_id"]: r["visible_to"] for r in rows}
    finally:
        conn.close()


def load_user_ctx(current_user: dict) -> dict:
    """补齐用户上下文：{user_id, role, membership}。"""
    user_id = current_user.get("user_id")
    role = current_user.get("role") or "viewer"
    membership = "free"
    if role != "admin" and user_id:
        conn = get_db()
        try:
            row = conn.execute("SELECT membership, membership_expires FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                membership = row["membership"] or "free"
                # 会员过期视为免费
                exp = row["membership_expires"]
                if membership != "free" and exp and exp <= datetime.now().isoformat():
                    membership = "free"
        finally:
            conn.close()
    return {"user_id": user_id, "role": role, "membership": membership}


def access_status(user_ctx: dict, visible_to: str) -> dict:
    """计算可见状态：{visible, locked, requires}。

    - visible=False：列表不展示（hidden / admin 级且非 admin）
    - visible=True 且 locked=True：展示但不可用，requires 标注所需会员等级
    """
    visible_to = visible_to or "all"
    if visible_to == "hidden":
        # 全站下线：任何人（含 admin）列表不展示，仅管理后台可见
        return {"visible": False, "locked": False}
    if user_ctx["role"] == "admin":
        return {"visible": True, "locked": False}
    if visible_to in ("admin",):
        return {"visible": False, "locked": False}
    if visible_to == "all":
        return {"visible": True, "locked": False}
    # pro / vip：按会员等级判定
    require = _REQUIRE_LEVEL[visible_to]
    level = _MEMBERSHIP_LEVEL.get(user_ctx["membership"], 0)
    if level >= require:
        return {"visible": True, "locked": False}
    return {"visible": True, "locked": True, "requires": visible_to}


def can_access(user_ctx: dict, visible_to: str) -> bool:
    """是否允许实际使用（列表可见 + 未锁定）。"""
    st = access_status(user_ctx, visible_to)
    return st["visible"] and not st.get("locked", False)


def set_visibility(resource_type: str, resource_id: str, visible_to: str) -> None:
    """设置资源可见范围（upsert）。"""
    if visible_to not in VISIBLE_TO_VALUES:
        raise ValueError("无效的可见范围")
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO resource_visibility (resource_type, resource_id, visible_to, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(resource_type, resource_id)
               DO UPDATE SET visible_to=excluded.visible_to, updated_at=excluded.updated_at""",
            (resource_type, resource_id, visible_to, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_visibility(resource_type: str, known_ids: list[str]) -> list[dict]:
    """管理后台：返回所有资源 + 当前可见范围（含未配置的默认 all）。"""
    conf = get_visibility_map(resource_type)
    return [{"resource_id": rid, "visible_to": conf.get(rid, "all")} for rid in known_ids]

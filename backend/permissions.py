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
    {"id": "pipeline", "path": "/pipeline", "label": "口播短视频工厂"},
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
    {"id": "drama", "path": "/drama", "label": "短剧工厂"},
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
    {"id": "seo", "path": "/seo", "label": "SEO 分析"},
    {"id": "strategy", "path": "/strategy", "label": "内容策略"},
    {"id": "monitor", "path": "/monitor", "label": "竞品监控"},
    {"id": "favorites", "path": "/favorites", "label": "收藏中心"},
    {"id": "data-analyzer", "path": "/data-analyzer", "label": "数据分析沙箱"},
    # ── 门户系统新增页面 ──
    {"id": "board",         "path": "/board",           "label": "需求看板"},
    {"id": "workspace",     "path": "/workspace",        "label": "AI 工作台"},
    {"id": "projects",      "path": "/projects",         "label": "项目空间"},
    {"id": "artifacts",     "path": "/artifacts",        "label": "成果仓库"},
    {"id": "pipelines",     "path": "/pipelines",        "label": "CI/CD 流水线"},
    {"id": "teams",         "path": "/teams",            "label": "Team 管理"},
    {"id": "knowledge-bases","path": "/knowledge-bases", "label": "知识库"},
    {"id": "skills",        "path": "/skills",           "label": "Skills"},
    {"id": "mcp-servers",   "path": "/mcp-servers",      "label": "MCP Servers"},
    {"id": "tool-hub",      "path": "/tool-hub",         "label": "全部工具"},
    {"id": "tasks",         "path": "/tasks",            "label": "任务中心"},
    {"id": "records",       "path": "/records",          "label": "记录中心"},
    {"id": "notifications", "path": "/notifications",    "label": "通知中心"},
    {"id": "config",        "path": "/config",           "label": "模型配置"},
    {"id": "help",          "path": "/help",             "label": "使用帮助"},
    {'id': 'downloads', 'name': 'downloads', 'path': '/downloads', 'requires': 'all', 'locked': False}, 
    {'id': 'search', 'name': 'search', 'path': '/search', 'requires': 'all', 'locked': False}, 
    {'id': 'audit-log', 'name': 'audit-log', 'path': '/audit-log', 'requires': 'all', 'locked': False}, 
    {'id': 'creator-center', 'name': 'creator-center', 'path': '/creator-center', 'requires': 'all', 'locked': False}, 
    {'id': 'invite-history', 'name': 'invite-history', 'path': '/invite-history', 'requires': 'all', 'locked': False}, 
    {'id': 'usage-detail', 'name': 'usage-detail', 'path': '/usage-detail', 'requires': 'all', 'locked': False}, 
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


# 权限来源标注：用于管理端「角色-权限矩阵」可视化，说明每个资源对当前用户
# 的可见状态是由哪一层配置决定的（角色 > 会员等级 > 资源配置 > 默认公开）
SOURCE_ROLE = "role"  # 管理员角色：全量放行
SOURCE_MEMBERSHIP = "membership"  # 会员等级：pro/vip 权益或锁定提示
SOURCE_CONFIG = "config"  # 后台显式配置的可见范围
SOURCE_DEFAULT = "default"  # 未配置，默认公开
SOURCE_HIDDEN = "hidden"  # 全站下线 / admin 专属（配置所致）


def permission_source(user_ctx: dict, visible_to: str, configured: bool) -> str:
    """标注权限来源：判断可见状态由哪一层规则决定。"""
    visible_to = visible_to or "all"
    if user_ctx["role"] == "admin" and visible_to != "hidden":
        return SOURCE_ROLE
    if visible_to in ("hidden", "admin"):
        return SOURCE_HIDDEN
    if visible_to == "all":
        return SOURCE_CONFIG if configured else SOURCE_DEFAULT
    # pro / vip：无论是否解锁，来源都是会员等级
    return SOURCE_MEMBERSHIP


def build_permission_matrix(user_ctx: dict, resources: list[dict], vis_map: dict[str, str]) -> list[dict]:
    """权限矩阵：为每个资源计算可见状态 + 权限来源（管理端可视化/单测断言用）。

    - user_ctx: load_user_ctx 的产物 {user_id, role, membership}
    - resources: [{id, path/label...}]（PAGES 或 tool_hub 定义）
    - vis_map: get_visibility_map(resource_type) 的产物 {resource_id: visible_to}
    返回每项追加 visible_to / visible / locked / requires / source 字段。
    """
    result = []
    for r in resources:
        visible_to = vis_map.get(r["id"], "all")
        status = access_status(user_ctx, visible_to)
        result.append(
            {
                **r,
                "visible_to": visible_to,
                "visible": status["visible"],
                "locked": status.get("locked", False),
                "requires": status.get("requires", ""),
                "source": permission_source(user_ctx, visible_to, r["id"] in vis_map),
            }
        )
    return result


def matrix_summary(items: list[dict]) -> dict:
    """矩阵汇总：可见/锁定/不可见计数，供管理端概览。"""
    return {
        "total": len(items),
        "visible": sum(1 for i in items if i["visible"]),
        "locked": sum(1 for i in items if i.get("locked")),
        "hidden": sum(1 for i in items if not i["visible"]),
    }

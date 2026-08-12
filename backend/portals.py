#!/usr/bin/env python3
"""门户系统（v16.0）：按业务场景隔离导航与功能，支持多垂直方向并行。

- Portal = 业务门户，每个用户绑定一个 portal_type
- rdm      = 研发管理版（中小企业研发团队）
- media    = 自媒体创作版（内容创作者 / 电商）
- general  = 通用版（全部功能）

设计原则：
- 门户定义是静态配置（PORTAL_DEFS），运行时只从数据库读取可见性状态
- 数据库表 portals / portal_page_config 用于扩展和持久化自定义门户
- seed_portals() 保证幂等初始化，不会覆盖已有的自定义配置
- 前端通过 /api/portal/current 获取当前用户的完整导航树，Sidebar 直接渲染
"""

import json
import logging
from datetime import datetime

from common.db import get_db

from permissions import PAGES, load_user_ctx  # noqa: F401 (re-exported for convenience)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# 门户定义（静态配置）
# ══════════════════════════════════════════════════════════════

_PORTAL_PAGE_MAP: dict[str, list[str]] = {
    "rdm": [
        # 首页 & 任务
        "tasks", "records", "favorites", "notifications",
        # 研发工作台
        "board", "workspace", "projects", "artifacts", "sandbox", "pipelines",
        # 智能体
        "agents", "teams", "workflows", "knowledge-bases", "skills", "mcp-servers",
        # 协作 & 工具
        "chat", "help",
        # 系统
        "api-platform", "usage-analytics", "usage-detail", "usage-detail", "scheduler", "config",
    ],
    "media": [
        # 首页 & 任务
        "tasks", "records", "favorites", "notifications",
        # 创作工坊
        "image-factory", "video-factory", "drama", "music-factory",
        "copywriting", "translation", "ppt-factory", "meme",
        # 发布运营
        "publish", "strategy", "seo", "monitor", "growth",
        # AI 工具
        "digital-human", "voice-chat", "video-analyzer",
        "mindmap", "forecast", "doc-qa", "web-search",
        "code-interpreter",
        # 应用广场
        "games", "miniapp", "voice-dubbing",
        "gallery", "templates",
        # 效率工具
        "tool-hub", "excel", "data-analyzer", "pdf-tools",
        "batch-process", "stock",
        # 协作 & 系统
        "chat", "help", "api-platform", "usage-analytics",
    ],
    "general": [p["id"] for p in PAGES],
}

_PORTAL_NAV_GROUPS: dict[str, list[dict]] = {
    "rdm": [
        {
            "key": "rdm_workbench",
            "label": "研发工作台",
            "icon_key": "Code2",
            "color": "from-blue-500 to-indigo-600",
            "pages": ["board", "workspace", "projects", "artifacts", "sandbox", "pipelines"],
        },
        {
            "key": "rdm_agents",
            "label": "智能体",
            "icon_key": "Bot",
            "color": "from-emerald-500 to-teal-600",
            "pages": ["agents", "teams", "workflows", "knowledge-bases", "skills", "mcp-servers"],
        },
        {
            "key": "rdm_tools",
            "label": "开发工具",
            "icon_key": "Wrench",
            "color": "from-orange-500 to-red-600",
            "pages": ["code-interpreter", "doc-qa", "web-search", "data-analyzer", "excel", "pdf-tools", "batch-process"],
        },
        {
            "key": "rdm_collab",
            "label": "协作与任务",
            "icon_key": "MessageSquare",
            "color": "from-violet-500 to-purple-600",
            "pages": ["chat", "tasks", "records", "favorites", "notifications"],
        },
        {
            "key": "rdm_system",
            "label": "系统",
            "icon_key": "Settings",
            "color": "from-amber-500 to-orange-600",
            "pages": ["api-platform", "usage-analytics", "scheduler", "config", "help"],
        },
    ],
    "media": [
        {
            "key": "media_create",
            "label": "创作工坊",
            "icon_key": "Wand2",
            "color": "from-accent-500 to-blue-600",
            "pages": [
                "image-factory", "video-factory", "drama", "music-factory",
                "copywriting", "translation", "ppt-factory", "meme",
            ],
        },
        {
            "key": "media_publish",
            "label": "发布运营",
            "icon_key": "Send",
            "color": "from-rose-500 to-pink-600",
            "pages": ["publish", "strategy", "seo", "monitor", "growth", "gallery", "templates"],
        },
        {
            "key": "media_ai",
            "label": "AI 工具",
            "icon_key": "Brain",
            "color": "from-teal-500 to-cyan-600",
            "pages": [
                "digital-human", "voice-chat", "video-analyzer",
                "mindmap", "forecast", "doc-qa", "web-search", "code-interpreter",
            ],
        },
        {
            "key": "media_apps",
            "label": "应用工坊",
            "icon_key": "Gamepad2",
            "color": "from-rose-500 to-pink-600",
            "pages": ["games", "miniapp", "voice-dubbing"],
        },
        {
            "key": "media_office",
            "label": "效率工具",
            "icon_key": "Wrench",
            "color": "from-orange-500 to-red-600",
            "pages": ["tool-hub", "excel", "data-analyzer", "stock", "pdf-tools", "batch-process"],
        },
        {
            "key": "media_collab",
            "label": "协作与任务",
            "icon_key": "MessageSquare",
            "color": "from-violet-500 to-purple-600",
            "pages": ["chat", "tasks", "records", "favorites", "notifications", "help"],
        },
        {
            "key": "media_system",
            "label": "系统",
            "icon_key": "Settings",
            "color": "from-amber-500 to-orange-600",
            "pages": ["api-platform", "usage-analytics"],
        },
    ],
    "general": [],  # 通用版沿用前端硬编码导航，此处为空表示不强制
}

# 兼容旧格式：Sidebar.jsx 渲染时把 nav_groups 里的 pages 映射为 items
# 这里做统一转换，让前端不必关心内部结构差异
def _normalize_nav_groups(raw_groups: list[dict]) -> list[dict]:
    """将后端 nav_groups 转换为 Sidebar 期望格式（pages → items）。"""
    from permissions import PAGES
    page_meta = {p["id"]: p for p in PAGES}
    result = []
    for grp in raw_groups:
        items = []
        for page_id in grp.get("pages", []):
            meta = page_meta.get(page_id, {})
            items.append({
                "path": meta.get("path", f"/{page_id}"),
                "label": meta.get("label", page_id),
                "pageId": page_id,
            })
        result.append({
            **grp,
            "items": items,
            "pages": None,  # 标记已转换
        })
    return result

# icon 名称 → lucide-react 导入名映射（由 Sidebar 负责动态解析）
ICON_MAP = {
    "Home": "Home",
    "Code2": "Code2",
    "Bot": "Bot",
    "Wrench": "Wrench",
    "MessageSquare": "MessageSquare",
    "Settings": "Settings",
    "Wand2": "Wand2",
    "Send": "Send",
    "Brain": "Brain",
    "Gamepad2": "Gamepad2",
    "CheckCircle2": "CheckCircle2",
    "HistoryIcon": "HistoryIcon",
    "Star": "Star",
    "Bell": "Bell",
    "Crown": "Crown",
    "ListTodo": "ListTodo",
    "Sparkles": "Sparkles",
    "FolderKanban": "FolderKanban",
    "FileText": "FileText",
    "Play": "Play",
    "GitBranch": "GitBranch",
    "Users": "Users",
    "Layers": "Layers",
    "Database": "Database",
    "BookOpen": "BookOpen",
    "Server": "Server",
    "ImageIcon": "ImageIcon",
    "Film": "Film",
    "Clapperboard": "Clapperboard",
    "Music": "Music",
    "PenTool": "PenTool",
    "Languages": "Languages",
    "Presentation": "Presentation",
    "Sticker": "Sticker",
    "UserCircle": "UserCircle",
    "Mic2": "Mic2",
    "Monitor": "Monitor",
    "Share2": "Share2",
    "TrendingUp": "TrendingUp",
    "Search": "Search",
    "Globe": "Globe",
    "Terminal": "Terminal",
    "Smartphone": "Smartphone",
    "Volume2": "Volume2",
    "Lightbulb": "Lightbulb",
    "Radar": "Radar",
    "Target": "Target",
    "GalleryVerticalEnd": "GalleryVerticalEnd",
    "Store": "Store",
    "Table2": "Table2",
    "BarChart3": "BarChart3",
    "Landmark": "Landmark",
    "FileSearch": "FileSearch",
    "Files": "Files",
    "FlaskConical": "FlaskConical",
    "Activity": "Activity",
    "HelpCircle": "HelpCircle",
    "Brain": "Brain",
    "Shield": "Shield",
    "Key": "Key",
    "Clock": "Clock",
    "Puzzle": "Puzzle",
}

PORTAL_DEFS: dict[str, dict] = {
    "rdm": {
        "id": "rdm",
        "name": "研发管理版",
        "description": "面向中小企业研发团队，覆盖需求→开发→测试→部署全流程",
        "nav_groups": _PORTAL_NAV_GROUPS["rdm"],
        "page_ids": _PORTAL_PAGE_MAP["rdm"],
        "highlight_tools": ["prd-engine", "sandbox", "workflows", "agents", "pipelines", "code-interpreter"],
    },
    "media": {
        "id": "media",
        "name": "自媒体创作版",
        "description": "面向自媒体/电商创作者，覆盖内容生产→发布→数据分析全链路",
        "nav_groups": _PORTAL_NAV_GROUPS["media"],
        "page_ids": _PORTAL_PAGE_MAP["media"],
        "highlight_tools": ["image-factory", "video-factory", "copywriting", "publish", "seo", "strategy"],
    },
    "general": {
        "id": "general",
        "name": "通用版",
        "description": "展示全部功能模块",
        "nav_groups": [],
        "page_ids": _PORTAL_PAGE_MAP["general"],
        "highlight_tools": [],
    },
}


# ══════════════════════════════════════════════════════════════
# 数据库操作
# ══════════════════════════════════════════════════════════════

def seed_portals() -> None:
    """幂等初始化门户数据（仅插入不存在的记录）。"""
    conn = get_db()
    try:
        now = datetime.now().isoformat()
        for pid, defn in PORTAL_DEFS.items():
            row = conn.execute("SELECT id FROM portals WHERE id=?", (pid,)).fetchone()
            if row:
                continue
            conn.execute(
                """INSERT INTO portals (id, name, description, nav_groups, highlight_tools, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    pid,
                    defn["name"],
                    defn["description"],
                    json.dumps(defn["nav_groups"], ensure_ascii=False),
                    json.dumps(defn["highlight_tools"], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            # 写入页面映射
            for page_id in defn["page_ids"]:
                conn.execute(
                    """INSERT OR IGNORE INTO portal_page_config (portal_id, page_id, enabled)
                       VALUES (?, ?, 1)""",
                    (pid, page_id),
                )
        conn.commit()
    finally:
        conn.close()


def get_portal(portal_type: str) -> dict | None:
    """从数据库加载门户配置（含动态页面启用状态）。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM portals WHERE id=?", (portal_type,)).fetchone()
        if not row:
            # 回退到静态定义
            return PORTAL_DEFS.get(portal_type)
        data = dict(row)
        data["nav_groups"] = json.loads(data["nav_groups"] or "[]")
        data["highlight_tools"] = json.loads(data["highlight_tools"] or "[]")
        # 加载实际启用的页面
        pages = conn.execute(
            "SELECT page_id FROM portal_page_config WHERE portal_id=? AND enabled=1",
            (portal_type,),
        ).fetchall()
        data["page_ids"] = [p["page_id"] for p in pages]
        return data
    finally:
        conn.close()


def get_all_portals() -> list[dict]:
    """获取所有门户列表（管理后台用）。"""
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, name, description FROM portals ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_portal_type(user_id: str) -> str:
    """读取用户绑定的门户类型，未设置时默认 general。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT portal_type FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return "general"
        pt = row["portal_type"] or "general"
        return pt if pt in PORTAL_DEFS else "general"
    finally:
        conn.close()


def set_user_portal_type(user_id: str, portal_type: str) -> None:
    """设置用户门户类型（INSERT OR REPLACE 确保不存在时也生效）。"""
    if portal_type not in PORTAL_DEFS:
        raise ValueError(f"无效的门户类型: {portal_type}")
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, membership, active, portal_type)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET portal_type=excluded.portal_type",
            (user_id, user_id, "__unused__", "user", "free", 1, portal_type),
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 导航构建（供前端使用）
# ══════════════════════════════════════════════════════════════

def build_portal_nav(portal_type: str, user_ctx: dict) -> list[dict]:
    """为指定门户构建前端导航树。

    nav_groups 中的 pages 字段是 page_id 字符串列表，不是对象列表。
    返回格式与 Sidebar.jsx 期望的结构一致（含 icon_key / color / items[].pageId）。
    如果门户没有自定义 nav_groups，则返回空列表（前端回退到硬编码导航）。
    """
    portal = get_portal(portal_type)
    if not portal or not portal.get("nav_groups"):
        return []

    # 加载该门户实际启用的页面
    conn = get_db()
    try:
        vis_rows = conn.execute(
            "SELECT page_id FROM portal_page_config WHERE portal_id=? AND enabled=1",
            (portal_type,),
        ).fetchall()
        visible_pages = {r["page_id"] for r in vis_rows}
    finally:
        conn.close()

    page_meta = {p["id"]: p for p in PAGES}

    nav_groups = []
    for grp in portal["nav_groups"]:
        items = []
        for page_id in grp.get("pages", []):
            if page_id not in visible_pages:
                continue
            meta = page_meta.get(page_id, {})
            items.append({
                "path": meta.get("path", f"/{page_id}"),
                "label": meta.get("label", page_id),
                "pageId": page_id,
            })
        if not items:
            continue
        nav_groups.append({
            "key": grp["key"],
            "label": grp["label"],
            "icon_key": grp.get("icon_key", "Brain"),
            "color": grp.get("color", "from-gray-500 to-gray-600"),
            "pages": items,  # 前端 Sidebar 用 pages 字段渲染
        })
    return nav_groups


def get_portal_nav_for_user(user_ctx: dict) -> dict:
    """获取当前用户的门户导航 + 高亮工具列表。

    返回的 nav_groups 已转换为 Sidebar 期望格式（每项含 items 数组）。
    """
    portal_type = get_user_portal_type(user_ctx.get("user_id", ""))
    portal = get_portal(portal_type) or PORTAL_DEFS.get(portal_type, {})
    raw_groups = portal.get("nav_groups", []) if portal else []
    # 转换为 Sidebar 期望的 items 格式
    nav_groups = _normalize_nav_groups(raw_groups) if raw_groups else []
    return {
        "portal_type": portal_type,
        "portal_name": portal.get("name", portal_type),
        "portal_description": portal.get("description", ""),
        "nav_groups": nav_groups,
        "highlight_tools": portal.get("highlight_tools", []),
        "has_custom_nav": bool(nav_groups),
    }

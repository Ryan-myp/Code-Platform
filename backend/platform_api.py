#!/usr/bin/env python3
"""Platform v9.0 API - 首页/任务/通知/仪表盘"""

import json
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import require_auth
from common.db import get_db

# v17-F：首页热接口短 TTL 缓存（30 秒），避免每次进入首页都全表 COUNT / 重复拉取最近列表
_HOME_CACHE_TTL = 30
_HOME_CACHE: dict[str, tuple[float, object]] = {}


def _home_cache_get(key: str) -> object | None:
    item = _HOME_CACHE.get(key)
    if item and time.time() - item[0] < _HOME_CACHE_TTL:
        return item[1]
    _HOME_CACHE.pop(key, None)
    return None


def _home_cache_set(key: str, value: object) -> None:
    _HOME_CACHE[key] = (time.time(), value)

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# Models
# ══════════════════════════════════════════════════════════════


class GlobalTaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "P2"
    due_date: str = ""
    tags: list = []
    project_id: str = ""
    agent_id: str = ""
    assigned_to: str = ""


class GlobalTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    tags: list | None = None
    assigned_to: str | None = None


class NotificationCreate(BaseModel):
    type: str = "info"
    title: str
    content: str = ""
    target_type: str = ""
    target_id: str = ""
    user_id: str = "all"


class DashboardWidgetUpdate(BaseModel):
    widget_type: str
    title: str = ""
    config: dict = {}
    position: int = 0
    size: str = "md"
    visible: bool = True


# ══════════════════════════════════════════════════════════════
# Home / Dashboard
# ══════════════════════════════════════════════════════════════


@router.get("/api/home/stats")
async def get_home_stats(current_user: dict = require_auth()):
    """获取首页统计数据"""
    cached = _home_cache_get("stats")
    if cached is not None:
        return cached
    conn = get_db()
    try:
        stats = {
            "agents": conn.execute("SELECT COUNT(*) FROM agents WHERE active=1").fetchone()[0],
            "workflows": conn.execute("SELECT COUNT(*) FROM workflows WHERE active=1").fetchone()[0],
            "projects": conn.execute("SELECT COUNT(*) FROM projects WHERE active=1").fetchone()[0],
            "tasks_total": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE active=1").fetchone()[0],
            "tasks_todo": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE status='todo' AND active=1").fetchone()[
                0
            ],
            "tasks_done": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE status='done' AND active=1").fetchone()[
                0
            ],
            "notifications_unread": conn.execute("SELECT COUNT(*) FROM notifications WHERE read=0").fetchone()[0],
            "artifacts": conn.execute("SELECT COUNT(*) FROM artifacts WHERE active=1").fetchone()[0],
        }
        _home_cache_set("stats", stats)
        return stats
    finally:
        conn.close()


@router.get("/api/home/recent")
async def get_home_recent(current_user: dict = require_auth()):
    """获取最近活动"""
    cached = _home_cache_get("recent")
    if cached is not None:
        return cached
    conn = get_db()
    try:
        # 最近的任务
        recent_tasks = []
        for row in conn.execute(
            "SELECT id, title, status, priority, due_date FROM global_tasks WHERE active=1 ORDER BY updated_at DESC LIMIT 5"
        ).fetchall():
            recent_tasks.append(dict(row))

        # 最近的项目
        recent_projects = []
        for row in conn.execute(
            "SELECT id, name, status, updated_at FROM projects WHERE active=1 ORDER BY updated_at DESC LIMIT 5"
        ).fetchall():
            recent_projects.append(dict(row))

        # 最近的通知
        recent_notifications = []
        for row in conn.execute(
            "SELECT id, type, title, content, created_at FROM notifications WHERE read=0 ORDER BY created_at DESC LIMIT 5"
        ).fetchall():
            recent_notifications.append(dict(row))

        # 最近的需求（AI 工作台流水线状态）
        recent_requirements = []
        for row in conn.execute(
            "SELECT id, name, status, priority, prd_text, review_report, tech_design, test_cases, code, code_review, pipeline_status, updated_at "
            "FROM requirements WHERE active=1 ORDER BY updated_at DESC LIMIT 5"
        ).fetchall():
            r = dict(row)
            try:
                r["pipeline_status"] = json.loads(r.get("pipeline_status") or "{}")
            except Exception:
                r["pipeline_status"] = {}
            recent_requirements.append(r)

        # 最近的流水线（部署状态）
        recent_pipelines = []
        for row in conn.execute("SELECT * FROM pipelines WHERE active=1 ORDER BY updated_at DESC LIMIT 5").fetchall():
            p = dict(row)
            try:
                p["config"] = json.loads(p.get("config") or "{}")
            except Exception:
                p["config"] = {}
            run = conn.execute(
                "SELECT status, started_at, finished_at FROM pipeline_runs WHERE pipeline_id=? ORDER BY started_at DESC LIMIT 1",
                (p["id"],),
            ).fetchone()
            p["last_run"] = dict(run) if run else None
            recent_pipelines.append(p)

        result = {
            "tasks": recent_tasks,
            "projects": recent_projects,
            "notifications": recent_notifications,
            "requirements": recent_requirements,
            "pipelines": recent_pipelines,
        }
        _home_cache_set("recent", result)
        return result
    finally:
        conn.close()


@router.get("/api/home/widgets")
async def get_dashboard_widgets(current_user: dict = require_auth()):
    """获取仪表盘组件"""
    conn = get_db()
    try:
        widgets = []
        for row in conn.execute(
            "SELECT * FROM dashboard_widgets WHERE user_id IN ('default', ?) AND visible=1 ORDER BY position",
            (current_user["username"],),
        ).fetchall():
            w = dict(row)
            w["config"] = json.loads(w.get("config", "{}"))
            widgets.append(w)

        # 如果没有组件，返回默认布局
        if not widgets:
            widgets = _get_default_widgets()
        return widgets
    finally:
        conn.close()


@router.put("/api/home/widgets/{widget_id}")
async def update_dashboard_widget(widget_id: str, data: DashboardWidgetUpdate, current_user: dict = require_auth()):
    """更新仪表盘组件"""
    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM dashboard_widgets WHERE id=?", (widget_id,)).fetchone()
        if not existing:
            # 创建新组件
            widget_id = f"widget_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO dashboard_widgets (id, user_id, widget_type, title, config, position, size, visible, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    widget_id,
                    current_user["username"],
                    data.widget_type,
                    data.title,
                    json.dumps(data.config),
                    data.position,
                    data.size,
                    int(data.visible),
                    datetime.now().isoformat(),
                ),
            )
        else:
            conn.execute(
                """UPDATE dashboard_widgets SET widget_type=?, title=?, config=?, position=?, size=?, visible=?, updated_at=?
                   WHERE id=?""",
                (
                    data.widget_type,
                    data.title,
                    json.dumps(data.config),
                    data.position,
                    data.size,
                    int(data.visible),
                    datetime.now().isoformat(),
                    widget_id,
                ),
            )
        conn.commit()
        return {"ok": True, "id": widget_id}
    finally:
        conn.close()


def _get_default_widgets():
    """默认仪表盘布局"""
    return [
        {"id": "stats", "widget_type": "stats", "title": "数据概览", "config": {}, "position": 0, "size": "lg"},
        {"id": "tasks", "widget_type": "tasks", "title": "待办任务", "config": {}, "position": 1, "size": "md"},
        {"id": "recent", "widget_type": "recent", "title": "最近活动", "config": {}, "position": 2, "size": "md"},
        {
            "id": "quick_actions",
            "widget_type": "quick_actions",
            "title": "快捷操作",
            "config": {},
            "position": 3,
            "size": "sm",
        },
    ]


# ══════════════════════════════════════════════════════════════
# Global Tasks
# ══════════════════════════════════════════════════════════════


@router.get("/api/tasks")
async def list_global_tasks(
    status: str | None = None,
    priority: str | None = None,
    project_id: str | None = None,
    current_user: dict = require_auth(),
):
    """获取全局任务列表"""
    conn = get_db()
    try:
        query = "SELECT * FROM global_tasks WHERE active=1"
        params = []
        if status:
            query += " AND status=?"
            params.append(status)
        if priority:
            query += " AND priority=?"
            params.append(priority)
        if project_id:
            query += " AND project_id=?"
            params.append(project_id)
        query += " ORDER BY priority, created_at DESC"

        tasks = []
        for row in conn.execute(query, params).fetchall():
            t = dict(row)
            t["tags"] = json.loads(t.get("tags", "[]"))
            tasks.append(t)
        return tasks
    finally:
        conn.close()


@router.post("/api/tasks")
async def create_global_task(data: GlobalTaskCreate, current_user: dict = require_auth()):
    """创建全局任务"""
    conn = get_db()
    try:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO global_tasks
               (id, title, description, status, priority, due_date, tags, project_id, agent_id,
                created_by, assigned_to, created_at, updated_at, active)
               VALUES (?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                task_id,
                data.title,
                data.description,
                data.priority,
                data.due_date,
                json.dumps(data.tags),
                data.project_id,
                data.agent_id,
                current_user["username"],
                data.assigned_to,
                now,
                now,
            ),
        )
        conn.commit()

        # 创建通知
        _create_notification(conn, "task", "新任务", f"任务「{data.title}」已创建", "global_task", task_id)

        return {"ok": True, "id": task_id}
    finally:
        conn.close()


@router.get("/api/tasks/{task_id}")
async def get_global_task(task_id: str, current_user: dict = require_auth()):
    """获取单个任务详情"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM global_tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "任务不存在")
        t = dict(row)
        t["tags"] = json.loads(t.get("tags", "[]"))
        return t
    finally:
        conn.close()


@router.put("/api/tasks/{task_id}")
async def update_global_task(task_id: str, data: GlobalTaskUpdate, current_user: dict = require_auth()):  # noqa: C901
    """更新全局任务"""
    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM global_tasks WHERE id=?", (task_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "任务不存在")

        updates = []
        params = []
        if data.title is not None:
            updates.append("title=?")
            params.append(data.title)
        if data.description is not None:
            updates.append("description=?")
            params.append(data.description)
        if data.status is not None:
            updates.append("status=?")
            params.append(data.status)
            if data.status == "done":
                updates.append("completed_at=?")
                params.append(datetime.now().isoformat())
        if data.priority is not None:
            updates.append("priority=?")
            params.append(data.priority)
        if data.due_date is not None:
            updates.append("due_date=?")
            params.append(data.due_date)
        if data.tags is not None:
            updates.append("tags=?")
            params.append(json.dumps(data.tags))
        if data.assigned_to is not None:
            updates.append("assigned_to=?")
            params.append(data.assigned_to)

        if updates:
            updates.append("updated_at=?")
            params.append(datetime.now().isoformat())
            params.append(task_id)
            conn.execute(f"UPDATE global_tasks SET {', '.join(updates)} WHERE id=?", params)
            conn.commit()

        return {"ok": True}
    finally:
        conn.close()


@router.delete("/api/tasks/{task_id}")
async def delete_global_task(task_id: str, current_user: dict = require_auth()):
    """删除全局任务"""
    conn = get_db()
    try:
        conn.execute("UPDATE global_tasks SET active=0 WHERE id=?", (task_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Notifications
# ══════════════════════════════════════════════════════════════


@router.get("/api/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = require_auth(),
):
    """获取通知列表（v15 分页：limit/offset + 总数）。

    返回 {"items": [...], "total": n}，供前端分页与未读角标展示。
    """
    conn = get_db()
    try:
        base = "FROM notifications WHERE user_id IN ('all', ?)"
        params = [current_user["username"]]
        if unread_only:
            base += " AND read=0"
        total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * {base} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, max(offset, 0)],
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": max(offset, 0)}
    finally:
        conn.close()


@router.get("/api/notifications/unread-count")
async def unread_notification_count(current_user: dict = require_auth()):
    """未读通知数（侧边栏/页面角标）。"""
    conn = get_db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN ('all', ?) AND read=0",
            (current_user["username"],),
        ).fetchone()[0]
        return {"count": count}
    finally:
        conn.close()


@router.post("/api/notifications")
async def create_notification(data: NotificationCreate, current_user: dict = require_auth()):
    """创建通知"""
    conn = get_db()
    try:
        notif_id = f"notif_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO notifications (id, type, title, content, target_type, target_id, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                notif_id,
                data.type,
                data.title,
                data.content,
                data.target_type,
                data.target_id,
                data.user_id,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return {"ok": True, "id": notif_id}
    finally:
        conn.close()


@router.put("/api/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, current_user: dict = require_auth()):
    """标记通知已读"""
    conn = get_db()
    try:
        conn.execute("UPDATE notifications SET read=1, read_at=? WHERE id=?", (datetime.now().isoformat(), notif_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.put("/api/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = require_auth()):
    """标记所有通知已读"""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE notifications SET read=1, read_at=? WHERE user_id IN ('all', ?) AND read=0",
            (datetime.now().isoformat(), current_user["username"]),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/api/notifications/{notif_id}")
async def delete_notification(notif_id: str, current_user: dict = require_auth()):
    """删除通知"""
    conn = get_db()
    try:
        conn.execute("DELETE FROM notifications WHERE id=?", (notif_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════


def _create_notification(
    conn, type: str, title: str, content: str, target_type: str = "", target_id: str = "", user_id: str = "all"
):
    """创建通知记录"""
    notif_id = f"notif_{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO notifications (id, type, title, content, target_type, target_id, user_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (notif_id, type, title, content, target_type, target_id, user_id, datetime.now().isoformat()),
    )
    conn.commit()

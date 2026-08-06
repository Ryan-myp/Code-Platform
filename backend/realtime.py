#!/usr/bin/env python3
"""WebSocket 实时通信管理器。

v8.0 新增：为对话执行、工作流运行提供实时进度推送，
替代前端轮询。

任务频道（async task）：
- task:{task_id}      — 单个任务进度推送（useAsyncTask 订阅，仅任务创建者/管理员可订阅）
- task:user:{username} — 用户任务列表变更广播（任务中心实时刷新，仅本人可订阅）
worker 线程通过 send_progress_threadsafe 投递到事件循环，
WebSocket 连接需携带 ?token=JWT 鉴权。
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from common.auth import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["实时通信"])

# 单条消息发送超时（秒）：慢客户端不阻塞频道内其他连接的广播
SEND_TIMEOUT = 3.0
# 客户端消息接收超时（秒）：僵尸连接（断网无 FIN）超时后关闭释放 fd
RECV_TIMEOUT = 60.0

# 事件循环引用：main.py lifespan 启动时调用 set_loop 注入，供 worker 线程投递广播
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """注入主事件循环（应用启动时调用）。"""
    global _loop
    _loop = loop


def send_progress_threadsafe(channel: str, event: str, data: dict | None = None) -> None:
    """线程安全进度推送：worker 线程调用，投递到事件循环执行广播。

    未注入事件循环（测试环境）时静默跳过。
    """
    if _loop is None or _loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(manager.send_progress(channel, event, data or {}), _loop)
    except (RuntimeError, Exception):  # noqa: BLE001 广播失败不影响任务主流程
        logger.debug("ws broadcast skipped: %s", channel)


class ConnectionManager:
    """管理 WebSocket 连接，支持按频道（channel）分组推送消息。

    频道设计：
    - chat:{agent_id}    — Agent 对话实时响应
    - workflow:{run_id}  — 工作流执行进度
    - session:{session_id} — 会话消息推送
    """

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = None  # asyncio.Lock 在首次使用时创建

    @property
    def lock(self):
        if self._lock is None:
            import asyncio

            self._lock = asyncio.Lock()
        return self._lock

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """接受 WebSocket 连接并加入指定频道。"""
        await websocket.accept()
        async with self.lock:
            self._connections[channel].append(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")

    async def disconnect(self, websocket: WebSocket, channel: str) -> None:
        """从频道中移除连接。"""
        async with self.lock:
            if channel in self._connections:
                try:
                    self._connections[channel].remove(websocket)
                except ValueError:
                    pass
                if not self._connections[channel]:
                    del self._connections[channel]
        logger.info(f"WebSocket disconnected from channel: {channel}")

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        """向频道内所有连接广播消息（并发发送 + 3s 超时，慢客户端不阻塞全局）。"""
        async with self.lock:
            connections = list(self._connections.get(channel, []))
        if not connections:
            return
        text = json.dumps(message, ensure_ascii=False, default=str)

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_text(text), timeout=SEND_TIMEOUT)
                return None
            except Exception:  # noqa: BLE001 断线/超时连接标记为 stale
                return ws

        results = await asyncio.gather(*(_send(ws) for ws in connections))
        # 清理已断开/超时的连接
        stale = [ws for ws in results if ws is not None]
        if stale:
            async with self.lock:
                for ws in stale:
                    try:
                        self._connections.get(channel, []).remove(ws)
                    except ValueError:
                        pass

    async def send_progress(
        self,
        channel: str,
        event: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """发送结构化进度消息。"""
        await self.broadcast(
            channel,
            {
                "event": event,
                "data": data or {},
                "timestamp": datetime.now().isoformat(),
            },
        )

    def get_connection_count(self, channel: str | None = None) -> int:
        """获取连接数（用于监控）。"""
        if channel:
            return len(self._connections.get(channel, []))
        return sum(len(conns) for conns in self._connections.values())


# 全局实例
manager = ConnectionManager()


async def _check_task_channel_access(channel: str, user: dict) -> tuple[int, str] | None:
    """任务频道归属校验：task:user:{username} 仅本人；task:{task_id} 仅创建者/管理员。

    返回 (code, reason) 表示拒绝；None 表示允许。
    """
    if not channel.startswith("task:"):
        return None
    if channel.startswith("task:user:"):
        sub_user = channel[len("task:user:") :]
        if sub_user != user.get("sub") and user.get("role") != "admin":
            return (4403, "forbidden")
        return None
    task_id = channel[len("task:") :]
    try:
        from common.db import get_db

        conn = get_db()
        try:
            row = conn.execute("SELECT created_by FROM async_tasks WHERE id=?", (task_id,)).fetchone()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 查询失败按无权限处理
        row = None
    if row is None:
        return (4404, "task not found")
    if row["created_by"] != user.get("sub") and user.get("role") != "admin":
        return (4403, "forbidden")
    return None


async def _heartbeat_loop(websocket: WebSocket) -> None:
    """心跳保活循环：60s 无消息视为僵尸连接（断网无 FIN）超时关闭释放 fd。"""
    while True:
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=RECV_TIMEOUT)
        except asyncio.TimeoutError:
            await websocket.close(code=4408, reason="heartbeat timeout")
            return
        # 心跳响应
        if data == "ping":
            await websocket.send_text("pong")


@router.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    """WebSocket 端点 — 客户端连接 /ws/{channel}?token=JWT 接收实时消息。

    频道命名约定：
    - chat:{agent_id}
    - workflow:{run_id}
    - session:{session_id}
    - task:{task_id} / task:user:{username}
    """
    # 鉴权：必须携带有效 JWT（query 参数，WebSocket 无法带 header）
    token = websocket.query_params.get("token", "")
    user = None
    if token:
        try:
            user = decode_access_token(token)
        except Exception:  # noqa: BLE001
            user = None
    if not user:
        await websocket.close(code=4401, reason="unauthorized")
        return
    # 任务频道归属校验：task:* 频道仅任务创建者/管理员可订阅（payload 含业务数据）
    deny = await _check_task_channel_access(channel, user)
    if deny:
        await websocket.close(code=deny[0], reason=deny[1])
        return
    await manager.connect(websocket, channel)
    try:
        await _heartbeat_loop(websocket)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, channel)
    except Exception as e:
        logger.warning(f"WebSocket error on channel {channel}: {e}")
        await manager.disconnect(websocket, channel)
    else:
        await manager.disconnect(websocket, channel)

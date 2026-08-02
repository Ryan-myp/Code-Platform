#!/usr/bin/env python3
"""WebSocket 实时通信管理器。

v8.0 新增：为对话执行、工作流运行提供实时进度推送，
替代前端轮询。
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["实时通信"])


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
        """向频道内所有连接广播消息。"""
        async with self.lock:
            connections = list(self._connections.get(channel, []))
        text = json.dumps(message, ensure_ascii=False, default=str)
        stale = []
        for ws in connections:
            try:
                await ws.send_text(text)
            except Exception:
                stale.append(ws)
        # 清理已断开的连接
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
        await self.broadcast(channel, {
            "event": event,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        })

    def get_connection_count(self, channel: str | None = None) -> int:
        """获取连接数（用于监控）。"""
        if channel:
            return len(self._connections.get(channel, []))
        return sum(len(conns) for conns in self._connections.values())


# 全局实例
manager = ConnectionManager()


@router.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    """WebSocket 端点 — 客户端连接 /ws/{channel} 接收实时消息。

    频道命名约定：
    - chat:{agent_id}
    - workflow:{run_id}
    - session:{session_id}
    """
    await manager.connect(websocket, channel)
    try:
        while True:
            # 保持连接，接收客户端心跳
            data = await websocket.receive_text()
            # 心跳响应
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket, channel)
    except Exception as e:
        logger.warning(f"WebSocket error on channel {channel}: {e}")
        await manager.disconnect(websocket, channel)

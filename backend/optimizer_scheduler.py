"""
企业级优化器调度器
每小时20分自动运行优化任务。
"""

import asyncio
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Callable

from loguru import logger

from enterprise_optimizer import run_enterprise_optimizer


class EnterpriseOptimizerScheduler:
    """每小时20分运行的企业级优化调度器。"""

    def __init__(self, callback: Callable = None):
        self.callback = callback or run_enterprise_optimizer
        self.running = False
        self._stop_event = asyncio.Event()

    def _next_run_time(self) -> datetime:
        """计算下次运行时间（每小时20分）。"""
        now = datetime.now()
        next_run = now.replace(minute=20, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(hours=1)
        return next_run

    def _seconds_until_next(self) -> int:
        """距离下次运行的秒数。"""
        next_run = self._next_run_time()
        return int((next_run - datetime.now()).total_seconds())

    async def _run_once(self):
        """执行一次优化任务。"""
        logger.info("⏰ 定时优化任务触发")
        try:
            result = self.callback()
            logger.info(f"✅ 优化任务完成: {result}")
        except Exception as e:
            logger.error(f"❌ 优化任务失败: {e}", exc_info=True)

    async def _run_loop(self):
        """主循环：等待到20分，运行，再等待。"""
        logger.info("🕐 企业级优化调度器启动，每小时20分运行")
        
        while not self._stop_event.is_set():
            sleep_seconds = self._seconds_until_next()
            logger.info(f"⏳ 下次运行: {_next_run_time_str()}, 等待 {sleep_seconds}s")
            
            # 等待到目标时间（最多3600秒，每小时检查一次）
            for _ in range(sleep_seconds):
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(1)
            
            if self._stop_event.is_set():
                break
            
            # 执行优化
            await self._run_once()
            
            # 短暂休眠后继续循环
            await asyncio.sleep(60)

    def start(self, background: bool = False):
        """启动调度器。"""
        self.running = True
        
        if background:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            task = loop.create_task(self._run_loop())
            
            def handle_stop(signum, frame):
                logger.info("收到停止信号，优雅关闭调度器...")
                self.stop()
                loop.stop()
            
            signal.signal(signal.SIGINT, handle_stop)
            signal.signal(signal.SIGTERM, handle_stop)
            
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                self.stop()
                loop.stop()
        else:
            # 同步模式（用于测试）
            asyncio.run(self._run_loop())

    def stop(self):
        """停止调度器。"""
        self.running = False
        self._stop_event.set()
        logger.info("企业级优化调度器已停止")


def _next_run_time_str() -> str:
    """格式化下次运行时间。"""
    now = datetime.now()
    next_run = now.replace(minute=20, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(hours=1)
    return next_run.strftime("%H:%M")


def run_once_now():
    """立即运行一次（用于测试）。"""
    return run_enterprise_optimizer()


if __name__ == "__main__":
    scheduler = EnterpriseOptimizerScheduler()
    
    if len(sys.argv) > 1 and sys.argv[1] == "now":
        # 立即运行一次
        logger.info("立即运行一次企业级优化...")
        result = run_once_now()
        logger.info(f"完成: {result}")
    else:
        # 后台守护模式
        scheduler.start(background=True)

"""公共辅助函数库 — 统一各模块重复的步骤/计算辅助函数。

这些函数曾在多个业务文件（extended_api / video_factory / miniapp /
short_drama / dh_gateway / image_factory / stock_tools / digital_human /
search_api 等）中重复定义，现统一收敛到此模块，各文件通过 import 复用。
"""

from __future__ import annotations

from typing import Any


# ── 步骤执行辅助（step 系列）──────────────────────────────
def _prepare_step_context(**kwargs: Any) -> dict:
    """准备步骤执行上下文。"""
    return {"context": kwargs, "status": "initialized", "data": {}}


def _execute_single_step(step_name: str, step_data: dict) -> dict:
    """执行单个处理步骤。"""
    return {"step": step_name, "status": "completed", "data": step_data}


def _finalize_step_results(results: list) -> dict:
    """汇总步骤执行结果。"""
    return {"total_steps": len(results), "results": results, "status": "completed"}


# ── 计算上下文辅助（compute 系列）─────────────────────────
def _initialize_compute_context(data: dict) -> dict:
    """初始化计算上下文。"""
    return {"data": data, "results": {}, "status": "running"}


def _execute_compute_step(step_name: str, step_data: dict) -> dict:
    """执行计算步骤。"""
    return {"step": step_name, "status": "completed", "data": step_data}


def _aggregate_compute_results(results: list) -> dict:
    """聚合计算结果。"""
    return {"total_steps": len(results), "aggregated": results}


# ── 通用上下文辅助（common 系列）──────────────────────────
def _prepare_common_context(**kwargs: Any) -> dict:
    """准备通用操作上下文。"""
    return {"context": kwargs, "status": "initialized", "data": {}}


def _execute_common_step(step_name: str, step_data: dict) -> dict:
    """执行通用操作步骤。"""
    return {"step": step_name, "status": "completed", "data": step_data}


def _finalize_common_operation(results: list) -> dict:
    """汇总通用操作结果。"""
    return {"total_steps": len(results), "results": results, "status": "completed"}


# ── 通用上下文辅助（context 系列）──────────────────────────
def _prepare_context(**kwargs: Any) -> dict:
    """准备处理上下文。"""
    return {"context": kwargs, "status": "initialized", "data": {}}


def _execute_step(step_name: str, step_data: dict) -> dict:
    """执行处理步骤。"""
    return {"step": step_name, "status": "completed", "data": step_data}


def _finalize_results(results: list) -> dict:
    """汇总处理结果。"""
    return {"total_steps": len(results), "results": results, "status": "completed"}


# ── 其他公共小工具 ────────────────────────────────────────
def ts() -> int:
    """当前时间戳（秒）。"""
    import time

    return int(time.time())


def _notify_progress(progress: Any, pct: float, stage: str) -> None:
    """安全回调进度（progress 可为 None），失败静默。"""
    if progress:
        try:
            progress(pct, stage)
        except Exception:
            pass


def _report(progress: Any, pct: float, stage: str) -> None:
    """安全回调进度（progress 可为 None）。"""
    _notify_progress(progress, pct, stage)

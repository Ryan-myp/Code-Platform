#!/usr/bin/env python3
"""发布就绪包基础设施（商业化发布 v14）。

- ``build_publish_zip``：统一 zip 打包（UTF-8 文件名、目录化组织）
- ``license_text``：AI 生成内容商用授权说明模板
- ``platform_spec_text``：平台规格说明模板（尺寸/格式/时长/审核要求）
- ``PublishProvider`` + ``publish_registry``：预留自动发布接口位
  （对接微信/网易云/抖音等平台开放 API 需企业资质，此处仅提供扩展点，
  实现类注册后即可在对应工厂触发真实发布）

各工厂（meme/music/image/video/game/miniapp）复用本模块产出"发布就绪包"。
"""

from __future__ import annotations

import io
import logging
import os
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- zip 打包

def build_publish_zip(entries: dict[str, str | bytes | os.PathLike], pack_name: str) -> io.BytesIO:
    """将 ``entries``（zip 内相对路径 → 文件内容或磁盘路径）打包为内存 zip。

    - 文本内容以 UTF-8 写入（文件名含中文，zip 头置 UTF-8 标志，主流系统可直接解压）
    - 路径自动归一化（去前导 ``/``），避免 zip 目录穿越
    - 返回 ``io.BytesIO``，调用方可直接用于 StreamingResponse
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in entries.items():
            safe = str(rel_path).lstrip("/\\").replace("\\", "/")
            # zip slip 防护：过滤 .. 与 . 路径段，防止解压逃逸出目标目录
            safe = "/".join(p for p in safe.split("/") if p and p not in (".", ".."))
            if not safe:
                continue
            if isinstance(content, os.PathLike):
                content = str(content)
            if isinstance(content, str) and "\n" in content:
                zf.writestr(safe, content.encode("utf-8"))
            elif isinstance(content, str):
                # 单行字符串且磁盘上存在 → 视为文件路径
                if os.path.isfile(content):
                    zf.write(content, safe)
                else:
                    zf.writestr(safe, content.encode("utf-8"))
            elif isinstance(content, bytes):
                zf.writestr(safe, content)
            else:
                zf.write(content, safe)
    return buf


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def pack_dir_name(prefix: str) -> str:
    """发布包顶层目录名，如 ``wechat_meme_pack_20260810_120000``。"""
    return f"{prefix}_{_stamp()}"


# ---------------------------------------------------------------- 授权说明

def license_text(product: str, generated_by: str = "AI 创作工坊") -> str:
    """AI 生成内容商用授权说明（随发布包附带的 LICENSE.txt）。"""
    return f"""{product} —— AI 生成内容商用授权说明
================================================

授权范围
--------
1. 本发布包内的全部生成内容（{product}及相关配套物料）由「{generated_by}」
   生成，生成成果的著作权归创作者（您）所有。
2. 您有权将生成内容用于商业用途，包括但不限于：上架售卖、平台发布、
   宣传推广、印刷制品、衍生再创作，无需另行支付生成费用。

使用限制
--------
1. 不得将生成内容用于违法、侵权、欺诈、色情等违反法律法规及公序良俗的场景。
2. 不得声称内容为人工原创并冒用他人身份发布。
3. 不得将本工具的生成能力（模型/接口）本身转售或二次封装对外提供。
4. 发布平台（微信、网易云、抖音、QQ 音乐等）可能有各自的审核规范，
   请遵守目标平台的《平台规则》与《内容规范》，因违反平台规则导致的
   下架、封禁等后果由创作者自行承担。

内容免责
--------
1. 生成内容中的文字、形象、音频等均由 AI 生成，若与任何现实人物、商标、
   版权作品存在相似之处，纯属巧合，请勿用于误导性宣传。
2. 若生成内容涉及第三方素材（字体、配乐等），已按开源/商业授权内置，
   如对商用范围有疑问，请以素材原始授权条款为准。

版本：v1.0（{datetime.now().strftime("%Y-%m-%d")}）
"""


# ---------------------------------------------------------------- 平台规格

def platform_spec_text(platform: str, specs: list[dict], notes: str = "") -> str:
    """平台规格说明（随发布包附带的 platform_spec.md）。

    ``specs``：``{"name": "主图", "value": "240×240 PNG ≤500KB", "desc": "..."}``
    """
    lines = [f"# {platform} 发布规格说明", ""]
    for s in specs:
        name = s.get("name", "")
        value = s.get("value", "")
        desc = s.get("desc", "")
        lines.append(f"## {name}")
        lines.append(f"- 规格：{value}")
        if desc:
            lines.append(f"- 说明：{desc}")
        lines.append("")
    if notes:
        lines.append("## 平台要求")
        lines.append(notes)
        lines.append("")
    lines.append(f"（由 AI 创作工坊生成，{datetime.now().strftime('%Y-%m-%d')}）")
    return "\n".join(lines)


# ---------------------------------------------------------------- 自动发布接口位

class PublishProvider(ABC):
    """自动发布 Provider 抽象基类（预留接口位）。

    对接真实平台开放 API（微信表情开放平台、网易云音乐人、抖音开放平台等）
    需要企业资质/AppKey/内容审核，当前仅定义扩展契约：

    - 实现 ``platform`` 与 ``publish``，在 ``publish_registry.register()`` 注册
    - 工厂在发布包生成后调用 ``publish_registry.publish(platform, payload)``
    - 未注册的 platform 静默跳过（只产出发布包，不阻塞主流程）
    """

    @property
    @abstractmethod
    def platform(self) -> str:
        """平台标识，如 ``wechat_meme`` / ``netease_music`` / ``douyin_video``。"""

    @abstractmethod
    def publish(self, payload: dict) -> dict:
        """执行自动发布；返回 ``{"published": bool, "message": str, "ref": str}``。"""


class _PublishRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, PublishProvider] = {}

    def register(self, provider: PublishProvider) -> None:
        self._providers[provider.platform] = provider
        logger.info("发布 Provider 已注册: %s", provider.platform)

    def providers(self) -> list[str]:
        return sorted(self._providers)

    def publish(self, platform: str, payload: dict) -> dict:
        provider = self._providers.get(platform)
        if provider is None:
            logger.info("平台 %s 未配置自动发布（仅产出发布包）", platform)
            return {"published": False, "message": f"平台 {platform} 未配置自动发布（需企业资质）", "ref": ""}
        try:
            return provider.publish(payload)
        except Exception as e:  # 自动发布失败不阻塞主流程
            logger.exception("自动发布失败: %s", platform)
            return {"published": False, "message": f"自动发布失败: {e}", "ref": ""}


# 全局注册表：各工厂可 import 后注册自定义 provider
publish_registry = _PublishRegistry()

#!/usr/bin/env python3
"""路由注册中心 — 集中管理所有 FastAPI Router 的注册。

主入口 main.py 只需调用 register_routers(app)，避免路由分散在入口文件底部。

分组规则：
  - core：核心业务（工厂、引擎、工作流）
  - content：内容创作（图片/视频/音乐/配音/表情包/短剧/数字人）
  - tools：效率工具（数据分析、SEO、股票、PDF、思维导图等）
  - commerce：商业化（支付、配额、分享、会员、API 计费、转化分析）
  - platform：平台能力（Agent、工作流、知识库、MCP、沙箱）
  - admin：管理与运维（后台、审计、备份、通知）
  - enterprise：企业服务（私有化部署、定制开发、报价管理）
"""

from fastapi import FastAPI

from ai_video_api import router as ai_video_router
from apikey_api import router as apikey_api_router
from batch_api import router as batch_api_router
from common.backup import router as backup_router
from chat_engine import router as chat_engine_router
from collab_engine import router as collab_engine_router
from competitor_monitor import router as competitor_monitor_router
from content_strategy import router as content_strategy_router
from data_forecast import router as data_forecast_router
from dh_gateway import router as dh_gateway_router
from digital_human import router as digital_human_router
from doc_qa import router as doc_qa_router
from drafts import router as drafts_router
from drama_templates import router as drama_templates_router
from extensions_agents import router as extensions_agents_router
from favorites_api import router as favorites_api_router
from feedback_api import router as feedback_router
from gallery import router as gallery_router
from game_factory import router as game_factory_router
from growth_engine import router as growth_engine_router
from image_factory import router as image_factory_router
from meme_factory import router as meme_factory_router
from meme_templates import router as meme_templates_router
from mindmap import router as mindmap_router
from mindmap_templates import router as mindmap_templates_router
from miniapp import router as miniapp_router
from music_factory import router as music_factory_router
from music_scene_templates import router as music_scene_templates_router
from notify_api import router as notify_api_router
from oauth_api import router as oauth_router
from openai_gateway import router as openai_gateway_router
from pdf_doc_templates import router as pdf_doc_templates_router
from pdf_tools import router as pdf_tools_router
from platform_api import router as platform_api_router
from prd_engine import router as prd_engine_router
from publishing import router as publishing_router
from realtime import router as realtime_router
from relay_api import router as relay_router
from scheduler import router as scheduler_router
from search_api import router as search_api_router
from seo_analyzer import router as seo_analyzer_router
from sessions import router as sessions_router
from short_drama import router as drama_router
from smart_dashboard import router as smart_dashboard_router
from stock_tools import router as stock_tools_router
from stripe_api import router as stripe_router
from task_queue import router as task_queue_router
from team_api import router as team_router
from template_store import router as template_store_router
from templates_market import router as templates_market_router
from video_analyzer import router as video_analyzer_router
from video_factory import router as video_factory_router
from video_templates import router as video_templates_router
from voice_chat import router as voice_chat_router
from voice_factory import router as voice_factory_router
from voice_templates import router as voice_templates_router
from web_search import router as web_search_router

# ── 新增商业化模块（v20）────────────────────────────────────────
from api_billing import router as api_billing_router, ensure_api_keys_tables  # noqa: E402
from conversion_analytics import router as analytics_router, ensure_analytics_tables  # noqa: E402
from enterprise_api import router as enterprise_router, ensure_enterprise_tables  # noqa: E402

# ── 企业级优化器（v18）────────────────────────────────────────
from optimizer_integration import router as optimizer_router, init_optimizer_system  # noqa: E402

# ── 管理后台（v9.1）──────────────────────────────────────────
from admin_api import router as admin_api_router  # noqa: E402

# ── 扩展 API（v9.0 Phase 2-4 + Office）──────────────────────
from extended_api import router as extended_api_router  # noqa: E402

# ── 效率工具箱（v9.0）────────────────────────────────────────
from tool_hub import router as tool_hub_router  # noqa: E402

# ── AI 数据分析沙箱（v9.0）───────────────────────────────────
from data_analyzer import router as data_analyzer_router  # noqa: E402


def register_routers(app: FastAPI) -> None:
    """按功能分组注册所有路由到 FastAPI 应用。"""

    # ══════════════════════════════════════════════════════════
    # core：核心业务引擎
    # ══════════════════════════════════════════════════════════
    app.include_router(prd_engine_router)
    app.include_router(chat_engine_router)
    app.include_router(sessions_router)
    app.include_router(task_queue_router)
    app.include_router(platform_api_router)
    app.include_router(extended_api_router)
    app.include_router(tool_hub_router)
    app.include_router(data_analyzer_router)
    app.include_router(stock_tools_router)
    app.include_router(growth_engine_router)
    app.include_router(content_strategy_router)
    app.include_router(smart_dashboard_router)

    # ══════════════════════════════════════════════════════════
    # content：内容创作工厂
    # ══════════════════════════════════════════════════════════
    app.include_router(ai_video_router)
    app.include_router(image_factory_router)
    app.include_router(video_factory_router)
    app.include_router(video_templates_router)
    app.include_router(video_analyzer_router)
    app.include_router(music_factory_router)
    app.include_router(voice_factory_router)
    app.include_router(voice_templates_router)
    app.include_router(voice_chat_router)
    app.include_router(meme_factory_router)
    app.include_router(meme_templates_router)
    app.include_router(digital_human_router)
    app.include_router(dh_gateway_router)
    app.include_router(drama_router)
    app.include_router(drama_templates_router)
    app.include_router(music_scene_templates_router)
    app.include_router(game_factory_router)
    app.include_router(miniapp_router)
    app.include_router(publishing_router)
    app.include_router(drafts_router)
    app.include_router(gallery_router)
    app.include_router(templates_market_router)
    app.include_router(template_store_router)

    # ══════════════════════════════════════════════════════════
    # tools：效率工具箱 & 数据分析
    # ══════════════════════════════════════════════════════════
    app.include_router(pdf_tools_router)
    app.include_router(pdf_doc_templates_router)
    app.include_router(mindmap_router)
    app.include_router(mindmap_templates_router)
    app.include_router(seo_analyzer_router)
    app.include_router(competitor_monitor_router)
    app.include_router(data_forecast_router)
    app.include_router(doc_qa_router)
    app.include_router(web_search_router)
    app.include_router(search_api_router)
    app.include_router(batch_api_router)
    app.include_router(realtime_router)

    # ══════════════════════════════════════════════════════════
    # platform：平台能力（Agent、工作流、知识库、沙箱）
    # ══════════════════════════════════════════════════════════
    app.include_router(extensions_agents_router)
    app.include_router(openai_gateway_router)
    app.include_router(relay_router)

    # ══════════════════════════════════════════════════════════
    # commerce：商业化（支付、配额、分享、会员）
    # ══════════════════════════════════════════════════════════
    app.include_router(stripe_router)
    app.include_router(apikey_api_router)
    app.include_router(api_billing_router)
    app.include_router(analytics_router)
    app.include_router(favorites_api_router)

    # ══════════════════════════════════════════════════════════
    # social：社交 & 协作
    # ══════════════════════════════════════════════════════════
    app.include_router(oauth_router)
    app.include_router(team_router)
    app.include_router(collab_engine_router)

    # ══════════════════════════════════════════════════════════
    # admin：管理与运维
    # ══════════════════════════════════════════════════════════
    app.include_router(admin_api_router)
    app.include_router(backup_router)
    app.include_router(notify_api_router)
    app.include_router(feedback_router)
    app.include_router(scheduler_router)

    # ══════════════════════════════════════════════════════════
    # enterprise：企业级功能
    # ══════════════════════════════════════════════════════════
    init_optimizer_system()
    app.include_router(optimizer_router)
    app.include_router(enterprise_router)

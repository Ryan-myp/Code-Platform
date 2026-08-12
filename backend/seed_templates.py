#!/usr/bin/env python3
"""模板市场种子数据（v17.6）。

向 templates 表填充与高频工具对应的种子模板，使模板市场/全局搜索不再为空。
数据来源：tool_records 真实使用统计（meeting-notes 会议纪要最热等）。

幂等：seed_templates() 仅在 templates 表为空时插入。
"""

import logging
import uuid
from datetime import datetime

from common.db import get_db

logger = logging.getLogger(__name__)

# (name, description, category, tool_id, price)
_TEMPLATES = [
    # ── 会议协作（最热：meeting-notes 23次）──
    ("周会纪要模板", "团队周会高效纪要：进展/阻塞/下周计划三段式，直接生成结构化纪要", "会议", "meeting-notes", 0),
    ("需求评审会议纪要", "需求评审会专用：议题/决策/遗留问题/责任人跟踪", "会议", "meeting-notes", 0),
    ("客户拜访纪要", "客户拜访记录：背景/需求/承诺事项/跟进计划", "会议", "meeting-notes", 0),
    ("每日站会速记", "10分钟站会模板：昨日完成/今日计划/阻塞事项", "会议", "meeting-notes", 0),

    # ── 职场效率（weekly-report 3次）──
    ("周报模板", "结构化周报：本周成果/数据/下周计划，自动生成汇报要点", "职场", "weekly-report", 0),
    ("OKR季度模板", "目标-关键结果拆解：公司/团队/个人三层对齐", "职场", "okr-generator", 0),
    ("项目复盘报告", "项目复盘：目标回顾/结果评估/原因分析/经验沉淀", "职场", "prd-generator", 0),
    ("晋升述职材料", "晋升述职：业绩亮点/能力成长/未来规划", "职场", "weekly-report", 0),

    # ── PPT（3次）──
    ("产品发布会PPT", "发布会路演结构：痛点-方案-演示-定价-行动号召", "PPT", "ppt-factory", 0),
    ("季度总结PPT", "季度经营汇报：数据看板+亮点+不足+下季规划", "PPT", "ppt-factory", 0),
    ("融资路演BP", "投资人路演：市场规模/产品/商业模式/财务预测", "PPT", "ppt-factory", 0),
    ("培训课件PPT", "教学培训：知识点拆解+案例+互动练习", "PPT", "ppt-factory", 0),

    # ── 自媒体（viral-title 4次 / xiaohongshu 2次）──
    ("小红书爆款笔记", "小红书种草笔记：抓眼球标题+场景化正文+标签策略", "自媒体", "xiaohongshu", 0),
    ("公众号推文框架", "公众号长文结构：钩子开头/价值正文/转化结尾", "自媒体", "copywriting", 0),
    ("短视频口播脚本", "短视频口播：黄金3秒开头+节奏控制+CTA", "自媒体", "video-script", 0),
    ("爆款标题生成器", "标题党公式库：数字+悬念+痛点+对比，一键生成10个候选", "自媒体", "viral-title", 0),

    # ── 研发管理（prd 2次 / api-doc 1次）──
    ("PRD需求文档", "产品需求文档：背景/用户故事/功能清单/验收标准", "研发", "prd-generator", 0),
    ("技术方案设计", "技术方案：架构图/模块划分/接口设计/风险预案", "研发", "prd-generator", 0),
    ("API接口文档", "接口文档模板：路径/参数/响应/错误码/示例", "研发", "api-doc", 0),
    ("测试用例模板", "测试用例：前置条件/步骤/预期结果/优先级", "研发", "test-cases", 0),

    # ── 数据分析（forecast）──
    ("经营数据分析", "经营分析框架：收入/成本/毛利/环比同比趋势", "数据", "data-analyzer", 0),
    ("用户行为分析", "用户分析：活跃/留存/转化漏斗/流失预警", "数据", "data-analyzer", 0),

    # ── 营销增长（growth）──
    ("活动策划方案", "营销活动：目标/人群/玩法/预算/风险", "营销", "growth", 0),
    ("用户增长策略", "增长策略：获客-激活-留存-变现-推荐全链路", "营销", "growth", 0),
]


def seed_templates() -> int:
    """幂等填充种子模板，返回插入条数。"""
    conn = get_db()
    try:
        # 确保表存在（v17.4 仅建表于生产环境，测试库/新库需幂等建表）
        conn.execute(
            """CREATE TABLE IF NOT EXISTS templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT '',
                tool_id TEXT DEFAULT '',
                price REAL DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                sales INTEGER DEFAULT 0,
                creator_id TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )"""
        )
        count = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        if count > 0:
            return 0
        now = datetime.now().isoformat()
        inserted = 0
        for name, desc, category, tool_id, price in _TEMPLATES:
            tpl_id = f"tpl_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO templates (id, name, description, category, tool_id, price,
                   usage_count, sales, creator_id, active, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tpl_id, name, desc, category, tool_id, price, 0, 0, "", 1, now, now),
            )
            inserted += 1
        conn.commit()
        logger.info("模板种子数据已填充: %d 条", inserted)
        return inserted
    finally:
        conn.close()


if __name__ == "__main__":
    seed_templates()
logger.info("模板种子数据填充完成")

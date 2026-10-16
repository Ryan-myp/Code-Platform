"""v18.3 模型成本估算层（诚实边界：估算而非账单）。

platform 只持有字符数（usage_logs），不持有 provider 账单。
本模块提供：
- MODEL_PRICES：常用模型的每 1K token 单价（USD，input/output 分开，近似值）
- estimate_cost(model, in_chars, out_chars)：字符→token 启发式（1 token ≈ 1.5 字符，
  对中英混合保守）+ 单价表 → 成本估算
- 未知模型：fallback 价格（中档价），detail 里如实标注 "unknown"

用于 by-agent 成本核算的 cost_est 列；不是财务口径，UI 上必须标注「估算」。
"""

from __future__ import annotations

# USD per 1K tokens (input, output) —— 2026 年常见档位的近似值，可随供应商调价更新
MODEL_PRICES: dict = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "deepseek-chat": (0.0003, 0.0009),
    "deepseek-reasoner": (0.0011, 0.0044),
    "glm-4": (0.001, 0.002),
    "glm-4-flash": (0.0003, 0.0006),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-sonnet-4": (0.003, 0.015),
}
# 未知模型兜底：中档价，避免 0 成本假象
FALLBACK_PRICE: tuple = (0.001, 0.003)
# 字符 → token 启发式（中英混合保守系数）
_CHARS_PER_TOKEN = 1.5


def estimate_cost(model: str, in_chars: int = 0, out_chars: int = 0) -> float:
    """估算单次调用的 USD 成本（单价为 per 1K tokens，结果截断到 6 位）。"""
    p_in, p_out = MODEL_PRICES.get(model, FALLBACK_PRICE)
    in_tokens = max(0, int(in_chars)) / _CHARS_PER_TOKEN
    out_tokens = max(0, int(out_chars)) / _CHARS_PER_TOKEN
    return round(in_tokens / 1000 * p_in + out_tokens / 1000 * p_out, 6)


def is_priced(model: str) -> bool:
    """模型是否在价格表内（用于标注「估算置信度」）。"""
    return model in MODEL_PRICES

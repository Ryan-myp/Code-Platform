"""公共基础层 — 数据库 / LLM / 配置 / 鉴权的单一来源。

所有业务模块应从这里导入，避免 get_db / call_llm / load_config 的重复定义。
"""

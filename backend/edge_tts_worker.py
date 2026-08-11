#!/usr/bin/env python3
"""edge-tts 独立合成 worker（子进程隔离）。

主进程通过 subprocess 调用本脚本完成单段 TTS 合成，
避免 edge-tts 长文本内部限速 / websocket 异常导致主事件循环卡死。

用法：python3 edge_tts_worker.py <text> <voice> <rate> <out_path> [pitch] [words_path] [style]

pitch 为可选音调参数（如 "+10Hz" / "-5%"），商用配音支持语调调整。
words_path 为可选 JSON 输出路径：写入逐词时间戳（歌声合成用），
格式 [{"text": str, "start": float秒, "end": float秒}, ...]。
style 为可选 Azure 情绪风格（如 cheerful/sad/angry/gentle/serious）：非空时
用 <mstts:express-as> SSML 包裹文本驱动情绪化发音（v13.24 数字人情绪系统）。
"""

import asyncio
import json
import logging
import sys

logger = logging.getLogger(__name__)


async def main() -> int:
    text, voice, rate, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    pitch = sys.argv[5] if len(sys.argv) > 5 else ""
    words_path = sys.argv[6] if len(sys.argv) > 6 else ""
    style = sys.argv[7] if len(sys.argv) > 7 else ""
    import edge_tts

    if style:
        # 情绪风格：SSML express-as 包裹（文本 HTML 转义，防止 <>& 破坏 XML 结构）
        import html

        payload = html.escape(text)
        text = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN">'
            f'<voice name="{voice}"><mstts:express-as style="{style}">'
            f"{payload}</mstts:express-as></voice></speak>"
        )

    kwargs = {"rate": rate}
    if pitch:
        kwargs["pitch"] = pitch
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kwargs)

    words: list[dict] = []
    with open(out_path, "wb") as out_f:
        async for msg in communicate.stream():
            if msg["type"] == "audio":
                out_f.write(msg["data"])
            elif msg["type"] == "WordBoundary":
                # offset/duration 以 100ns 为单位
                off = msg.get("offset") or 0
                dur = msg.get("duration") or 0
                try:
                    words.append(
                        {"text": msg.get("text", ""), "start": off / 1e7, "end": (off + dur) / 1e7}
                    )
                except TypeError:
                    # 个别消息字段缺失时静默跳过该词
                    pass
    if words_path and words:
        with open(words_path, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as e:  # noqa: BLE001
        logger.error(f"EDGE_TTS_ERROR: {e}")
        sys.exit(1)

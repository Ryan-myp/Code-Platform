#!/usr/bin/env python3
"""edge-tts 独立合成 worker（子进程隔离）。

主进程通过 subprocess 调用本脚本完成单段 TTS 合成，
避免 edge-tts 长文本内部限速 / websocket 异常导致主事件循环卡死。

用法：python3 edge_tts_worker.py <text> <voice> <rate> <out_path>
"""
import asyncio
import sys


async def main() -> int:
    text, voice, rate, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(out_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as e:  # noqa: BLE001
        print(f"EDGE_TTS_ERROR: {e}", file=sys.stderr)
        sys.exit(1)

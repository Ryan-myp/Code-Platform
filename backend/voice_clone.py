"""声音克隆 — v1 参数近似克隆（免费层）。

上传 10-60s 干净人声样本 → librosa pyin 基频分析 → edge-tts 音色池匹配
（基频最近的同性别音色）→ 音调补偿（pitch = 样本基频 - 音色基准基频，±20Hz 内）
→ 生成时用匹配音色 + 音调补偿合成配音，实现"声音气质近似克隆"。

定位与边界：
- 本方案是计划 Phase 3 的降级路线（"音色参数近似克隆作为免费层"），
  样本音频本身不用于配音（仅作分析），避免版权/合规风险。
- 升级路径：engine 字段预留 cosyvoice（CosyVoice2/GPT-SoVITS 本地推理），
  接口与表结构不变，仅替换 analyze/fit 内部实现。

依赖懒加载：librosa/numpy 未安装时抛明确错误，不影响数字人 2D 主链路启动。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# edge-tts 中文音色池：基频为常见朗读语料实测近似值（Hz），用于音色气质匹配。
# 仅收录 edge-tts 服务端当前验证可用的音色（2026-08 实测：Xiaomo/Xiaorui/Xiaohan/
# Xiaomeng/Xiaorou/Yunfeng/Yunhao/Yunye 已 NoAudioReceived，匹配到会白等超时）。
# 结构: (voice_id, 名称, 性别, 基准基频Hz, 风格)
VOICE_POOL: list[tuple[str, str, str, float, str]] = [
    ("zh-CN-XiaoxiaoNeural", "晓晓", "女", 230.0, "活泼少女"),
    ("zh-CN-XiaoyiNeural", "晓伊", "女", 215.0, "温柔知性"),
    ("zh-CN-YunxiNeural", "云希", "男", 175.0, "阳光少年"),
    ("zh-CN-YunyangNeural", "云扬", "男", 155.0, "专业播报"),
    ("zh-CN-YunjianNeural", "云健", "男", 135.0, "浑厚磁性"),
    ("zh-CN-YunxiaNeural", "云夏", "男", 125.0, "低沉厚重"),
]

# 样本时长范围（计划 Phase 3.1：上传 10-60s 干净人声）
MIN_SAMPLE_SECONDS = 10.0
MAX_SAMPLE_SECONDS = 60.0

# edge-tts 音调补偿范围（Hz，官方 ±50 内，保守取 ±20 避免机械感）
PITCH_MIN = -20
PITCH_MAX = 20

# 性别判定阈值（Hz）
_F0_FEMALE_MIN = 190.0
_F0_MALE_MAX = 165.0


def analyze_sample(path: str) -> dict:
    """分析人声样本，返回 {duration, f0_mean, voiced_ratio, gender}。

    - duration: 音频时长（秒）
    - f0_mean: 浊音段基频中位数（Hz），语音身份的核心特征
    - voiced_ratio: 浊音占比（0-1），过低说明背景音乐/噪音干扰
    - gender: 女 / 男 / 中性（按基频分布判定）

    样本过短/过长、无人声时抛 ValueError（调用方转 400）。
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=16000, mono=True)
    duration = len(y) / sr
    if duration < MIN_SAMPLE_SECONDS or duration > MAX_SAMPLE_SECONDS:
        raise ValueError(f"样本时长需在 {MIN_SAMPLE_SECONDS:.0f}-{MAX_SAMPLE_SECONDS:.0f} 秒之间（当前 {duration:.1f}s）")
    # pyin: 概率基频跟踪，对噪音鲁棒；fmin/fmax 在 librosa 0.10+ 为 keyword-only
    f0, voiced_flag, _ = librosa.pyin(
        y, fmin=70.0, fmax=500.0, sr=sr, frame_length=1024
    )
    voiced = f0[~np.isnan(f0)]
    if len(voiced) < 10:
        raise ValueError("未检测到清晰人声，请上传干净人声样本（无背景音乐/噪音）")
    f0_mean = float(np.median(voiced))
    voiced_ratio = float(len(voiced) / max(len(voiced_flag), 1))
    if f0_mean >= _F0_FEMALE_MIN:
        gender = "女"
    elif f0_mean <= _F0_MALE_MAX:
        gender = "男"
    else:
        gender = "中性"
    return {
        "duration": round(duration, 1),
        "f0_mean": round(f0_mean, 1),
        "voiced_ratio": round(voiced_ratio, 3),
        "gender": gender,
    }


def fit_voice(f0_mean: float) -> dict:
    """基频 → 匹配音色 + 音调补偿参数。

    返回 {edge_voice, voice_name, gender, pitch_hz, speed, base_f0, style}：
    - 同性别池内选基准基频最接近样本的音色（音色气质最像）
    - pitch_hz = clip(样本基频 - 音色基准基频, -20, +20) 补偿剩余音调差异
    - speed 恒 1.0（由生成时用户指定语速），预留
    """
    if f0_mean >= _F0_FEMALE_MIN:
        pool = [v for v in VOICE_POOL if v[2] == "女"]
    elif f0_mean <= _F0_MALE_MAX:
        pool = [v for v in VOICE_POOL if v[2] == "男"]
    else:
        pool = VOICE_POOL  # 中性音域：全池最近匹配
    best = min(pool, key=lambda v: abs(f0_mean - v[3]))
    edge_voice, name, gender, base_f0, style = best
    pitch = int(round(f0_mean - base_f0))
    pitch = max(PITCH_MIN, min(PITCH_MAX, pitch))
    return {
        "edge_voice": edge_voice,
        "voice_name": name,
        "gender": gender,
        "pitch_hz": pitch,
        "speed": 1.0,
        "base_f0": base_f0,
        "style": style,
    }

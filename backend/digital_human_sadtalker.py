"""数字人 SadTalker 引擎通道（平台侧客户端）。

调用独立推理服务 avatar_engine（127.0.0.1:9890）：
POST /release_task（multipart）→ 轮询 /query_result → 下载 /v1/video → 补平台水印。

设计约束：
- 探活防抖（30s 缓存），服务不可用时抛错触发上层降级（live_portrait/2d）
- SadTalker 推理为 CPU 长任务（20-50 分钟/15s 视频），超时上限 3600s
- v13.23 推理分辨率 256→512（内存充足时）；超限自动保 256，平台缩放链路保持
- stage 映射：pending 排队 / extract_3dmm / audio_to_coeff / face_render（耗时最长）
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time

import requests

logger = logging.getLogger(__name__)

AVATAR_API_BASE = os.environ.get("AVATAR_API_BASE", "http://127.0.0.1:9890")
_AVATAR_TIMEOUT = 30          # HTTP 请求超时
_AVATAR_POLL_INTERVAL = 15    # 任务轮询间隔
# 推理总时长上限：avatar 引擎串行（同时仅 1 任务），需覆盖「排队等待 + 自身推理」两段耗时。
# 实测 CPU 推理 15-25s 音频约 40-62 分钟，排队长任务时总时长可达 2 小时 → 取 7200s。
_AVATAR_MAX_WAIT = 7200       # 推理总时长上限（120 分钟）
_avatar_cache: dict = {"ok": None, "at": 0.0, "busy": 0}

# SadTalker 原生输出 256x256（内存受限时）/ 512x512（v13.23 默认）；平台按用户选择的分辨率统一缩放
_RESOLUTION_SIZES = {"720p": (1280, 720), "1080p": (1920, 1080)}

# v13.23 推理分辨率升级：内存充足（>=10GB 可用）时用 512 提升面部清晰度，否则保 256 稳定
_RENDER_SIZE_HIGH = 512
_RENDER_SIZE_SAFE = 256
_RENDER_SIZE_MEM_GB = 10.0


def _pick_render_size() -> int:
    """探测可用内存决定推理分辨率：>=10GB 用 512，否则 256（防 OOM 保稳）。"""
    try:
        import psutil

        avail_gb = psutil.virtual_memory().available / (1024**3)
    except Exception:
        try:
            import subprocess

            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            avail_gb = int(out.stdout.strip() or 0) / (1024**3) * 0.5  # 保守：物理内存一半视为可用
        except Exception:
            avail_gb = 0.0
    return _RENDER_SIZE_HIGH if avail_gb >= _RENDER_SIZE_MEM_GB else _RENDER_SIZE_SAFE


def _avatar_ok() -> bool:
    """引擎探活（30s 防抖）；同时记录 busy（排队中任务数）供进度提示。"""
    now = time.monotonic()
    if _avatar_cache["ok"] is not None and now - _avatar_cache["at"] < 30:
        return _avatar_cache["ok"]
    ok = False
    busy = 0
    try:
        r = requests.get(f"{AVATAR_API_BASE}/health", timeout=5)
        j = r.json()
        ok = r.status_code == 200 and j.get("status") == "ok"
        busy = int(j.get("running") or 0) + int(j.get("pending") or 0)
    except Exception:
        ok = False
    _avatar_cache.update(ok=ok, at=now, busy=busy)
    return ok


def _stage_pct(stage: str) -> tuple[float, str]:
    """stage → (进度百分比, 提示文案)。"""
    return {
        "": (58, "SadTalker 推理排队中…"),
        "loading": (60, "正在加载数字人模型（首次约 1 分钟）…"),
        "extract_3dmm": (62, "提取人脸 3DMM 系数…"),
        "audio_to_coeff": (66, "音频转口型/表情系数…"),
        "face_render": (72, "面部渲染中（CPU 推理，预计 20-50 分钟）…"),
    }.get(stage, (70, "SadTalker 推理中…"))


def _apply_watermark(video_path: str, size: tuple[int, int] = (1280, 720)) -> None:
    """右下角叠加平台水印（复用 live_portrait_engine 的水印生成）。"""
    from live_portrait_engine import _make_watermark_png, _pick_video_encoder

    wm_path = os.path.join(tempfile.mkdtemp(), "wm.png")
    _make_watermark_png(wm_path, size[0], size[1])
    tmp_out = video_path + ".wm.mp4"
    enc = _pick_video_encoder()
    quality = ["-crf", "18"] if enc == "libx264" else ["-b:v", "5M", "-maxrate", "7M", "-bufsize", "10M"]
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", wm_path,
        "-filter_complex", "[0:v][1:v]overlay=(W-w-30):(H-h-30)",
        "-c:v", enc, *quality,
        "-c:a", "copy",
        "-movflags", "+faststart",
        tmp_out,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=900)
    shutil.move(tmp_out, video_path)
    shutil.rmtree(os.path.dirname(wm_path), ignore_errors=True)


def _scale_to_resolution(video_path: str, resolution: str) -> None:
    """SadTalker 原生 256/512 方图 → 平台目标分辨率（lanczos 缩放，保持帧率/音频）。"""
    size = _RESOLUTION_SIZES.get(resolution)
    if not size:
        return
    tmp_out = video_path + ".scaled.mp4"
    enc = "libx264"
    quality = ["-crf", "18", "-preset", "slow"]
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"scale={size[0]}:{size[1]}:flags=lanczos",
        "-c:v", enc, *quality,
        "-c:a", "copy",
        "-movflags", "+faststart",
        tmp_out,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=900)
    shutil.move(tmp_out, video_path)


# v13.24 情绪 → 3DMM 表情幅度（expression_scale）：欢快/悲伤等强情绪放大表情，
# 平淡情绪小幅增强（默认 1.5 比旧版固定 1.0 生动）
EMOTION_EXPRESSION_SCALE = {
    "neutral": 1.3,
    "happy": 1.8,
    "sad": 1.8,
    "angry": 2.0,
    "gentle": 1.5,
    "serious": 1.3,
}



def _sadtalker_submit(photo_path: str, audio_path: str, render_size: int, expression_scale: float) -> str:
    """提交 SadTalker 任务，返回 task_id。"""
    with open(photo_path, "rb") as imf, open(audio_path, "rb") as auf:
        r = requests.post(
            f"{AVATAR_API_BASE}/release_task",
            files={"image": ("face.png", imf, "image/png"), "audio": ("voice.wav", auf, "audio/wav")},
            data={"pose_style": 0, "size": render_size, "still": "true", "expression_scale": expression_scale},
            timeout=_AVATAR_TIMEOUT,
        )
    r.raise_for_status()
    return r.json()["data"]["task_id"]


def _sadtalker_poll(task_id: str, _report) -> str:
    """轮询任务直到成功，返回文件 URL。"""
    t0 = time.monotonic()
    last_pct, last_stage = 55, "已提交"
    while time.monotonic() - t0 < _AVATAR_MAX_WAIT:
        time.sleep(_AVATAR_POLL_INTERVAL)
        try:
            q = requests.get(f"{AVATAR_API_BASE}/query_result", params={"task_id": task_id}, timeout=10)
            item = next((x for x in (q.json().get("data") or []) if x.get("task_id") == task_id), None)
        except Exception as e:
            logger.warning(f"SadTalker 任务 {task_id} 查询失败: {e}")
            continue
        if not item:
            continue
        status = item.get("status", "")
        if status == "success":
            result = json.loads(item.get("result") or "[]")
            return result[0].get("file", "") if result else ""
        if status == "failed":
            raise RuntimeError(f"SadTalker 推理失败: {item.get('error') or '未知错误'}")
        if status in ("pending", "running"):
            pct, hint = _stage_pct(item.get("stage", ""))
            if pct != last_pct or hint != last_stage:
                _report(pct, hint)
                last_pct, last_stage = pct, hint
    raise TimeoutError(f"SadTalker 推理超时（>{_AVATAR_MAX_WAIT}s），请重试")


def _sadtalker_download(file_url: str, output_path: str) -> None:
    """下载产物视频到目标路径。"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    dl = requests.get(f"{AVATAR_API_BASE}/v1/video", params={"path": file_url}, timeout=120)
    dl.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(dl.content)
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
        raise RuntimeError("SadTalker 视频回传失败（文件无效）")

def generate_with_sadtalker(  # noqa: C901
    photo_path: str,
    audio_path: str,
    output_path: str,
    resolution: str = "720p",
    watermark: bool = False,
    progress=None,  # Callable[[float, str], None]
    emotion: str = "neutral",
) -> dict:
    """照片 + 音频 → SadTalker 口播视频（阻塞直至完成或失败）。

    失败抛异常：上层按引擎降级链回退 live_portrait / 2d。
    emotion（v13.24）：驱动 3DMM 表情幅度（expression_scale），情绪越强表情越夸张。
    """
    if not _avatar_ok():
        raise RuntimeError("SadTalker 引擎未就绪（avatar_engine 9890 未启动）")

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    # 1. 提交任务（提交前再探活一次，更新排队计数）；推理分辨率按内存预算 512/256
    _avatar_ok()
    render_size = _pick_render_size()
    expression_scale = EMOTION_EXPRESSION_SCALE.get(emotion, 1.5)
    task_id = _sadtalker_submit(photo_path, audio_path, render_size, expression_scale)
    if _avatar_cache.get("busy"):
        _report(55, f"SadTalker 引擎繁忙（{_avatar_cache['busy']} 个任务排队），已提交，预计等待较长…")
    else:
        _report(55, "SadTalker 任务已提交，正在排队…")

    # 2. 轮询任务状态
    t0 = time.monotonic()
    file_url = _sadtalker_poll(task_id, _report)

    # 3. 下载产物
    _report(96, "推理完成，正在回传视频…")
    _sadtalker_download(file_url, output_path)

    # 4. 分辨率统一：原生 256x256 → 平台目标分辨率（720p/1080p）
    _scale_to_resolution(output_path, resolution)

    # 5. 商业水印
    if watermark:
        _apply_watermark(output_path, _RESOLUTION_SIZES.get(resolution, (1280, 720)))

    duration = round((time.monotonic() - t0) / 60, 1)
    logger.info(f"SadTalker 出片完成: {duration} 分钟, render_size={render_size} -> {output_path}")
    return {"engine": "sadtalker", "duration_min": duration, "render_size": render_size}

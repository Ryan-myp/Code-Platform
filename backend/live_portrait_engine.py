"""照片数字人引擎（计划 Phase 2.1）。

引擎接口：generate_from_photo(photo_path, audio_path, output_path, resolution) → MP4

v1 实现：Wav2Lip（GAN）口型同步 —— 权重公开可下载、M4 Pro MPS 推理、口型同步业界标准：
- 输入：单张正脸照片 + 配音音频
- 流程：mediapipe 人脸关键点 → 5 点仿射对齐（Wav2Lip 标准脸坐标系）→
       音频 mel 频谱（Tacotron2 参数）→ 逐帧口型推理（25fps）→ 逆变换贴回照片 →
       16:9 画布合成（模糊背景+照片居中）→ ffmpeg 合成音频 + 中文水印 overlay
- 升级路径：LivePortrait audio-driven 权重（audio2motion_vae/mlp，官方仓库 gated）
  获取后可无缝替换内部实现，接口与并发控制不变。

依赖懒加载：torch/torchvision/opencv/mediapipe/librosa/numpy 未安装时抛明确错误，
不影响数字人 2D 主链路启动。模型权重：backend/models/live_portrait/wav2lip/wav2lip_gan.pth
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time

try:
    import numpy as np  # 轻量且 torch 必带；cv2/mediapipe/librosa 仍在函数内懒加载
    import torch  # 模型类继承依赖；缺失时降级（类可加载不可实例化），由 _require_deps() 拦截
    _ModuleBase = torch.nn.Module
except ImportError:
    # 重型依赖缺失：模块仍可加载（2D 主链路与错误提示不受影响），运行时由 _require_deps() 抛安装指引
    np = None
    torch = None
    _ModuleBase = object

logger = logging.getLogger(__name__)

# ── 全局并发控制（复用 _RENDER_SLOT 模式：推理串行防显存/内存争抢） ──
_LIVE_PORTRAIT_SLOT = threading.BoundedSemaphore(1)
_ENGINE_LOCK = threading.Lock()
_ENGINE_STATE: dict = {"model": None, "device": None, "loaded_at": 0.0}

_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "live_portrait", "wav2lip")
_MODEL_PATH = os.path.join(_MODEL_DIR, "wav2lip_gan.pth")

# Wav2Lip 标准脸坐标系（256x256，模型训练分布：眼睛 y≈110，嘴 y≈195）
_STANDARD_LANDMARKS = {
    "left_eye": (62.5, 110.0),
    "right_eye": (193.5, 110.0),
    "nose": (128.0, 155.0),
    "left_mouth": (76.5, 195.0),
    "right_mouth": (179.5, 195.0),
}
_MEL_STEP = 16  # 每个视频帧对应的 mel 时间帧窗口
_FPS = 25  # Wav2Lip 训练对齐帧率（输出后可由 ffmpeg 转任意帧率）
_WAV2LIP_IMG_SIZE = 256


def _require_deps() -> None:
    """检查重型依赖，缺失时给出可操作的安装提示（懒加载，不影响主链路启动）。"""
    missing = []
    for mod in ("torch", "cv2", "mediapipe", "librosa", "numpy", "scipy"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        raise RuntimeError(
            f"照片数字人引擎依赖缺失（{', '.join(missing)}），请执行: "
            "pip3 install torch torchvision opencv-python-headless mediapipe librosa numpy scipy soundfile"
        )
    if not os.path.exists(_MODEL_PATH):
        raise RuntimeError(
            f"照片数字人模型权重缺失: {_MODEL_PATH}，请下载 wav2lip_gan.pth 后重试"
        )


def _pick_video_encoder() -> str:
    """视频编码器自动选择：Apple 硬件编码优先，无则回退 libx264。"""
    import subprocess as sp

    try:
        out = sp.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        if "videotoolbox" in out and "h264_videotoolbox" in out:
            return "h264_videotoolbox"
    except Exception:  # noqa: BLE001 — 编码器探测失败回退 CPU
        pass
    return "libx264"


# ── Wav2Lip 模型定义（官方结构精简版，仅推理所需） ──────────────────

class _Conv2d(_ModuleBase):
    def __init__(self, cin, cout, kernel_size, stride, padding, residual=False):
        super().__init__()
        self.conv_block = torch.nn.Sequential(
            torch.nn.Conv2d(cin, cout, kernel_size, stride, padding),
            torch.nn.BatchNorm2d(cout),
        )
        self.act = torch.nn.ReLU()
        self.residual = residual

    def forward(self, x):
        out = self.conv_block(x)
        if self.residual:
            out = out + x
        return self.act(out)


class _Conv2dTranspose(_ModuleBase):
    def __init__(self, cin, cout, kernel_size, stride, padding, output_padding=0):
        super().__init__()
        self.conv_block = torch.nn.Sequential(
            torch.nn.ConvTranspose2d(cin, cout, kernel_size, stride, padding, output_padding),
            torch.nn.BatchNorm2d(cout),
        )
        self.act = torch.nn.ReLU()

    def forward(self, x):
        return self.act(self.conv_block(x))


class _Wav2Lip(_ModuleBase):
    """Wav2Lip generator（https://github.com/Rudrabha/Wav2Lip 官方结构）。

    输入：audio (B,80,16) + face (B,6,96,96)（下半被 mask 的原图 + 原图，/255）
    输出：(B,3,96,96)，Sigmoid [0,1] 的 BGR 帧（训练数据为 cv2 读取，BGR 语义）
    """

    def __init__(self):
        super().__init__()
        # 官方 Wav2Lip GAN 结构（wav2lip_gan.pth）：block2 有 3 个 residual；block5 仅 1 个；
        # block6 为 3x3(s1,p0)+1x1 —— 与官方非 GAN 版（每 block 3 层）不同，权重结构实测对齐
        self.face_encoder_blocks = torch.nn.ModuleList([
            torch.nn.Sequential(_Conv2d(6, 16, kernel_size=7, stride=1, padding=3)),
            torch.nn.Sequential(_Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
                                _Conv2d(32, 32, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(32, 32, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
                                _Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
                                _Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2d(128, 256, kernel_size=3, stride=2, padding=1),
                                _Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2d(256, 512, kernel_size=3, stride=2, padding=1),
                                _Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2d(512, 512, kernel_size=3, stride=1, padding=0),
                                _Conv2d(512, 512, kernel_size=1, stride=1, padding=0)),
        ])
        self.audio_encoder = torch.nn.Sequential(
            _Conv2d(1, 32, kernel_size=3, stride=1, padding=1),
            _Conv2d(32, 32, kernel_size=3, stride=1, padding=1, residual=True),
            _Conv2d(32, 32, kernel_size=3, stride=1, padding=1, residual=True),
            _Conv2d(32, 64, kernel_size=3, stride=(3, 1), padding=1),
            _Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
            _Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
            _Conv2d(64, 128, kernel_size=3, stride=3, padding=1),
            _Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),
            _Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),
            _Conv2d(128, 256, kernel_size=3, stride=(3, 2), padding=1),
            _Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True),
            _Conv2d(256, 512, kernel_size=3, stride=1, padding=0),
            _Conv2d(512, 512, kernel_size=1, stride=1, padding=0),
        )
        self.face_decoder_blocks = torch.nn.ModuleList([
            torch.nn.Sequential(_Conv2d(512, 512, kernel_size=1, stride=1, padding=0)),
            torch.nn.Sequential(_Conv2dTranspose(1024, 512, kernel_size=3, stride=1, padding=0),
                                _Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2dTranspose(1024, 512, kernel_size=3, stride=2, padding=1, output_padding=1),
                                _Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(512, 512, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2dTranspose(768, 384, kernel_size=3, stride=2, padding=1, output_padding=1),
                                _Conv2d(384, 384, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(384, 384, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2dTranspose(512, 256, kernel_size=3, stride=2, padding=1, output_padding=1),
                                _Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(256, 256, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2dTranspose(320, 128, kernel_size=3, stride=2, padding=1, output_padding=1),
                                _Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(128, 128, kernel_size=3, stride=1, padding=1, residual=True)),
            torch.nn.Sequential(_Conv2dTranspose(160, 64, kernel_size=3, stride=2, padding=1, output_padding=1),
                                _Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True),
                                _Conv2d(64, 64, kernel_size=3, stride=1, padding=1, residual=True)),
        ])
        self.output_block = torch.nn.Sequential(
            _Conv2d(80, 32, kernel_size=3, stride=1, padding=1),
            torch.nn.Conv2d(32, 3, kernel_size=1, stride=1, padding=0),
            torch.nn.Sigmoid(),
        )

    def forward(self, audio_sequences, face_sequences):
        audio_embedding = self.audio_encoder(audio_sequences)
        feats = []
        x = face_sequences
        for f in self.face_encoder_blocks:
            x = f(x)
            feats.append(x)
        x = audio_embedding
        for f in self.face_decoder_blocks:
            x = f(x)
            x = torch.cat((x, feats[-1]), dim=1)
            feats.pop()
        return self.output_block(x)


# ── 模型加载（懒加载单例） ─────────────────────────────────────────

def _load_model():
    """懒加载 Wav2Lip 模型（全局单例，线程安全）。返回 (model, device)。"""
    with _ENGINE_LOCK:
        if _ENGINE_STATE["model"] is not None:
            return _ENGINE_STATE["model"], _ENGINE_STATE["device"]
        import torch

        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        t0 = time.monotonic()
        # 优先安全模式（仅反序列化张量）；老式 checkpoint 含优化器状态时降级兼容
        try:
            checkpoint = torch.load(_MODEL_PATH, map_location="cpu", weights_only=True)
        except Exception:  # noqa: BLE001 — 旧权重格式兼容
            checkpoint = torch.load(_MODEL_PATH, map_location="cpu", weights_only=False)
        state = checkpoint.get("state_dict", checkpoint)
        model = _Wav2Lip()
        new_s = {k.replace("module.", ""): v for k, v in state.items()}
        model.load_state_dict(new_s)
        model.to(device).eval()
        _ENGINE_STATE.update({"model": model, "device": device, "loaded_at": t0})
        logger.info(f"Wav2Lip 模型加载完成（{device}），耗时 {time.monotonic() - t0:.1f}s")
        return model, device


# ── 音频 → mel 频谱（Tacotron2 参数，与 Wav2Lip 训练一致） ──────────

def _melspectrogram(wav: np.ndarray) -> np.ndarray:
    """wav (16000Hz mono) → 归一化 mel 频谱 (80, T)，范围 [-4, 4]。"""
    import librosa
    import numpy as np
    from scipy import signal

    wav = signal.lfilter([1, -0.97], [1], wav)  # preemphasis 0.97
    D = librosa.stft(wav, n_fft=800, hop_length=200, win_length=800)
    mel_basis = librosa.filters.mel(sr=16000, n_fft=800, n_mels=80, fmin=55, fmax=7600)
    S = mel_basis @ np.abs(D)
    S = 20 * np.log10(np.maximum(1e-5, S)) - 20  # ref_level_db=20
    return np.clip((S + 100) / 100 * 8 - 4, -4, 4)  # symmetric, max_abs=4


def _mel_chunks(wav_path: str) -> list:
    """音频 → (80,16) mel 分块列表，每块对应一帧 25fps 视频。"""
    import librosa
    import numpy as np

    wav, _ = librosa.load(wav_path, sr=16000, mono=True)
    mel = _melspectrogram(wav)
    step = 80.0 / _FPS
    chunks = []
    i = 0
    while True:
        start = int(i * step)
        if start >= mel.shape[1]:
            break
        seg = mel[:, start : start + _MEL_STEP]
        if seg.shape[1] < _MEL_STEP:
            seg = np.pad(seg, ((0, 0), (0, _MEL_STEP - seg.shape[1])), mode="constant", constant_values=-4)
        chunks.append(seg.astype(np.float32))
        i += 1
    if not chunks:
        raise RuntimeError("配音音频无效或为空，无法生成照片数字人")
    return chunks


# ── 人脸检测与 5 点仿射对齐（mediapipe FaceMesh → Wav2Lip 标准坐标系） ──

def _face_align_params(bgr: np.ndarray) -> tuple:
    """检测照片正脸并计算 Wav2Lip 对齐参数。

    返回 (tform, inv_tform, aligned_face)：
    - tform: 2x3 仿射（原图 → 256x256 标准脸坐标系）
    - inv_tform: 逆变换（口型帧 → 原图）
    - aligned_face: 对齐后的 256x256 BGR 脸图
    无清晰正脸时抛 RuntimeError。
    """
    import cv2
    import mediapipe as mp
    import numpy as np

    h, w = bgr.shape[:2]
    mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=1, refine_landmarks=True,
        min_detection_confidence=0.5,
    )
    try:
        results = mesh.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    finally:
        mesh.close()
    if not results or not results.multi_face_landmarks:
        raise RuntimeError("照片未检测到清晰正脸，请上传正面免冠、光线充足的照片")

    lm = results.multi_face_landmarks[0].landmark
    pts = np.array([(p.x * w, p.y * h) for p in lm])
    # 5 点：左右眼中心 / 鼻尖 / 左右嘴角（mediapipe 33=右眼外角, 263=左眼外角）
    left_eye = (pts[33] + pts[133]) / 2
    right_eye = (pts[263] + pts[362]) / 2
    src = np.array(
        [left_eye, right_eye, pts[1], pts[61], pts[291]], dtype=np.float32
    )
    dst = np.array(
        [
            _STANDARD_LANDMARKS["left_eye"],
            _STANDARD_LANDMARKS["right_eye"],
            _STANDARD_LANDMARKS["nose"],
            _STANDARD_LANDMARKS["left_mouth"],
            _STANDARD_LANDMARKS["right_mouth"],
        ],
        dtype=np.float32,
    )
    tform, inliers = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC)
    # 头盔/眼镜/阴影等遮挡会造成个别关键点异常：内点 ≥3 即可；不足时用 LMEDS 兜底（对异常值鲁棒）
    if tform is None or (inliers is not None and inliers.sum() < 3):
        tform, _ = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
    if tform is None:
        raise RuntimeError("照片人脸关键点检测异常，请使用正脸、无遮挡的照片")
    inv_tform = cv2.invertAffineTransform(tform)
    aligned = cv2.warpAffine(
        bgr, tform, (_WAV2LIP_IMG_SIZE, _WAV2LIP_IMG_SIZE), borderMode=cv2.BORDER_REPLICATE
    )
    return tform, inv_tform, aligned


# ── 帧合成（16:9 画布：模糊背景 + 照片居中） ───────────────────────

def _compose_frame(out_bgr: np.ndarray, photo_bgr: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    import cv2
    import numpy as np

    ph, pw = photo_bgr.shape[:2]
    bg = cv2.resize(photo_bgr, (out_w, out_h))
    bg = cv2.GaussianBlur(bg, (31, 31), 0)
    bg = (bg * 0.55).astype(np.uint8)
    scale = out_h / ph
    fw, fh = int(pw * scale), out_h
    if fw > out_w:  # 照片过宽：按宽度适配并垂直居中
        scale = out_w / pw
        fw, fh = out_w, int(ph * scale)
    fore = cv2.resize(out_bgr, (fw, fh))  # 前景=Wav2Lip 输出帧（含口型动态），非原图
    x0, y0 = (out_w - fw) // 2, (out_h - fh) // 2
    out = bg.copy()
    out[y0 : y0 + fh, x0 : x0 + fw] = fore
    return out


# ── 主流程 ─────────────────────────────────────────────────────────

def generate_from_photo(  # noqa: C901 — 推理主流程，分步注释保持可读
    photo_path: str,
    audio_path: str,
    output_path: str,
    resolution: str = "720p",
    watermark: bool = False,
    progress: callable | None = None,
) -> dict:
    """照片 → 口型同步数字人视频（MP4，含配音音频）。

    参数：
    - photo_path: 正脸照片（jpg/png）
    - audio_path: 配音音频（mp3/wav，edge-tts 输出即可）
    - output_path: 输出 MP4 路径
    - resolution: 720p | 1080p（16:9 画布）
    - watermark: 是否叠加中文商业水印（右下角，ffmpeg overlay 零逐帧成本）
    - progress: 进度回调 (percent 0-100, stage 文案)

    返回 {"duration": 秒, "frames": 帧数, "fps": 25}。
    失败抛 RuntimeError（上层捕获后降级 2D 引擎）。
    """
    _require_deps()  # 先查依赖再 import：缺失时抛安装指引，而非裸 ModuleNotFoundError
    import cv2
    import numpy as np
    import torch

    if not os.path.exists(photo_path):
        raise RuntimeError(f"照片文件不存在: {photo_path}")
    if not os.path.exists(audio_path):
        raise RuntimeError(f"音频文件不存在: {audio_path}")

    OUT_W, OUT_H = (1920, 1080) if resolution == "1080p" else (1280, 720)

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:  # noqa: BLE001 — 进度回调失败不影响主流程
                pass

    if not _LIVE_PORTRAIT_SLOT.acquire(timeout=600):
        raise RuntimeError("照片数字人推理繁忙，请稍后重试")
    frames_dir = tempfile.mkdtemp(prefix="lp_frames_")
    try:
        _report(5, "正在加载照片数字人模型…")
        model, device = _load_model()

        photo = cv2.imread(photo_path)
        if photo is None:
            raise RuntimeError("照片文件无法解析，请使用 jpg/png 格式")
        _report(10, "正在检测人脸…")
        tform, inv_tform, aligned_face = _face_align_params(photo)

        _report(15, "正在分析配音音频…")
        chunks = _mel_chunks(audio_path)
        n_frames = len(chunks)
        duration = n_frames / _FPS
        if duration > 600:
            raise RuntimeError(f"音频过长（{duration:.0f}s），照片数字人最长支持 600s")

        # 模型输入准备（每帧同一张脸，仅音频不同）：96x96 下半 mask + 原图，/255
        face96 = cv2.resize(aligned_face, (96, 96))
        face96 = face96.astype(np.float32) / 255.0
        face_in = np.concatenate((face96.copy(), face96), axis=2)  # (96,96,6) 下半=0
        face_in[48:, :, :3] = 0.0
        face_tensor = torch.from_numpy(face_in.transpose(2, 0, 1)).unsqueeze(0).to(device)  # (1,6,96,96)

        # 水印 PNG（一次性生成，ffmpeg overlay 叠加）
        wm_path = ""
        if watermark:
            wm_path = os.path.join(frames_dir, "wm.png")
            _make_watermark_png(wm_path, OUT_W, OUT_H)

        _report(20, "正在生成口型动画…")
        batch_size = 16
        batch_start = time.monotonic()
        deadline = max(n_frames * 0.2, 300)  # 看门狗：单批 30s 无进展 + 总时长超限即中断
        last_batch_at = time.monotonic()
        for i in range(0, n_frames, batch_size):
            batch = chunks[i : i + batch_size]
            # 官方输入布局 (B, T, 1, 80, 16) → 单帧批 (B, 1, 80, 16)：mel 80 维是空间 H，16 帧是 W
            mel_batch = torch.from_numpy(np.stack(batch)).unsqueeze(1).to(device)  # (B,1,80,16)
            with torch.no_grad():
                pred = model(mel_batch, face_tensor.expand(len(batch), -1, -1, -1))
            pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0
            now = time.monotonic()
            if now - last_batch_at > 30:
                raise TimeoutError(f"口型推理停滞（>{30}s 无进展，第 {i}/{n_frames} 帧）")
            last_batch_at = now
            if now - batch_start > deadline:
                raise TimeoutError(f"口型推理总时长超限（>{deadline:.0f}s，第 {i}/{n_frames} 帧）")
            for j, p in enumerate(pred):
                p = p.astype(np.uint8)
                p = cv2.resize(p, (_WAV2LIP_IMG_SIZE, _WAV2LIP_IMG_SIZE))
                # 逆变换贴回原图（BGR，模型与 cv2 通道语义一致，无需转换）
                frame = cv2.warpAffine(
                    p, inv_tform, (photo.shape[1], photo.shape[0]), borderMode=cv2.BORDER_REPLICATE
                )
                composed = _compose_frame(frame, photo, OUT_W, OUT_H)
                cv2.imwrite(os.path.join(frames_dir, f"{i + j:04d}.jpg"), composed, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if progress:
                _report(20 + int(60 * (i + len(batch)) / n_frames), "口型动画生成中…")

        _report(85, "口型动画完成，正在合成视频…")
        _ffmpeg_compose(frames_dir, audio_path, output_path, OUT_W, OUT_H, wm_path)
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise RuntimeError("视频合成失败（输出文件无效）")
        logger.info(f"照片数字人出片完成: {duration:.1f}s {n_frames}帧 -> {output_path}")
        return {"duration": round(duration, 2), "frames": n_frames, "fps": _FPS}
    finally:
        _LIVE_PORTRAIT_SLOT.release()
        shutil.rmtree(frames_dir, ignore_errors=True)


def _make_watermark_png(path: str, out_w: int, out_h: int) -> None:
    """生成中文水印透明 PNG（右下角），供 ffmpeg overlay 叠加。"""
    from PIL import Image, ImageDraw, ImageFont

    text = "AI 数字人 · 小团智能"
    font_candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    font = None
    for fp in font_candidates:
        try:
            font = ImageFont.truetype(fp, int(24 * out_w / 1280))
            break
        except Exception:  # noqa: BLE001 — 候选字体逐个尝试
            continue
    if font is None:
        font = ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w = int(probe.textlength(text, font=font))  # textlength 返回 float，PIL 尺寸需 int
    h = int(font.size * 1.4)
    pad = int(16 * out_w / 1280)
    layer = Image.new("RGBA", (w + pad * 2, h + pad), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.text((pad, 4), text, font=font, fill=(0, 0, 0, 120))
    draw.text((pad + 2, 6), text, font=font, fill=(0, 0, 0, 120))
    draw.text((pad, 5), text, font=font, fill=(255, 255, 255, 180))
    layer.save(path)


def _ffmpeg_compose(frames_dir: str, audio_path: str, output_path: str, out_w: int, out_h: int, wm_path: str) -> None:
    """帧序列 + 音频 + 水印 → MP4（videotoolbox 优先，失败自动 720p 无重试降级 libx264）。"""
    enc = _pick_video_encoder()
    # v14.0 码率按分辨率分级：720p 短视频 5M 已满足观感（编码更快），1080p 保持 6M 画质
    if enc != "libx264":
        hd = out_h >= 1080
        quality_args = [
            "-b:v", "6M" if hd else "5M",
            "-maxrate", "8M" if hd else "7M",
            "-bufsize", "12M" if hd else "10M",
        ]
    else:
        quality_args = ["-crf", "18"]
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(_FPS),
        "-i", os.path.join(frames_dir, "%04d.jpg"),
        "-i", audio_path,
    ]
    if wm_path:
        cmd += ["-i", wm_path, "-filter_complex", "[0:v][2:v]overlay=(W-w-30):(H-h-30)"]
    cmd += [
        "-c:v", enc, *quality_args,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)

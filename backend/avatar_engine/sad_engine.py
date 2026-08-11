"""SadTalker 推理封装：单图 + 音频 → 口型说话视频。

运行约束（Apple Silicon）：
- Face Renderer 使用 Conv3D，PyTorch MPS 不支持 → 强制 CPU + 多线程优化
- 15s 视频（256 分辨率）预计 20-50 分钟，调用方需走异步任务
"""
from __future__ import annotations

import gc
import logging
import os
import sys
import time

logger = logging.getLogger("avatar_engine.sad")

# CPU 线程优化（Apple Silicon 性能核数）
os.environ.setdefault("OMP_NUM_THREADS", "8")
os.environ.setdefault("MKL_NUM_THREADS", "8")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "8")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "8")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "8")

# SadTalker 2023 代码使用 numpy 1.24 已移除的老别名（np.float/np.int 等）。
# numpy 固定 1.23.4 时 numba 0.61 又不兼容 → 保持 numpy 1.26 + 注入别名，兼容面最小。
def _patch_numpy_aliases() -> None:
    import numpy as np

    for _name, _target in (("float", float), ("int", int), ("bool", bool), ("object", object), ("complex", complex), ("str", str)):
        if not hasattr(np, _name):
            setattr(np, _name, _target)


_patch_numpy_aliases()

SADTALKER_ROOT = os.path.expanduser("~/ai-models/SadTalker")
CHECKPOINT_DIR = os.path.join(SADTALKER_ROOT, "checkpoints")
CONFIG_DIR = os.path.join(SADTALKER_ROOT, "src", "config")

_engine = None  # 全局单例（懒加载，串行推理）


class SadTalkerEngine:
    def __init__(self, root: str = SADTALKER_ROOT) -> None:
        self.root = root
        if root not in sys.path:
            sys.path.insert(0, root)
        import torch

        torch.set_num_threads(8)
        self.torch = torch
        self._models: dict = {}

    # ── 模型加载（首次推理时懒加载，耗时数秒） ──────────────
    def _load(self) -> None:
        if self._models:
            return
        t0 = time.monotonic()
        from src.facerender.animate import AnimateFromCoeff
        from src.test_audio2coeff import Audio2Coeff
        from src.utils.init_path import init_path
        from src.utils.preprocess import CropAndExtract

        sadtalker_paths = init_path(CHECKPOINT_DIR, CONFIG_DIR, 256, False, "crop")
        self._models = {
            "paths": sadtalker_paths,
            "preprocess": CropAndExtract(sadtalker_paths, "cpu"),
            "audio2coeff": Audio2Coeff(sadtalker_paths, "cpu"),
            "animate": AnimateFromCoeff(sadtalker_paths, "cpu"),
        }
        logger.info(f"SadTalker 模型加载完成，耗时 {time.monotonic() - t0:.1f}s")

    # ── 生成口播视频 ─────────────────────────────────────
    def generate(
        self,
        image_path: str,
        audio_path: str,
        out_dir: str,
        pose_style: int = 0,
        size: int = 256,
        still: bool = True,
        preprocess: str = "crop",
        batch_size: int = 4,
        expression_scale: float = 1.5,
        progress=None,  # Callable[[str], None] — 阶段回调（供任务状态透传）
    ) -> str:
        """生成口播视频，返回 mp4 绝对路径。

        expression_scale（0.5~2.5）：3DMM 表情幅度系数，>1 放大表情让情绪更明显
        （v13.24 情绪增强，默认 1.5 比旧版固定 1.0 生动）。
        """
        import shutil

        self._load()
        from src.generate_batch import get_data
        from src.generate_facerender_batch import get_facerender_data

        m = self._models
        os.makedirs(out_dir, exist_ok=True)
        save_dir = os.path.join(out_dir, "work")
        os.makedirs(save_dir, exist_ok=True)

        # 1) 3DMM 提取（裁剪面部）
        logger.info("阶段 1/4: 3DMM 提取")
        if progress:
            progress("extract_3dmm")
        first_frame_dir = os.path.join(save_dir, "first_frame_dir")
        os.makedirs(first_frame_dir, exist_ok=True)
        first_coeff_path, crop_pic_path, crop_info = m["preprocess"].generate(
            image_path, first_frame_dir, preprocess, source_image_flag=True, pic_size=size
        )
        if first_coeff_path is None:
            raise RuntimeError("无法从输入图片提取 3DMM 系数（人脸检测失败）")

        # 2) 音频 → 3DMM 系数
        logger.info("阶段 2/4: 音频转系数")
        if progress:
            progress("audio_to_coeff")
        batch = get_data(first_coeff_path, audio_path, "cpu", None, still=still)
        coeff_path = m["audio2coeff"].generate(batch, save_dir, pose_style, None)

        # 3) 系数 → 视频帧
        logger.info("阶段 3/4: 面部渲染（CPU，耗时最长）")
        if progress:
            progress("face_render")
        data = get_facerender_data(
            coeff_path,
            crop_pic_path,
            first_coeff_path,
            audio_path,
            batch_size,
            None,
            None,
            None,
            expression_scale=max(0.5, min(2.5, float(expression_scale))),
            still_mode=still,
            preprocess=preprocess,
            size=size,
        )
        result = m["animate"].generate(
            data,
            save_dir,
            image_path,
            crop_info,
            enhancer=None,
            background_enhancer=None,
            preprocess=preprocess,
            img_size=size,
        )

        # 4) 整理产物
        out_mp4 = os.path.join(out_dir, "result.mp4")
        shutil.move(result, out_mp4)
        shutil.rmtree(save_dir, ignore_errors=True)
        gc.collect()
        logger.info(f"生成完成: {out_mp4}")
        return out_mp4


def get_engine() -> SadTalkerEngine:
    global _engine
    if _engine is None:
        _engine = SadTalkerEngine()
    return _engine

"""mac 环境音频加载补丁

torchaudio 2.11 的 load() 强制走 torchcodec，而 torchcodec 0.15 与 torch 2.13
ABI 不兼容（libtorchcodec_core4.dylib 加载失败）。本补丁将 torchaudio.load
替换为 soundfile 实现（与 CosyVoice 官方 load_wav 的 backend='soundfile' 同源），
在 import CosyVoice 前调用 patch_audio() 即可。
"""
import io

import torch
import torchaudio

try:
    import soundfile as sf
except ImportError:  # 无 soundfile 时保持原行为
    sf = None


def _soundfile_load(uri, frame_offset=0, num_frames=-1, normalize=True,
                    channels_first=True, format=None, buffer_size=None, backend=None):
    if sf is None:
        raise ImportError("soundfile required for voice_engine audio patch")
    if torch.is_tensor(uri):  # 已加载的 tensor 直接返回（兼容内部调用）
        return uri, 22050
    if isinstance(uri, bytes):
        f = io.BytesIO(uri)
    else:
        f = uri
    n = int(num_frames) if num_frames is not None and num_frames > 0 else -1
    data, sr = sf.read(f, dtype="float32", always_2d=True, frames=n)
    if frame_offset > 0:
        data = data[int(frame_offset):]
    wav = torch.from_numpy(data.T)  # (channels, frames)
    if not normalize:
        wav = wav * 32768.0
    return wav, sr


def _soundfile_save(uri, src, sample_rate, channels_first=True, format=None,
                    encoding=None, bits_per_sample=None, buffer_size=None,
                    backend=None, compression=None):
    if sf is None:
        raise ImportError("soundfile required for voice_engine audio patch")
    data = src.numpy()
    if not channels_first and data.ndim == 2:
        data = data.T
    if data.ndim == 2:
        data = data.T  # soundfile 期望 (frames, channels)
    data = data.astype("float32")
    fmt = "WAV" if not isinstance(uri, str) else None
    sf.write(uri, data, int(sample_rate), format=fmt)


def patch_audio():
    """替换 torchaudio.load/save 为 soundfile 实现（幂等）"""
    if sf is None:
        return
    if getattr(torchaudio.load, "_patched", False):
        return
    torchaudio.load = _soundfile_load
    torchaudio.load._patched = True
    torchaudio.save = _soundfile_save
    torchaudio.save._patched = True

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


TARGET_SR = 16000


def _read_audio_any(in_path: str) -> Tuple[np.ndarray, int]:
    try:
        data, sr = sf.read(in_path, always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float32, copy=False)
        return data, int(sr)
    except Exception as e:
        raise


def _resample_if_needed(y: np.ndarray, sr: int, target_sr: int = TARGET_SR) -> np.ndarray:
    if sr == target_sr:
        return y
    # Use polyphase resampling for quality and speed
    gcd = np.gcd(sr, target_sr)
    up = target_sr // gcd
    down = sr // gcd
    return resample_poly(y, up, down).astype(np.float32, copy=False)


def ensure_wav_mono_16k(in_path: str, out_path: str) -> None:
    """Convert input audio to PCM16 WAV mono 16k. If direct read fails, try ffmpeg if available."""
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    try:
        y, sr = _read_audio_any(in_path)
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("无法解析该音频格式，请上传 WAV/PCM，或安装 ffmpeg 后重试")
        cmd = [ffmpeg, "-y", "-i", in_path, "-ac", "1", "-ar", str(TARGET_SR), "-sample_fmt", "s16", out_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    y = _resample_if_needed(y, sr, TARGET_SR)
    sf.write(out_path, y, TARGET_SR, subtype="PCM_16")


def get_wav_duration(path: str) -> float:
    info = sf.info(path)
    if info.frames and info.samplerate:
        return float(info.frames) / float(info.samplerate)
    data, sr = sf.read(path, always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return float(len(data)) / float(sr)

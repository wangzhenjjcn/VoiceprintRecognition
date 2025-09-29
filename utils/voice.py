from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import numpy as np
import torch

_BASE = Path(__file__).resolve().parent.parent
_MODEL_DIR = _BASE / "data" / "models"
_MODEL_DIR.mkdir(parents=True, exist_ok=True)


# -------- 声纹嵌入（SpeechBrain ECAPA） --------
_classifier = None

def _load_classifier():
    global _classifier
    if _classifier is None:
        from speechbrain.pretrained import EncoderClassifier
        _classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(_MODEL_DIR / "ecapa"),
            run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"},
        )
    return _classifier


def extract_embedding(wav_path: str) -> np.ndarray:
    import soundfile as sf
    data, sr = sf.read(wav_path, always_2d=False)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    wav = torch.from_numpy(data.astype(np.float32)).unsqueeze(0)
    classifier = _load_classifier()
    with torch.no_grad():
        emb = classifier.encode_batch(wav)
    emb = emb.squeeze(0).squeeze(0).cpu().numpy()
    return emb


# -------- XTTS 与 Edge TTS --------
_xtts = None

def _normalize_language(lang: str) -> str:
    if not lang:
        return "zh-cn"
    lang = lang.lower()
    aliases = {
        "zh": "zh-cn",
        "zh_cn": "zh-cn",
        "zh-cn": "zh-cn",
        "en": "en",
        "en-us": "en",
        "ja": "ja",
        "jp": "ja",
    }
    return aliases.get(lang, lang)


def _load_xtts():
    global _xtts
    if _xtts is not None:
        return _xtts
    try:
        from TTS.api import TTS  # type: ignore
    except Exception as e:
        raise RuntimeError("未检测到可用的 XTTS 库。请使用 requirements-xtts.txt 在 Python 3.10-3.12 环境安装 TTS 包。")
    _xtts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
    return _xtts


def synthesize_with_xtts(text: str, ref_wav: str, out_path: str, language: str = "zh-cn") -> None:
    language = _normalize_language(language)
    tts = _load_xtts()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    tts.tts_to_file(text=text, file_path=out_path, speaker_wav=ref_wav, language=language)


# -------- Fallback: Edge TTS（联网） --------
async def _edge_tts_async(text: str, out_path: str, voice: str = "zh-CN-XiaoxiaoNeural"):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])


def synthesize_with_edge_tts(text: str, out_path: str, voice: str = "zh-CN-XiaoxiaoNeural") -> None:
    asyncio.run(_edge_tts_async(text=text, out_path=out_path, voice=voice))

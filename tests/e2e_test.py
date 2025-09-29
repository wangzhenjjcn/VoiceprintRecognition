import io
import os
import time
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import requests

BASE = "http://127.0.0.1:5000"


def gen_test_wav(path: str, seconds: float = 2.0, sr: int = 16000):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = 0.2 * np.sin(2 * np.pi * 1000 * t)
    sf.write(path, y.astype(np.float32), sr, subtype="PCM_16")


def main():
    tmp_dir = Path("data/tmp"); tmp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = tmp_dir / "test.wav"
    gen_test_wav(str(wav_path))

    with open(wav_path, "rb") as f:
        files = {"audio": ("test.wav", f, "audio/wav")}
        data = {"skip_embedding": "1"}
        r = requests.post(BASE + "/api/upload", files=files, data=data, timeout=60)
    r.raise_for_status()
    j = r.json()
    assert j.get("ok"), j
    pid = j["profile_id"]

    r2 = requests.post(BASE + "/api/synthesize", json={
        "profile_id": pid,
        "text": "你好，我是测试语音。",
        "language": "zh-cn"
    }, timeout=120)
    r2.raise_for_status()
    j2 = r2.json()
    assert j2.get("ok"), j2

    url = BASE + j2["url"]
    r3 = requests.get(url, timeout=60)
    r3.raise_for_status()
    assert int(r3.headers.get("Content-Length", "1")) > 1000
    print("OK:", url)


if __name__ == "__main__":
    main()

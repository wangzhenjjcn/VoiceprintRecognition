import os
import json
import uuid
import time
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory, abort

from utils.audio import ensure_wav_mono_16k, get_wav_duration
from utils.voice import (
    extract_embedding,
    synthesize_with_xtts,
    synthesize_with_edge_tts,
)

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
PROFILE_DIR = DATA_DIR / "profiles"

for d in [DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, PROFILE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


def _json_error(message: str, status: int = 400):
    resp = jsonify({"ok": False, "error": message})
    resp.status_code = status
    return resp


def _edge_voice_for_language(language: str) -> str:
    lang = (language or "zh-cn").strip().lower()
    if lang.startswith("zh"):
        return "zh-CN-XiaoxiaoNeural"
    if lang.startswith("en"):
        return "en-US-AriaNeural"
    if lang.startswith("ja") or lang.startswith("jp"):
        return "ja-JP-NanamiNeural"
    return "zh-CN-XiaoxiaoNeural"


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/upload")
def api_upload():
    if "audio" not in request.files:
        return _json_error("缺少音频文件字段 'audio'")

    file = request.files["audio"]
    if file.filename == "":
        return _json_error("未选择文件")

    ext = os.path.splitext(file.filename)[1].lower() or ".wav"
    raw_id = str(uuid.uuid4())
    raw_path = UPLOAD_DIR / f"{raw_id}{ext}"
    file.save(raw_path)

    norm_path = UPLOAD_DIR / f"{raw_id}.wav"
    try:
        ensure_wav_mono_16k(str(raw_path), str(norm_path))
    except Exception as e:
        return _json_error(f"音频转码失败: {e}")

    try:
        duration = get_wav_duration(str(norm_path))
    except Exception:
        duration = None

    skip_embed_env = os.environ.get("SKIP_EMBEDDING", "").strip().lower() in {"1", "true", "yes"}
    skip_embed_req = (request.form.get("skip_embedding") or "").strip().lower() in {"1", "true", "yes"}

    emb_path = None
    if not (skip_embed_env or skip_embed_req):
        try:
            embedding = extract_embedding(str(norm_path))
            emb_path = PROFILE_DIR / f"{raw_id}.npy"
            import numpy as np
            np.save(emb_path, embedding)
        except Exception as e:
            emb_path = None
            app.logger.warning(f"提取声纹嵌入失败: {e}")

    profile = {
        "id": raw_id,
        "created_at": int(time.time()),
        "ref_wav": str(norm_path.relative_to(BASE_DIR)),
        "embedding": str(emb_path.relative_to(BASE_DIR)) if emb_path else None,
        "duration_sec": duration,
    }
    profile_path = PROFILE_DIR / f"{raw_id}.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    return jsonify({"ok": True, "profile_id": raw_id, "duration_sec": duration})


@app.post("/api/synthesize")
def api_synthesize():
    data = request.get_json(silent=True) or request.form
    profile_id = (data.get("profile_id") or "").strip()
    text = (data.get("text") or "").strip()
    language = (data.get("language") or "zh-cn").strip()

    if not profile_id:
        return _json_error("缺少 profile_id")
    if not text:
        return _json_error("请输入要合成的文字")

    profile_path = PROFILE_DIR / f"{profile_id}.json"
    if not profile_path.exists():
        return _json_error("找不到对应的声纹配置，请先上传/录制音频建模")

    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    ref_wav_rel = profile.get("ref_wav")
    ref_wav = (BASE_DIR / ref_wav_rel).resolve() if ref_wav_rel else None
    if not ref_wav or not ref_wav.exists():
        return _json_error("参考音频缺失或已被删除")

    out_id = str(uuid.uuid4())
    out_wav = OUTPUT_DIR / f"{out_id}.wav"

    method = None
    try:
        synthesize_with_xtts(text=text, ref_wav=str(ref_wav), out_path=str(out_wav), language=language)
        method = "xtts_v2"
        out_file = out_wav
    except Exception as e:
        app.logger.warning(f"XTTS 合成失败，回退到 Edge TTS: {e}")
        out_mp3 = OUTPUT_DIR / f"{out_wav.stem}.mp3"
        voice = _edge_voice_for_language(language)
        synthesize_with_edge_tts(text=text, out_path=str(out_mp3), voice=voice)
        method = "edge_tts"
        out_file = out_mp3

    return jsonify({
        "ok": True,
        "file": out_file.name,
        "url": f"/outputs/{out_file.name}",
        "method": method,
    })


@app.get("/outputs/<path:filename>")
def get_output(filename: str):
    safe_path = (OUTPUT_DIR / filename).resolve()
    if not safe_path.exists() or (OUTPUT_DIR not in safe_path.parents and safe_path != OUTPUT_DIR):
        abort(404)
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=False)


@app.get("/uploads/<path:filename>")
def get_upload(filename: str):
    safe_path = (UPLOAD_DIR / filename).resolve()
    if not safe_path.exists() or (UPLOAD_DIR not in safe_path.parents and safe_path != UPLOAD_DIR):
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

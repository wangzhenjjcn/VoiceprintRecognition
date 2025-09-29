# VoiceprintRecognition Web 服务

基于 Flask 的端到端示例：
- 录音/上传音频，自动转码为 WAV 单声道 16k
- 提取声纹嵌入（SpeechBrain ECAPA）并保存 Profile（可通过环境变量或表单参数跳过，加速测试）
- 文本转语音：优先尝试 Coqui XTTS v2 零样本克隆；若不可用或失败，回退到 Edge TTS（不克隆，仅按语言选择合成音色）
- 前端可播放与下载生成的音频

## 环境要求
- Python 3.13（默认，仅 Edge TTS 回退可用）或 Python 3.10–3.12（可启用 XTTS）
- Windows 10/11，建议使用虚拟环境

## 安装
```bash
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

## 运行
```bash
# 可设置跳过嵌入提取（更快，少下载模型）
$env:SKIP_EMBEDDING="1"
python app.py
```
访问 `http://localhost:5000`。

## 启用零样本克隆（XTTS）
- 需要 Python 3.10–3.12。请使用该版本新建虚拟环境。
- 安装可选依赖：
```bash
pip install -r requirements-xtts.txt
```
- 启动后，后端会动态导入 XTTS 并下载模型（首次较慢）。合成成功时返回的 `method` 为 `xtts_v2`，表示使用了克隆；否则回退为 `edge_tts`。

## 语言与声音映射（回退模式）
- zh-cn → zh-CN-XiaoxiaoNeural
- en → en-US-AriaNeural
- ja → ja-JP-NanamiNeural

## 端到端测试
确保服务已启动：
```bash
python tests/e2e_test.py
```
测试会：生成本地 WAV → 上传(跳过嵌入) → 合成文本 → 校验返回可播放链接。

## 目录结构
```
app.py
requirements.txt
requirements-xtts.txt
static/
  css/style.css
  js/app.js
templates/
  index.html
utils/
  audio.py
  voice.py
  __init__.py
tests/
  e2e_test.py
data/
  uploads/
  outputs/
  profiles/
  models/
```

## 常见问题
- 首次合成慢：XTTS 模型体积大，下载与加载耗时；失败会回退到 Edge TTS。
- CPU 运行慢：如有 NVIDIA GPU，可在 Python 3.10–3.12 环境安装匹配 CUDA 的 `torch/torchaudio`。
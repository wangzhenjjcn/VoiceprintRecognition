(function () {
  const btnStart = document.getElementById('btnStart');
  const btnStop = document.getElementById('btnStop');
  const btnPlay = document.getElementById('btnPlay');
  const btnUploadRecorded = document.getElementById('btnUploadRecorded');
  const fileInput = document.getElementById('fileInput');
  const btnUploadFile = document.getElementById('btnUploadFile');
  const recordedAudio = document.getElementById('recordedAudio');
  const uploadStatus = document.getElementById('uploadStatus');

  const textInput = document.getElementById('textInput');
  const langSelect = document.getElementById('langSelect');
  const btnSynthesize = document.getElementById('btnSynthesize');
  const synthStatus = document.getElementById('synthStatus');
  const synthAudio = document.getElementById('synthAudio');
  const downloadLink = document.getElementById('downloadLink');

  let mediaStream = null;
  let audioContext = null;
  let sourceNode = null;
  let processor = null;
  let recordedBuffers = [];
  let recordedSampleRate = 44100;
  let profileId = null;

  function setButtonsRecording(isRecording) {
    btnStart.disabled = isRecording;
    btnStop.disabled = !isRecording;
    btnPlay.disabled = isRecording || recordedBuffers.length === 0;
    btnUploadRecorded.disabled = isRecording || recordedBuffers.length === 0;
  }

  function floatTo16BitPCM(float32Array) {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return view;
  }

  function writeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    view.setUint32(0, 0x46464952, false);
    view.setUint32(4, 36 + samples.length * 2, true);
    view.setUint32(8, 0x45564157, false);
    view.setUint32(12, 0x20746d66, false);
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    view.setUint32(36, 0x61746164, false);
    view.setUint32(40, samples.length * 2, true);

    const pcm = floatTo16BitPCM(samples);
    let offset = 44;
    for (let i = 0; i < pcm.byteLength; i++) {
      view.setUint8(offset + i, pcm.getUint8(i));
    }

    return new Blob([view], { type: 'audio/wav' });
  }

  function mergeBuffers(buffers) {
    let length = 0;
    buffers.forEach(b => length += b.length);
    const merged = new Float32Array(length);
    let offset = 0;
    buffers.forEach(b => { merged.set(b, offset); offset += b.length; });
    return merged;
  }

  async function startRecording() {
    recordedBuffers = [];
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      recordedSampleRate = audioContext.sampleRate;
      sourceNode = audioContext.createMediaStreamSource(mediaStream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);
      sourceNode.connect(processor);
      processor.connect(audioContext.destination);
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        recordedBuffers.push(new Float32Array(input));
      };
      setButtonsRecording(true);
      uploadStatus.textContent = '正在录音...';
    } catch (err) {
      console.error(err);
      uploadStatus.textContent = '无法访问麦克风：' + err;
    }
  }

  function stopRecording() {
    if (processor) {
      processor.disconnect();
      processor.onaudioprocess = null;
      processor = null;
    }
    if (sourceNode) {
      sourceNode.disconnect();
      sourceNode = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.stop());
      mediaStream = null;
    }
    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }

    const samples = mergeBuffers(recordedBuffers);
    const wavBlob = writeWAV(samples, recordedSampleRate);
    const url = URL.createObjectURL(wavBlob);
    recordedAudio.src = url;
    recordedAudio.style.display = 'block';

    btnPlay.disabled = false;
    btnUploadRecorded.disabled = false;
    setButtonsRecording(false);
    uploadStatus.textContent = '录音完成，可以回放或上传';
  }

  function playRecording() {
    if (recordedAudio.src) {
      recordedAudio.play();
    }
  }

  async function uploadBlob(blob) {
    uploadStatus.textContent = '正在上传与建模...';
    const form = new FormData();
    form.append('audio', blob, 'recorded.wav');
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: form
    });
    const data = await res.json();
    if (!data.ok) {
      uploadStatus.textContent = '上传失败：' + (data.error || '未知错误');
      return null;
    }
    profileId = data.profile_id;
    uploadStatus.textContent = `建模成功（时长: ${data.duration_sec ? data.duration_sec.toFixed(1) + 's' : '未知'}），可进行合成。`;
    btnSynthesize.disabled = false;
    return data;
  }

  async function uploadRecorded() {
    const blob = await fetch(recordedAudio.src).then(r => r.blob());
    await uploadBlob(blob);
  }

  async function uploadFile() {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      uploadStatus.textContent = '请先选择一个音频文件';
      return;
    }
    await uploadBlob(file);
  }

  async function synthesize() {
    synthStatus.textContent = '正在合成，请稍候...（首次可能较慢）';
    synthAudio.style.display = 'none';
    downloadLink.style.display = 'none';

    const text = textInput.value.trim();
    const language = langSelect.value;

    const res = await fetch('/api/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_id: profileId, text, language })
    });
    const data = await res.json();
    if (!data.ok) {
      synthStatus.textContent = '合成失败：' + (data.error || '未知错误');
      return;
    }
    const url = data.url;
    synthAudio.src = url;
    synthAudio.style.display = 'block';

    downloadLink.href = url;
    downloadLink.style.display = 'inline-block';
    downloadLink.download = data.file;

    synthStatus.textContent = '合成完成' + (data.method ? `（方式：${data.method}）` : '');
  }

  btnStart.addEventListener('click', startRecording);
  btnStop.addEventListener('click', stopRecording);
  btnPlay.addEventListener('click', playRecording);
  btnUploadRecorded.addEventListener('click', uploadRecorded);
  btnUploadFile.addEventListener('click', uploadFile);
  btnSynthesize.addEventListener('click', synthesize);
})();

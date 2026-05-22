"""
avatar_ui.py — Animated virtual interviewer with lip-synced TTS playback.
"""

from __future__ import annotations

import base64
import html
import json

import streamlit.components.v1 as components

# Professional portrait (Unsplash — free to use)
PORTRAIT_URL = (
    "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2"
    "?w=520&h=680&fit=crop&crop=faces&q=80"
)

_AVATAR_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: transparent;
    color: #e8eaf0;
    overflow: hidden;
  }
  .stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px 4px 12px;
  }
  .badge {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #a78bfa;
    margin-bottom: 10px;
  }
  .frame {
    position: relative;
    width: 280px;
    height: 340px;
    border-radius: 20px;
    overflow: hidden;
    background: linear-gradient(160deg, #1a1d2e 0%, #0d0f17 100%);
    border: 2px solid #2a2d40;
    box-shadow: 0 12px 40px rgba(108, 99, 255, 0.25);
  }
  .frame.speaking {
    border-color: #6c63ff;
    box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.35), 0 16px 48px rgba(108, 99, 255, 0.3);
  }
  .portrait {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center 15%;
    transform-origin: center 80%;
    transition: transform 0.08s ease-out;
  }
  .frame.speaking .portrait {
    animation: breathe 2.4s ease-in-out infinite;
  }
  @keyframes breathe {
    0%, 100% { transform: scale(1) translateY(0); }
    50% { transform: scale(1.012) translateY(-2px); }
  }
  .scanline {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      180deg,
      transparent 0%,
      rgba(108, 99, 255, 0.06) 50%,
      transparent 100%
    );
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.3s;
  }
  .frame.speaking .scanline { opacity: 1; animation: scan 2s linear infinite; }
  @keyframes scan {
    0% { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
  }
  .mouth-wrap {
    position: absolute;
    left: 50%;
    bottom: 28%;
    transform: translateX(-50%);
    width: 72px;
    height: 28px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    pointer-events: none;
  }
  .mouth {
    width: 44px;
    height: 6px;
    background: rgba(30, 20, 25, 0.75);
    border-radius: 50% 50% 45% 45% / 60% 60% 100% 100%;
    transition: height 0.05s ease-out, width 0.05s ease-out;
    box-shadow: inset 0 -2px 4px rgba(0,0,0,0.3);
  }
  .frame.speaking .mouth {
    background: rgba(50, 30, 38, 0.85);
  }
  .eyes {
    position: absolute;
    top: 38%;
    left: 50%;
    transform: translateX(-50%);
    width: 100px;
    height: 12px;
    pointer-events: none;
  }
  .eye {
    position: absolute;
    width: 18px;
    height: 4px;
    background: rgba(0,0,0,0.15);
    border-radius: 50%;
    top: 0;
  }
  .eye.left { left: 18px; }
  .eye.right { right: 18px; }
  .blink .eye {
    animation: blink 4s infinite;
  }
  @keyframes blink {
    0%, 46%, 48%, 100% { transform: scaleY(1); }
    47% { transform: scaleY(0.1); }
  }
  .live-pill {
    position: absolute;
    top: 12px;
    right: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,0,0,0.55);
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    opacity: 0;
    transition: opacity 0.25s;
  }
  .frame.speaking .live-pill { opacity: 1; }
  .dot {
    width: 8px;
    height: 8px;
    background: #ef4444;
    border-radius: 50%;
    animation: pulse 1s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.85); }
  }
  .name-plate {
    margin-top: 14px;
    text-align: center;
  }
  .name-plate h3 {
    font-size: 1.15rem;
    font-weight: 700;
    color: #fff;
  }
  .name-plate p {
    font-size: 0.8rem;
    color: #888;
    margin-top: 2px;
  }
  .caption {
    margin-top: 12px;
    width: 100%;
    max-width: 300px;
    min-height: 52px;
    padding: 10px 12px;
    background: #13151f;
    border: 1px solid #1e2230;
    border-radius: 10px;
    font-size: 0.82rem;
    line-height: 1.45;
    color: #c4c8d4;
  }
  .caption.empty { color: #555; font-style: italic; }
  .controls {
    margin-top: 10px;
    display: flex;
    gap: 8px;
    justify-content: center;
  }
  button {
    background: linear-gradient(135deg, #6c63ff, #8b5cf6);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }
  button:hover { opacity: 0.9; }
  button.secondary {
    background: #1e2230;
    border: 1px solid #2a2d40;
  }
  .status {
    margin-top: 8px;
    font-size: 0.75rem;
    color: #6c63ff;
    font-weight: 600;
    min-height: 1.2em;
  }
</style>
</head>
<body>
<div class="stage">
  <div class="badge">Live interviewer</div>
  <div class="frame blink" id="frame">
    <img class="portrait" id="portrait" src="__PORTRAIT__" alt="ARIA interviewer"
         onerror="this.onerror=null;this.src=__FALLBACK_SVG__;"/>
    <div class="scanline"></div>
    <div class="eyes">
      <div class="eye left"></div>
      <div class="eye right"></div>
    </div>
    <div class="mouth-wrap"><div class="mouth" id="mouth"></div></div>
    <div class="live-pill"><span class="dot"></span> Speaking</div>
  </div>
  <div class="name-plate">
    <h3>__NAME__</h3>
    <p>Senior Technical Interviewer</p>
  </div>
  <div class="caption __CAPTION_CLASS__" id="caption">__CAPTION__</div>
  <div class="status" id="status">__STATUS__</div>
  <div class="controls">
    <button type="button" id="replay" __REPLAY_DISABLED__>Replay voice</button>
    <button type="button" class="secondary" id="mute">Mute</button>
  </div>
  <audio id="audio" preload="auto" data-instance="__INSTANCE__" __AUDIO_SRC__></audio>
</div>
<script>
(function() {
  const instanceId = "__INSTANCE__";
  const frame = document.getElementById('frame');
  const mouth = document.getElementById('mouth');
  const statusEl = document.getElementById('status');
  const audio = document.getElementById('audio');
  const replayBtn = document.getElementById('replay');
  const muteBtn = document.getElementById('mute');
  const hasAudio = __HAS_AUDIO__;

  let ctx = null, analyser = null, source = null, raf = null, muted = false;

  function setSpeaking(on) {
    frame.classList.toggle('speaking', on);
    statusEl.textContent = on ? 'Asking question…' : (hasAudio ? 'Ready' : 'Waiting for audio');
  }

  function animateMouth() {
    if (!analyser || audio.paused || audio.ended) {
      mouth.style.height = '6px';
      mouth.style.width = '44px';
      if (raf) cancelAnimationFrame(raf);
      raf = null;
      return;
    }
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i];
    const avg = sum / data.length / 255;
    const h = 6 + avg * 22;
    const w = 44 + avg * 18;
    mouth.style.height = h + 'px';
    mouth.style.width = w + 'px';
    raf = requestAnimationFrame(animateMouth);
  }

  function setupAudio() {
    if (!hasAudio) return;
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      source = ctx.createMediaElementSource(audio);
      analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyser.connect(ctx.destination);
    } catch (e) {
      console.warn('WebAudio setup failed', e);
    }
  }

  function play() {
    if (!hasAudio) return;
    if (ctx && ctx.state === 'suspended') ctx.resume();
    audio.currentTime = 0;
    audio.play().then(() => {
      setSpeaking(true);
      animateMouth();
    }).catch(() => setSpeaking(false));
  }

  audio.addEventListener('ended', () => {
    setSpeaking(false);
    mouth.style.height = '6px';
    mouth.style.width = '44px';
    if (raf) cancelAnimationFrame(raf);
  });

  audio.addEventListener('pause', () => {
    if (!audio.ended) return;
    setSpeaking(false);
  });

  replayBtn.addEventListener('click', play);
  muteBtn.addEventListener('click', () => {
    muted = !muted;
    audio.muted = muted;
    muteBtn.textContent = muted ? 'Unmute' : 'Mute';
  });

  if (hasAudio) {
    setupAudio();
    audio.addEventListener('canplaythrough', play, { once: true });
    if (audio.readyState >= 3) play();
  } else {
    setSpeaking(false);
    statusEl.textContent = 'Text-only mode';
  }
})();
</script>
</body>
</html>
"""


def render_interviewer_avatar(
    audio_bytes: bytes | None = None,
    speech_text: str = "",
    interviewer_name: str = "ARIA",
    height: int = 580,
    instance_id: str = "0",
) -> None:
    """Render animated interviewer with optional lip-synced TTS."""
    caption = (speech_text or "").strip()
    caption_class = "" if caption else "empty"
    if not caption:
        caption = "Your interviewer will speak the question aloud."

    if audio_bytes:
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        audio_src = f'src="data:audio/mpeg;base64,{audio_b64}"'
        has_audio = "true"
        replay_disabled = ""
        status = "Loading voice…"
    else:
        audio_src = ""
        has_audio = "false"
        replay_disabled = "disabled"
        status = "No audio — read the question on the right"

    fallback_svg = (
        "data:image/svg+xml,"
        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 260'%3E"
        "%3Crect fill='%231a1d2e' width='200' height='260'/%3E"
        "%3Ccircle fill='%23c4a882' cx='100' cy='88' r='52'/%3E"
        "%3Cellipse fill='%236c63ff' cx='100' cy='230' rx='70' ry='55'/%3E"
        "%3C/svg%3E"
    )

    html_out = (
        _AVATAR_HTML.replace("__PORTRAIT__", PORTRAIT_URL)
        .replace("__FALLBACK_SVG__", json.dumps(fallback_svg))
        .replace("__INSTANCE__", html.escape(str(instance_id)))
        .replace("__NAME__", html.escape(interviewer_name))
        .replace("__CAPTION__", html.escape(caption[:420] + ("…" if len(caption) > 420 else "")))
        .replace("__CAPTION_CLASS__", caption_class)
        .replace("__STATUS__", html.escape(status))
        .replace("__AUDIO_SRC__", audio_src)
        .replace("__HAS_AUDIO__", has_audio)
        .replace("__REPLAY_DISABLED__", replay_disabled)
    )

    components.html(html_out, height=height, scrolling=False)


def render_interviewer_preview(height: int = 420) -> None:
    """Static avatar on setup screen."""
    render_interviewer_avatar(
        audio_bytes=None,
        speech_text="Hi! I'm your AI interviewer. Start the session and I'll ask you questions face to face.",
        height=height,
    )

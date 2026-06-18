from __future__ import annotations

import json


def output_html(token: str) -> str:
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Maya Meet Output</title></head>
<body style="margin:0;background:#101114;color:#f5f5f5;font:32px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:grid;place-items:center;height:100vh;">
<div id="status" style="max-width:1040px;padding:56px;line-height:1.28;text-align:center;white-space:pre-wrap;">Maya</div>
<audio id="maya-audio" autoplay playsinline preload="auto"></audio>
<script>
const token = {json.dumps(token)};
const params = new URLSearchParams(window.location.search);
const sessionId = params.get('session_id') || 'recall_default';
const statusEl = document.getElementById('status');
const audio = document.getElementById('maya-audio');
async function report(status, reason) {{
  try {{
    await fetch('/meet/output/playback?token=' + encodeURIComponent(token) + '&session_id=' + encodeURIComponent(sessionId), {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{status: status, reason_code: reason || status}})
    }});
  }} catch (error) {{
    console.error('maya output report failed', error);
  }}
}}
function setStatus(text) {{
  if (statusEl) statusEl.textContent = text;
}}
async function poll() {{
  try {{
    const response = await fetch('/meet/output/next?token=' + encodeURIComponent(token) + '&session_id=' + encodeURIComponent(sessionId), {{cache: 'no-store'}});
    const data = await response.json();
    if (data.utterance && data.utterance.audio_url) {{
      const utteranceId = data.utterance.id || 'playback';
      let started = false;
      setStatus(data.utterance.preview || 'Maya speaking');
      audio.pause();
      audio.currentTime = 0;
      audio.src = new URL(data.utterance.audio_url, window.location.origin).href + '&cb=' + Date.now();
      audio.onplaying = () => {{
        started = true;
        report('playback_started', utteranceId);
      }};
      audio.onended = () => {{
        setStatus('Maya');
        report('playback_ended', data.utterance.id || 'playback_ended');
      }};
      audio.onerror = () => {{
        setStatus('Maya output failed');
        report('playback_failed', data.utterance.id || 'playback_failed');
      }};
      audio.load();
      await audio.play();
      setTimeout(() => {{
        if (!started && !audio.paused) {{
          report('playback_started', utteranceId);
        }}
      }}, 750);
    }}
  }} catch (error) {{
    await report('playback_failed', String(error));
    console.error('maya output poll failed', error);
  }} finally {{
    setTimeout(poll, 1000);
  }}
}}
poll();
</script>
</body>
</html>"""

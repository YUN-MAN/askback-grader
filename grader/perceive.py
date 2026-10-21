"""Stage 0：把 mp4 變成文字與圖片（探測、抽幀、ASR、畫面描述）。"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from . import llm


def _run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(video: Path) -> Dict[str, Any]:
    r = _run("ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", str(video))
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失敗: {video}")
    d = json.loads(r.stdout)
    v = next((s for s in d.get("streams", []) if s["codec_type"] == "video"), {})
    return {"duration": float(d["format"]["duration"]),
            "has_video": bool(v), "has_audio": any(s["codec_type"] == "audio" for s in d["streams"]),
            "width": v.get("width"), "height": v.get("height")}


def extract_frames(video: Path, out_dir: Path, n: int = 8) -> List[Path]:
    """均勻抽 n 張 JPEG（長邊 960）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = probe(video)["duration"]
    frames = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        p = out_dir / f"frame_{i:02d}.jpg"
        _run("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
             "-frames:v", "1", "-vf", "scale='min(960,iw)':-2", str(p))
        if p.exists():
            frames.append(p)
    return frames


def transcribe(video: Path, out_dir: Path) -> List[Dict[str, Any]]:
    """回傳 [{start,end,text}]。用 faster-whisper；沒安裝時回傳空 list 並記錄原因。"""
    cache = out_dir / "transcript.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return []
    model = WhisperModel(os.environ.get("GRADER_WHISPER_MODEL", "large-v3"), compute_type="auto")
    # 自己用 ffmpeg 解碼成 16k mono float32，避開 faster-whisper 內建 PyAV 的版本相容問題
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-f", "f32le", "-ac", "1",
                          "-ar", "16000", "-"], capture_output=True).stdout
    segs, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), language="zh", vad_filter=True,
                                 initial_prompt=os.environ.get("GRADER_ASR_PROMPT", "以下是台灣國小到高中的繁體中文教學影片旁白。"))
    out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
    out_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


_DESCRIBE_SYS = ("你是影片畫面轉述員。對每張畫面，用繁體中文簡短寫出：畫面上的文字與算式、圖形或角色、"
                 "是否看得到「AI 生成教學示範，非原講者本人」這行標示。只描述看到的，不要推論或解題。")


def describe_frames(frames: List[Path], out_dir: Path) -> Dict[str, Any]:
    """回傳 {"descriptions": [...], "badge_visible": bool|None}；mock 時 badge_visible 為 None（未驗證）。"""
    cache = out_dir / "frames.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    if llm.provider_for("vision") == "mock":
        res = {"descriptions": [f"（mock）第 {i + 1} 張畫面" for i in range(len(frames))], "badge_visible": None}
    else:
        user = ("依序描述這幾張畫面。輸出 JSON：{\"descriptions\": [每張一句], "
                "\"badge_visible\": 是否每張都看得到 AI 生成標示(true/false)}")
        res = llm.chat_json("vision", _DESCRIBE_SYS, user, images=frames)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def perceive(video: Path, work: Path, n_frames: int = 8) -> Dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    frames = extract_frames(video, work / "frames", n_frames)
    segs = transcribe(video, work)
    desc = describe_frames(frames, work)
    return {"info": info, "frames": [str(p) for p in frames], "segments": segs,
            "transcript": " ".join(s["text"] for s in segs),
            "descriptions": desc.get("descriptions", []), "badge_visible": desc.get("badge_visible")}

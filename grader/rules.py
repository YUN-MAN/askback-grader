"""Stage 1：規則檢查（硬性條件 + 影音品質）。不需要任何 LLM。

回傳每項檢查的 pass/fail、數值與理由，並換算成 0–100 的影音品質分。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

MIN_S, MAX_S = 30.0, 90.0


def _run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _mean_volume(video: Path) -> Optional[float]:
    err = _run("ffmpeg", "-hide_banner", "-i", str(video), "-af", "volumedetect", "-vn", "-f", "null", "-").stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", err)
    return float(m[1]) if m else None


def _has_black(video: Path) -> bool:
    err = _run("ffmpeg", "-hide_banner", "-i", str(video), "-vf",
               "fps=1/5,blackdetect=d=4:pix_th=0.02", "-an", "-f", "null", "-").stderr
    return "black_start" in err


def _scene_changes(video: Path) -> int:
    """場景變化次數；整支近乎靜態圖時為 0 或很少。"""
    err = _run("ffmpeg", "-hide_banner", "-i", str(video), "-vf",
               "fps=4,select='gt(scene,0.02)',showinfo", "-an", "-f", "null", "-").stderr
    return err.count("pts_time:")


def check(info: Dict[str, Any], video: Path, *, transcript: str = "",
          badge_visible: Optional[bool] = None) -> Dict[str, Any]:
    """info 來自 perceive.probe。badge_visible 為 None 表示尚未驗證（mock），不扣分但標註。"""
    dur = info["duration"]
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: Optional[bool], value: Any, reason: str, weight: float, hard: bool = False) -> None:
        checks.append({"name": name, "ok": ok, "value": value, "reason": reason,
                       "weight": weight, "hard": hard})

    add("has_video", info["has_video"], None, "需要有畫面", 1, hard=True)
    add("has_audio", info["has_audio"], None, "需要有旁白語音", 1, hard=True)
    add("duration", MIN_S <= dur <= MAX_S, round(dur, 1), f"長度 {dur:.1f}s，要求 {MIN_S:.0f}–{MAX_S:.0f}s", 2, hard=True)

    vol = _mean_volume(video) if info["has_audio"] else None
    add("audible", vol is not None and vol > -45, vol,
        "平均音量過低（接近靜音）" if (vol is None or vol <= -45) else f"平均音量 {vol} dB", 2)
    add("loudness_range", vol is not None and -35 <= vol <= -10, vol,
        f"平均音量 {vol} dB，建議 -35～-10 dB" if vol is not None else "無法量測", 1)

    add("no_black_stretch", not _has_black(video), None, "有長時間全黑畫面" if _has_black(video) else "無長時間全黑", 1)
    sc = _scene_changes(video)
    add("not_static", sc >= 3, sc, f"場景變化 {sc} 次" + ("，畫面幾乎靜止" if sc < 3 else ""), 1)
    add("resolution", (info["height"] or 0) >= 480, f'{info["width"]}x{info["height"]}',
        "解析度至少 480p", 1)

    if transcript:
        cps = len(re.sub(r"\s", "", transcript)) / dur
        add("speech_rate", 2.5 <= cps <= 7.0, round(cps, 2),
            f"語速 {cps:.1f} 字/秒，建議 2.5–7（太快學生跟不上，太慢拖沓）", 1)

    add("ai_badge", badge_visible, badge_visible,
        {True: "每張抽樣畫面都有 AI 生成標示", False: "缺少「AI 生成教學示範，非原講者本人」標示",
         None: "尚未驗證（需要視覺模型）"}[badge_visible], 2, hard=True)

    scored = [c for c in checks if c["ok"] is not None]
    got = sum(c["weight"] for c in scored if c["ok"])
    total = sum(c["weight"] for c in scored)
    hard_fail = [c["name"] for c in checks if c["hard"] and c["ok"] is False]
    return {"score": round(100 * got / total, 1) if total else 0.0,
            "hard_fail": hard_fail, "checks": checks,
            "unverified": [c["name"] for c in checks if c["ok"] is None]}

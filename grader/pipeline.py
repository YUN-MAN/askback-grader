from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from . import llm, perceive, rules, student, review, aggregate


def score(video: Path, work_root: Path, k: int = 5, n_frames: int = 8) -> Dict[str, Any]:
    work = work_root / video.stem
    p = perceive.perceive(video, work, n_frames)
    r = rules.check(p["info"], video, transcript=p["transcript"], badge_visible=p["badge_visible"])
    mock = any(llm.provider_for(x) == "mock" for x in llm.ROLES)
    s = student.run(p, k=k)
    rev = review.review(p)
    out = {"video": str(video), "info": p["info"], "rules": r, "student": s, "review": rev,
           "result": aggregate.aggregate(r, s, rev, mock=mock)}
    work.mkdir(parents=True, exist_ok=True)
    (work / "result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

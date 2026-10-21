"""聚合：四個課程評分項 → 0–100 總分與理由。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

WEIGHTS = {"correctness": 0.35, "responsiveness": 0.30, "continuity": 0.20, "av_quality": 0.15}
HARD_FAIL_CAP = 30.0


def aggregate(rules: Dict[str, Any], student: Dict[str, Any], rev: Dict[str, Any], *, mock: bool) -> Dict[str, Any]:
    reasons: List[str] = []
    comp: Dict[str, Optional[float]] = {}

    comp["correctness"] = rev["correctness"]["score"]
    reasons.append(f"內容正確 {comp['correctness']}：{rev['correctness']['reason']}")
    for e in rev.get("errors", []):
        reasons.append(f"  錯誤({e.get('severity')}) {e.get('where')}：{e.get('what')}")

    # 回應提問與適齡：前後測增益(60%) + 審查的 responsiveness / grade_fit(40%)；沒有增益時退回審查
    qual = (rev["responsiveness"]["score"] + rev["grade_fit"]["score"]) / 2
    gain = student.get("gain_score")
    if gain is None:
        comp["responsiveness"] = qual
        reasons.append(f"回應提問 {qual:.1f}（僅審查；前後測無有效題：{student.get('note', '')}）")
    else:
        comp["responsiveness"] = round(0.6 * gain + 0.4 * qual, 1)
        reasons.append(f"回應提問 {comp['responsiveness']}：AI 小明增益 {gain}"
                       f"（有效題 {student.get('n_valid')}，直接迷思題修正率 {student.get('fixed')}），審查 {qual:.1f}")

    comp["continuity"] = rev["continuity"]["score"]
    reasons.append(f"延續教法 {comp['continuity']}（無原片，僅估計）：{rev['continuity']['reason']}")
    comp["av_quality"] = rules["score"]
    reasons.append(f"影音品質 {rules['score']}：" + (
        "未通過 " + "、".join(rules["hard_fail"]) if rules["hard_fail"] else "硬性條件通過")
        + (f"；未驗證 {', '.join(rules['unverified'])}" if rules["unverified"] else ""))

    total = sum(WEIGHTS[k] * float(v) for k, v in comp.items())
    if rules["hard_fail"]:
        total = min(total, HARD_FAIL_CAP)
        reasons.append(f"硬性條件未過，總分上限 {HARD_FAIL_CAP}")
    return {"score": round(total, 1), "components": comp, "weights": WEIGHTS,
            "reasons": reasons, "mock": mock}

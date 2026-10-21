"""Stage 3：內容正確性、回應提問、適齡與銜接審查（judge 角色）。"""

from __future__ import annotations

from typing import Any, Dict

from . import llm

_SYS = """你是嚴格的教學影片審查員，審查一支為回應學生提問而做的 30–90 秒補充教學影片（繁體中文）。
依下列四項各給 0–100 分並附一句理由；找出所有科學／數學錯誤（含口誤、錯誤的圖示、單位錯誤），逐條列出：
- correctness：解釋是否正確（有任何實質錯誤，上限 40 分）
- responsiveness：是否真的解開影片開頭複述的那個疑問，而不是另講一套
- grade_fit：用詞與深度是否適合該年段
- continuity：是否沿用原課程的教法／舉例，並明確把學生帶回原課程（沒有原片可比對時，只看「有沒有明確銜接回去」）
只輸出 JSON：{"correctness":{"score":int,"reason":str},"responsiveness":{...},"grade_fit":{...},
"continuity":{...},"errors":[{"where":str,"what":str,"severity":"minor|major"}]}"""


def review(perceived: Dict[str, Any]) -> Dict[str, Any]:
    user = (f"【逐字稿】\n{perceived['transcript'] or '（無）'}\n\n【畫面描述】\n"
            + "\n".join(f"{i + 1}. {d}" for i, d in enumerate(perceived["descriptions"])))
    mock = {k: {"score": 70, "reason": "（mock）"} for k in ("correctness", "responsiveness", "grade_fit", "continuity")}
    mock["errors"] = []
    res = llm.chat_json("judge", _SYS, user, mock=mock, temperature=0.0)
    majors = [e for e in res.get("errors", []) if e.get("severity") == "major"]
    if majors:
        res["correctness"]["score"] = min(res["correctness"]["score"], 40)
    return res

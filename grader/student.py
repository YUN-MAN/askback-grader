"""Stage 2：AI 小明前後測。

隔離原則（程式層面，不靠 prompt 約束）：
  * author 看得到全部影片內容，負責還原問題與出題；
  * student 只拿到「迷思描述 + 題目」（基線），或再加上「影片文字化內容」（看影片後）；
    永遠看不到答案、出題者的說明或其他題目；
  * judge 不看答案鍵，獨立解題；與答案鍵不符的題目整題剔除。
基線與看影片後各取樣 k 次，增益 = 看影片後答對率 − 基線答對率（只計基線會答錯的題）。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from . import llm

LETTERS = "ABCD"

_AUTHOR_SYS = """你是教學評量設計者。下面是一支「補充教學影片」的逐字稿與畫面描述。
這支影片是為了回應某位學生看原課程時的提問而做的。請：
1. 從影片還原：學生的問題(question)、學生背後的迷思(misconception，一句話寫出錯誤推理)、影片教的概念(concept)。
2. 出 4 題「遷移題」四選一：換數字或情境，不能與影片裡的例題相同。其中第 1 題必須直接重現該迷思，
   而且迷思會導向的錯誤答案要放在選項裡(misconception_choice)。
3. 每題給出正確選項(answer)。題目必須只用國小到高中範圍、與影片同年段的知識，並且在影片內容為真的前提下有唯一正解。
只輸出 JSON：{"question":str,"misconception":str,"concept":str,"grade":str,
"items":[{"q":str,"choices":[str,str,str,str],"answer":0-3,"misconception_choice":0-3 或 null}]}"""

_STUDENT_SYS = """你是台灣的國小六年級學生小明，口語、直覺。你心中有一個想法（可能是錯的）：
「{misconception}」
請依自己的想法與你所知道的作答。{video}只回答選項字母（A/B/C/D），不要解釋。"""

_JUDGE_SYS = "你是嚴謹的解題者。獨立解下面的四選一題，不要參考任何外部提示。只回答選項字母 A/B/C/D。"


def author(perceived: Dict[str, Any]) -> Dict[str, Any]:
    user = (f"【逐字稿】\n{perceived['transcript'] or '（無）'}\n\n【畫面描述】\n"
            + "\n".join(f"{i + 1}. {d}" for i, d in enumerate(perceived["descriptions"])))
    mock = {"question": "（mock）學生的問題", "misconception": "（mock）學生的迷思", "concept": "（mock）概念",
            "grade": "國小",
            "items": [{"q": f"（mock）第 {i + 1} 題", "choices": ["甲", "乙", "丙", "丁"], "answer": 0,
                       "misconception_choice": 1 if i == 0 else None} for i in range(4)]}
    res = llm.chat_json("author", _AUTHOR_SYS, user, mock=mock, temperature=0.3)
    items = [it for it in res.get("items", [])
             if isinstance(it.get("choices"), list) and len(it["choices"]) == 4 and it.get("answer") in range(4)]
    res["items"] = items
    return res


def _fmt(item: Dict[str, Any]) -> str:
    return item["q"] + "\n" + "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(item["choices"]))


def _letter(text: str) -> Optional[int]:
    for ch in text.strip().upper():
        if ch in LETTERS:
            return LETTERS.index(ch)
    return None


def verify_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """judge 獨立解題；不一致的題目剔除。mock 時全部保留。"""
    kept = []
    for it in items:
        mock = LETTERS[it["answer"]]
        got = _letter(llm.chat("judge", _JUDGE_SYS, _fmt(it), temperature=0.0, mock=mock))
        if got == it["answer"]:
            kept.append(it)
    return kept


def _ask(item: Dict[str, Any], misconception: str, video_digest: Optional[str], baseline_mock: int,
         treated_mock: int, k: int) -> List[Optional[int]]:
    video = (f"你剛看完一支補充教學影片，內容如下：\n{video_digest}\n" if video_digest else "你沒有看過任何補充影片。")
    sys_p = _STUDENT_SYS.format(misconception=misconception, video=video)
    mock = LETTERS[treated_mock if video_digest else baseline_mock]
    return [_letter(llm.chat("student", sys_p, _fmt(item), temperature=0.7, mock=mock)) for _ in range(k)]


def run(perceived: Dict[str, Any], k: int = 5, seed: int = 0) -> Dict[str, Any]:
    random.seed(seed)
    spec = author(perceived)
    items = verify_items(spec["items"])
    digest = ("【旁白】" + (perceived["transcript"] or "（無逐字稿）") + "\n【畫面】"
              + "；".join(perceived["descriptions"]))
    rows = []
    for it in items:
        wrong = it.get("misconception_choice")
        wrong = wrong if wrong is not None else (it["answer"] + 1) % 4
        base = _ask(it, spec["misconception"], None, wrong, it["answer"], k)
        treat = _ask(it, spec["misconception"], digest, wrong, it["answer"], k)
        acc = lambda xs: sum(x == it["answer"] for x in xs) / len(xs)
        b, t = acc(base), acc(treat)
        rows.append({"q": it["q"], "baseline_acc": b, "treated_acc": t,
                     "valid": b < 0.5, "direct_misconception": it.get("misconception_choice") is not None})
    valid = [r for r in rows if r["valid"]]
    if not valid:
        return {"spec": {k_: spec.get(k_) for k_ in ("question", "misconception", "concept", "grade")},
                "rows": rows, "gain_score": None, "fixed": None,
                "note": "沒有基線會答錯的有效題目，無法衡量增益（小明沒有展現迷思，或題目太簡單）"}
    # 正規化增益：(t-b)/(1-b)，clip 到 [0,1]
    norm = [max(0.0, min(1.0, (r["treated_acc"] - r["baseline_acc"]) / (1 - r["baseline_acc"]))) for r in valid]
    direct = [n for r, n in zip(valid, norm) if r["direct_misconception"]]
    return {"spec": {k_: spec.get(k_) for k_ in ("question", "misconception", "concept", "grade")},
            "rows": rows, "n_valid": len(valid), "gain_score": round(100 * sum(norm) / len(norm), 1),
            "fixed": (round(100 * sum(direct) / len(direct), 1) if direct else None), "note": ""}

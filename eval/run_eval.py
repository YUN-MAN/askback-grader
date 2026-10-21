"""對 data/good 與 data/bad 全部影片打分，輸出排序驗證報告 runs/eval_report.json。

指標：
  * pairwise：同一支原片，好版本分數 > 壞版本分數的比例
  * per_defect：各缺陷平均掉分，以及被扣的是哪一項（應該對應到該缺陷）
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grader import pipeline  # noqa: E402


def main() -> int:
    work = Path("runs/eval")
    good = {p.stem: pipeline.score(p, work / "good", k=3) for p in sorted(Path("data/good").glob("*.mp4"))}
    rows, wins, total = [], 0, 0
    drop = defaultdict(list)
    for d in sorted(p for p in Path("data/bad").iterdir() if p.is_dir()):
        for v in sorted(d.glob("*.mp4")):
            try:
                bad = pipeline.score(v, work / d.name, k=3)["result"]
            except Exception as e:  # 壞影片可能無法解析，記錄即可
                rows.append({"defect": d.name, "video": v.name, "error": str(e)[:100]})
                continue
            g = good[v.stem]["result"]
            total += 1
            wins += g["score"] > bad["score"]
            for c in g["components"]:
                drop[(d.name, c)].append(g["components"][c] - bad["components"][c])
            rows.append({"defect": d.name, "video": v.name, "good": g["score"], "bad": bad["score"],
                         "correct_order": g["score"] > bad["score"]})
    per = defaultdict(dict)
    for (defect, comp), xs in drop.items():
        per[defect][comp] = round(sum(xs) / len(xs), 1)
    rep = {"pairwise_accuracy": round(wins / total, 3) if total else None, "pairs": total,
           "per_defect_component_drop": per, "rows": rows,
           "good_scores": {k: v["result"]["score"] for k, v in good.items()}}
    Path("runs").mkdir(exist_ok=True)
    Path("runs/eval_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("pairwise_accuracy", "pairs", "per_defect_component_drop")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

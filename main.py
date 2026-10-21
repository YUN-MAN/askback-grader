"""python main.py score video.mp4 [--k 5] [--work runs]   → 印出 JSON 並寫入 runs/<name>/result.json
python main.py rules video.mp4                           → 只跑規則檢查（不需要 LLM）"""

import argparse
import json
import sys
from pathlib import Path

from grader import perceive, rules, pipeline


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["score", "rules"])
    ap.add_argument("video", type=Path)
    ap.add_argument("--k", type=int, default=5, help="每題取樣次數")
    ap.add_argument("--work", type=Path, default=Path("runs"))
    a = ap.parse_args()
    if not a.video.exists():
        print(f"找不到影片: {a.video}", file=sys.stderr)
        return 2
    if a.command == "rules":
        res = rules.check(perceive.probe(a.video), a.video)
    else:
        res = pipeline.score(a.video, a.work, k=a.k)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

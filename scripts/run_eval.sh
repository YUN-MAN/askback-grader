#!/usr/bin/env bash
# 在計算節點跑排序驗證。需要先 export 各供應商金鑰，Qwen 端點要先起好。
#   ./scripts/run_eval.sh
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
hrun -c 8 -m 32 python eval/make_variants.py
hrun -c 8 -m 32 python eval/run_eval.py

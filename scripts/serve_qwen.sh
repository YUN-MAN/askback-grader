#!/usr/bin/env bash
# 在 Battleship 起 Qwen（<=30B）的 vLLM OpenAI 相容端點，給 AI 小明用。
#   ./scripts/serve_qwen.sh                 # 預設 Qwen3-30B-A3B，3090/4090 級 x1～2
#   MODEL=Qwen/Qwen3-8B ./scripts/serve_qwen.sh
# 注意：s07 與其他節點網路不互通。client 必須跑在同一個節點，用 -N 指定同一台。
# 這支腳本用 hrun 提交（script 型的 normal job）。登入節點只負責送出，不跑運算。
set -euo pipefail
MODEL="${MODEL:-Qwen/Qwen3-8B}"       # 30B-A3B bf16 約需 60GB，目前閒置卡湊不齊
PORT="${PORT:-8000}"
GPUS="${GPUS:-1}"
GPU_TYPE="${GPU_TYPE:-TITANRTX}"   # 名稱以 hrun -h / hnode -v 為準
DTYPE="${DTYPE:-half}"            # TITAN RTX 是 Turing，不支援 bf16；Ada/Ampere 可用 bfloat16
NODE="${NODE:-}"          # 例如 NODE=s05；要和 client 同節點
extra=(); [ -n "$NODE" ] && extra+=(-N "$NODE")
exec hrun "${extra[@]}" -G -g "$GPU_TYPE" -m 96 -c 8 -n qwen-serve \
  python -m vllm.entrypoints.openai.api_server --model "$MODEL" --port "$PORT" \
  --tensor-parallel-size "$GPUS" --dtype "$DTYPE" --max-model-len 8192 --host 0.0.0.0

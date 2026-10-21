# askback-grader：替補充教學影片打分的 AI 學生

輸入一支 AskBack 補充教學影片（只需要 mp4），輸出 0–100 分與逐項理由（JSON）。

## 怎麼打分

```
mp4 ─ Stage 0 感知：ffprobe、抽幀、ASR（faster-whisper）、視覺模型轉述畫面
    ├ Stage 1 規則檢查 → 影音品質分 + 硬性條件（30–90s、有聲有畫、AI 生成標示）
    ├ Stage 2 AI 小明前後測 → 迷思有沒有被糾正（增益）
    ├ Stage 3 審查 → 內容正確、回應提問、適齡、銜接
    └ 聚合：正確 35% + 回應提問 30% + 延續教法 20% + 影音品質 15%
```

**Stage 2 的設計重點**：作者模型還原影片回應的問題與迷思，出 4 題遷移題（四選一）；judge 獨立解題，與答案鍵
不符就剔除；AI 小明（Qwen ≤30B）帶著迷思，**基線**（沒看影片）與**看完影片**各答 k 次。只計基線會答錯的題，
增益 = (看完 − 基線)/(1 − 基線)。小明永遠看不到答案與出題者資訊。

硬性條件未過（缺聲音／長度不符／缺 AI 標示）總分上限 30。

## 執行（Battleship）

```bash
cp .env.example .env     # 填金鑰；GRADER_PROVIDER=mock 時不連網，只驗證流程
pip install -r requirements.txt   # 在計算節點（hrun bash script）或 venv，不要在登入節點
./scripts/serve_qwen.sh  # 起 Qwen vLLM（NODE=sXX，client 必須同節點）
hrun -c 8 -m 32 python main.py score data/good/V11.mp4
hrun -c 2 -m 8  python main.py rules data/good/V11.mp4    # 只跑規則，不需要 LLM
```

## 驗證（E）

```bash
python eval/make_variants.py   # 從 data/good 做出 silent / no_audio / too_short / too_long / static / black / low_res
python eval/run_eval.py        # → runs/eval_report.json：成對排序正確率、各缺陷掉了哪一項
```

## 現況

- ✅ Stage 0（探測、抽幀、ASR、視覺轉述）、Stage 1、聚合、驗證腳本
- ✅ `mock` 模式可在無金鑰下跑通；**mock 的分數沒有意義**，輸出會標 `"mock": true`
- ⚠️ Stage 2、3 的 prompt 尚未用真實模型驗證，需先跑一輪看小明是否真的會答錯（有效題數）
- ⚠️ `not_static` 等門檻只在 3 支範例影片上粗調
- ⬜ 內容缺陷變體（數學錯誤、答非所問）：需改寫旁白 + TTS
- ⬜ 沒有原片可比對，「延續教法」只能估計

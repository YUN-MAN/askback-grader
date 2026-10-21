# 資料來源與授權

## `data/good/`（V01.mp4、V11.mp4、V19.mp4）

這三支是 [askback-skill](https://github.com/Jimmynycu/askback-skill) 產生的 **AI 補充教學影片**範例，
僅用來測試與示範本專案的打分流程。

- 影片內容改作自**均一教育平台 Junyi Academy** 的教材（官方 YouTube 頻道），
  授權為 **CC BY-NC-SA 3.0 TW**：<https://creativecommons.org/licenses/by-nc-sa/3.0/tw/>
  - 姓名標示：均一教育平台 Junyi Academy
  - 非商業使用
  - 相同方式分享（改作須採相同授權）
- 影片為 AI 生成的教學示範，**不是原講者本人**，也不代表均一平台或原講者認可。
- 影片由 askback-skill 的作者製作；本專案只是複製使用。

這三支影片的授權與下方「程式碼」不同，請勿因為整個 repo 是 MIT 就以為影片也是 MIT。

## `data/bad/`

由 `eval/make_variants.py` 對 `data/good/` 的影片以 ffmpeg 加工產生（靜音、過短、過長等缺陷變體），
屬於上述影片的改作，同樣適用 CC BY-NC-SA 3.0 TW。這個目錄不納入版本控制，需要時重新產生。

## 程式碼

`grader/`、`eval/`、`scripts/`、`main.py` 等程式碼採 MIT 授權，見根目錄 `LICENSE`。

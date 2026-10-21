"""用 ffmpeg 從好影片做出「已知有缺陷」的變體，放到 data/bad/<缺陷>/<原名>.mp4。

只做不需要重新生成內容的影音缺陷。內容缺陷（數學錯誤、答非所問）需要改寫旁白並重新 TTS，
見 eval/README 的 TODO。
"""
import subprocess
import sys
from pathlib import Path

GOOD, BAD = Path("data/good"), Path("data/bad")

# 缺陷名 -> ffmpeg 參數（輸入 -i 之後、輸出檔之前）
DEFECTS = {
    "silent":      ["-c:v", "copy", "-af", "volume=0"],
    "no_audio":    ["-c:v", "copy", "-an"],
    "too_short":   ["-t", "15", "-c:v", "libx264", "-c:a", "aac"],
    "too_long":    ["-stream_loop", "-1", "-t", "120", "-c:v", "libx264", "-c:a", "aac"],  # -stream_loop 要放在 -i 前，見下
    "static":      ["-vf", "select=eq(n\\,0),loop=-1:1:0,fps=30", "-c:v", "libx264", "-c:a", "copy"],
    "black":       ["-vf", "drawbox=t=fill:color=black:w=iw:h=ih", "-c:v", "libx264", "-c:a", "copy"],
    "low_res":     ["-vf", "scale=320:-2", "-c:v", "libx264", "-c:a", "copy"],
}


def main() -> int:
    for src in sorted(GOOD.glob("*.mp4")):
        for name, args in DEFECTS.items():
            out = BAD / name / src.name
            out.parent.mkdir(parents=True, exist_ok=True)
            pre = []
            if name == "too_long":
                pre, args = ["-stream_loop", "-1"], ["-t", "120", "-c:v", "libx264", "-c:a", "aac"]
            cmd = ["ffmpeg", "-y", "-loglevel", "error", *pre, "-i", str(src), *args, "-shortest" if name == "static" else "-y", str(out)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(("ok  " if r.returncode == 0 else "FAIL"), out, r.stderr.strip()[:120])
    return 0


if __name__ == "__main__":
    sys.exit(main())

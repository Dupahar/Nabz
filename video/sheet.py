"""Contact sheet of preview frames: python video/sheet.py <glob> <out.jpg> [cols] [tile_w]"""
import subprocess
import sys
from pathlib import Path

files = sorted(Path(".").glob(sys.argv[1]))
out = sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 5
tw = int(sys.argv[4]) if len(sys.argv) > 4 else 360
probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(files[0])],
                       capture_output=True, text=True).stdout.strip().split(",")
th = int(tw * int(probe[1]) / int(probe[0]))
args = []
for f in files:
    args += ["-i", str(f)]
scales = "".join(f"[{i}:v]scale={tw}:{th}[v{i}];" for i in range(len(files)))
layout = "|".join(f"{(i % cols) * (tw + 6)}_{(i // cols) * (th + 6)}" for i in range(len(files)))
fc = scales + "".join(f"[v{i}]" for i in range(len(files))) + f"xstack=inputs={len(files)}:layout={layout}:fill=white[o]"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", fc, "-map", "[o]", "-q:v", "3", out], check=True)
print("wrote", out, len(files), "tiles")

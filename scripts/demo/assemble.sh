#!/usr/bin/env bash
# Joins the product capture to the pitch slides and extends beats.json so the
# narration can name a slide the same way it names a moment on screen.
#
# The slides are stills, so their "beat" is simply where they start on the joined
# timeline. Writing them into beats.json rather than hardcoding timestamps keeps
# ONE scheduling model: narration.txt names a beat, schedule.py spaces the lines,
# and neither has to know which beats came from a browser and which from a PNG.
set -euo pipefail
DIR="${DEMO_DIR:-/tmp/makanlah-demo}"
FF="${DEMO_FFMPEG:-$(command -v ffmpeg)}"
# Sized to the narration each slide carries, measured from the rendered wavs rather
# than picked. arch runs to 18.3s, market to 12.6s, close to 22.5s. market was 21s for
# 12.6s of speech -- eight seconds of a still frame with nobody talking over it -- and
# close was 20s for 22.5s, which is why the last line needed a tail pad to have any
# picture behind it at all.
ARCH_S="${DEMO_ARCH_SECONDS:-20}"
MARKET_S="${DEMO_MARKET_SECONDS:-14}"
CLOSE_S="${DEMO_CLOSE_SECONDS:-24}"

for f in "$DIR/capture.webm" "$DIR/beats.json" "$DIR/slide-arch.png" "$DIR/slide-market.png" "$DIR/slide-close.png"; do
  [ -f "$f" ] || { echo "missing $f" >&2; exit 1; }
done

# The capture is 1440x900; the slides are 1920x1080. Normalise both to 1920x1080
# here rather than at mux time, because concat demands identical streams and a
# mismatch fails silently by dropping frames rather than by erroring.
"$FF" -y -loglevel error -i "$DIR/capture.webm" \
  -vf "scale=1728:1080,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#F4F7F4,fps=25,format=yuv420p" \
  -an "$DIR/seg-capture.mp4"

for pair in "arch:$ARCH_S" "market:$MARKET_S" "close:$CLOSE_S"; do
  name="${pair%%:*}"; secs="${pair##*:}"
  "$FF" -y -loglevel error -loop 1 -t "$secs" -i "$DIR/slide-$name.png" \
    -vf "scale=1920:1080,fps=25,format=yuv420p" "$DIR/seg-$name.mp4"
done

printf "file '%s'\n" "$DIR/seg-capture.mp4" "$DIR/seg-arch.mp4" "$DIR/seg-market.mp4" "$DIR/seg-close.mp4" > "$DIR/concat.txt"
"$FF" -y -loglevel error -f concat -safe 0 -i "$DIR/concat.txt" -c copy "$DIR/pitch.mp4"

python3 - "$DIR" "$ARCH_S" "$MARKET_S" "$CLOSE_S" <<'PY'
import json, subprocess, sys
from pathlib import Path
d = Path(sys.argv[1]); arch_s, market_s, close_s = (int(x) for x in sys.argv[2:5])

def secs(p):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'csv=p=0', str(p)], capture_output=True, text=True).stdout.strip()
    return float(out)

cap = round(secs(d / 'seg-capture.mp4') * 1000)
beats = [b for b in json.loads((d / 'beats.json').read_text()) if b['name'] != 'end']
beats += [
    {'name': 'arch', 'ms': cap},
    {'name': 'market', 'ms': cap + arch_s * 1000},
    {'name': 'close', 'ms': cap + (arch_s + market_s) * 1000},
    {'name': 'end', 'ms': cap + (arch_s + market_s + close_s) * 1000},
]
(d / 'beats.json').write_text(f'{json.dumps(beats, indent=2)}\n')
print(f'  capture {cap}ms + slides {(arch_s + market_s + close_s) * 1000}ms')
for b in beats:
    print(f'    {b["ms"]:>7}ms  {b["name"]}')
PY

mv "$DIR/pitch.mp4" "$DIR/capture-joined.mp4"
echo "joined: $DIR/capture-joined.mp4"

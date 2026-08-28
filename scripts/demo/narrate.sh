#!/usr/bin/env bash
# Narrates the capture and muxes the two into the deliverable.
#
# Narration is rendered one line at a time and delayed to the beat it describes,
# using the offsets record.mjs measured. One continuous read drifts out of sync
# within a few seconds and then actively contradicts the picture.
set -euo pipefail

DIR="${DEMO_DIR:-${TMPDIR:-/tmp}/makanlah-demo}"
VOICES="${DEMO_VOICES:-$DIR/voices}"
VOICE="${DEMO_VOICE:-en_US-lessac-medium}"
SCRIPT="${DEMO_SCRIPT:-$(dirname "$0")/narration.txt}"
FF="${DEMO_FFMPEG:-$(command -v ffmpeg || echo "$DIR/node_modules/ffmpeg-static/ffmpeg")}"
OUT="${DEMO_OUT:-$DIR/makanlah-demo.mp4}"

for f in "$DIR/capture.webm" "$DIR/beats.json" "$SCRIPT"; do
  [ -f "$f" ] || { echo "missing: $f (run record.mjs first)" >&2; exit 1; }
done
[ -x "$FF" ] || { echo "no ffmpeg at $FF" >&2; exit 1; }

rm -rf "$DIR/seg" && mkdir -p "$DIR/seg"

# Resolve each "beat | offset | text" line against the measured beats. A line
# naming a beat that did not happen is dropped with a warning rather than
# silently narrating over the wrong picture.
python3 - "$DIR" "$SCRIPT" <<'PY'
import json, sys, pathlib
d, script = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
beats = {b['name']: b['ms'] for b in json.loads((d / 'beats.json').read_text())}
out = []
for raw in script.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith('#'):
        continue
    name, offset, text = (p.strip() for p in line.split('|', 2))
    if name not in beats:
        print(f'  skipped (beat {name!r} never happened): {text[:50]}...', file=sys.stderr)
        continue
    out.append({'ms': beats[name] + int(offset), 'text': text})
out.sort(key=lambda x: x['ms'])
(d / 'lines.json').write_text(json.dumps(out, indent=2))
print(f'  {len(out)} lines resolved against {len(beats)} beats')
PY

n=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$DIR/lines.json")
[ "$n" -gt 0 ] || { echo "no narration lines resolved" >&2; exit 1; }

for i in $(seq 0 $((n - 1))); do
  python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[int(sys.argv[2])]['text'])" "$DIR/lines.json" "$i" \
    | piper -m "$VOICE" --data-dir "$VOICES" -f "$DIR/seg/$i.wav" 2>/dev/null
done

# One delayed input per line, mixed onto a common timeline.
inputs=(); filters=""; labels=""
for i in $(seq 0 $((n - 1))); do
  ms=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[int(sys.argv[2])]['ms'])" "$DIR/lines.json" "$i")
  inputs+=(-i "$DIR/seg/$i.wav")
  filters="$filters[$i:a]adelay=$ms|$ms[a$i];"
  labels="$labels[a$i]"
done
"$FF" -y "${inputs[@]}" \
  -filter_complex "${filters}${labels}amix=inputs=$n:normalize=0[out]" \
  -map "[out]" -ar 44100 "$DIR/narration.wav" >/dev/null 2>&1

# ffmpeg -i with no output file reports the duration and then exits non-zero,
# which pipefail turns into an abort. Swallow the status; the probe is the point.
dur() {
  local probe
  probe=$({ "$FF" -i "$1" 2>&1 || true; })
  awk -F'Duration: ' '/Duration: /{split($2,a,","); split(a[1],t,":");
    print t[1]*3600+t[2]*60+t[3]; exit}' <<<"$probe"
}
vid=$(dur "$DIR/capture.webm"); aud=$(dur "$DIR/narration.wav")

# The capture is 1440x900, which is 16:10. Cropping to 16:9 would cut content, so
# it scales to 1728x1080 and pads with the app's own background colour, which
# makes the bars invisible. If the closing line outruns the picture, hold the
# last frame rather than cutting the sentence off.
pad=$(awk -v a="$aud" -v v="$vid" 'BEGIN{d=a-v; print (d>0)? d+0.4 : 0}')
tpad=""
[ "$(awk -v p="$pad" 'BEGIN{print (p>0)}')" = 1 ] && tpad="tpad=stop_mode=clone:stop_duration=$pad,"

"$FF" -y -i "$DIR/capture.webm" -i "$DIR/narration.wav" \
  -filter_complex "[0:v]${tpad}scale=1728:1080,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#F4F7F4[v]" \
  -map "[v]" -map 1:a -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart "$OUT" >/dev/null 2>&1

printf 'video %.1fs  narration %.1fs  tail-pad %.1fs\n' "$vid" "$aud" "$pad"
ls -lh "$OUT" | awk '{print "output: " $NF " (" $5 ")"}'

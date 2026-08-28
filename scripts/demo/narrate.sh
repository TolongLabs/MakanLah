#!/usr/bin/env bash
# Narration synced to the visual beats, not laid over the top.
#
# Each line is rendered separately and delayed to the second where the thing it
# describes is actually on screen. One continuous read drifts out of sync within
# a few seconds and then contradicts the picture, which is worse than silence.
set -e
cd /tmp/claude-1000/-home-user-Documents-TolongLabs-MakanLah/4964dd32-db7a-44dc-bbfa-966c1ec73068/scratchpad
FF=./node_modules/ffmpeg-static/ffmpeg
mkdir -p seg

# start_ms | text  -- starts chosen from the capture's own beats
say() {
  local i="$1" ms="$2" text="$3"
  printf '%s\n' "$text" | piper -m en_US-lessac-medium --data-dir voices -f "seg/$i.wav" 2>/dev/null
  echo "$ms" > "seg/$i.ms"
}

say 1 1000 "MakanLah recommends restaurants in Kuala Lumpur. Every pick shows the post it came from."
say 2 11000 "It doesn't start with a search box. It asks what you're craving, who you're with, and how far you're willing to go."
say 3 24000 "Then it reads what people actually wrote. Real posts, from RedNote and Google Maps, in English, Malay and Chinese."
say 4 34000 "Every result carries the words someone wrote. Not a generated summary. The post itself, quoted."
say 5 43000 "That's the difference. A recommendation you can check."

# Build one delayed input per segment, then mix them onto a common timeline.
inputs=(); filters=(); labels=""
for i in 1 2 3 4 5; do
  inputs+=(-i "seg/$i.wav")
  filters+=("[$((i - 1)):a]adelay=$(cat "seg/$i.ms")|$(cat "seg/$i.ms")[a$i];")
  labels="$labels[a$i]"
done
"$FF" -y "${inputs[@]}" \
  -filter_complex "${filters[*]}${labels}amix=inputs=5:normalize=0[out]" \
  -map "[out]" -ar 44100 narration.wav >/dev/null 2>&1

"$FF" -i narration.wav 2>&1 | grep Duration

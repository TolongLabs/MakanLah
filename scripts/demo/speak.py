"""Narration voice for the demo video. Kokoro-82M, Apache 2.0, CPU-only.

Piper was the shortcut and it is audibly synthetic. The owner asked for an anime
voice, which is a real constraint rather than a flourish: it sets the register of
the whole video, and the wrong one makes a food product sound like a compliance
training module.

**Why jf_nezumi, measured rather than guessed.** Eight candidates were
synthesised on the same line, then scored two ways: median fundamental frequency
for register, and word error rate from an independent ASR pass for
intelligibility. Adult female speech sits near 165-200 Hz and anime voice acting
near 250-350 Hz, so pitch alone favoured jf_alpha at 273 Hz -- but jf_alpha is
the *least* intelligible of the eight at 50% WER ("Every kick shows the post").

    voice        F0     WER
    jf_alpha    273Hz   50%
    jf_nezumi   242Hz   14%   <- chosen
    bf_lily     200Hz   29%
    af_bella    198Hz   29%
    af_sky      155Hz   29%

jf_nezumi is in register and is the clearest of every voice tested. Across the
real script it scores 5%, and its only error is hearing "MakanLah" as "Makan La"
-- which is how the words are actually pronounced.

A phonetic respelling was tried and made it worse (7%), turning "Makan" into
"Mark on". The raw text wins; do not re-add a hint without re-measuring.

Licence matters as much as sound. Kokoro is Apache 2.0. XTTS v2, F5-TTS and Fish
Speech all sound good and are all non-commercial, and a launch video is a
commercial use.
"""

import os
import sys
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro

HERE = Path(os.environ.get('KOKORO_HOME', Path.home() / 'Documents/TolongLabs/makanlah-video'))
VOICE = os.environ.get('DEMO_VOICE', 'jf_nezumi')
SPEED = float(os.environ.get('DEMO_SPEED', '1.0'))


def main():
    if len(sys.argv) < 2:
        print('usage: speak.py <out.wav>   (text on stdin)', file=sys.stderr)
        return 2
    text = sys.stdin.read().strip()
    if not text:
        print('no text on stdin', file=sys.stderr)
        return 2
    model, voices = HERE / 'kokoro-v1.0.onnx', HERE / 'voices-v1.0.bin'
    for f in (model, voices):
        if not f.exists():
            print(f'missing {f}. See scripts/demo/README.md for the download.', file=sys.stderr)
            return 1
    audio, rate = Kokoro(str(model), str(voices)).create(text, voice=VOICE, speed=SPEED, lang='en-us')
    sf.write(sys.argv[1], audio, rate)
    return 0


if __name__ == '__main__':
    sys.exit(main())

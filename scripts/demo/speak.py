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

HERE = Path(os.environ.get('KOKORO_HOME', Path.home() / 'Documents/TolongLabs/makanlah-video'))
VOICE = os.environ.get('DEMO_VOICE', 'jf_nezumi')
SPEED = float(os.environ.get('DEMO_SPEED', '1.0'))

# DEMO_TTS=chatterbox clones the owner's voice from a reference clip instead. Kokoro
# stays the default: it needs no reference, renders in a second rather than forty, and
# the measurements above are all against it.
TTS = os.environ.get('DEMO_TTS', 'kokoro')
CB_HOME = Path(os.environ.get('CHATTERBOX_HOME', HERE / 'chatterbox-spike'))
CB_REF = Path(os.environ.get('CHATTERBOX_REF', CB_HOME / 'jahoda-ref.wav'))


def speak_chatterbox(text, out):
    """Chatterbox TTS, MIT, CPU. Lives in its own venv because it needs torch and a
    Python that is not this one -- so re-exec there rather than making the Kokoro
    environment carry 3 GB of wheels it never uses.

    THE ATTENTION SETTING IS NOT OPTIONAL. On this hardware the fused attention
    kernel emits all-NaN audio -- 180,960 of 180,960 samples on the first run -- and
    the failure surfaces two layers away, as `Audio buffer is not finite everywhere`
    raised by librosa inside the Perth watermarker. It reads as a watermarker bug and
    is not one. The tell is `Could not initialize NNPACK! Reason: Unsupported
    hardware` in the startup log. Eager attention plus the MATH SDPA backend produces
    finite audio; drop either and the narration is silence with a confusing traceback.
    """
    import torch

    # BEFORE the chatterbox import: MKL-DNN is a second fused path, separate from
    # SDPA, and on this hardware it is the other half of the NaN. Disabling only one
    # of the two still yields silence.
    torch.backends.mkldnn.enabled = False

    import torchaudio
    from chatterbox.tts import ChatterboxTTS

    model = ChatterboxTTS.from_pretrained(device='cpu')
    model.t3.tfmr.config._attn_implementation = 'eager'
    for m in model.t3.tfmr.modules():
        if hasattr(m, 'config'):
            m.config._attn_implementation = 'eager'
    with torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.MATH):
        wav = model.generate(text, audio_prompt_path=str(CB_REF))
    if not torch.isfinite(wav).all():
        print('chatterbox produced non-finite audio; refusing to write silence', file=sys.stderr)
        return 1
    torchaudio.save(out, wav, model.sr)
    return 0


def main():
    if len(sys.argv) < 2:
        print('usage: speak.py <out.wav>   (text on stdin)', file=sys.stderr)
        return 2
    text = sys.stdin.read().strip()
    if not text:
        print('no text on stdin', file=sys.stderr)
        return 2

    if TTS == 'chatterbox':
        cb_python = CB_HOME / '.venv/bin/python'
        if not cb_python.exists():
            print(f'missing {cb_python}. See scripts/demo/README.md for the install.', file=sys.stderr)
            return 1
        # Re-exec under the venv that has torch, unless already there.
        if Path(sys.executable).resolve() != cb_python.resolve():
            import subprocess

            return subprocess.run([str(cb_python), __file__, sys.argv[1]], input=text, text=True).returncode
        return speak_chatterbox(text, sys.argv[1])

    import soundfile as sf
    from kokoro_onnx import Kokoro

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

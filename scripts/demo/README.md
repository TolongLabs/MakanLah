# Demo Video Pipeline

Records the product, narrates it, and muxes the two. **Free, local, no account.** Run three times: 47.7s on 2026-08-28,
then 55.4s twice on 2026-08-29 after the citation work, all at 1920×1080 and around 2.5 MB.

**The third run is the one worth looking at, and the difference is the corpus rather than the pipeline.** `record.mjs`
reported **1** two-source pair on screen in the second run and **4** in the third, because the extraction replay (#42)
gave venues real testimony to corroborate with. The same script, unchanged, films a materially better product.

Rationale and the options that were rejected:
[`../../docs/superpowers/research/2026-08-28-agent-recorded-demo-video.md`](../../docs/superpowers/research/2026-08-28-agent-recorded-demo-video.md).

```
narration.txt ──► kokoro ──► narration.wav ──┐
              └──► subtitles.py ──► .srt ────┤
                                             ├──► ffmpeg ──► makanlah-demo.mp4
record.mjs ──► Playwright ──► capture.webm ──┘
```

Both the voice and the subtitles read the same `lines.json`, so what is spoken and what is written cannot disagree.

## Run It

Everything writes to a scratch directory, never into the repo. **Do not commit the output** — `.mp4` and `.webm` are
gitignored for that reason.

```bash
# 1. Both servers. The API must be up or the capture records empty states.
scripts/dev-api.sh                       # :8000
cd web && bun run dev --port 5188         # :5188

# 2. One-time tooling, installed into DEMO_DIR rather than the repo: this pulls a
#    browser and has no business in the app's dependency tree.
export DEMO_DIR="${TMPDIR:-/tmp}/makanlah-demo" && mkdir -p "$DEMO_DIR" && cd "$DEMO_DIR"
bun add -d playwright ffmpeg-static
# Kokoro lives outside the repo: a 311MB model has no business in a git checkout.
# KOKORO_HOME overrides the default location.
mkdir -p ~/Documents/TolongLabs/makanlah-video && cd $_
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python kokoro-onnx soundfile
curl -sLO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -sLO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# 3. Capture, narrate, mux
node scripts/demo/record.mjs
bash scripts/demo/narrate.sh
```

`DEMO_DIR` is where everything is read from and written to. `DEMO_WEB`, `DEMO_API`, `DEMO_VOICE` and `DEMO_OUT` override
the rest; none of them need setting for a local run.

Chromium is not installed for Playwright on this machine, so `record.mjs` uses `channel: 'chrome'` — the system Chrome.

**The `DEMO_DIR` install above is optional now.** `record.mjs` prefers a Playwright installed there and falls back to
the repo's own copy, which exists because the cross-engine motion check needs it. Before that fallback the file resolved
a `resolve-from-here.cjs` shim that nothing ever created, so it could not run at all.

## Why It Looks The Way It Does

**The pauses are deliberate and they feel too long while you are editing.** The product's whole claim is the cited post,
and a reader needs two to three seconds to register that the quote is real. Automation's instinct is to click instantly,
which reads as fake and skips the only thing worth showing.

**Narration is keyed to beats the capture measures, not to fixed timestamps.** `record.mjs` writes `beats.json` — the
offset of every moment worth narrating — and `narration.txt` names a beat rather than a millisecond. A page that gets
slower moves the narration with it. One continuous read drifts out of sync within a few seconds and then actively
contradicts the picture, which is worse than silence.

**Padded, not cropped, to 1920×1080.** The capture is 1440×900, which is 16:10. Cropping to 16:9 would cut content, so
it scales to 1728×1080 and pads with `#F4F7F4` — sampled from the app's own background, so the bars are invisible.

## The Voice, And Why It Is That One

**Kokoro-82M, voice `jf_nezumi`.** Apache 2.0, CPU-only, and commercial-safe, which matters because a launch post is a
commercial use and three of the best-sounding open models are not: XTTS v2 is CPML, F5-TTS and Fish Speech are CC-BY-NC.
Check the licence before the voice.

The owner asked for an anime voiceover. That is a real constraint rather than a flourish -- it sets the register of the
whole video -- so the voice was picked by measurement rather than taste. Eight candidates read the same line and were
scored twice: median fundamental frequency for register, and word error rate from an independent ASR pass for
intelligibility.

| Voice       | Median F0  | WER     |
| ----------- | ---------- | ------- |
| `jf_alpha`  | 273 Hz     | 50%     |
| `jf_nezumi` | **242 Hz** | **14%** |
| `bf_lily`   | 200 Hz     | 29%     |
| `af_bella`  | 198 Hz     | 29%     |
| `af_sky`    | 155 Hz     | 29%     |

Adult female speech sits near 165-200 Hz and anime voice acting near 250-350 Hz, so pitch alone favoured `jf_alpha` --
**which is the least intelligible of the eight.** `jf_nezumi` is in register and the clearest of every voice tested;
across the real script it scores 5%, and its only error is hearing "MakanLah" as "Makan La", which is how the words are
actually pronounced.

A phonetic respelling was tried and made it **worse** (7%), turning "Makan" into "Mark on". The raw text wins. Do not
re-add a hint without re-measuring.

`DEMO_VOICE` overrides the choice and `DEMO_SPEED` the pace.

## Subtitles

English, burned in, bottom-centred, per the owner's brief. `subtitles.py` builds them from the same `lines.json` and the
same wav durations the narration uses, so the two cannot drift.

**Two defects the first render exposed**, both invisible to a passing check:

- **Cards overlapped** when one line's audio outran the next line's beat, leaving two different claims stacked on one
  frame. Cards now truncate at the next start.
- **A greedy wrap stranded single words** -- `...the post it came` / `from.` A one-word card is a jolt, and it landed on
  the sentence making the product's claim. Lines are now split to minimise the longest, which also stops the per-line
  boxes forming a ragged stepped edge.

**The style was tuned by rendering a frame and looking at it.** A numeric check for "dark pixels, near the bottom,
centred" passed happily on type twice the size it should have been: `FontSize` is a libass script unit, not a pixel, so
26 came out enormous at 1080p and 14 is right. Under `BorderStyle=3` the box also takes its colour from `OutlineColour`,
so an alpha set on `BackColour` is silently ignored and the scrim renders fully opaque.

## Known Gaps In What This Records

- **`/ask` is not in the UI**, so the strongest moment in the product — the copilot answering `covered: false`, "the
  posts don't mention whether it's halal" — cannot be filmed. It exists as an API endpoint only
- **The API is local**, so the capture points at `127.0.0.1:8000` via `?api=`. A public URL needs
  [#6](https://github.com/TolongLabs/MakanLah/issues/6)
- **`data/corpus/spike.db` can never show a corroboration pair.** It is the original 50-post RedNote capture and holds
  **one platform**, so a run against it renders every result single-sourced. That is the file, not a regression, and the
  distinction is easy to lose: the live corpus is Postgres on Neon via `DATABASE_URL`, 1,507 posts across two platforms
  with 134 venues corroborating. Check which one you are pointed at before diagnosing a thin demo
- **Some venues still cite a postal address** rather than testimony, because the corpus holds nothing better for them
  ([#25](https://github.com/TolongLabs/MakanLah/issues/25)). 28 of 243 venues, down from 82

The corroboration pair now renders, and `record.mjs` **asserts it** rather than assuming: it reports how many two-source
pairs were on screen, and a run reporting zero has recorded the bug that
[#20](https://github.com/TolongLabs/MakanLah/issues/20) was.

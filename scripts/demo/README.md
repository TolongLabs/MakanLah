# Demo Video Pipeline

Records the product, narrates it, and muxes the two. **Free, local, no account.** Proven end to end on 2026-08-28;
output was 47.7s at 1920×1080, 2.9 MB.

Rationale and the options that were rejected:
[`../../docs/superpowers/research/2026-08-28-agent-recorded-demo-video.md`](../../docs/superpowers/research/2026-08-28-agent-recorded-demo-video.md).

```
narration.txt ──► piper ──► narration.wav ──┐
                                            ├──► ffmpeg ──► makanlah-demo.mp4
record.mjs ──► Playwright ──► capture.webm ─┘
```

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
uv tool install piper-tts
uv tool run --from piper-tts python -m piper.download_voices en_US-lessac-medium --data-dir voices

# 3. Capture, narrate, mux
node scripts/demo/record.mjs
bash scripts/demo/narrate.sh
```

`DEMO_DIR` is where everything is read from and written to. `DEMO_WEB`, `DEMO_API`, `DEMO_VOICE` and `DEMO_OUT` override
the rest; none of them need setting for a local run.

Chromium is not installed for Playwright on this machine, so `record.mjs` uses `channel: 'chrome'` — the system Chrome.

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

## Upgrading The Voice

Piper is the shortcut, not the recommendation. It is CPU-only and tiny, and it is **audibly synthetic** — fine for
checking the pipeline, weaker than it should be for a launch.

**Kokoro-82M** is the upgrade: Apache 2.0, 54 voices, CPU-capable, and the best open default in 2026. It is a drop-in
replacement for the `piper` call in `narrate.sh`; nothing else changes.

**Check the licence before the voice.** XTTS v2, F5-TTS and Fish Speech all sound better than Piper and are all
**non-commercial**. A launch post is a commercial use.

## Known Gaps In What This Records

- **`/ask` is not in the UI**, so the strongest moment in the product — the copilot answering `covered: false`, "the
  posts don't mention whether it's halal" — cannot be filmed. It exists as an API endpoint only
- **The API is local**, so the capture points at `127.0.0.1:8000` via `?api=`. A public URL needs
  [#6](https://github.com/TolongLabs/MakanLah/issues/6)
- **Some venues still cite a postal address** rather than testimony, because the corpus holds nothing better for them
  ([#25](https://github.com/TolongLabs/MakanLah/issues/25)). 28 of 243 venues, down from 82

The corroboration pair now renders, and `record.mjs` **asserts it** rather than assuming: it reports how many two-source
pairs were on screen, and a run reporting zero has recorded the bug that
[#20](https://github.com/TolongLabs/MakanLah/issues/20) was.

# Recording The Demo Video With An Agent, For Free

**Date:** 2026-08-28 · **For:** the LinkedIn launch post · **Status:** recommendation, not yet executed

**Recommendation: Playwright drives and records the browser, Kokoro-82M speaks the script, ffmpeg joins them.** All
three are free, all run locally, none needs an account or a card. Budget half a day, not a week.

**Avoid Remotion** — it is the obvious answer and it is **not free for a company**.

---

## The Pipeline

```
script.md ──► Kokoro-82M ──► narration.wav ──┐
                                             ├──► ffmpeg ──► demo.mp4
demo.spec.ts ──► Playwright ──► capture.webm ┘
```

Four decisions, taken separately because they fail separately.

### 1. Capture — Playwright

**Already in this repo**, wired in `.mcp.json`, and the frontend session has been using it for screenshots all day.

`recordVideo` in the browser context writes a WebM per test with no plugin, no compositor and no desktop. It records the
**page**, not the screen, so no window chrome, no notifications, and it is identical on every machine — which matters
because a re-record after a UI change should differ only where the UI differs.

The route is a Playwright script that walks the real flow: landing → `/taste` wizard → `/discover` → a venue page with
its citation trail. That is the product's actual argument, and the script doubles as an E2E test.

**Its limits, honestly:** no cursor, no zoom, no click highlight. A raw Playwright capture looks like a robot using a
website, because it is. Section 4 covers the cheap fixes.

**Alternative, if the demo should show the terminal instead:**
[`charmbracelet/vhs`](https://github.com/charmbracelet/vhs) (~19.6k stars) records a terminal from a declarative `.tape`
file — window size, theme, typing speed, pauses — and renders GIF, MP4 or WebM. It is CI-runnable, so the recording
regenerates itself. **For MakanLah the browser is the product**, so VHS is the wrong surface here; it would be the right
one for the ingestion pipeline.

### 2. Narration — Kokoro-82M

**Kokoro-82M is the pick.** 82M parameters, **Apache 2.0**, 54 voices across 8 languages, faster than real time, and it
**runs on CPU** — no GPU, no CUDA. Roughly 2-3 GB. On this 5 GB box that is the deciding property.

| Model          | Licence         | Verdict                                                                                                                                    |
| -------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Kokoro-82M** | **Apache 2.0**  | **Use this.** Best default in 2026, CPU-only, commercial-safe                                                                              |
| Chatterbox     | MIT             | Better quality, zero-shot cloning, beat ElevenLabs 65.3% to 24.5% in a blind study. Heavier                                                |
| Piper          | GPL-3.0         | **Already installed on this machine** (Kawan gitignores its `.onnx` voices). Tiny, real-time on a Pi, but audibly synthetic next to Kokoro |
| XTTS v2        | **CPML**        | **Non-commercial.** Best cloning, wrong licence for a product launch                                                                       |
| F5-TTS         | **CC-BY-NC**    | **Non-commercial.** Same problem                                                                                                           |
| Fish Speech    | **CC-BY-NC-SA** | **Non-commercial**                                                                                                                         |

**Check the licence before the voice.** Three of the six best-sounding options are non-commercial, and a product launch
post is a commercial use. Kokoro and Chatterbox are the commercial-safe pair.

**Piper is the shortcut if today matters more than polish** — it is already on the machine, so it costs zero setup. Its
output is noticeably more robotic, which for a food product is a real cost.

The open/closed gap has nearly closed: **223 ELO in 2023 down to 81 by mid-2026** on the Speech Arena, with open models
now beating ElevenLabs in blind tests more often than not.

### 3. Assembly — ffmpeg

One command muxes narration over capture. No framework needed, and adding one is where this turns into a week.

**Do not reach for Remotion.** It is the most-recommended programmatic video tool and it **requires a per-company
commercial licence**. For a one-off launch video it is both the most work and the only paid item in the pipeline.

**Motion Canvas** (MIT, TypeScript) is the free alternative _if_ the video needs animated explainer sections — it has a
live editor with waveform sync for lining animation to narration. But it has **no first-class headless server
rendering**, so it is a hand-produced tool, not an agent-driven one. Only worth it if the demo needs motion graphics the
product itself does not provide.

### 4. Making It Not Look Robotic

The gap between a Playwright capture and something worth posting is small and specific:

- **Slow the input.** Default automation types instantly, which reads as fake. `page.type(..., { delay: 60 })` and an
  explicit pause after each step
- **Pause on the evidence.** The product's whole claim is the cited post. Hold on it for 2-3 seconds — long enough to
  read a line, which is longer than feels right while editing
- **Zoom in post.** ffmpeg `zoompan` on the two or three moments that matter, rather than a cursor library
- **Record at 1440, deliver at 1080.** Downscaling hides aliasing and text renders sharper

A crop of the corroboration pair and a citation is more persuasive than a cursor tour of the whole app.

---

## What To Actually Show

**Do not demo the search box.** A query and a ranked list is indistinguishable from Google Maps, which is the exact
objection the product exists to answer.

**Demo the evidence.** In order:

1. The `/taste` wizard — this is not a search engine
2. A result **with its cited post visible**, in Chinese, with the venue name in the original script
3. **`/ask` returning `covered: false`** — "the posts don't mention whether it's halal". **This is the strongest thing
   in the product** and it takes four seconds to show. A recommender that admits what it does not know is a claim no
   maps product can make
4. The two-source corroboration pair — **blocked on [#20](https://github.com/TolongLabs/MakanLah/issues/20)**, which
   found it has never rendered

---

## Blockers Before Recording

| Blocker                                                     | Why it stops the recording                                                                                                                |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **[#20](https://github.com/TolongLabs/MakanLah/issues/20)** | The corroboration layout has never rendered. **Do not record until this is fixed** — it is the best frame in the video                    |
| **[#6](https://github.com/TolongLabs/MakanLah/issues/6)**   | No public API. A local-only API means recording against `?api=localhost`, and the URL in the post would not work for anyone who clicks it |
| **`/tmp` is a full 1 GB tmpfs**                             | Video capture needs scratch space. This must be cleared first                                                                             |
| **[#16](https://github.com/TolongLabs/MakanLah/issues/16)** | p95 4.66s. On camera that is a long, honest pause. Either cut it, or let it run and let the copy own it                                   |

**The order that makes sense: fix #20, deploy #6, clear the disk, then record.** Recording first produces a video that
has to be redone.

---

## Estimated Effort

| Step                       | Effort                                             |
| -------------------------- | -------------------------------------------------- |
| Playwright demo script     | 1-2 hours, and it doubles as an E2E test           |
| Kokoro install + narration | 1 hour, most of it the model download              |
| ffmpeg assembly + zooms    | 1 hour                                             |
| **Total**                  | **Half a day**, entirely free, no account anywhere |

---

## Sources

- [Best Open-Source TTS Models 2026 — CodeSOTA](https://www.codesota.com/speech/best-open-source)
- [Best Local TTS Models 2026: 8 Open-Source Voices Tested](https://localaimaster.com/blog/best-local-tts-models)
- [Kokoro TTS Local Setup (2026)](https://localaimaster.com/blog/kokoro-tts-local-setup)
- [Kokoro vs XTTS vs Chatterbox: Best Local TTS in 2026?](https://localaimaster.com/blog/kokoro-vs-xtts-vs-chatterbox)
- [Best Open-Source Text to Speech in 2026: 8 Free Models Ranked](https://texttolab.com/blog/open-source-text-to-speech)
- [charmbracelet/vhs](https://github.com/charmbracelet/vhs)
- [How to Create Terminal Demos as Code with VHS](https://tenthirtyam.org/dispatches/2026/04/16/how-to-create-terminal-demos-as-code-with-vhs-by-charm/)
- [Remotion vs Motion Canvas vs Revideo 2026 — PkgPulse](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026)
- [Remotion vs Motion Canvas: Code-Based Video Tools Compared](https://rendercomp.com/blog/remotion-vs-motion-canvas-comparison/)
- [Turning Playwright Tests Into Videos](https://dev.to/thepatriczek/i-was-tired-of-re-recording-product-demos-every-sprint-so-i-built-a-tool-that-turns-playwright-21od)
- [product-demo — GitHub Topics](https://github.com/topics/product-demo)

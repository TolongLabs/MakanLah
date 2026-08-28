# Live2D Model Drop-In

The taste wizard's mascot renders the **LiveroiD_A-Y01** Live2D model. The model binaries are **gitignored and not in
this repository**: they are a BOOTH download covered by the Live2D proprietary licence.

**The app runs without them.** `Mascot.tsx` keeps its text reading on screen until the model actually mounts and keeps
it permanently if the load fails, so nothing on the results path depends on this directory.

## What Is Installed, And Why It Is Not A Straight Copy

Two departures from "copy both folders", both measured rather than assumed:

| Change                                              | Reason                                                                                                                                                |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Y01's texture is resized 8192x16384 → 2048x4096** | The original is **31 MB** for a mascot that renders at about 200 CSS px. Resized it is **2.7 MB**, a 91% cut, with no visible difference at that size |
| **Y02 ships only its four `.exp3.json` files**      | `LiveroiD_A-Y02.model3.json` is never loaded, so its own 31 MB texture is never fetched. Y01 references Y02 **only** for expressions                  |

Installed weight is **4.2 MB** against 64 MB for the raw pair.

```
web/public/models/liveroid/
  LiveroiD_A-Y01/
    LiveroiD_A-Y01.model3.json      <- modelRegistry.ts points at this
    LiveroiD_A-Y01.moc3
    LiveroiD_A-Y01.physics3.json
    LiveroiD_A-Y01.cdi3.json
    LiveroiD_A-Y01.8192/texture_00.png   <- resized; the folder keeps the model's own naming
  LiveroiD_A-Y02/
    blush.exp3.json  browLink.exp3.json  cool.exp3.json  worried.exp3.json
```

To reproduce the resize from an original download:

```bash
uv run --with pillow python -c "
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
im = Image.open('texture_00.png')
im.resize((2048, im.height * 2048 // im.width), Image.LANCZOS).save('texture_00.png', optimize=True)"
```

## Verifying A Drop-In

Files under 200 bytes are Git LFS pointer stubs, not the model. That is the failure this section exists for: the copy in
the Kawan app is entirely stubs, and a stub loads as a 404 rather than as an error that names itself.

```bash
find web/public/models/liveroid -type f -size -200c
```

Anything that prints is a stub.

## Why LiveroiD And Not The Other Candidate

`tororo_hijiki_ja` was also evaluated. It is far lighter (2048 textures, ~1 MB, 206 KB moc3) and it has real motions
including an idle. **It has no expressions at all.** The mascot's whole job is reporting evidence strength across four
states, so a model with motions and no expressions cannot do it. LiveroiD carries exactly the four the binding needs:
`blush`, `browLink`, `cool`, `worried`.

## Cubism Core

`live2dcubismcore.min.js` sits one level up in `web/public/` and **is** committed. It is the Live2D Cubism Core,
distributed under the "Redistributable Code" clause of the Live2D proprietary software licence agreement. It is loaded
on demand by `src/live2d/cubismCore.ts`, never from `index.html`, so it costs nothing until the mascot mounts.

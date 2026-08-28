# Live2D Model Drop-In

The taste wizard's mascot renders the **LiveroiD_A-Y01** Live2D model. The model binaries are **not in this
repository** and are gitignored: they are a BOOTH download covered by the Live2D proprietary licence, and
`texture_00.png` alone is 31 MB, which is more than a PWA promising a decision in two minutes should carry.

**The app runs without them.** `MascotStage` catches the load failure and falls back to a text panel that reports the
same evidence strength, so nothing on the results path depends on this directory.

## What Goes Here

Both folders are required. `LiveroiD_A-Y01`'s expressions reference `../LiveroiD_A-Y02/*`, so Y01 alone will not load.

```
web/public/models/liveroid/
  LiveroiD_A-Y01/
    LiveroiD_A-Y01.model3.json      <- modelRegistry.ts points at this
    LiveroiD_A-Y01.moc3
    LiveroiD_A-Y01.physics3.json
    LiveroiD_A-Y01.cdi3.json
    blush.exp3.json  browLink.exp3.json  cool.exp3.json  worried.exp3.json
    LiveroiD_A-Y01.8192/texture_00.png
  LiveroiD_A-Y02/
    ... same shape
```

`live2dcubismcore.min.js` sits one level up in `web/public/` and **is** committed. It is the Live2D Cubism Core,
distributed under the "Redistributable Code" clause of the Live2D proprietary software licence agreement. It is loaded
on demand by `src/live2d/cubismCore.ts`, never from `index.html`, so it costs nothing until the mascot mounts.

## Verifying A Drop-In

Files under 200 bytes are Git LFS pointer stubs, not the model. That is the failure this README exists for.

```bash
find web/public/models/liveroid -type f -size -200c
```

Anything that prints is a stub. The model will not load until it is replaced with the real file.

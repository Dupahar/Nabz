# Nabz demo video

Two cuts of the same ~59-second film:
- `out/nabz_60s.mp4`: 1080×1920, for LinkedIn and X mobile.
- `out/nabz_60s_16x9.mp4`: 1920×1080, for the submission and YouTube.

Both have burned-in captions, so they work with the sound off.

## Re-render

```bash
python video/build.py                 # both cuts (≈10 min); uses the cached capture in video/cache/shots
python video/build.py --capture       # first re-capture the live app (starts its own server on :8001)
python video/build.py --only portrait --check   # one cut, plus check frames in out/check/
python video/preview.py landscape 12.5 30      # still frames for quick layout checks
```

- To change the narration, edit `script.py` (scene list, voiceover lines, `REPO_URL`). Scene lengths stretch to fit each voiceover line.
- The cut must stay ≤ 60 s. The build refuses to render otherwise.

## How it's made

| Layer | What | Real or generated |
|---|---|---|
| Voiceover | Gnani **Timbre v3.0** (voice "Shubham"), the same TTS Nabz uses for rep debriefs | Generated (Gnani TTS) |
| Live demo | The real Nabz app driven by Playwright in Chrome: PIN login, typing the visit, consent, a real upload of `demo/out/sharma-kirana-el.ogg`, the live progress chips, then the already-processed visit page and the manager dashboard | **Real app, real pipeline** |
| Voice debrief | The actual `debrief.ogg` that Timbre produced for that visit | Real output |
| Motion graphics | `timeline.html`, a deterministic virtual clock rendered frame by frame at 30 fps (pulse line, stats, callouts, badges, captions) | Generated |
| Music | A synthesized heartbeat pulse and pads (`audio.py`, numpy), ducked under speech; street ambience from the benchmark noise set | Generated, royalty-free |

## Honesty notes

- The visit audio (ElevenLabs voices plus synthetic shop noise) and the 10 dashboard visits are synthetic. A closing line says so: *"Demo visits use AI-generated voices… processed live by the real Nabz pipeline"*. The app's own synthetic-data banner and badges are visible on screen.
- **The progress chips come from a real upload.** That run was waiting in Gnani's batch queue, so the film cuts to the same recording's earlier, completed run (`20261109-180804-sharma-kirana-store`). That earlier run's result is real.
- **The dashboard was filmed on a sandbox copy** of the same app and data (port 8002). Only the manager's demo PIN was set to the documented `1234`, because the config's manager hash didn't match it. The page and data are identical.
- **One label is hidden in the progress frames.** The app's stage sentence still mentioned "denoise", which is now switched off because our benchmark showed it hurts accuracy. That one stale sentence is hidden. The chips themselves are untouched.
- **The benchmark number shown:**
  - Prisma v3.0 had 12.7% word error at 10 dB street noise.
  - Whisper small had 27% on clean audio.
  - Both were measured on our open benchmark using synthetic Hinglish (`benchmark/`).

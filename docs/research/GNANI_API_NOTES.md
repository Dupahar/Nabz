# Gnani API notes (from docs.gnani.ai, 2026-11-09)

Docs index: https://docs.gnani.ai/llms.txt · Python SDK: `pip install -U "gnani-vachana>=0.8.1"` (reads `GNANI_API_KEY`)

Base URL: `https://api.vachana.ai` · Auth header: `X-API-Key-ID: <key>`

## Prisma STT (Batch). This is the API FieldNotes needs.
Batch is the only mode that does diarization. REST is limited to 30 s clips and has no speaker labels.

1. `POST /stt/v3/batch/jobs` (multipart: `config` = JSON, `files` = audio) returns `job_id`
2. `POST /stt/v3/batch/jobs/{id}/start`. Creating a job does not start it.
3. `GET  /stt/v3/batch/jobs/{id}`. Poll at most every 10 s. Terminal: COMPLETED, PARTIAL_FAILURE, FAILED, START_FAILED, CANCELLED.
4. `GET  /stt/v3/batch/jobs/{id}/files?status=COMPLETED` returns a `transcript_url` that expires after 1 h.
5. Webhook alternative: pass `callback_url` at creation. Delivery is best-effort; polling is the source of truth.

Config fields used by FieldNotes:
| field | value | why |
|---|---|---|
| model | `prisma-v3.0` | code-mix, auto language detection, hints |
| language_code | `indic-auto` or `hi-IN,en-IN` | Hinglish field calls |
| format | `codemix` | English words in Latin script inside Hindi |
| keyterms | ≤200 | product catalogue, SKUs, competitor names (from CRM) |
| topic | ≤1600 chars | "Sales meeting between <rep> and <account> about ..." |
| speaker_names | 1–4 | rep + customer names (can't be combined with keyterms) |
| with_diarization | true | fail the file if diarization fails |
| num_speakers | 2–3 | upper bound (1–8) |
| with_denoise | true | noisy shop floors and car parks |

Output: `full_transcript`, `duration_seconds`, `segments[]` with `segment_id, start_time, end_time, text, speaker_id, confidence, language_detected, sentiment, emotion`.
Limits: 10 MB per file on multipart (presigned `/stt/v3/batch/v2/jobs` up to 5 GiB), 4 h max. No inverse text normalisation on Batch.
Errors: 400 INVALID_CONFIG for v3-only fields on v2.5 or for invalid field combos.

## Timbre TTS (REST)
`POST /api/v1/tts/inference` with JSON `{text, model: timbre-v3.0|timbre-v2.5, voice, language, speed, audio_config: {container: ogg|mp3|wav, sample_rate}}`. Returns raw audio bytes.
- Languages: auto, hi-IN, en-IN, ta-IN, te-IN, kn-IN, ml-IN, mr-IN, pa-IN, bn-IN, gu-IN, hi-en (Hinglish)
- v3.0 voices (all 10 languages): Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash, Devansh, Yashraj, Chetana, Vasudha, Riyaa, Tarika, Harshad. v3.0 supports inline tags like `<pauses>`.
- `container: ogg` with `encoding: oggopus` produces a Telegram/WhatsApp voice-note format directly.
- Write numbers and amounts as words. Overly long text returns a 500, so chunk it.
- Also available: SSE, WebSocket, and voice cloning (a manager's own voice for the debriefs?).

## Evon
No hosted Evon API appears in the docs. Gnani's own call-analytics guide (`/api/use-cases/call-analytics.md`) uses Claude or GPT-4o for the LLM step, so pairing Prisma with Claude is the pattern Gnani itself documents.

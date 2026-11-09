# Nabz web API (contract between app/server.py and app/static/*)

Served by FastAPI on http://localhost:8000. All JSON. Auth is a demo login: the user picks a person
from `config/workspace.yaml`, stored in cookie `nabz_user` (their handle). Every API call is
evaluated for that user's role.
- **rep:** own visits only.
- **manager:** all visits plus intel.
- **admin:** everything, plus audit and erasure.

Without the cookie, the API returns 401 `{"detail": "login"}`.

## Pages (static HTML)
- `GET /`: rep app (`static/rep.html`), mobile-first. Records a visit and lists my visits.
- `GET /dashboard`: market intelligence and team (`static/dashboard.html`). For managers and admins;
  a rep sees "ask your manager".
- `GET /visit/{call_id}`: one visit (`static/visit.html`).
- `GET /login`: pick a user (`static/login.html`).
- Shared assets: `static/style.css`, `static/common.js`. Chart.js loads from the jsDelivr CDN.

## Session
- `POST /api/login` with `{"handle": "arjun"}` sets the cookie and returns the user object.
- `POST /api/logout`
- `GET /api/me` returns `{"name","handle","role","language","region"}`
- `GET /api/config` returns `{"company","about","team":[user...],"segments":[...],"lenses":[{"id","name","score_label"}],"products":[...],"competitors":[...]}`

## Visits
`POST /api/visits` takes `multipart/form-data` with these fields:
- `audio`: a file (webm/ogg/m4a/mp3/wav)
- `account`: the customer's shop or organisation (string)
- `contact`: the person met (string, optional)
- `segment`: one of config.segments
- `region`: optional; defaults to the rep's region
- `consent_method`: `verbal` | `rep-confirmed` | `written`
- `consent_confirmed`: `"true"`. Required; without it the API returns 400.
- `note`: optional rep note

Response: `{"call_id": "...", "status": "queued"}`. Processing runs in the background.

`GET /api/visits?scope=mine|all&limit=50` returns a list, newest first:

```json
[{"call_id","account","contact","segment","region","rep","rep_handle","recorded_at","duration_sec",
  "status","stage","error",
  "lens","lens_name","score_label","score","sentiment","summary","flags":0,"debrief":true}]
```

`status` is one of `queued|transcribing|analysing|voicing|done|error`. `stage` is human-readable
text such as "Transcribing with Gnani Prisma…". The analysis fields are null until `done`.

`GET /api/visits/{call_id}` returns:

```json
{
  "visit": {...same as list item...},
  "consent": {"method","confirmed_by","subject","recorded_at","purpose"},
  "transcript": {"language","languages":[...],"engine","model","diarized":true,
                 "segments":[{"i","start","end","speaker_label","speaker_name","side","text"}]},
  "redactions": {"counts": {"PHONE": 1}},
  "analysis": {...analysis.json (see tools/analysis.py template)...},
  "metrics": {...metrics.json or null...},
  "notes_md": "markdown",
  "followup": {"to","subject","body","status": "drafted|sent|rejected"},
  "crm_proposal": {"account","stage","value_inr","next_step","next_date","status": "proposed|approved|rejected", "approved_by"},
  "lens": {"id","name","score_label","checklist": {"key":"question"}},
  "audit": [{"ts","actor","action","detail"}],
  "assets": {"debrief": "/api/visits/{id}/debrief.ogg" | null, "scorecard": "/api/visits/{id}/scorecard.png" | null}
}
```

- `GET /api/visits/{id}/debrief.ogg` and `GET /api/visits/{id}/scorecard.png` return files.
- `POST /api/visits/{id}/approve` with `{"crm": true, "followup": true}` returns `{"ok": true, "applied": [...]}`.
  Only managers, or the visit's own rep, can approve.
- `POST /api/visits/{id}/reject` returns `{"ok": true}`.
- `POST /api/visits/{id}/erase` returns `{"ok": true}`. Consent withdrawn: everything for the visit
  is deleted, and a tombstone stays in the audit log. Allowed for the rep, an admin, or a manager.

## Market intelligence (managers and admins)
`GET /api/intel?days=30&region=All&segment=All` returns:

```json
{
  "kpis": {"visits": 12, "avg_score": 64, "reps": 3, "hours_audio": 1.2, "compliance_flags": 1,
           "consent_rate": 1.0, "pii_redacted": 7, "quotes_verified": 0.98},
  "competitors": [{"name": "Britannia", "mentions": 5, "negative_for_us": 3, "regions": {"Delhi NCR": 3, "Mumbai": 2},
                   "quotes": [{"call_id","account","text","quote"}]}],
  "signals_by_type": [{"type": "price", "count": 6, "by_region": {"Delhi NCR": 4}}],
  "demand": [{"product": "Maggi", "count": 4, "positive": 3, "negative": 1}],
  "price_sensitivity": [{"segment": "Kirana", "visits": 6, "price_concern_rate": 0.5}],
  "concerns": [{"category": "price", "count": 5, "unhandled": 3}],
  "voice_of_customer": [{"call_id","account","segment","region","type","polarity","product","competitor","text","quote","recorded_at"}],
  "reps": [{"name","handle","region","visits","avg_score","talk_ratio","questions","spin": {"implication": 1, "need-payoff": 2},
            "top_tip": "..."}],
  "compliance": [{"call_id","account","rep","rule","severity","quote"}],
  "trend": [{"date": "2026-11-09", "visits": 3, "avg_score": 61}],
  "regions": ["Delhi NCR", "Mumbai", "Lucknow"],
  "segments": ["Kirana", "..."]
}
```

## Trust and admin
- `GET /api/trust` returns `{"audit_ok": true, "audit_events": 120, "audit_head": "ab12…", "consent_rate": 1.0, "pii_redacted": 7, "quotes_verified": 0.98, "data_region": "Gnani batch results: AWS ap-south-1 (Mumbai)", "retention": {"audio_days": 1, "transcripts_days": 365}}`
- `GET /api/cost?days=30` returns `{"stt_minutes","tts_chars","llm_tokens","inr": null|number,"per_visit": {...}}`
- `GET /api/audit?limit=100`: admin only. Returns the list of audit events.

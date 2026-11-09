"""The video's script: scenes, voiceover lines and on-screen captions. Edit here, then `python video/build.py`.

Every voiceover line is spoken by Gnani Timbre v3.0 (the same TTS that voices Nabz's debriefs).
Scene durations stretch to fit their voiceover, so changing a line re-times the cut automatically.
"""

REPO_URL = "github.com/Dupahar/Nabz"   # shown on the closing card
NARRATOR = {"voice": "Shubham", "model": "timbre-v3.0", "speed": 1.08}

# id: scene renderer in timeline.html · min: minimum seconds · vo: list of (language, text)
SCENES = [
    {"id": "hook", "min": 5.2, "vo": [("en-IN", "Sharma ji just switched to Britannia. Fifteen days' credit.")]},
    {"id": "reveal", "min": 4.6, "vo": [("en-IN", "Your head office finds out next quarter. Nabz hears it today.")]},
    {"id": "stats", "min": 6.0, "vo": [("en-IN", "Eighty-nine percent of India's offline FMCG sales happen in general trade. "
                                                  "None of what's said there reaches HQ.")]},
    {"id": "rep", "min": 7.5, "vo": [("en-IN", "The rep takes consent and records the visit. "
                                                "Gnani Prisma transcribes the Hinglish, separates speakers and cuts the noise.")]},
    {"id": "visit", "min": 6.0, "vo": [("en-IN", "Phone numbers are redacted before any AI sees them. "
                                                  "Every insight is quoted, and verified against the transcript.")]},
    {"id": "debrief", "min": 6.0, "vo": [], "audio": "debrief"},   # the real Timbre debrief plays here
    {"id": "dash", "min": 8.0, "vo": [("en-IN", "And the manager feels the market's pulse. Britannia's credit push in Delhi. "
                                                 "Patanjali in Lucknow. In the customer's own words.")]},
    {"id": "trust", "min": 6.5, "vo": [("en-IN", "Consent first. P I I redacted. Quotes verified in code. Built on Gnani AI.")]},
    {"id": "cta", "min": 5.0, "vo": [("hi-en", "Nabz. Bazaar ki nabz, har baat se.")]},
]

# Captions shown on screen (spoken text, lightly tidied). Same order as the vo lines.
CAPTION_FIX = {"P I I": "PII", "Eighty-nine percent": "89%", "Fifteen days'": "15 days'"}

MAX_SECONDS = 60.0
FPS = 30

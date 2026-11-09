"""The film: scenes, voiceover lines and captions. Edit here, then `python video/build.py`.

Every voiceover line is spoken by Gnani Timbre v3.0. Scene durations stretch to fit their voiceover.
Structure: cold open (problem) → reveal → three feature beats → the market, live → trust → end card.
"""

REPO_URL = "github.com/Dupahar/Nabz"
NARRATOR = {"voice": "Shubham", "model": "timbre-v3.0", "speed": 1.08}

SCENES = [
    {"id": "hook", "min": 5.2, "vo": [("en-IN", "Sharma ji just switched to Britannia. Fifteen days' credit.")]},
    {"id": "reveal", "min": 4.6, "vo": [("en-IN", "Your head office finds out next quarter. Nabz hears it today.")]},
    {"id": "stats", "min": 6.0, "vo": [("en-IN", "Eighty-nine percent of India's offline FMCG sales happen in general trade. "
                                                  "None of what's said there reaches HQ.")]},
    {"id": "capture", "min": 7.5, "vo": [("en-IN", "The rep takes consent and records the visit. "
                                                    "Gnani Prisma transcribes the Hinglish and separates the speakers, even over street noise.")]},
    {"id": "understands", "min": 6.0, "vo": [("en-IN", "Phone numbers are redacted before any AI sees them. "
                                                        "Every insight is quoted, and verified against the transcript.")]},
    {"id": "coaching", "min": 6.0, "vo": [], "audio": "debrief"},   # the real Timbre debrief plays here
    {"id": "market", "min": 8.0, "vo": [("en-IN", "And the manager feels the market's pulse. Britannia's credit push in Delhi. "
                                                   "Patanjali in Lucknow. In the customer's own words.")]},
    {"id": "trust", "min": 6.5, "vo": [("en-IN", "Consent first. P I I redacted. Quotes verified in code. Built on Gnani AI.")]},
    {"id": "end", "min": 5.0, "vo": [("hi-en", "Nabz. Bazaar ki nabz, har baat se.")]},
]

# The 2-3 minute product demo (16:9). Same voice; live footage from the real app throughout.
SCENES_DEMO = [
    {"id": "hook", "min": 6.0, "vo": [("en-IN", "Sharma ji just switched to Britannia. Fifteen days' credit. "
                                                 "Your rep heard it at the counter.")]},
    {"id": "stats", "min": 9.0, "vo": [("en-IN", "Eighty-nine percent of India's offline FMCG sales happen in general trade. "
                                                  "Thousands of these conversations happen every day, and none of what's said reaches head office. "
                                                  "Until next quarter's report.")]},
    {"id": "reveal", "min": 7.0, "vo": [("en-IN", "Nabz hears it today. Kirana-counter intelligence, for FMCG brands.")]},
    {"id": "login", "min": 9.0, "vo": [("en-IN", "Here is a real visit. Arjun, a distributor rep in Delhi, opens Nabz on his phone "
                                                  "and logs in with his PIN. He notes the shop and the person he's meeting.")]},
    {"id": "consent", "min": 8.0, "vo": [("en-IN", "Before recording, he reads a short consent notice, in Hinglish. "
                                                    "No consent, no processing.")]},
    {"id": "upload", "min": 11.0, "vo": [("en-IN", "He records the visit, or uploads it. Gnani Prisma transcribes the Hinglish, "
                                                    "separates the speakers, and holds up in street noise.")]},
    {"id": "transcript", "min": 8.0, "vo": [("en-IN", "Every line is labelled by speaker. The phone number Sharma ji read out "
                                                       "is redacted before any AI sees it.")]},
    {"id": "score", "min": 11.0, "vo": [("en-IN", "The visit is scored through an FMCG lens: order taken, scheme explained, stock checked, "
                                                   "competitor noted. And the market signals are pulled out: Britannia's credit, and a slow-moving SKU.")]},
    {"id": "quote", "min": 9.0, "vo": [("en-IN", "Every insight is quoted, and code checks the quote. Click one, and the transcript "
                                                  "shows exactly where it was said. Twenty-four of twenty-four, verified.")]},
    {"id": "coach", "min": 9.5, "vo": [("en-IN", "Arjun gets his coaching as a voice note, in his own language, from Gnani Timbre.")],
     "audio": "debrief", "audio_after_vo": True},
    {"id": "tips", "min": 6.0, "vo": [("en-IN", "What went well, and one thing to try next time.")]},
    {"id": "act", "min": 11.0, "vo": [("en-IN", "Nothing touches the CRM without a person. His manager reviews the proposed update "
                                                 "and follow-up, and approves. Every action goes into a tamper-evident audit log.")]},
    {"id": "market", "min": 15.0, "vo": [("en-IN", "And head office feels the market's pulse, live. Britannia's credit push across Delhi. "
                                                    "Patanjali at Lucknow chemists. In the customer's own words, with compliance flags "
                                                    "and a verified audit chain.")]},
    {"id": "hood", "min": 9.0, "vo": [("en-IN", "Under the hood, Gnani Prisma and Timbre. Two percent word error on clean Hinglish. "
                                                 "About thirty paise of analysis per visit.")]},
    {"id": "end", "min": 6.0, "vo": [("hi-en", "Nabz. Bazaar ki nabz, har baat se.")]},
]
DEMO_MIN, DEMO_MAX = 130.0, 165.0

CAPTION_FIX = {"P I I": "PII", "Eighty-nine percent": "89%", "Fifteen days'": "15 days'", "reaches HQ": "reaches head office",
               "Two percent": "2%", "Twenty-four of twenty-four": "24 of 24", "thirty paise": "₹0.30"}

MAX_SECONDS = 60.0
FPS = 30

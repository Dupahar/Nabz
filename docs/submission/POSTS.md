# Posts

The interview shortlist is ranked on verified engagement by the deadline, so post as early as
possible and reply to every comment. Don't buy engagement or swap it: that disqualifies.

## Post 1: LinkedIn (attach the 60-second video)

Sharma ji switched to Britannia because of 15 days' credit.
Your head office finds out next quarter. **Nabz hears it today.**

89% of India's offline FMCG sales go through traditional trade (NIQ). The conversations that decide
them happen at the kirana counter, in Hinglish, over traffic noise. Nobody at the brand ever hears them.

So I built **Nabz** (नब्ज़, "pulse": *bazaar ki nabz*) on @Gnani.ai's Indian speech models:

🎙️ The salesman records the visit on his phone, after the owner says yes. Consent comes first.
🧠 Gnani **Prisma** transcribes the noisy Hinglish, separates the speakers, and gets "Parle-G" and "carton" right.
🔒 Phone numbers are redacted before any AI sees the text, even when spoken as "nau aath chaar…".
📊 Every market signal (competitor credit, scheme confusion, slow movers) is backed by a quote that code checks against the transcript.
🔊 The rep gets a 20-second coaching voice note in his own language, spoken by Gnani **Timbre**.

Demo note: the dashboard uses synthetic visits voiced by AI, run through the real pipeline. The opening clip is a real recording.

Code and noise benchmark: github.com/Dupahar/Nabz

Which FMCG category should I pilot with first: snacks, beverages or staples? 👇

#GnaniAI #GreatIndianAIInternshipChallenge #FMCG #VoiceAI #IndianLanguages #Kirana

## Post 1: X thread

1/ Sharma ji switched to Britannia because of 15 days' credit. Your head office finds out next quarter. Nabz hears it today. 🧵 [video]
#GnaniAI #GreatIndianAIInternshipChallenge

2/ 89% of India's offline FMCG sales go through kiranas (NIQ). The conversations happen at the counter, in Hinglish, over traffic. Brands never hear them.

3/ Nabz: the salesman records the visit (after consent). @GnaniAI Prisma transcribes the noisy Hinglish, separates the speakers, and gets the brand names right.

4/ Every insight ("Britannia giving 15-day credit", "10+1 scheme too big") must quote the transcript. Code checks it. No quote, no claim.

5/ The rep gets a 20-sec coaching voice note in his own language, from Gnani Timbre. Phone numbers are redacted before any AI sees the text.

6/ Demo dashboard = synthetic visits, voiced by AI, through the real pipeline. Code and benchmark: github.com/Dupahar/Nabz

## Post 2: the benchmark (a day later, or as the first comment)

How well does Indian speech AI hear a real shop counter?

I tested Gnani **Prisma v3.0** against **Whisper** on Hinglish and English field-sales conversations
at 20 → 0 dB of street, cafeteria and crowd noise, with the phone about 1.7 m away in a simulated shop.

To keep it fair, every conversation was voiced twice, by Gnani Timbre and by **independent ElevenLabs
voices**, so Gnani's own TTS isn't grading Gnani's ASR.

- Clean Hinglish: **Prisma about 2% word error**, Whisper medium 8–12%, Whisper small 22–27%
- At 10 dB of street noise: **Prisma 11–14%** vs Whisper medium 23–31%
- Brand, price and day **keyterm recall** at 10 dB: **Prisma 89%** vs Whisper medium 60%
- Where Prisma didn't win: on Indian English at 0 dB, Whisper was as good or better
- A surprise: Prisma's built-in `denoise` option made accuracy *worse* (12.7% → 21.4% at 10 dB), so I turned it off
- Where it still slips: "Delhivery" → "delivery", even with keyterms

At 0 dB (noise as loud as the speech) every model loses about half the words, so put the phone
between the two speakers.

Method, code and caveats (synthetic speech, simulated rooms, 6 conversations per voice source):
github.com/Dupahar/Nabz/tree/main/benchmark

#GnaniAI #GreatIndianAIInternshipChallenge #SpeechRecognition #IndicAI

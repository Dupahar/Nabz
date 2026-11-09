"""Script-agnostic text normalisation for scoring code-mixed (Hinglish) speech-to-text output.

The problem: the same spoken word can legitimately be written as "मीटिंग" or "meeting", "दस" or
"10" or "das". Plain WER would count every such difference as an error. Every reference and every
hypothesis goes through the same rules below, so no system gets special treatment:

 1. Unicode NFC; Devanagari digits -> ASCII; remove thousands separators inside numbers (48,000 -> 48000).
 2. Devanagari runs are transliterated to Latin with ITRANS (indic-transliteration), then:
    retroflex/long-vowel capitals are lower-cased (T->t, A->a, ...), anusvara M -> n,
    chandrabindu/nukta/visarga marks dropped, and the inherent word-final schwa removed
    (दस -> "dasa" -> "das").
 3. Lower-case; punctuation (incl. the danda ।) removed; hyphens split words.
 4. Loose spelling: z->j, f->ph, w->v, q->k, x->ks, ee->i, oo->u, and any doubled letter collapsed
    (chattis/chatis, maggi/magi). This makes "zyada"/"jyada"/"ज़्यादा" one token.
 5. Number words in Hindi (Devanagari or romanised) and English are converted to digits and
    multi-word amounts are combined: "अड़तालीस हज़ार" / "48 hazar" / "forty eight thousand" -> 48000,
    "दस हज़ार दो सौ" -> 10200, "two lakh ten thousand" -> 210000, "1.8 lakh" -> 180000.
    Ordinals become digits (fifteenth / 15th -> 15). "percent"/"परसेंट"/"%" -> "percent".

These rules are deliberately loose; they can merge genuinely different words (e.g. "tin"/"तीन").
That is the same for every system, and keyterm recall is reported separately as the business metric.
"""

from __future__ import annotations

import re
import unicodedata

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

DEVANAGARI_RUN = re.compile(r"[ऀ-ॿ]+")
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _itrans_word(word: str) -> str:
    word = word.replace("ॉ", "ो").replace("ऑ", "ओ")  # candra o -> o
    t = transliterate(word, sanscript.DEVANAGARI, sanscript.ITRANS)
    t = t.replace(".N", "n").replace(".n", "n").replace(".D", "d").replace(".Dh", "dh").replace("~", "")
    t = t.replace(".h", "").replace(".", "").replace("^", "")
    t = t.replace("RRi", "ri").replace("R^i", "ri").replace("M", "n").replace("H", "h")
    t = t.replace("Sh", "sh").replace("GY", "gy").replace("JN", "gy")
    # word-final inherent (short) schwa: consonant + 'a' at the end (dasa -> das). ITRANS writes the
    # long vowel as 'A', so checking before lower-casing keeps ज़्यादा -> zyada.
    if len(t) > 2 and t.endswith("a") and t[-2] not in "aeiouAEIOU":
        t = t[:-1]
    return t.lower()


def devanagari_to_latin(text: str) -> str:
    return DEVANAGARI_RUN.sub(lambda m: _itrans_word(m.group(0)), text)


def _loose(token: str) -> str:
    t = token
    for a, b in (("z", "j"), ("f", "ph"), ("w", "v"), ("q", "k"), ("x", "ks"), ("ee", "i"), ("oo", "u")):
        t = t.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", t)


def _base_tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).translate(DEV_DIGITS)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    text = text.replace("%", " percent ").replace("₹", " rupees ")
    text = devanagari_to_latin(text)
    text = text.lower().replace("-", " ")
    text = re.sub(r"[^\w\s.]", " ", text)  # keep '.' for decimals for now
    out = []
    for tok in text.split():
        tok = tok.strip(".")
        if not tok:
            continue
        if re.fullmatch(r"\d+(\.\d+)?", tok):
            out.append(tok)
            continue
        m = re.fullmatch(r"(\d+)(st|nd|rd|th)", tok)
        if m:
            out.append(m.group(1))
            continue
        tok = tok.replace(".", " ")
        out.extend(_loose(t) for t in tok.split() if t)
    return out


# ---- number words -------------------------------------------------------------------------
_HI_UNITS = {
    "शून्य": 0, "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "छः": 6, "छे": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15, "पन्द्रह": 15,
    "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19, "बीस": 20, "इक्कीस": 21, "बाईस": 22, "तेईस": 23,
    "चौबीस": 24, "पच्चीस": 25, "छब्बीस": 26, "सत्ताईस": 27, "अट्ठाईस": 28, "उनतीस": 29, "तीस": 30,
    "इकतीस": 31, "बत्तीस": 32, "तैंतीस": 33, "चौंतीस": 34, "पैंतीस": 35, "छत्तीस": 36, "सैंतीस": 37,
    "अड़तीस": 38, "उनतालीस": 39, "चालीस": 40, "इकतालीस": 41, "बयालीस": 42, "तैंतालीस": 43, "चवालीस": 44,
    "पैंतालीस": 45, "छियालीस": 46, "सैंतालीस": 47, "अड़तालीस": 48, "अड़तालिस": 48, "उनचास": 49, "पचास": 50,
    "पचपन": 55, "साठ": 60, "पैंसठ": 65, "सत्तर": 70, "पचहत्तर": 75, "अस्सी": 80, "नब्बे": 90,
}
_HI_MULT = {"सौ": 100, "हज़ार": 1000, "हजार": 1000, "लाख": 100000, "करोड़": 10**7, "करोड": 10**7}
_EN_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
_EN_UNITS.update({"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90})
_EN_MULT = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lakhs": 100000, "lac": 100000, "crore": 10**7,
            "crores": 10**7, "million": 10**6}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
             "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
             "fifteenth": 15, "sixteenth": 16, "twentieth": 20, "thirtieth": 30}

UNITS: dict[str, float] = {}
MULTS: dict[str, int] = {}
for _src, _dst in ((_HI_UNITS, UNITS), (_HI_MULT, MULTS)):
    for _w, _v in _src.items():
        for _t in _base_tokens(_w):
            _dst[_t] = _v
for _src, _dst in ((_EN_UNITS, UNITS), (_EN_MULT, MULTS)):
    for _w, _v in _src.items():
        _dst[_loose(_w)] = _v
# romanised Hindi that the transliteration rules don't produce on their own
for _w, _v in {"hazar": 1000, "hajar": 1000, "lakh": 100000, "lac": 100000, "karod": 10**7, "karor": 10**7}.items():
    MULTS[_loose(_w)] = _v
ORDINALS = {_loose(k): v for k, v in _ORDINALS.items()}
SYNONYMS = {t: "percent" for w in ("परसेंट", "प्रतिशत", "pratishat", "persent", "parsent") for t in _base_tokens(w)}
SYNONYMS[_loose("percent")] = "percent"
SYNONYMS[_loose("per cent")] = "percent"
SYNONYMS["rs"] = "rupees"
for t in _base_tokens("रुपये") + _base_tokens("रुपए") + ["rupe", "rupay", "rupaye", "rupee", "rupes"]:
    SYNONYMS[t] = "rupees"


def _is_num(tok: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)?", tok)) or tok in UNITS


def _combine(tokens: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ORDINALS and not _is_num(tok):
            out.append(str(ORDINALS[tok]))
            i += 1
            continue
        if not _is_num(tok):
            out.append(SYNONYMS.get(tok, tok))
            i += 1
            continue
        total, cur, j = 0.0, 0.0, i
        while j < len(tokens) and (_is_num(tokens[j]) or tokens[j] in MULTS):
            t = tokens[j]
            if t in MULTS:
                m = MULTS[t]
                if m == 100:
                    cur = (cur or 1) * 100
                else:
                    total += (cur or 1) * m
                    cur = 0
            else:
                v = float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else UNITS[t]
                if cur == 0:
                    cur = v
                elif (cur >= 100 and v < 100) or (cur >= 20 and cur % 10 == 0 and v < 10):
                    cur += v  # "ek sau bees", "twenty four"
                else:
                    break  # two separate numbers in a row ("15 15"): end this amount here
            j += 1
        value = total + cur
        out.append(str(int(value)) if float(value).is_integer() else f"{value:g}")
        i = j
    return out


def normalize_tokens(text: str) -> list[str]:
    return _combine(_base_tokens(text))


def normalize(text: str) -> str:
    return " ".join(normalize_tokens(text))


def _key(tok: str) -> str:
    """Consonant skeleton of a token, so 'delivery'/'डिलीवरी', 'scheme'/'स्कीम', 'margin'/'मार्जिन' match."""
    if tok.isdigit() or tok in ("percent", "rupees"):
        return tok
    t = tok.replace("sch", "sk").replace("ck", "k").replace("ph", "f").replace("ksh", "ks")
    t = re.sub(r"c(?=[eiy])", "s", t)
    t = re.sub(r"c(?!h)", "k", t)
    t = re.sub(r"g(?=[ei])", "j", t)
    t = re.sub(r"(?<=[bdgkpt])h", "", t)  # aspiration varies in romanised Hindi: bh/b, th/t
    head, rest = t[:1], re.sub(r"[aeiouy]", "", t[1:])
    k = re.sub(r"(.)\1+", r"\1", head + rest)
    return k or tok


def phonetic(text: str) -> str:
    """normalize() plus a per-token consonant skeleton. Lenient by design: it also merges some different
    short words (का/की/के -> k), equally for every system. Used for the 'phonetic WER' column."""
    return " ".join(_key(t) for t in normalize_tokens(text))


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    samples = [
        "सब मिलाकर अड़तालीस हज़ार रुपये। Payment सोमवार तक कर दीजिए।",
        "सब मिलाकर 48,000 रुपए, payment Monday तक",
        "लगभग दस हज़ार दो सौ रुपये महीना।",
        "Our price is two lakh ten thousand, Kirloskar quoted 1.8 lakh.",
        "दस tablets का strip एक सौ बीस रुपये का है।",
        "Interest rate 14% है और tenure 36 महीने",
        "चौदह परसेंट बहुत ज़्यादा है",
        "Our budget meeting is on the fifteenth / 15th.",
        "Parle-G की दस पेटी चाहिए",
        "डॉक्टर मेहता, twenty four hours",
    ]
    for s in samples:
        print(f"{s}\n   -> {normalize(s)}")

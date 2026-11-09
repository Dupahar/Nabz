"""Quote verification must reject altered quotes (the audit's attacks) and accept real ones."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from analysis import find_quote, ground  # noqa: E402

SEGS = [
    {"i": 0, "speaker": "S1", "text": "Namaste Sharma ji, kaisa chal raha hai?"},
    {"i": 1, "speaker": "S2", "text": "We will not switch to Britannia, don't worry."},
    {"i": 2, "speaker": "S2", "text": "Bas paanch carton bhej do. Price is 120 rupees."},
    {"i": 3, "speaker": "S1", "text": "Hum is hafte 5 cartons bhejenge."},
    {"i": 4, "speaker": "S2", "text": "Abhi main interested nahi hoon, baad mein dekhte hain."},
    {"i": 5, "speaker": "S2", "text": "इस हफ़्ते Parle-G के पाँच carton भेज दो।"},
]


def ok(q, hint=None):
    return find_quote(q, SEGS, hint)[0]


def test_exact_quotes_verify():
    assert ok("We will not switch to Britannia")
    assert ok("bas paanch carton bhej do", 2)
    assert ok("इस हफ्ते Parle-G के पाँच carton")  # nukta variant folded


def test_negation_flip_rejected():
    assert not ok("We will switch to Britannia, don't worry")
    assert not ok("Abhi main interested hoon, baad mein dekhte hain")


def test_number_change_rejected():
    assert not ok("Hum is hafte 50 cartons bhejenge")
    assert not ok("Bas paanch carton bhej do. Price is 210 rupees")


def test_cross_speaker_stitching_rejected():
    # words from S1 (segment 0) and S2 (segment 1) glued together
    assert not ok("kaisa chal raha hai We will not switch")


def test_same_speaker_continuation_allowed():
    assert ok("don't worry Bas paanch carton bhej do")


def test_partial_word_rejected():
    # substring inside a word must not count ("ritannia" is not a word in the transcript)
    assert not ok("ritannia don't")


def test_too_short_rejected():
    assert not ok("Britannia")


def test_ground_corrects_wrong_segment():
    a = {"needs": [{"text": "x", "quote": "Bas paanch carton bhej do", "segment": 0}], "checklist": {}}
    g = ground(a, SEGS)
    assert g["verified"] == 1 and a["needs"][0]["segment"] == 2

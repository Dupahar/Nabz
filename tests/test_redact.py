"""Redaction: catch Indian identifiers however they are spoken; never damage prices."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from redact import redact_segments, redact_text  # noqa: E402


def red(t):
    return redact_text(t)


def test_phone_spoken_english_digits():
    out, found = red("mera number nine eight four five zero one two three four five hai")
    assert "PHONE" in found and "9845" not in out


def test_phone_spoken_tens():
    out, found = red("call me on ninety eight forty five zero one two three four five")
    assert "PHONE" in found, out


def test_phone_spoken_hindi_devanagari():
    out, found = red("नंबर नौ आठ चार पांच शून्य एक दो तीन चार पांच है")
    assert "PHONE" in found


def test_phone_written_grouped():
    assert "PHONE" in red("98450 12345 pe call karo")[1]


def test_pan_gstin_ifsc_lowercase_email():
    out, found = red("PAN ABCPE1234F, GST 27ABCDE1234F1Z5, ifsc hdfc0001234, mail priya@brightmart.in")
    assert {"PAN", "GSTIN", "IFSC", "EMAIL"} <= set(found)


def test_aadhaar_needs_valid_checksum():
    assert "AADHAAR" in red("aadhaar 2345 6789 0124")[1]
    assert "AADHAAR" not in red("aadhaar 2345 6789 0125")[1]


def test_prices_not_merged():
    out, found = red("rates hain 120 150 180 200, aur MRP 45")
    assert found == [] and out == "rates hain 120 150 180 200, aur MRP 45"


def test_amounts_and_quantities_untouched():
    text = "paanch carton aur teen carton, chaar lakh assi hazaar, 4,80,000 per month"
    assert red(text) == (text, [])


def test_split_across_segments_same_speaker():
    segs = [{"i": 0, "speaker": "S2", "text": "mera number nine eight four five"},
            {"i": 1, "speaker": "S2", "text": "zero one two three four five, likh lo"}]
    hits = redact_segments(segs)
    assert any(h["type"] == "PHONE" for h in hits)
    assert "9845" not in segs[0]["text"] and "012345" not in segs[1]["text"]


def test_split_across_different_speakers_not_joined():
    segs = [{"i": 0, "speaker": "S1", "text": "order 98450"}, {"i": 1, "speaker": "S2", "text": "12345 boxes"}]
    assert redact_segments(segs) == []

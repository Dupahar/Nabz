"""Set a team member's login PIN (stored as a salted PBKDF2-SHA256 hash in config/workspace.yaml).

    python tools/set_pin.py --handle arjun --pin 4821
    python tools/set_pin.py --all --pin 1234        # demo: same PIN for everyone (change before real use)

The PIN never appears in the file, only `pin_hash: "pbkdf2_sha256$<iterations>$<salt>$<hash>"`.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re

from common import CONFIG_FILE, utf8_stdout, workspace

ITERATIONS = 200_000


def hash_pin(pin: str, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def check_pin(pin: str, stored: str | None) -> bool:
    if not stored or not pin:
        return False
    try:
        alg, iterations, salt, digest = stored.split("$")
        if alg != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, TypeError):
        return False


def set_pin(handle: str, pin: str) -> None:
    text = CONFIG_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"^(\s*- \{[^}\n]*\bhandle: " + re.escape(handle) + r"\b[^}\n]*?)(, pin_hash: \"[^\"]*\")?\}", re.M)
    if not pattern.search(text):
        raise SystemExit(f"error: no team member with handle '{handle}' (one-line {{...}} entries expected)")
    text = pattern.sub(lambda m: f'{m.group(1)}, pin_hash: "{hash_pin(pin)}"}}', text, count=1)
    CONFIG_FILE.write_text(text, encoding="utf-8")


def main() -> None:
    utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--handle")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pin", required=True)
    args = ap.parse_args()
    if not re.fullmatch(r"\d{4,8}", args.pin):
        raise SystemExit("error: PIN must be 4-8 digits")
    handles = [m["handle"] for m in workspace().get("team", [])] if args.all else [args.handle]
    if not handles or handles == [None]:
        raise SystemExit("error: give --handle or --all")
    for h in handles:
        set_pin(h, args.pin)
        print(f"PIN set for {h}")


if __name__ == "__main__":
    main()

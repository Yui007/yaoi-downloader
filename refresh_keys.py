#!/usr/bin/env python3
"""Compatibility wrapper for the old key recovery script.

The app stores verified constants in ``keys.json``. ``--write`` also patches the
legacy ``basic.py`` constants for anyone still calling that script.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from yaoi import config
from yaoi.app_context import source_from_settings
from yaoi.sources.yaoi import BASE

BASIC_PATH = Path(__file__).with_name("basic.py")


def patch_basic(path: Path, sign_key: bytes, seal_key: bytes) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    for name, value in (("SIGN_KEY", sign_key), ("SEAL_KEY", seal_key)):
        hex_value = value.hex()
        block = (
            f"{name} = bytes.fromhex(\n"
            f'    "{hex_value[:32]}"\n'
            f'    "{hex_value[32:]}"\n'
            f")"
        )
        pattern = rf"{name}\s*=\s*bytes\.fromhex\(\s*(?:\"[0-9a-fA-F]+\"\s*)+\)"
        if not re.search(pattern, text):
            raise SystemExit(f"Could not find {name} in {path}.")
        text = re.sub(pattern, block, text, count=1)
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default=BASE, help="Any yaoi.me page with a chapter.")
    parser.add_argument("--write", action="store_true", help="Also patch basic.py constants.")
    parser.add_argument("--check", action="store_true", help="Exit 2 when keys drifted.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    settings = config.load_settings()
    source = source_from_settings(settings)
    current = source.store.load()
    try:
        from yaoi.sources import keys as keylib

        live = keylib.refresh(source.client, source.store, args.url, save=not args.check)
    except Exception as exc:  # noqa: BLE001 - this is a command-line report
        print(f"could not recover keys: {exc}", file=sys.stderr)
        return 1

    changed = live.sign != current.sign or live.seal != current.seal
    patched = False
    if args.write:
        patched = patch_basic(BASIC_PATH, live.sign, live.seal)

    if args.json:
        print(
            json.dumps(
                {
                    "chapter_url": live.chapter_url,
                    "sign_key": live.sign.hex(),
                    "seal_key": live.seal.hex(),
                    "sign_fp": live.sign_fp,
                    "seal_fp": live.seal_fp,
                    "changed": changed,
                    "basic_patched": patched,
                },
                indent=2,
            )
        )
    else:
        print(f"chapter     : {live.chapter_url}")
        print(f"sign key    : {live.sign.hex()}")
        print(f"seal key    : {live.seal.hex()}")
        print(f"keys.json   : {'updated' if not args.check else 'unchanged (check)'}")
        print(f"basic.py    : {'patched' if patched else 'not touched'}")
        print(f"status      : {'drift detected' if changed else 'same as local'}")
    if args.check and changed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Selection grammar shared by the CLI, the wizard, and the GUI."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .errors import SelectionError

_NUM = r"\d+(?:\.\d+)?"
_ITEM = re.compile(rf"^\s*({_NUM})\s*(?:-\s*({_NUM}))?\s*$")


def _number(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise SelectionError(f"Not a chapter number: {value!r}") from exc


def label_number(label: str) -> float | None:
    """The first numeric run in a label: 'Ch.23.5' -> 23.5."""
    match = re.search(_NUM, label or "")
    return float(match.group()) if match else None


def parse_selection(
    text: str,
    count: int,
    labels: Sequence[str] | None = None,
) -> list[int]:
    """Return 0-based indexes, sorted and unique.

    Integers and ranges are positions in the visible list. A bare decimal
    (``23.5``) matches the chapter label with that number when labels are
    supplied, which is the only place a non-integer position can mean
    something.
    """
    raw = (text or "").strip()
    if not raw:
        raise SelectionError("Choose at least one chapter.")
    if count <= 0:
        raise SelectionError("This series has no chapters.")

    tokens = [token.strip() for token in raw.split(",")]
    if any(not token for token in tokens):
        raise SelectionError("Empty token in the chapter selection.")

    lower = raw.lower()
    if lower in {"all", "*"}:
        return list(range(count))
    if any(token.lower() in {"all", "*"} for token in tokens):
        raise SelectionError('"all" cannot be combined with other chapters.')

    picked: set[int] = set()
    for token in tokens:
        match = _ITEM.match(token)
        if not match:
            raise SelectionError(f"Cannot read chapter selection {token!r}.")
        first_text, second_text = match.group(1), match.group(2)
        if second_text is None:
            if first_text.endswith(".0"):
                first_text = first_text[:-2]
            if "." in first_text and labels is not None:
                wanted = _number(first_text)
                matches = [
                    index
                    for index, label in enumerate(labels)
                    if label_number(label) == wanted
                ]
                if not matches:
                    raise SelectionError(f"Chapter {first_text} is not in this list.")
                picked.update(matches)
                continue
            if "." in first_text:
                raise SelectionError(
                    f"{first_text} is a chapter label; pass the chapter list to resolve it."
                )
            value = int(first_text)
            if value < 1 or value > count:
                raise SelectionError(f"Chapter {value} is outside 1-{count}.")
            picked.add(value - 1)
            continue

        start, end = _number(first_text), _number(second_text)
        if start > end:
            start, end = end, start
        if start < 1 or end > count:
            raise SelectionError(f"Range {token} is outside 1-{count}.")
        first_index = max(0, int(start + 0.999999) - 1)
        last_index = min(count - 1, int(end) - 1)
        if first_index > last_index:
            raise SelectionError(f"Range {token} selects no chapters.")
        picked.update(range(first_index, last_index + 1))

    return sorted(picked)

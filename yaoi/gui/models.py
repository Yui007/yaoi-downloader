"""Qt model adapters — widgets never own download state."""

from __future__ import annotations

import time
from dataclasses import dataclass

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

from ..models import ChapterGroup, SeriesCard
from ..names import safe_name
from ..selection import parse_selection

CARD_ROLE = Qt.ItemDataRole.UserRole + 1
FADE_ROLE = Qt.ItemDataRole.UserRole + 2
COVER_ROLE = Qt.ItemDataRole.UserRole + 3

GROUP_ROLE = Qt.ItemDataRole.UserRole + 1
CHECKED_ROLE = Qt.ItemDataRole.UserRole + 2
PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 3


def compact_ranges(indexes: list[int], count: int) -> str:
    if not indexes:
        return ""
    if len(indexes) == count:
        return "all"
    values = sorted({index + 1 for index in indexes})
    chunks: list[str] = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        chunks.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    chunks.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(chunks)


class SeriesGridModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: list[SeriesCard] = []
        self._covers: dict[str, object] = {}
        self._reveal_start = 0.0

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.cards)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.cards):
            return None
        card = self.cards[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return card.title
        if role == CARD_ROLE:
            return card
        if role == COVER_ROLE:
            return self._covers.get(card.cover)
        if role == FADE_ROLE:
            return self.fade_for(index.row())
        return None

    def roleNames(self):
        return {
            CARD_ROLE: b"card",
            COVER_ROLE: b"cover",
            FADE_ROLE: b"fade",
        }

    def set_cards(self, cards: list[SeriesCard]) -> None:
        self.beginResetModel()
        self.cards = list(cards)
        self._covers = {}
        self._reveal_start = time.monotonic()
        self.endResetModel()

    def card(self, row: int) -> SeriesCard | None:
        return self.cards[row] if 0 <= row < len(self.cards) else None

    def set_cover(self, url: str, pixmap) -> None:
        self._covers[url] = pixmap
        for row, card in enumerate(self.cards):
            if card.cover == url:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [COVER_ROLE])

    def fade_for(self, row: int) -> float:
        from . import theme

        if not theme.motion():
            return 1.0
        elapsed = time.monotonic() - self._reveal_start
        delay = min(0.30, row * 0.014)
        return max(0.0, min(1.0, (elapsed - delay) / 0.44))

    def revealing(self) -> bool:
        from . import theme

        return theme.motion() and time.monotonic() - self._reveal_start < 1.4


@dataclass
class ProgressState:
    state: str = "queued"
    done: int = 0
    total: int = 0
    speed: float = 0.0
    message: str = ""
    path: str = ""
    from_value: float = 0.0
    target_value: float = 0.0
    started: float = 0.0

    def value_at(self, now: float) -> float:
        if self.target_value <= 0:
            return 0.0
        if self.started <= 0:
            return self.target_value
        t = min(1.0, max(0.0, (now - self.started) / 0.28))
        eased = 1 - (1 - t) ** 3
        return self.from_value + (self.target_value - self.from_value) * eased


class ChapterModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups: list[ChapterGroup] = []
        self.checked: set[int] = set()
        self.progress: dict[int, ProgressState] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.groups)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.groups):
            return None
        group = self.groups[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return group.label
        if role == GROUP_ROLE:
            return group
        if role == CHECKED_ROLE:
            return group.index in self.checked
        if role == PROGRESS_ROLE:
            return self.progress.get(group.index)
        return None

    def set_groups(self, groups: list[ChapterGroup], checked: set[int] | None = None) -> None:
        self.beginResetModel()
        self.groups = list(groups)
        self.checked = set(checked or ())
        self.progress = {}
        self.endResetModel()

    def group(self, row: int) -> ChapterGroup | None:
        return self.groups[row] if 0 <= row < len(self.groups) else None

    def set_checked(self, indexes: set[int]) -> None:
        self.checked = set(indexes)
        if self.groups:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self.groups) - 1, 0),
                [CHECKED_ROLE],
            )

    def apply_selection(self, text: str) -> None:
        labels = [group.label for group in self.groups]
        self.set_checked(set(parse_selection(text, len(self.groups), labels)))

    def toggle(self, row: int) -> None:
        group = self.group(row)
        if group is None:
            return
        if group.index in self.checked:
            self.checked.discard(group.index)
        else:
            self.checked.add(group.index)
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [CHECKED_ROLE])

    def select_all(self) -> None:
        self.checked = {group.index for group in self.groups}
        self._all_changed()

    def clear(self) -> None:
        self.checked.clear()
        self._all_changed()

    def _all_changed(self) -> None:
        if not self.groups:
            return
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self.groups) - 1, 0),
            [CHECKED_ROLE],
        )

    def selected_groups(self) -> list[ChapterGroup]:
        return [group for group in self.groups if group.index in self.checked]

    def selection_text(self) -> str:
        rows = [row for row, group in enumerate(self.groups) if group.index in self.checked]
        return compact_ranges(rows, len(self.groups))

    def set_progress(
        self,
        chapter_index: int,
        state: str,
        done: int = 0,
        total: int = 0,
        speed: float = 0.0,
        message: str = "",
        path: str = "",
    ) -> None:
        row = next((i for i, group in enumerate(self.groups) if group.index == chapter_index), -1)
        if row < 0:
            return
        now = time.monotonic()
        previous = self.progress.get(chapter_index)
        from_value = previous.value_at(now) if previous else 0.0
        target = 1.0 if state == "done" else (done / total if total else from_value)
        if state in {"failed", "cancelled"}:
            target = from_value
        self.progress[chapter_index] = ProgressState(
            state=state,
            done=done,
            total=total,
            speed=speed,
            message=message,
            path=path,
            from_value=from_value,
            target_value=max(0.0, min(1.0, target)),
            started=now,
        )
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [PROGRESS_ROLE])

    def active(self) -> bool:
        return any(state.state in {"fetching", "downloading", "exporting"} for state in self.progress.values())

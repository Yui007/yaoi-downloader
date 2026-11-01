"""Rich surfaces: one ink-and-paper theme, tables, live progress, summaries."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Iterator

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Column, Table
from rich.text import Text
from rich.theme import Theme

from ..models import ChapterGroup, JobEvent, JobSummary, Series, SeriesCard
from ..names import human_bytes, human_date, short_date

INK = Theme(
    {
        "accent": "#E4572E",
        "accent.soft": "#F2A07B",
        "paper": "#E9E6DF",
        "muted": "#98A2B3",
        "line": "#2A3240",
        "ok": "#6FCF97",
        "warn": "#E9B44C",
        "fail": "#E06C75",
        "title": "bold #F4F1EA",
        "subtitle": "italic #98A2B3",
        "chip": "#1C222C",
        "bar.back": "#2A3240",
        "bar.complete": "#E4572E",
        "bar.finished": "#6FCF97",
        "bar.pulse": "#F2A07B",
    }
)

console = Console(theme=INK, highlight=False, soft_wrap=False)
err_console = Console(theme=INK, stderr=True, highlight=False)

WORDMARK = [
    "  ██╗   ██╗ █████╗  ██████╗ ██╗",
    "  ╚██╗ ██╔╝██╔══██╗██╔═══██╗██║",
    "   ╚████╔╝ ███████║██║   ██║██║",
    "    ╚██╔╝  ██╔══██║╚██████╔╝██║",
    "     ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝",
]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(first: str, second: str, amount: float) -> str:
    a, b = _rgb(first), _rgb(second)
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def gradient(text: str, start: str = "#E4572E", end: str = "#F6C7A3") -> Text:
    out = Text()
    length = max(1, len(text) - 1)
    for index, char in enumerate(text):
        out.append(char, style=_mix(start, end, index / length))
    return out


def banner(show_tagline: bool = True) -> None:
    console.print()
    for line in WORDMARK:
        console.print(gradient(line, "#E4572E", "#F6D7B8"), end="\n")
    if show_tagline:
        console.print(
            Text("  a manga downloader to download manga from https://yaoi.me/", style="subtitle")
        )
    console.print(Text("  " + "─" * 52, style="line"))
    console.print()


def section(title: str, detail: str = "") -> None:
    line = Text("  ")
    line.append(title.upper(), style="bold #E4572E")
    if detail:
        line.append("   " + detail, style="muted")
    console.print(line)


def _status_style(status: str) -> str:
    return {
        "ongoing": "ok",
        "completed": "muted",
        "hiatus": "warn",
        "cancelled": "fail",
        "canceled": "fail",
        "upcoming": "accent.soft",
    }.get(status.lower(), "muted")


def card_table(cards: list[SeriesCard], title: str = "results") -> None:
    if not cards:
        console.print(Panel(Text("Nothing found. Try a shorter title.", style="muted"), border_style="line"))
        return
    table = Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        pad_edge=False,
        padding=(0, 1),
        title=Text(title, style="subtitle"),
        title_justify="left",
        header_style="muted",
    )
    table.add_column("#", justify="right", width=3, style="line")
    table.add_column("Title", style="paper", no_wrap=True, overflow="ellipsis", max_width=46)
    table.add_column("Status", width=10)
    table.add_column("Score", justify="right", width=5)
    table.add_column("Ch", justify="right", width=4, style="muted")
    table.add_column("Lang", width=10, style="muted")
    for index, card in enumerate(cards, 1):
        status = Text(card.status or "—", style=_status_style(card.status))
        table.add_row(
            str(index),
            card.title,
            status,
            Text(card.rating or "—", style="accent.soft"),
            str(card.chapters or "—"),
            ", ".join(card.languages) or "—",
        )
    console.print(table)


def series_panel(series: Series, groups: list[ChapterGroup] | None = None) -> None:
    header = Table.grid(padding=(0, 2))
    header.add_column(ratio=1)
    header.add_column(justify="right")
    title = gradient(series.title, "#F4F1EA", "#E4572E")
    title.stylize("bold")
    meta = Text()
    bits = [series.type, series.status, series.year, f"★ {series.score}" if series.score else ""]
    meta.append("  ·  ".join(bit for bit in bits if bit), style="muted")
    header.add_row(title, meta)

    details = Text()
    details.append("story  ", style="muted")
    details.append(series.authors_line, style="paper")
    if series.artists:
        details.append("      art  ", style="muted")
        details.append(", ".join(series.artists), style="paper")
    details.append("\n")
    details.append("genres ", style="muted")
    details.append(", ".join(series.genres) or "—", style="accent.soft")

    body = [header, Text(), details]
    if series.tags:
        tags = Text()
        for tag in series.tags[:14]:
            tags.append(f" {tag} ", style="chip")
            tags.append(" ")
        if len(series.tags) > 14:
            tags.append(f"+{len(series.tags) - 14}", style="muted")
        body.extend([Text(), tags])
    if series.description:
        body.extend([Text(), Text(series.description, style="muted")])
    if groups is not None:
        pages = sum(group.pages for group in groups)
        size = sum(group.size for group in groups)
        body.extend(
            [
                Text(),
                Text(
                    f"{len(groups)} {'chapter' if len(groups) == 1 else 'chapters'}"
                    f"  ·  {pages:,} pages  ·  {human_bytes(size)}",
                    style="ok",
                ),
            ]
        )
    console.print(
        Panel(
            Group(*body),
            border_style="line",
            padding=(1, 2),
            title=Text(" series ", style="subtitle"),
            title_align="left",
        )
    )


def chapter_table(groups: list[ChapterGroup], limit: int = 120) -> None:
    table = Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        pad_edge=False,
        padding=(0, 1),
        header_style="muted",
    )
    table.add_column("#", justify="right", width=4, style="line")
    table.add_column("Chapter", no_wrap=True, overflow="ellipsis", max_width=40)
    table.add_column("Date", width=10, style="muted")
    table.add_column("Pages", justify="right", width=5, style="muted")
    table.add_column("Size", justify="right", width=8, style="muted")
    table.add_column("Scanlator", max_width=16, style="accent.soft")
    table.add_column("Versions", justify="right", width=8, style="muted")
    for group in groups[:limit]:
        label = Text(group.label)
        if group.extra:
            label.append("  extra", style="warn")
        table.add_row(
            str(group.index),
            label,
            short_date(group.created_at),
            str(group.pages or "—"),
            human_bytes(group.size),
            group.variant.source_name if group.variant else "—",
            str(len(group.variants)),
        )
    console.print(table)
    if len(groups) > limit:
        console.print(Text(f"  … {len(groups) - limit} more chapters", style="muted"))


def selection_hint(groups: list[ChapterGroup]) -> None:
    print = console.print
    print(
        Text(
            f"  select with -c  1,5,10-20  or  all    ·  1–{len(groups)} visible",
            style="muted",
        )
    )


class JsonEmitter:
    def __init__(self) -> None:
        self.start = time.monotonic()
        self.summary: JobSummary | None = None

    def handle(self, event: JobEvent) -> None:
        print(json.dumps(event.to_dict(), ensure_ascii=False), flush=True)
        if event.kind == "summary":
            self.summary = JobSummary(
                done=event.done,
                failed=event.state == "failed" and 1 or 0,
                bytes=event.bytes,
            )

    def close(self) -> None:
        return None


class PlainEmitter:
    def __init__(self) -> None:
        self.start = time.monotonic()

    def handle(self, event: JobEvent) -> None:
        if event.kind == "job":
            print(f"{event.message} — {event.total} {'chapter' if event.total == 1 else 'chapters'}")
        elif event.kind == "chapter" and event.state == "done":
            print(f"  done   {event.label}  {human_bytes(event.bytes)}  {event.path}")
        elif event.kind == "chapter" and event.state == "failed":
            print(f"  failed {event.label}  {event.message}")
        elif event.kind == "chapter" and event.state == "cancelled":
            print(f"  cancelled {event.label}")
        elif event.kind == "summary":
            print(
                f"summary: {event.done} done, {event.failed} failed, "
                f"{event.cancelled} cancelled, {human_bytes(event.bytes)}"
            )

    def close(self) -> None:
        return None


class JobProgress:
    def __init__(self, total_chapters: int, series_title: str):
        self.total_chapters = total_chapters
        self.series_title = series_title
        self.start = time.monotonic()
        self.progress = Progress(
            SpinnerColumn(style="accent"),
            TextColumn("[accent]{task.description}", table_column=Column(width=22, no_wrap=True)),
            BarColumn(bar_width=None, style="bar.back", complete_style="bar.complete", finished_style="bar.finished", pulse_style="bar.pulse"),
            MofNCompleteColumn(table_column=Column(width=9, justify="right")),
            TextColumn("{task.fields[speed]}", table_column=Column(width=10, no_wrap=True), style="muted"),
            TextColumn("{task.fields[state]}", table_column=Column(width=13, no_wrap=True), style="accent.soft"),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        )
        self.header = Text()
        self.bytes_done = 0
        self._render_header(0, 0)
        self.aggregate = self.progress.add_task(
            "all chapters", total=max(1, total_chapters), completed=0, speed="", state="waiting"
        )
        self.tasks: dict[int, int] = {}
        self.completed = 0
        self.live = Live(
            Group(self.header, Text(), self.progress),
            console=console,
            refresh_per_second=12,
            transient=True,
            vertical_overflow="visible",
        )

    def _render_header(self, finished: int, bytes_done: int) -> None:
        elapsed = max(0.001, time.monotonic() - self.start)
        speed = bytes_done / elapsed
        self.header.plain = ""
        self.header.append("  " + self.series_title, style="title")
        self.header.append(
            f"    {finished}/{self.total_chapters} chapters  ·  {human_bytes(bytes_done)}"
            f"  ·  {human_bytes(speed)}/s",
            style="muted",
        )

    def __enter__(self) -> JobProgress:
        self.live.start()
        return self

    def __exit__(self, *args) -> None:
        self.live.stop()

    def handle(self, event: JobEvent) -> None:
        if event.kind == "job":
            self.series_title = event.message or self.series_title
            self._render_header(0, 0)
            return
        if event.kind == "chapter":
            task = self.tasks.get(event.chapter_index)
            if task is None:
                task = self.progress.add_task(
                    f"ch {event.chapter_index} · {event.label}"[:22],
                    total=max(1, event.total or 0),
                    completed=0,
                    speed="",
                    state="fetching",
                )
                self.tasks[event.chapter_index] = task
            speed = f"{human_bytes(event.speed)}/s" if event.speed else ""
            state = {
                "fetching": "hashing",
                "downloading": "downloading",
                "exporting": "sealing",
                "done": "done",
                "failed": "failed",
                "cancelled": "cancelled",
            }.get(event.state, event.state)
            self.progress.update(
                task,
                total=max(1, event.total or 0),
                completed=min(event.done, event.total or event.done),
                speed=speed,
                state=state,
            )
            if event.state in {"done", "failed", "cancelled"}:
                self.completed += 1
                if event.state == "done":
                    self.bytes_done += event.bytes
                self.progress.update(
                    self.aggregate,
                    completed=self.completed,
                    state="done" if self.completed >= self.total_chapters else "working",
                )
                self._render_header(self.completed, self.bytes_done)
                if event.state == "failed":
                    self.live.console.print(
                        Text(f"  ch {event.chapter_index} failed · {event.message}", style="fail")
                    )
            return
        if event.kind == "summary":
            self.progress.update(self.aggregate, completed=max(self.completed, event.done + event.failed + event.cancelled))
            self._render_header(event.done + event.failed + event.cancelled, event.bytes)
            self.live.refresh()

    def close(self) -> None:
        return None


@contextmanager
def spinner(message: str) -> Iterator[None]:
    with console.status(f"[accent]{message}", spinner="dots12", spinner_style="accent"):
        yield


def summary_panel(summary: JobSummary, elapsed: float) -> None:
    title = " finished " if summary.ok else " needs attention "
    table = Table.grid(padding=(0, 3))
    table.add_column(style="muted")
    table.add_column(style="paper")
    table.add_row("done", f"[ok]{summary.done}[/]")
    table.add_row("failed", f"[fail]{summary.failed}[/]" if summary.failed else "0")
    table.add_row("cancelled", f"[warn]{summary.cancelled}[/]" if summary.cancelled else "0")
    table.add_row("size", human_bytes(summary.bytes))
    table.add_row("time", f"{elapsed:.1f}s")
    if summary.paths:
        table.add_row("library", summary.paths[0] if len(summary.paths) == 1 else f"{len(summary.paths)} files")
    if summary.messages:
        table.add_row("notes", "\n".join(summary.messages[:3]))
    console.print(
        Panel(
            table,
            border_style="ok" if summary.ok else "fail",
            padding=(1, 2),
            title=Text(title, style="ok" if summary.ok else "fail"),
            title_align="left",
        )
    )


def error_panel(message: str, hint: str = "") -> None:
    body = Text(message, style="paper")
    if hint:
        body.append("\n" + hint, style="muted")
    console.print(Panel(body, border_style="fail", padding=(1, 2), title="could not continue", title_align="left"))


def library_table(series_list) -> None:
    if not series_list:
        console.print(Panel(Text("The shelf is empty. Download something.", style="muted"), border_style="line"))
        return
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, pad_edge=False, header_style="muted")
    table.add_column("Series", style="paper", max_width=52)
    table.add_column("Chapters", justify="right", style="accent.soft")
    table.add_column("Size", justify="right", style="muted")
    table.add_column("Updated", style="muted")
    table.add_column("Path", style="line", max_width=40, overflow="ellipsis")
    for item in series_list:
        table.add_row(
            item.title,
            str(item.chapters),
            item.size_label,
            human_date(item.updated * 1000),
            str(item.path),
        )
    console.print(table)

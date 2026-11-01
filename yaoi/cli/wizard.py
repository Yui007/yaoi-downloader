"""Bare `yaoi`: a short, forgiving wizard over the same core calls."""

from __future__ import annotations

import signal
import time
from pathlib import Path

from rich.prompt import Confirm, Prompt

from ..app_context import options_from_settings
from ..downloader import DownloadJob
from ..errors import YaoiError
from ..filters import available_languages, available_sources, filter_chapters
from ..library import open_path
from ..selection import parse_selection
from ..sources.yaoi import YaoiSource
from . import render


def _pick_search(source: YaoiSource) -> str:
    query = Prompt.ask("[accent]search[/]  title or words").strip()
    if not query:
        return ""
    with render.spinner(f"looking for {query!r}…"):
        cards = source.search(query, 12)
    if not cards:
        render.console.print("[muted]Nothing found. Try a shorter title.[/]")
        return ""
    render.card_table(cards, f"matches · {query!r}")
    answer = Prompt.ask(
        "pick",
        choices=[str(index) for index in range(1, len(cards) + 1)],
        default="1",
    )
    return cards[int(answer) - 1].url


def _choose_filter(groups, kind: str):
    values = available_sources(groups) if kind == "scanlator" else available_languages(groups)
    if not values:
        return None
    choices = ["Any", *values]
    answer = Prompt.ask(f"[accent]{kind}[/]", choices=choices, default="Any")
    return None if answer == "Any" else answer


def _fetch_series(source: YaoiSource, url: str):
    with render.spinner("opening the series…"):
        series = source.series(url)
        groups = source.chapters(series)
    return series, groups


def _run(source, series, groups, settings, options) -> tuple:
    started = time.monotonic()
    progress = render.JobProgress(len(groups), series.title)
    job = DownloadJob(
        source,
        series,
        groups,
        options,
        client=source.client,
        on_event=progress.handle,
    )
    previous = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):
        job.cancel()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handler)
    try:
        with progress:
            summary = job.run()
    finally:
        signal.signal(signal.SIGINT, previous)
    return summary, time.monotonic() - started


def run(source: YaoiSource, settings: dict) -> int:
    render.banner()
    render.console.print(
        "[muted]  paste a series URL, or search by title.  [/]"
        "[muted]ctrl+c leaves partial pages on disk.[/]\n"
    )
    try:
        while True:
            raw = Prompt.ask("[accent]series URL or search term[/]").strip()
            if not raw:
                render.console.print("[muted]  nothing to do.[/]")
                return 0
            if "yaoi.me" not in raw and not raw.startswith(("http://", "https://")):
                raw = _pick_search(source)
                if not raw:
                    continue
            try:
                series, groups = _fetch_series(source, raw)
            except YaoiError as exc:
                render.error_panel(exc.message, exc.hint)
                continue

            source_filter = _choose_filter(groups, "scanlator")
            language = _choose_filter(groups, "language")
            visible = filter_chapters(groups, source_filter, language)
            if not visible:
                render.console.print("[warn]  no chapters match those filters.[/]")
                continue

            render.series_panel(series, visible)
            render.section("chapters", f"{len(visible)} visible")
            render.chapter_table(visible, 24)
            render.selection_hint(visible)

            selection = Prompt.ask(
                "[accent]chapters[/]  [muted](1-{0}, all, 1,5,10-20)[/]".format(len(visible)),
                default="all",
            )
            try:
                indexes = parse_selection(selection, len(visible), [group.label for group in visible])
            except YaoiError as exc:
                render.error_panel(exc.message, exc.hint)
                continue
            chosen = [visible[index] for index in indexes]
            fmt = Prompt.ask("[accent]format[/]", choices=["images", "pdf", "cbz"], default="cbz")
            keep = Confirm.ask("[accent]keep images after export?[/]", default=False)
            options = options_from_settings(
                settings,
                format=fmt,
                keep_images=keep,
            )

            pages = sum(group.pages for group in chosen)
            render.console.print()
            render.console.print(
                f"  [title]{series.title}[/]  [muted]{len(chosen)} chapters · "
                f"{pages:,} pages · {fmt.upper()} · {options.chapters_workers}×{options.images_workers}[/]"
            )
            if not Confirm.ask("  start?", default=True):
                continue
            summary, elapsed = _run(source, series, chosen, settings, options)
            render.summary_panel(summary, elapsed)

            if summary.paths and Confirm.ask("  open the folder?", default=False):
                target = Path(summary.paths[0])
                open_path(target if target.is_dir() else target.parent)
            if not Confirm.ask("  download something else?", default=False):
                if summary.cancelled and summary.done == 0:
                    return 130
                return 0 if not summary.failed else 1
    except KeyboardInterrupt:
        render.console.print("\n[warn]  cancelled.[/]")
        return 130
    except YaoiError as exc:
        render.error_panel(exc.message, exc.hint)
        return exc.code

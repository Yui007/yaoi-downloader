"""Typer surface. Direct when piped, human when a terminal is present."""

from __future__ import annotations

import json
import signal
import time
from pathlib import Path
from typing import Optional

import typer
from typer import rich_utils as typer_help

from .. import config
from ..app_context import options_from_settings, source_from_settings
from ..downloader import DownloadJob, summary_line
from ..errors import SelectionError, YaoiError
from ..filters import available_languages, available_sources, filter_chapters
from ..library import open_path, scan_library
from ..models import JobSummary
from ..names import human_bytes, human_date
from ..selection import parse_selection
from ..sources import keys as keylib
from ..sources.yaoi import BASE, YaoiSource
from . import render, wizard

# Typer draws its own help console; give it the same ink and vermilion.
typer_help.STYLE_OPTION = "bold #E4572E"
typer_help.STYLE_COMMANDS_TABLE_FIRST_COLUMN = "bold #F2A07B"
typer_help.STYLE_COMMANDS_TABLE_PADDING = (0, 2)
typer_help.STYLE_SWITCH = "bold #6FCF97"
typer_help.STYLE_TYPES = "#E9B44C"
typer_help.STYLE_USAGE = "#98A2B3"
typer_help.STYLE_USAGE_COMMAND = "bold #F4F1EA"
typer_help.STYLE_HELPTEXT = "#98A2B3"
typer_help.STYLE_HELPTEXT_FIRST_LINE = "#E9E6DF"
typer_help.STYLE_OPTION_DEFAULT = "#98A2B3"
typer_help.STYLE_OPTION_HELP = "#98A2B3"
typer_help.STYLE_REQUIRED_LONG = "bold #E06C75"
typer_help.STYLE_REQUIRED_SHORT = "bold #E06C75"
typer_help.STYLE_OPTIONS_PANEL_BORDER = "#2A3240"
typer_help.STYLE_COMMANDS_PANEL_BORDER = "#2A3240"
typer_help.STYLE_ERRORS_PANEL_BORDER = "#E06C75"
typer_help.STYLE_ABORTED = "#E06C75"
typer_help.OPTIONS_PANEL_TITLE = "options"
typer_help.COMMANDS_PANEL_TITLE = "commands"
typer_help.ARGUMENTS_PANEL_TITLE = "arguments"

app = typer.Typer(
    name="yaoi",
    help="A manga downloader to download manga from https://yaoi.me/.",
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
    rich_markup_mode="rich",
)
keys_app = typer.Typer(help="Reader keys: check drift or recover and verify.")
app.add_typer(keys_app, name="keys")

FORMATS = {"images", "pdf", "cbz"}


def _fail(exc: YaoiError, json_output: bool = False) -> None:
    if json_output:
        render.err_console.print(json.dumps({"event": "error", "message": exc.message, "hint": exc.hint}))
    else:
        render.error_panel(exc.message, exc.hint)
    raise typer.Exit(exc.code)


def _settings() -> dict:
    return config.load_settings()


def _source(settings: dict) -> YaoiSource:
    return source_from_settings(settings)


def _json_ready(value):
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


def _fetch(source: YaoiSource, url: str, animate: bool):
    if animate:
        with render.spinner("reading the series…"):
            series = source.series(url)
            groups = source.chapters(series)
    else:
        series = source.series(url)
        groups = source.chapters(series)
    return series, groups


def _choose_chapters(
    groups,
    selection: str,
    assume_yes: bool,
    json_output: bool,
):
    visible = group_labels = [group.label for group in groups]
    if not selection:
        if assume_yes:
            selection = "all"
        elif render.console.is_terminal:
            selection = render.console.input("[accent]chapters[/]  [muted](1-{0}, all, 1,5,10-20)[/]  › ".format(len(groups))).strip() or "all"
        else:
            raise SelectionError("Pass -c or --yes when there is no terminal.")
    try:
        indexes = parse_selection(selection, len(groups), visible)
    except SelectionError as exc:
        raise exc
    return [groups[index] for index in indexes]


def _validate_format(fmt: str) -> str:
    value = (fmt or "cbz").lower()
    if value not in FORMATS:
        raise SelectionError(f"Unknown format {fmt!r}; use images, pdf, or cbz.")
    return value


def _install_sigint(job: DownloadJob):
    previous = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):
        job.cancel()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handler)
    return previous


def _run_job(
    source: YaoiSource,
    series,
    groups,
    options,
    json_output: bool,
) -> tuple[JobSummary, float]:
    started = time.monotonic()
    emitter_cls = render.JsonEmitter if json_output else (
        render.JobProgress if render.console.is_terminal else render.PlainEmitter
    )
    if emitter_cls is render.JobProgress:
        emitter = render.JobProgress(len(groups), series.title)
        context = emitter
    else:
        emitter = emitter_cls()
        context = None
    job = DownloadJob(
        source,
        series,
        groups,
        options,
        client=source.client,
        on_event=emitter.handle,
    )
    previous = _install_sigint(job)
    try:
        if context is not None:
            with context:
                summary = job.run()
        else:
            summary = job.run()
    finally:
        signal.signal(signal.SIGINT, previous)
        emitter.close()
    return summary, time.monotonic() - started


@app.callback()
def root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Print the version and exit.", is_eager=True),
):
    if version:
        render.console.print(f"yaoi [accent]{__import__('yaoi').__version__}[/]")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        settings = _settings()
        source = source_from_settings(settings)
        raise typer.Exit(wizard.run(source, settings))


@app.command()
def search(
    query: str = typer.Argument(..., help="Title or words to search for."),
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=100),
    json_output: bool = typer.Option(False, "--json", help="One machine-readable object."),
):
    """Search the catalogue."""
    try:
        source = _source(_settings())
        cards = source.search(query, limit)
    except YaoiError as exc:
        _fail(exc, json_output)
    if json_output:
        print(json.dumps([card.to_dict() for card in cards], ensure_ascii=False))
    else:
        render.section("search", f"{query!r} · {len(cards)} matches")
        render.card_table(cards)


@app.command()
def trending(
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=100),
    json_output: bool = typer.Option(False, "--json"),
):
    """What everyone is reading."""
    try:
        cards = _source(_settings()).trending(limit)
    except YaoiError as exc:
        _fail(exc, json_output)
    if json_output:
        print(json.dumps([card.to_dict() for card in cards], ensure_ascii=False))
    else:
        render.section("trending", f"{len(cards)} series")
        render.card_table(cards)


@app.command()
def latest(
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=100),
    json_output: bool = typer.Option(False, "--json"),
):
    """Recently updated series."""
    try:
        cards = _source(_settings()).latest(limit)
    except YaoiError as exc:
        _fail(exc, json_output)
    if json_output:
        print(json.dumps([card.to_dict() for card in cards], ensure_ascii=False))
    else:
        render.section("latest", f"{len(cards)} series")
        render.card_table(cards)


@app.command()
def info(
    url: str = typer.Argument(..., help="A yaoi.me series URL."),
    json_output: bool = typer.Option(False, "--json"),
    limit: int = typer.Option(120, "--limit", min=1, max=2000),
):
    """Cover, metadata, and every chapter."""
    try:
        source = _source(_settings())
        series, groups = _fetch(source, url, animate=not json_output and render.console.is_terminal)
        sources = available_sources(groups)
        languages = available_languages(groups)
    except YaoiError as exc:
        _fail(exc, json_output)
    if json_output:
        print(
            json.dumps(
                {
                    "series": series.to_dict(),
                    "chapters": [group.to_dict() for group in groups],
                    "sources": sources,
                    "languages": languages,
                },
                ensure_ascii=False,
            )
        )
        return
    render.series_panel(series, groups)
    render.section("chapters", f"{len(groups)} visible · {len(sources)} scanlators")
    render.chapter_table(groups, limit)
    render.selection_hint(groups)


@app.command()
def download(
    url: str = typer.Argument(..., help="A yaoi.me series URL."),
    chapters: str = typer.Option("", "-c", "--chapters", help='"all", "1,5", or "10-20".'),
    fmt: Optional[str] = typer.Option(None, "--format", "-f", help="images, pdf, or cbz."),
    keep_images: Optional[bool] = typer.Option(None, "--keep-images/--clean-images"),
    chapters_workers: Optional[int] = typer.Option(None, "--chapters-workers", min=1, max=8),
    images_workers: Optional[int] = typer.Option(None, "--images-workers", min=1, max=10),
    source_filter: Optional[str] = typer.Option(None, "--source", help="Scanlator name."),
    language: Optional[str] = typer.Option(None, "--lang", help="Language code, e.g. en."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Library root for this run."),
    assume_yes: bool = typer.Option(False, "--yes", "-y", help="Never prompt."),
    force: bool = typer.Option(False, "--force", help="Re-download pages that already exist."),
    json_output: bool = typer.Option(False, "--json", help="One event object per line."),
):
    """Download exactly the chapters you mean."""
    settings = _settings()
    animate = not json_output and render.console.is_terminal
    try:
        source = _source(settings)
        series, groups = _fetch(source, url, animate)
        visible = filter_chapters(groups, source_filter, language)
        if not visible:
            hint = (
                f"scanlators: {', '.join(available_sources(groups)) or 'none'}; "
                f"languages: {', '.join(available_languages(groups)) or 'none'}"
            )
            raise SelectionError("No chapters match those filters.", hint)
        selected = _choose_chapters(visible, chapters, assume_yes, json_output)
        chosen_format = _validate_format(fmt or settings["download"]["format"])
        options = options_from_settings(
            settings,
            format=chosen_format,
            keep_images=keep_images,
            chapters_workers=chapters_workers,
            images_workers=images_workers,
            out=out,
        )
        options = options.__class__(**{**options.__dict__, "force": force})
        if animate:
            total_pages = sum(group.pages for group in selected)
            chapter_word = "chapter" if len(selected) == 1 else "chapters"
            render.console.print(
                f"  [title]{series.title}[/]  [muted]{len(selected)} {chapter_word} · "
                f"{total_pages:,} pages · {chosen_format.upper()}[/]"
            )
            render.console.print()
        summary, elapsed = _run_job(source, series, selected, options, json_output)
    except KeyboardInterrupt:
        render.console.print("\n[warn]cancelled[/]  partial pages stay on disk")
        raise typer.Exit(130)
    except YaoiError as exc:
        _fail(exc, json_output)
    if not json_output:
        render.summary_panel(summary, elapsed)
    return_summary = summary
    if return_summary.cancelled and return_summary.done == 0:
        raise typer.Exit(130)
    if return_summary.failed:
        raise typer.Exit(1)


@app.command()
def library(
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Library root."),
    json_output: bool = typer.Option(False, "--json"),
):
    """What is already on the shelf."""
    settings = _settings()
    root = out or config.paths(settings)["library"]
    items = scan_library(root)
    if json_output:
        print(
            json.dumps(
                [
                    {
                        "title": item.title,
                        "path": str(item.path),
                        "chapters": item.chapters,
                        "bytes": item.bytes,
                        "updated": item.updated,
                    }
                    for item in items
                ],
                ensure_ascii=False,
            )
        )
        return
    render.section("library", f"{len(items)} series · {str(root)}")
    render.library_table(items)


@app.command()
def gui():
    """Open the desktop reading room."""
    try:
        from ..gui.app import main as gui_main
    except ImportError as exc:
        render.error_panel("PyQt6 is not installed.", "Install with: pip install -e '.[gui]'")
        raise typer.Exit(2) from exc
    raise typer.Exit(gui_main())


@keys_app.command("check")
def keys_check(
    url: str = typer.Option(BASE, "--url", help="Any yaoi.me page with a chapter."),
    json_output: bool = typer.Option(False, "--json"),
):
    """Exit 2 when the repo's keys differ from the live site."""
    try:
        settings = _settings()
        source = _source(settings)
        live = keylib.refresh(source.client, source.store, url, save=False)
        current = source.store.load()
    except YaoiError as exc:
        _fail(exc, json_output)
    changed = live.sign != current.sign or live.seal != current.seal
    if json_output:
        print(
            json.dumps(
                {
                    "changed": changed,
                    "current_sign": current.sign_fp,
                    "current_seal": current.seal_fp,
                    "live_sign": live.sign_fp,
                    "live_seal": live.seal_fp,
                    "verified_at": live.verified_at,
                },
                indent=2,
            )
        )
    else:
        render.section("reader keys")
        render.console.print(f"  current  sign [muted]{current.sign_fp}[/]  seal [muted]{current.seal_fp}[/]")
        render.console.print(f"  live     sign [ok]{live.sign_fp}[/]  seal [ok]{live.seal_fp}[/]")
        render.console.print(
            "  status   " + ("[warn]drift detected[/]" if changed else "[ok]verified[/]")
        )
    if changed:
        raise typer.Exit(2)


@keys_app.command("refresh")
def keys_refresh(
    url: str = typer.Option(BASE, "--url"),
    json_output: bool = typer.Option(False, "--json"),
    write: bool = typer.Option(False, "--write", help="Kept for compatibility; keys.json is always written."),
):
    """Recover, verify, and save new reader constants."""
    try:
        settings = _settings()
        source = _source(settings)
        current = source.store.load()
        live = keylib.refresh(source.client, source.store, url, save=True)
    except YaoiError as exc:
        _fail(exc, json_output)
    changed = live.sign != current.sign or live.seal != current.seal
    if json_output:
        print(
            json.dumps(
                {
                    "changed": changed,
                    "sign": live.sign.hex(),
                    "seal": live.seal.hex(),
                    "sign_fp": live.sign_fp,
                    "seal_fp": live.seal_fp,
                    "verified_at": live.verified_at,
                    "chapter_url": live.chapter_url,
                },
                indent=2,
            )
        )
        return
    render.section("reader keys", "recovered and verified")
    render.console.print(f"  sign     [accent]{live.sign_fp}[/]")
    render.console.print(f"  seal     [accent]{live.seal_fp}[/]")
    render.console.print(f"  status   [ok]saved to keys.json[/]")
    if changed:
        render.console.print("  [warn]the old constants were stale[/]")


def main() -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    app(prog_name="yaoi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

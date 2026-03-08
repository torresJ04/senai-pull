"""SENAI Courses Advisor CLI."""

from __future__ import annotations

import asyncio
from datetime import datetime

import click

from main import check_courses_update
from models import Snapshot
from reports import send_weekly_report
from scraper import scrape_it_courses
from turmas_scraper import scrape_all_turmas
from watched_classes import add_watched_class, load_watched_classes, remove_watched_class
from empty_response_cache import get_cache


@click.group()
def cli() -> None:
    """SENAI Courses Advisor CLI."""
    pass


@cli.command()
def watch() -> None:
    """Interactively add a class to watch list."""
    courses = scrape_it_courses()
    turmas = scrape_all_turmas(courses)
    if not turmas:
        click.echo("No turmas found.")
        return

    # Simple interactive selection
    for idx, t in enumerate(turmas, start=1):
        click.echo(
            f"[{idx}] {t.course_name} @ {t.unit_name} | "
            f"{t.start_date or '?'} - {t.end_date or '?'} | "
            f"{t.spots_left or 0}/{t.spots_total or 0} spots"
        )

    choice = click.prompt("Select turma number to watch", type=int)
    if 1 <= choice <= len(turmas):
        turma = turmas[choice - 1]
        add_watched_class(turma)
        click.echo(f"Added: {turma.course_name} @ {turma.unit_name}")
    else:
        click.echo("Invalid choice.")


@cli.command()
def unwatch() -> None:
    """Remove a class from watch list."""
    watched = load_watched_classes()
    if not watched:
        click.echo("No watched classes.")
        return

    for idx, w in enumerate(watched, start=1):
        click.echo(f"[{idx}] {w.course_name} @ {w.unit_name} (added {w.added_at})")

    choice = click.prompt("Select watched class number to remove", type=int)
    if 1 <= choice <= len(watched):
        target = watched[choice - 1]
        remove_watched_class(target.turma_key)
        click.echo(f"Removed: {target.course_name} @ {target.unit_name}")
    else:
        click.echo("Invalid choice.")


@cli.command()
def list_watched() -> None:
    """List all watched classes."""
    watched = load_watched_classes()
    if not watched:
        click.echo("No watched classes.")
        return
    for w in watched:
        click.echo(f"- {w.course_name} @ {w.unit_name} (added {w.added_at})")


@cli.command()
def report() -> None:
    """Generate and send weekly report now."""
    courses = scrape_it_courses()
    turmas = scrape_all_turmas(courses)
    snapshot = Snapshot(at=datetime.now(), courses=courses, turmas=turmas)
    asyncio.run(send_weekly_report(snapshot))
    click.echo("Report sent!")


@cli.command()
def check() -> None:
    """Run a manual check for updates."""
    asyncio.run(check_courses_update())
    click.echo("Check complete!")


@cli.command()
def cache_stats() -> None:
    """Show empty response cache statistics."""
    cache = get_cache()
    stats = cache.get_stats()

    click.echo("Empty Response Cache Statistics:")
    click.echo(f"  Total entries: {stats['total_entries']}")
    click.echo(f"  Currently skipped: {stats['currently_skipped']}")
    click.echo(f"  Empty threshold: {stats['empty_threshold']} consecutive empties")
    click.echo(f"  Cache expiry: {stats['cache_expiry_days']} days")

    if cache.entries:
        click.echo("\nTop 10 persistently empty combinations:")
        sorted_entries = sorted(
            cache.entries.values(),
            key=lambda e: e.consecutive_empty,
            reverse=True,
        )[:10]
        for entry in sorted_entries:
            status = "SKIPPED" if entry.should_skip() else "tracked"
            click.echo(
                f"  course_id={entry.course_id} unit_id={entry.unit_id}: "
                f"{entry.consecutive_empty} consecutive empties [{status}]"
            )


@cli.command()
@click.option(
    "--force",
    is_flag=True,
    help="Skip confirmation prompt",
)
def cache_reset(force: bool) -> None:
    """Reset the empty response cache (force re-check of all combinations)."""
    if not force:
        click.confirm(
            "This will clear the cache and retry all previously empty combinations. Continue?",
            abort=True,
        )

    cache = get_cache()
    count = len(cache.entries)
    cache.entries.clear()
    cache._save()

    click.echo(f"Cache reset! Cleared {count} entries.")


if __name__ == "__main__":
    cli()


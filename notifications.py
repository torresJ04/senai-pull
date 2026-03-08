"""Telegram notifications and message formatting for SENAI Courses Advisor."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from telegram import Bot
from telegram.error import TelegramError

import config
from models import Snapshot, Turma
from state_manager import CourseDiff, TurmaDiff
from watched_classes import WatchedClass

logger = logging.getLogger(__name__)


MAX_TELEGRAM_LENGTH = 4096


async def send_telegram_message(message: str) -> bool:
    """Send a message via Telegram bot.

    Returns True on success, False on failure or when Telegram is not
    configured.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured; skipping send.")
        return False

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=message)
        logger.info("Sent Telegram message (%s chars)", len(message))
        return True
    except TelegramError as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        return False


async def send_telegram_document(path: Path, caption: str | None = None) -> bool:
    """Send a document (e.g. HTML report) via Telegram bot."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured; skipping send.")
        return False

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        with path.open("rb") as f:
            await bot.send_document(
                chat_id=config.TELEGRAM_CHAT_ID,
                document=f,
                filename=path.name,
                caption=caption,
            )
        logger.info("Sent Telegram document %s", path)
        return True
    except TelegramError as exc:
        logger.error("Failed to send Telegram document %s: %s", path, exc)
        return False


def _split_long_message(message: str) -> List[str]:
    """Split a long message into chunks within Telegram's character limit."""
    if len(message) <= MAX_TELEGRAM_LENGTH:
        return [message]

    lines = message.splitlines(keepends=True)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > MAX_TELEGRAM_LENGTH and current:
            chunks.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)

    if current:
        chunks.append("".join(current))
    return chunks


def format_course_diff_message(diff: CourseDiff) -> str:
    """Format course differences as a readable message."""
    parts: list[str] = []

    if diff.new_courses:
        parts.append(f"🆕 New Courses ({len(diff.new_courses)}):")
        for c in diff.new_courses:
            workload = f"{c.workload_hours}h" if c.workload_hours is not None else "N/A"
            parts.append(f"- {c.name} ({c.modality}) - {workload}")
        parts.append("")

    if diff.deleted_courses:
        parts.append(f"❌ Removed Courses ({len(diff.deleted_courses)}):")
        for c in diff.deleted_courses:
            parts.append(f"- {c.name}")
        parts.append("")

    if diff.modified_courses:
        parts.append(f"✏️ Updated Courses ({len(diff.modified_courses)}):")
        for c in diff.modified_courses:
            workload = f"{c.workload_hours}h" if c.workload_hours is not None else "N/A"
            parts.append(f"- {c.name} ({c.modality}) - {workload}")
        parts.append("")

    if not parts:
        return "No course changes detected."

    return "\n".join(parts).strip()


def format_turma_diff_message(diff: TurmaDiff) -> str:
    """Format turma differences as a readable message."""
    parts: list[str] = []

    if diff.new_turmas:
        parts.append(f"📅 New Classes ({len(diff.new_turmas)}):")
        for t in diff.new_turmas:
            parts.extend(
                [
                    f"- {t.course_name} @ {t.unit_name}",
                    f"  Start: {t.start_date or 'N/A'} | End: {t.end_date or 'N/A'}",
                    f"  Spots: {t.spots_left or 0}/{t.spots_total or 0} | "
                    f"Schedule: {t.schedule_type or ''} {t.shift or ''}".strip(),
                ]
            )
        parts.append("")

    if diff.deleted_turmas:
        parts.append(f"🗑️ Removed Classes ({len(diff.deleted_turmas)}):")
        for t in diff.deleted_turmas:
            parts.append(f"- {t.course_name} @ {t.unit_name} ({t.start_date or 'N/A'})")
        parts.append("")

    if diff.spot_changes:
        parts.append(f"🔄 Spot Changes ({len(diff.spot_changes)}):")
        for old, new in diff.spot_changes:
            old_left = old.spots_left if old.spots_left is not None else 0
            new_left = new.spots_left if new.spots_left is not None else 0
            delta = new_left - old_left
            sign = "+" if delta >= 0 else ""
            parts.extend(
                [
                    f"- {new.course_name} @ {new.unit_name}",
                    f"  {old_left} → {new_left} ({sign}{delta})",
                ]
            )
        parts.append("")

    if not parts:
        return "No turma changes detected."

    return "\n".join(parts).strip()


def format_weekly_report(snapshot: Snapshot) -> str:
    """Format a comprehensive weekly report organized by unit."""
    if not snapshot.courses:
        return "📊 SENAI Courses Weekly Report\n\nNo courses found."

    # Group turmas by (course_id, unit_id)
    turmas_by_key: dict[tuple[int, int], list[Turma]] = {}
    for t in snapshot.turmas:
        turmas_by_key.setdefault((t.course_id, t.unit_id), []).append(t)

    # Build unit -> course structure
    units: dict[str, dict[str, list[Turma]]] = {}
    for (course_id, unit_id), turmas in turmas_by_key.items():
        # Find course and unit names from snapshot.courses
        course = next((c for c in snapshot.courses if c.course_id == course_id), None)
        if not course:
            continue
        unit = next((u for u in course.units if u.unit_id == unit_id), None)
        unit_name = f"{unit.city} - {unit.neighborhood}".strip(" -") if unit else "Unknown unit"
        course_title = f"{course.name} ({course.workload_hours or 'N/A'}h)"
        units.setdefault(unit_name, {}).setdefault(course_title, []).extend(turmas)

    lines: list[str] = []
    date_str = snapshot.at.date().isoformat()
    lines.append(f"📊 SENAI Courses Weekly Report - {date_str}")
    lines.append("")

    for unit_name in sorted(units.keys()):
        lines.append(f"🏫 {unit_name}")
        courses_for_unit = units[unit_name]
        for course_title in sorted(courses_for_unit.keys()):
            ts = courses_for_unit[course_title]
            lines.append(f"├─ {course_title} - {len(ts)} turmas")
            for idx, t in enumerate(ts):
                prefix = "│  ├─" if idx < len(ts) - 1 else "│  └─"
                lines.append(
                    f"{prefix} {t.start_date or '?'} - {t.end_date or '?'} | "
                    f"{t.spots_left or 0}/{t.spots_total or 0} spots | "
                    f"{t.schedule_type or ''} {t.shift or ''}".strip()
                )
        lines.append("")

    return "\n".join(lines).rstrip()


def format_spot_change_alert(watched: WatchedClass, turma: Turma) -> str:
    """Format spot change alert for watched class."""
    prev = watched.last_spots_left if watched.last_spots_left is not None else 0
    current = turma.spots_left if turma.spots_left is not None else 0
    delta = current - prev
    sign = "+" if delta >= 0 else ""

    lines = [
        "🔔 Spot Change Alert!",
        "",
        f"Course: {watched.course_name}",
        f"Unit: {watched.unit_name}",
        f"Previous: {prev} spots left",
        f"Current: {current} spots left ({sign}{delta})",
    ]
    if prev == 0 and current > 0:
        lines.append("✅ Spots just opened!")
    return "\n".join(lines)


__all__ = [
    "send_telegram_message",
    "send_telegram_document",
    "format_course_diff_message",
    "format_turma_diff_message",
    "format_weekly_report",
    "format_spot_change_alert",
]


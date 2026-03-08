"""Main application entry point with scheduling."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import schedule

import config
from models import Snapshot
from notifications import (
    format_course_diff_message,
    format_turma_diff_message,
    format_spot_change_alert,
    send_telegram_message,
)
from reports import send_weekly_report
from scraper import scrape_it_courses
from state_manager import diff_courses, diff_turmas, load_state, save_state
from turmas_scraper import scrape_all_turmas, scrape_specific_turmas
from watched_classes import check_watched_classes, load_watched_classes


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def check_courses_update() -> None:
    """Check for course and turma updates."""
    logger.info("Checking for course updates...")

    # Scrape current data
    courses = scrape_it_courses()
    turmas = scrape_all_turmas(courses)
    current_snapshot = Snapshot(at=datetime.now(), courses=courses, turmas=turmas)

    # Load previous state
    previous_snapshot = load_state()

    if previous_snapshot:
        # Diff courses
        course_diff = diff_courses(previous_snapshot.courses, current_snapshot.courses)
        if (
            course_diff.new_courses
            or course_diff.deleted_courses
            or course_diff.modified_courses
        ):
            message = format_course_diff_message(course_diff)
            for chunk in [message]:
                await send_telegram_message(chunk)

        # Diff turmas
        turma_diff = diff_turmas(previous_snapshot.turmas, current_snapshot.turmas)
        if (
            turma_diff.new_turmas
            or turma_diff.deleted_turmas
            or turma_diff.spot_changes
        ):
            message = format_turma_diff_message(turma_diff)
            for chunk in [message]:
                await send_telegram_message(chunk)

    # Save current state
    save_state(current_snapshot)
    logger.info(
        "Update check complete. Courses: %s, Turmas: %s",
        len(courses),
        len(turmas),
    )


async def check_watched_classes_update() -> None:
    """Check watched classes for spot changes.

    Uses selective scraping to only check the specific course/unit pairs
    that are being watched, avoiding a full scrape of the entire catalog.
    """
    logger.info("Checking watched classes...")

    watched = load_watched_classes()
    if not watched:
        logger.info("No watched classes configured.")
        return

    # Extract unique (course_id, unit_id) pairs from watched classes
    # Skip any that don't have course_id/unit_id (backward compatibility)
    target_pairs = {
        (w.course_id, w.unit_id)
        for w in watched
        if w.course_id is not None and w.unit_id is not None
    }

    # Only scrape courses to get unit metadata, then selectively scrape turmas
    courses = scrape_it_courses()

    if target_pairs:
        logger.info(
            "Selective scraping for %s watched classes (%s unique course/unit pairs)",
            len(watched),
            len(target_pairs),
        )
        turmas = scrape_specific_turmas(courses, target_pairs)
    else:
        # Fallback to full scrape if watched classes don't have IDs
        logger.warning(
            "Watched classes missing course_id/unit_id, falling back to full scrape"
        )
        turmas = scrape_all_turmas(courses)

    changes = check_watched_classes(turmas)

    for watched_class, current_turma in changes:
        message = format_spot_change_alert(watched_class, current_turma)
        await send_telegram_message(message)

    logger.info("Watched classes check complete. Changes: %s", len(changes))


async def send_scheduled_weekly_report() -> None:
    """Send the weekly report."""
    logger.info("Generating weekly report...")
    snapshot = load_state()
    if snapshot:
        await send_weekly_report(snapshot)
        logger.info("Weekly report sent.")
    else:
        logger.warning("No snapshot available for weekly report.")


def schedule_tasks() -> None:
    """Set up scheduled tasks."""
    weekday_name = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ][config.WEEKLY_REPORT_WEEKDAY]

    schedule.every().__getattribute__(weekday_name).at(
        f"{config.WEEKLY_REPORT_HOUR:02d}:00"
    ).do(lambda: asyncio.run(send_scheduled_weekly_report()))

    schedule.every().day.at("08:00").do(lambda: asyncio.run(check_courses_update()))

    schedule.every(config.WATCHED_CLASS_CHECK_INTERVAL).minutes.do(
        lambda: asyncio.run(check_watched_classes_update())
    )


def main() -> None:
    """Main application entry point."""
    logger.info("SENAI Courses Advisor starting...")
    logger.info("Data directory: %s", config.DATA_DIR)

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Notifications will be disabled.")
        logger.warning("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file.")

    schedule_tasks()
    logger.info("Tasks scheduled. Running initial check...")

    asyncio.run(check_courses_update())

    logger.info("Entering main loop. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")


if __name__ == "__main__":
    main()


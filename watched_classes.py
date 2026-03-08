"""Management of watched turmas (classes) for spot-change alerts."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import pytz

import config
from models import Turma

logger = logging.getLogger(__name__)


SAO_PAULO_TZ = pytz.timezone("America/Sao_Paulo")


@dataclass
class WatchedClass:
    """A class being actively monitored."""

    turma_key: str  # course_id_unit_id_turma_id
    course_name: str
    unit_name: str
    added_at: datetime
    last_spots_left: Optional[int] = None
    course_id: Optional[int] = None  # For selective scraping
    unit_id: Optional[int] = None  # For selective scraping


def _watched_to_dict(w: WatchedClass) -> dict:
    data = asdict(w)
    data["added_at"] = w.added_at.astimezone(SAO_PAULO_TZ).isoformat()
    return data


def _watched_from_dict(data: dict) -> WatchedClass:
    added_raw = data.get("added_at")
    if added_raw:
        added_at = datetime.fromisoformat(added_raw)
        if added_at.tzinfo is None:
            added_at = SAO_PAULO_TZ.localize(added_at)
    else:
        added_at = SAO_PAULO_TZ.localize(datetime.now())
    return WatchedClass(
        turma_key=data["turma_key"],
        course_name=data.get("course_name", ""),
        unit_name=data.get("unit_name", ""),
        added_at=added_at,
        last_spots_left=data.get("last_spots_left"),
        course_id=data.get("course_id"),
        unit_id=data.get("unit_id"),
    )


def _atomic_write_json(path, data: list[dict]) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    config.os.replace(tmp_path, path)


def load_watched_classes() -> list[WatchedClass]:
    """Load watched classes from WATCHED_CLASSES_FILE."""
    path = config.WATCHED_CLASSES_FILE
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        watched = [_watched_from_dict(item) for item in data]
        logger.info("Loaded %s watched classes from %s", len(watched), path)
        return watched
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load watched classes from %s: %s", path, exc)
        return []


def save_watched_classes(watched: list[WatchedClass]) -> None:
    """Save watched classes to WATCHED_CLASSES_FILE."""
    path = config.WATCHED_CLASSES_FILE
    try:
        payload = [_watched_to_dict(w) for w in watched]
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        config.os.replace(tmp_path, path)
        logger.info("Saved %s watched classes to %s", len(watched), path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save watched classes to %s: %s", path, exc)


def add_watched_class(turma: Turma) -> None:
    """Add a turma to the watch list."""
    watched = load_watched_classes()
    keys = {w.turma_key for w in watched}
    if turma.key in keys:
        logger.info("Turma %s already in watch list", turma.key)
        return
    now = SAO_PAULO_TZ.localize(datetime.now())
    wc = WatchedClass(
        turma_key=turma.key,
        course_name=turma.course_name,
        unit_name=turma.unit_name,
        added_at=now,
        last_spots_left=turma.spots_left,
        course_id=turma.course_id,
        unit_id=turma.unit_id,
    )
    watched.append(wc)
    save_watched_classes(watched)
    logger.info("Added watched class %s (%s @ %s)", turma.key, turma.course_name, turma.unit_name)


def remove_watched_class(turma_key: str) -> None:
    """Remove a turma from the watch list."""
    watched = load_watched_classes()
    new_watched = [w for w in watched if w.turma_key != turma_key]
    if len(new_watched) == len(watched):
        logger.info("No watched class with key %s to remove", turma_key)
        return
    save_watched_classes(new_watched)
    logger.info("Removed watched class %s", turma_key)


def check_watched_classes(current_turmas: list[Turma]) -> list[tuple[WatchedClass, Turma]]:
    """Check watched classes for spot changes.

    Returns list of (watched, current_turma) with changes and updates the
    stored ``last_spots_left`` values.
    """
    watched = load_watched_classes()
    if not watched:
        return []

    current_by_key = {t.key: t for t in current_turmas}
    changes: list[tuple[WatchedClass, Turma]] = []

    for w in watched:
        current = current_by_key.get(w.turma_key)
        if not current:
            continue
        if current.spots_left != w.last_spots_left:
            changes.append((w, current))
            w.last_spots_left = current.spots_left

    if changes:
        save_watched_classes(watched)
        logger.info("Detected %s watched class spot changes", len(changes))
    return changes


__all__ = [
    "WatchedClass",
    "load_watched_classes",
    "save_watched_classes",
    "add_watched_class",
    "remove_watched_class",
    "check_watched_classes",
]


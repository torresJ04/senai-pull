"""State management and diffing for SENAI Courses Advisor."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List, Optional

import pytz

import config
from models import Course, Snapshot, Turma

logger = logging.getLogger(__name__)


SAO_PAULO_TZ = pytz.timezone("America/Sao_Paulo")


@dataclass
class CourseDiff:
    """Represents changes in courses."""

    new_courses: list[Course]
    deleted_courses: list[Course]
    modified_courses: list[Course]


@dataclass
class TurmaDiff:
    """Represents changes in turmas."""

    new_turmas: list[Turma]
    deleted_turmas: list[Turma]
    spot_changes: list[tuple[Turma, Turma]]  # (old, new)


def _course_to_dict(course: Course) -> dict:
    data = asdict(course)
    return data


def _turma_to_dict(turma: Turma) -> dict:
    data = asdict(turma)
    return data


def _snapshot_to_dict(snapshot: Snapshot) -> dict:
    return {
        "at": snapshot.at.astimezone(SAO_PAULO_TZ).isoformat(),
        "courses": [_course_to_dict(c) for c in snapshot.courses],
        "turmas": [_turma_to_dict(t) for t in snapshot.turmas],
    }


def _course_from_dict(data: dict) -> Course:
    return Course(
        course_id=data["course_id"],
        name=data["name"],
        slug=data.get("slug", ""),
        modality=data.get("modality", ""),
        level=data.get("level", ""),
        area=data.get("area", ""),
        description=data.get("description", ""),
        workload_hours=data.get("workload_hours"),
        units=data.get("units", []),
        url=data.get("url", ""),
    )


def _turma_from_dict(data: dict) -> Turma:
    return Turma(
        turma_id=data.get("turma_id"),
        course_id=data["course_id"],
        unit_id=data["unit_id"],
        course_name=data.get("course_name", ""),
        unit_name=data.get("unit_name", ""),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        spots_total=data.get("spots_total"),
        spots_left=data.get("spots_left"),
        schedule_type=data.get("schedule_type"),
        shift=data.get("shift"),
        raw_text=data.get("raw_text"),
    )


def _snapshot_from_dict(data: dict) -> Snapshot:
    at_raw = data.get("at")
    if at_raw:
        at = datetime.fromisoformat(at_raw)
        if at.tzinfo is None:
            at = SAO_PAULO_TZ.localize(at)
    else:
        at = SAO_PAULO_TZ.localize(datetime.now())

    courses = [_course_from_dict(c) for c in data.get("courses", [])]
    turmas = [_turma_from_dict(t) for t in data.get("turmas", [])]
    return Snapshot(at=at, courses=courses, turmas=turmas)


def load_state() -> Optional[Snapshot]:
    """Load the last saved snapshot from STATE_FILE.

    Returns None if the file does not exist or is corrupted.
    """
    path = config.STATE_FILE
    if not path.exists():
        logger.info("No existing state file at %s", path)
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        snapshot = _snapshot_from_dict(data)
        logger.info(
            "Loaded state from %s: %s courses, %s turmas",
            path,
            len(snapshot.courses),
            len(snapshot.turmas),
        )
        return snapshot
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load state from %s: %s", path, exc)
        return None


def _atomic_write_json(path: os.PathLike, data: dict) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def save_state(snapshot: Snapshot) -> None:
    """Save current snapshot to STATE_FILE."""
    path = config.STATE_FILE
    try:
        payload = _snapshot_to_dict(snapshot)
        _atomic_write_json(path, payload)
        logger.info(
            "Saved state to %s: %s courses, %s turmas",
            path,
            len(snapshot.courses),
            len(snapshot.turmas),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save state to %s: %s", path, exc)


def diff_courses(old: List[Course], new: List[Course]) -> CourseDiff:
    """Compare two course lists and return differences.

    Courses are compared by course_id. A course is considered modified if any
    of its main fields (name, slug, modality, level, area, description,
    workload_hours, units length) differ.
    """
    old_by_id = {c.course_id: c for c in old}
    new_by_id = {c.course_id: c for c in new}

    new_ids = set(new_by_id.keys())
    old_ids = set(old_by_id.keys())

    new_courses = [new_by_id[i] for i in sorted(new_ids - old_ids)]
    deleted_courses = [old_by_id[i] for i in sorted(old_ids - new_ids)]

    modified_courses: list[Course] = []
    for cid in sorted(new_ids & old_ids):
        o = old_by_id[cid]
        n = new_by_id[cid]
        if _course_changed(o, n):
            modified_courses.append(n)

    return CourseDiff(
        new_courses=new_courses,
        deleted_courses=deleted_courses,
        modified_courses=modified_courses,
    )


def _course_changed(old: Course, new: Course) -> bool:
    """Return True if any relevant field has changed."""
    if (
        old.name != new.name
        or old.slug != new.slug
        or old.modality != new.modality
        or old.level != new.level
        or old.area != new.area
        or old.description != new.description
        or old.workload_hours != new.workload_hours
        or len(old.units) != len(new.units)
    ):
        return True
    return False


def diff_turmas(old: List[Turma], new: List[Turma]) -> TurmaDiff:
    """Compare two turma lists and return differences.

    Turmas are compared by turma.key (course_id_unit_id_turma_id/raw_text).
    """
    old_by_key = {t.key: t for t in old}
    new_by_key = {t.key: t for t in new}

    old_keys = set(old_by_key.keys())
    new_keys = set(new_by_key.keys())

    new_turmas = [new_by_key[k] for k in sorted(new_keys - old_keys)]
    deleted_turmas = [old_by_key[k] for k in sorted(old_keys - new_keys)]

    spot_changes: list[tuple[Turma, Turma]] = []
    for key in sorted(new_keys & old_keys):
        o = old_by_key[key]
        n = new_by_key[key]
        if o.spots_left != n.spots_left:
            spot_changes.append((o, n))

    return TurmaDiff(
        new_turmas=new_turmas,
        deleted_turmas=deleted_turmas,
        spot_changes=spot_changes,
    )


__all__ = [
    "CourseDiff",
    "TurmaDiff",
    "load_state",
    "save_state",
    "diff_courses",
    "diff_turmas",
]


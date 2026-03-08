"""Cache for tracking and skipping (course_id, unit_id) combinations that consistently return empty turmas.

This prevents wasted API calls to endpoints that we know will return no data.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

CACHE_FILE = Path(config.DATA_DIR) / "empty_turmas_cache.json"
EMPTY_THRESHOLD = 3  # Mark as empty after 3 consecutive empty responses
CACHE_EXPIRY_DAYS = 7  # Re-try empty endpoints after 7 days


@dataclass
class EmptyCacheEntry:
    """Track consecutive empty responses for a (course_id, unit_id) pair."""
    course_id: int
    unit_id: int
    consecutive_empty: int = 0
    first_empty_at: Optional[str] = None
    last_checked_at: Optional[str] = None

    @property
    def key(self) -> str:
        return f"{self.course_id}_{self.unit_id}"

    def should_skip(self) -> bool:
        """Return True if this endpoint should be skipped."""
        if self.consecutive_empty < EMPTY_THRESHOLD:
            return False

        # Check if cache expired
        if self.first_empty_at:
            first_empty = datetime.fromisoformat(self.first_empty_at)
            if datetime.now() - first_empty > timedelta(days=CACHE_EXPIRY_DAYS):
                return False  # Cache expired, retry

        return True


class EmptyResponseCache:
    """Manages cache of empty turmas responses."""

    def __init__(self):
        self.entries: dict[str, EmptyCacheEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if not CACHE_FILE.exists():
            return

        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                entry = EmptyCacheEntry(**entry_data)
                self.entries[entry.key] = entry

            logger.info(f"Loaded empty response cache with {len(self.entries)} entries")
        except Exception as exc:
            logger.warning(f"Failed to load empty response cache: {exc}")

    def _save(self) -> None:
        """Save cache to disk."""
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "entries": [asdict(entry) for entry in self.entries.values()],
            "updated_at": datetime.now().isoformat(),
        }

        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning(f"Failed to save empty response cache: {exc}")

    def should_skip(self, course_id: int, unit_id: int) -> bool:
        """Check if this (course_id, unit_id) should be skipped."""
        key = f"{course_id}_{unit_id}"
        entry = self.entries.get(key)

        if not entry:
            return False

        should_skip = entry.should_skip()

        # Reset if cache expired
        if not should_skip and entry.consecutive_empty >= EMPTY_THRESHOLD:
            logger.info(
                f"Cache expired for course_id={course_id} unit_id={unit_id}, will retry"
            )
            entry.consecutive_empty = 0
            entry.first_empty_at = None
            self._save()

        return should_skip

    def record_empty(self, course_id: int, unit_id: int) -> None:
        """Record an empty response for this combination."""
        key = f"{course_id}_{unit_id}"
        entry = self.entries.get(key)

        if not entry:
            entry = EmptyCacheEntry(
                course_id=course_id,
                unit_id=unit_id,
                consecutive_empty=1,
                first_empty_at=datetime.now().isoformat(),
                last_checked_at=datetime.now().isoformat(),
            )
            self.entries[key] = entry
        else:
            entry.consecutive_empty += 1
            if not entry.first_empty_at:
                entry.first_empty_at = datetime.now().isoformat()
            entry.last_checked_at = datetime.now().isoformat()

        if entry.consecutive_empty == EMPTY_THRESHOLD:
            logger.info(
                f"Marking course_id={course_id} unit_id={unit_id} as persistently empty "
                f"(will skip for {CACHE_EXPIRY_DAYS} days)"
            )

        self._save()

    def record_success(self, course_id: int, unit_id: int) -> None:
        """Record a successful response (turmas found)."""
        key = f"{course_id}_{unit_id}"

        # If this was previously marked as empty, reset it
        if key in self.entries:
            logger.info(
                f"Clearing empty cache for course_id={course_id} unit_id={unit_id} (turmas found)"
            )
            del self.entries[key]
            self._save()

    def get_stats(self) -> dict:
        """Get cache statistics."""
        skipped = sum(1 for e in self.entries.values() if e.should_skip())
        return {
            "total_entries": len(self.entries),
            "currently_skipped": skipped,
            "cache_expiry_days": CACHE_EXPIRY_DAYS,
            "empty_threshold": EMPTY_THRESHOLD,
        }


# Global cache instance
_cache: Optional[EmptyResponseCache] = None


def get_cache() -> EmptyResponseCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = EmptyResponseCache()
    return _cache

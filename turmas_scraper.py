"""Scraper for SENAI SP turmas (class schedules) shown in the VER TURMAS modal.

This module is intentionally implemented in an API-first way, with an HTML
fallback that parses the modal structure documented in PROJECT_SPEC.md.

The exact API endpoint used by ``openModalTurmas`` may change over time and is
not documented. The current implementation is therefore best-effort and is
designed to be easy to adapt: adjust ``_build_turmas_request`` and
``_extract_turma_items`` if you discover the concrete endpoint/markup.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict
from typing import Iterable, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

import config
from models import Course, Turma, Unit
from empty_response_cache import get_cache

logger = logging.getLogger(__name__)


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


def _parse_dates(start_raw: str | None, end_raw: str | None) -> tuple[Optional[str], Optional[str]]:
    """Parse date strings like 'Início: 15/03/2026' into DD/MM/YYYY strings.

    We keep them as locale-style strings for easier human reading and to avoid
    over-constraining the representation. The ``Snapshot`` serializer will be
    responsible for normalizing to ISO if needed.
    """

    def _extract(labelled: str | None) -> Optional[str]:
        if not labelled:
            return None
        text = _clean_text(labelled)
        # Try to grab the first date-like token
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", text)
        if not m:
            # Fallback to dateutil for anything date-ish
            try:
                dt = date_parser.parse(text, dayfirst=True)
                return dt.strftime("%d/%m/%Y")
            except Exception:
                return None
        return m.group(1)

    return _extract(start_raw), _extract(end_raw)


def _parse_spots(text: str | None) -> tuple[Optional[int], Optional[int]]:
    """Parse 'Vagas disponíveis: 12 de 30' -> (spots_left, spots_total)."""
    if not text:
        return None, None
    s = _clean_text(text)
    # Typical pattern: 'Vagas disponíveis: 12 de 30'
    m = re.search(r"(\d+)\s*de\s*(\d+)", s)
    if not m:
        # Sometimes only one value appears, e.g. 'Vagas: 20'
        m2 = re.search(r"(\d+)", s)
        if m2:
            value = int(m2.group(1))
            # Interpret as "spots_left" when phrased as "Vagas"
            if "vaga" in s.lower():
                return value, None
            return None, value
        return None, None
    left, total = m.groups()
    return int(left), int(total)


def _parse_schedule(text: str | None) -> tuple[Optional[str], Optional[str]]:
    """Parse schedule string into schedule_type and shift.

    Example:
        'Segunda a Sexta - Noite (19h às 22h)'
        -> schedule_type='Segunda a Sexta', shift='Noite'
    """
    if not text:
        return None, None
    s = _clean_text(text)
    # Drop time range in parentheses if present
    if "(" in s:
        s = s.split("(", 1)[0].strip()
    if " - " in s:
        schedule_type, shift = [part.strip() for part in s.split(" - ", 1)]
        return schedule_type or None, shift or None
    return s, None


def _build_turmas_request(
    course_id: int,
    unit_id: int,
    slug: str,
    *,
    estrategia: str,
    bolsa: int | None,
    gratuito: int | None,
    turno: int | None,
) -> tuple[str, dict, dict]:
    """Build the real POST request used by ``openModalTurmas``.

    Based on DevTools inspection, the browser sends a POST to
    ``/cursosturmas/`` with an x-www-form-urlencoded body containing:

    - nomeCurso: slug (e.g. 'administracao-de-sistemas-servicenow-csa')
    - cursoId: numeric course ID (e.g. 110384)
    - escolaId: numeric unit ID
    - estrategia: modality string (e.g. 'Presencial')
    - bolsa: '1'
    - gratuito: '1'
    - turno: '0'
    """
    url = f"{config.BASE_URL}/cursosturmas/"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": config.IT_COURSES_URL,
        "X-Requested-With": "XMLHttpRequest",
        "Origin": config.BASE_URL,
    }
    # IMPORTANT: DevTools shows that the actual payload for free IT courses is:
    # bolsa=1, gratuito=1, turno=0 for all cases we care about, regardless of
    # the numeric flags in openModalTurmas. To avoid under-fetching turmas, we
    # fix these to the observed values instead of trusting the last arguments.
    data = {
        "nomeCurso": slug,
        "cursoId": str(course_id),
        "escolaId": str(unit_id),
        "estrategia": estrategia or "Presencial",
        "bolsa": "1",
        "gratuito": "1",
        "turno": "0",
    }
    return url, headers, data


def _fetch_turmas_via_api(
    course_id: int,
    unit_id: int,
    slug: str,
    *,
    estrategia: str,
    bolsa: int | None,
    gratuito: int | None,
    turno: int | None,
) -> Optional[str]:
    """Try to fetch turmas HTML via the (undocumented) API endpoint.

    Returns the raw HTML fragment for the modal's body, or None on failure.
    """
    url, headers, data = _build_turmas_request(
        course_id,
        unit_id,
        slug,
        estrategia=estrategia,
        bolsa=bolsa,
        gratuito=gratuito,
        turno=turno,
    )
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=30)
        if not resp.ok:
            logger.warning(
                "Turmas API call failed for course_id=%s unit_id=%s status=%s",
                course_id,
                unit_id,
                resp.status_code,
            )
            return None
        return resp.text
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Error calling turmas API for course_id=%s unit_id=%s: %s",
            course_id,
            unit_id,
            exc,
        )
        return None


def _extract_turma_items(html: str) -> List[dict]:
    """Extract turma item dicts from the modal HTML fragment.

    Current structure (simplified) from the /cursosturmas/ response:

    <div class='card p-1 mb-2'>
      <div class='card-body pt-1'>
        <p class='card-text'>Barueri</p>  <!-- city/unit -->
        <div class='row m-2'>
          <span class='badge ...'>Presencial</span>
          <span class='badge ...'>Vagas: 20</span>
        </div>
        <div class='row m-2'>
          <strong>04/07/2026</strong>  <!-- início -->
          <strong>01/08/2026</strong>  <!-- fim -->
        </div>
        <div class='row'>
          <div class='col-6'>aos Sábados</div>        <!-- período -->
          <div class='col-6'>08:00 às 17:00</div>     <!-- horário -->
        </div>
        ...
      </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    # New structure from /cursosturmas/: one outer card per turma.
    # Prefer locating by the inner body and then going up to the parent card
    # to be resilient to class changes.
    body_cards = soup.select("div.card-body.pt-1")
    cards: List = []
    for body in body_cards:
        parent = body.parent
        if (
            parent
            and getattr(parent, "name", None) == "div"
            and "card" in (parent.get("class") or [])
        ):
            cards.append(parent)

    # Fallback: use older class-based selector
    if not cards:
        cards = soup.select("div.card.p-1.mb-2")

    # Final fallback to the older modal-based structure from PROJECT_SPEC.md
    if not cards:
        container = soup.find(id="modalTurmas") or soup
        cards = container.select(".turma-item")

    results: List[dict] = []

    for card in cards:
        # Spots: badge containing 'Vagas'
        vagas_el = None
        for badge in card.select(".badge"):
            if "vaga" in badge.get_text().lower():
                vagas_el = badge
                break

        # Dates: first two <strong> elements inside the card
        strongs = card.select("strong")
        start_raw = strongs[0].get_text() if len(strongs) >= 1 else None
        end_raw = strongs[1].get_text() if len(strongs) >= 2 else None
        start_date, end_date = _parse_dates(start_raw, end_raw)

        # Schedule: 'Período' / 'Horário' card
        schedule_type = None
        shift = None
        # Look for the row following the 'Período'/'Horário' header
        period_row = None
        for row in card.select(".row"):
            if "Período" in row.get_text():
                # Next sibling row should contain actual values
                period_row = row.find_next_sibling("div")
                break
        if period_row:
            cols = period_row.select(".col-6")
            if len(cols) >= 1:
                schedule_type = _clean_text(cols[0].get_text())
            if len(cols) >= 2:
                shift = _clean_text(cols[1].get_text())

        spots_left, spots_total = _parse_spots(
            vagas_el.get_text() if vagas_el else None
        )

        raw_text = _clean_text(card.get_text(" ", strip=True))

        results.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "spots_left": spots_left,
                "spots_total": spots_total,
                "schedule_type": schedule_type,
                "shift": shift,
                "raw_text": raw_text,
            }
        )

    return results


def fetch_turmas(
    course_id: int,
    unit_id: int,
    slug: str,
    *,
    course_name: str,
    unit_name: str,
    estrategia: str,
    bolsa: int | None,
    gratuito: int | None,
    turno: int | None,
    skip_cache: bool = False,
) -> list[Turma]:
    """Fetch turmas for a specific course and unit.

    This first attempts to use a (speculative) JSON/HTML endpoint similar to
    what ``openModalTurmas`` would call. If that fails, it returns an empty
    list but logs enough detail to help you adjust the implementation.

    Uses an empty response cache to skip combinations that consistently return
    no turmas, unless skip_cache=True.
    """
    cache = get_cache()

    # Check cache unless explicitly skipped
    if not skip_cache and cache.should_skip(course_id, unit_id):
        logger.debug(
            "Skipping course_id=%s unit_id=%s (in empty response cache)",
            course_id,
            unit_id,
        )
        return []

    logger.info(
        "Fetching turmas for course_id=%s unit_id=%s slug=%s estrategia=%s bolsa=%s gratuito=%s turno=%s",
        course_id,
        unit_id,
        slug,
        estrategia,
        bolsa,
        gratuito,
        turno,
    )
    html = _fetch_turmas_via_api(
        course_id,
        unit_id,
        slug,
        estrategia=estrategia,
        bolsa=bolsa,
        gratuito=gratuito,
        turno=turno,
    )
    if not html:
        logger.warning(
            "No turmas HTML returned for course_id=%s unit_id=%s slug=%s",
            course_id,
            unit_id,
            slug,
        )
        cache.record_empty(course_id, unit_id)
        return []

    items = _extract_turma_items(html)

    if not items:
        logger.warning(
            "HTML returned but no turmas parsed for course_id=%s unit_id=%s",
            course_id,
            unit_id,
        )
        cache.record_empty(course_id, unit_id)
        return []

    turmas: list[Turma] = []
    for idx, item in enumerate(items):
        turma = Turma(
            turma_id=str(idx),  # if a real turma_id field is found later, use that
            course_id=course_id,
            unit_id=unit_id,
            course_name=course_name,
            unit_name=unit_name,
            start_date=item["start_date"],
            end_date=item["end_date"],
            spots_total=item["spots_total"],
            spots_left=item["spots_left"],
            schedule_type=item["schedule_type"],
            shift=item["shift"],
            raw_text=item["raw_text"],
        )
        turmas.append(turma)

    # Record success in cache
    cache.record_success(course_id, unit_id)

    logger.info(
        "Parsed %s turmas for course_id=%s unit_id=%s",
        len(turmas),
        course_id,
        unit_id,
    )
    return turmas


def scrape_all_turmas(
    courses: Iterable[Course],
    *,
    delay_seconds: float = 0.0,
    city: str | None = None,
    max_workers: int = 5,
    skip_cache: bool = False,
) -> list[Turma]:
    """Scrape turmas for all courses and their units.

    If ``city`` is provided, only units whose city matches (case-insensitive)
    are queried. Requests are performed with limited concurrency using a
    ThreadPoolExecutor for better overall latency without overwhelming the
    remote server.

    Uses an empty response cache to skip combinations that consistently return
    no turmas, unless skip_cache=True.
    """

    tasks: list[tuple[Course, Unit, str]] = []
    for course in courses:
        for unit in course.units:
            unit_city = (unit.city or "").strip()
            if city and unit_city.lower() != city.strip().lower():
                continue
            unit_name = f"{unit.city} - {unit.neighborhood}".strip(" -")
            tasks.append((course, unit, unit_name))

    all_turmas: list[Turma] = []
    if not tasks:
        logger.info("No course/unit pairs to scrape for turmas.")
        return all_turmas

    cache = get_cache()
    logger.info(
        "Scraping turmas for %s course/unit pairs. Cache stats: %s",
        len(tasks),
        cache.get_stats(),
    )

    def _worker(args: tuple[Course, Unit, str]) -> list[Turma]:
        course, unit, unit_name = args
        try:
            return fetch_turmas(
                course_id=course.course_id,
                unit_id=unit.unit_id,
                slug=course.slug,
                course_name=course.name,
                unit_name=unit_name,
                estrategia=unit.estrategia,
                bolsa=unit.bolsa,
                gratuito=unit.gratuito,
                turno=unit.turno,
                skip_cache=skip_cache,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error scraping turmas for course_id=%s unit_id=%s: %s | course=%s unit=%s",
                course.course_id,
                unit.unit_id,
                exc,
                course.name,
                asdict(unit),
            )
            return []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(_worker, task): task for task in tasks
        }
        for future in as_completed(future_to_task):
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            turmas = future.result()
            all_turmas.extend(turmas)

    logger.info("Total turmas scraped: %s", len(all_turmas))
    return all_turmas


def scrape_specific_turmas(
    courses: Iterable[Course],
    target_pairs: set[tuple[int, int]],
) -> list[Turma]:
    """Scrape turmas only for specific (course_id, unit_id) pairs.

    This is optimized for watched classes where we only need to check
    a handful of specific course/unit combinations instead of the entire catalog.

    Args:
        courses: Iterable of all courses with units
        target_pairs: Set of (course_id, unit_id) tuples to scrape

    Returns:
        List of turmas for the specified pairs only
    """
    if not target_pairs:
        return []

    tasks: list[tuple[Course, Unit, str]] = []
    for course in courses:
        for unit in course.units:
            if (course.course_id, unit.unit_id) in target_pairs:
                unit_name = f"{unit.city} - {unit.neighborhood}".strip(" -")
                tasks.append((course, unit, unit_name))

    if not tasks:
        logger.info("No matching course/unit pairs found for selective scraping.")
        return []

    logger.info(
        "Selective scraping for %s specific course/unit pairs (out of %s requested)",
        len(tasks),
        len(target_pairs),
    )

    all_turmas: list[Turma] = []

    for course, unit, unit_name in tasks:
        try:
            turmas = fetch_turmas(
                course_id=course.course_id,
                unit_id=unit.unit_id,
                slug=course.slug,
                course_name=course.name,
                unit_name=unit_name,
                estrategia=unit.estrategia,
                bolsa=unit.bolsa,
                gratuito=unit.gratuito,
                turno=unit.turno,
                skip_cache=True,  # Always check watched classes
            )
            all_turmas.extend(turmas)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error in selective scraping for course_id=%s unit_id=%s: %s",
                course.course_id,
                unit.unit_id,
                exc,
            )

    logger.info("Selective scraping found %s turmas", len(all_turmas))
    return all_turmas


__all__ = ["fetch_turmas", "scrape_all_turmas", "scrape_specific_turmas"]


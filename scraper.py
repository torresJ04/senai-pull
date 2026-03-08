"""Scraper for SENAI SP IT courses listing page."""
import re
from typing import Optional
import unicodedata

import requests
from bs4 import BeautifulSoup

from config import IT_COURSES_URL
from models import Course, Unit


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


def _parse_workload_hours(horario_el) -> Optional[int]:
    if not horario_el:
        return None
    text = _clean_text(horario_el.get_text())
    match = re.search(r"(\d+)\s*horas", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _parse_open_modal_turmas(
    link,
) -> Optional[tuple[int, int, str, str, str, int, int, int]]:
    """Extract all arguments from VER TURMAS onclick.

    Returns:
        (course_id, unit_id, slug, course_name, estrategia, bolsa, gratuito, turno)
    """
    href = link.get("href") or ""
    if "openModalTurmas" not in href:
        return None
    # openModalTurmas('Name', 'slug', courseId, unitId, 'Presencial', 0, 1, 0);
    match = re.search(
        r"openModalTurmas\s*\(\s*"
        r"['\"]([^'\"]*)['\"]\s*,\s*"  # name
        r"['\"]([^'\"]*)['\"]\s*,\s*"  # slug
        r"(\d+)\s*,\s*"  # courseId
        r"(\d+)\s*,\s*"  # unitId
        r"['\"]([^'\"]*)['\"]\s*,\s*"  # estrategia
        r"(\d+)\s*,\s*"  # bolsa
        r"(\d+)\s*,\s*"  # gratuito
        r"(\d+)\s*"  # turno
        r"\)",
        href,
    )
    if not match:
        return None
    name, slug, course_id, unit_id, estrategia, bolsa, gratuito, turno = match.groups()
    return (
        int(course_id),
        int(unit_id),
        slug,
        name,
        estrategia,
        int(bolsa),
        int(gratuito),
        int(turno),
    )


def fetch_page(url: str = IT_COURSES_URL) -> str:
    """Fetch the courses listing page HTML."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def _slugify_city(city: str) -> str:
    """Convert a human city name to the slug used in ?cidadesp=."""
    # Normalize accents, keep ASCII only
    normalized = (
        unicodedata.normalize("NFKD", city)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.strip().lower())
    return slug.strip("-")


def fetch_page_for_city(city: str) -> str:
    """Fetch the courses listing page HTML filtered by city."""
    city_slug = _slugify_city(city)
    url = (
        f"{IT_COURSES_URL.replace('/cursos-livres/', '/0/')}"
        f"&modalidade=1&cidadesp={city_slug}"
    )
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def scrape_it_courses_for_city(city: str) -> list[Course]:
    """Fetch and parse SENAI IT free courses filtered by a specific city."""
    html = fetch_page_for_city(city)
    return parse_courses(html)


def parse_courses(html: str) -> list[Course]:
    """Parse the IT courses listing HTML into Course and Unit objects."""
    soup = BeautifulSoup(html, "html.parser")
    card_cursos = soup.find(id="card-cursos")
    if not card_cursos:
        return []

    courses: list[Course] = []
    # Course blocks: .card with .card-body inside the main content
    card_columns = card_cursos.select(".card-columns .card, .card-body")
    # Actually from goal.txt the structure is: .card with .card-body, and inside we have
    # .card-title, .card-text, .horario, and then .list-group with .list-group-item for units
    cards = card_cursos.select(".card")
    seen_course_ids: set[int] = set()

    for card in cards:
        body = card.find(class_="card-body")
        if not body:
            continue

        title_el = body.find("h5", class_="card-title")
        if not title_el:
            continue

        name = _clean_text(title_el.get_text())
        if not name or "Tecnologia" in name and "Informação" in name and len(name) < 50:
            # Skip section headers
            continue

        # Get badges
        badges = [b.get_text().strip() for b in body.select(".badge")]
        modality = next((b for b in badges if "Presencial" in b or "Distância" in b), "")
        level = next((b for b in badges if "Livres" in b or "Técnicos" in b or "Aprendiz" in b), "")
        area = next((b for b in badges if "Tecnologia" in b or "Informática" in b), "")

        desc_el = body.find("p", class_="card-text")
        description = _clean_text(desc_el.get_text()) if desc_el else ""

        horario_el = body.find("p", class_="horario")
        workload = _parse_workload_hours(horario_el)

        # Course id and slug from first "Ver Unidades" / VER TURMAS link
        list_group = card.find("ul", class_="list-group")
        units: list[Unit] = []
        course_id: Optional[int] = None
        slug: Optional[str] = None

        if list_group:
            for item in list_group.select("li.list-group-item"):
                # Skip "Declarar interesse" row
                if item.find("a", class_="btn-interesse"):
                    continue
                strong = item.find("strong")
                city_neighborhood = _clean_text(strong.get_text()) if strong else ""
                # "Barueri - Centro" or "São Paulo - Vila Alpina"
                parts = [p.strip() for p in city_neighborhood.split("-", 1)]
                city = parts[0] if parts else ""
                neighborhood = parts[1] if len(parts) > 1 else ""

                # Phone and address from next <p> and div
                phone = ""
                address = ""
                for p in item.find_all("p"):
                    t = _clean_text(p.get_text())
                    if "(" in t and ")" in t and len(t) < 25:
                        phone = t
                    elif "ALAMEDA" in t or "Rua" in t or "R." in t or "Av." in t:
                        address = t

                link = item.find("a", class_="btn-turmas", href=re.compile(r"openModalTurmas"))
                if link:
                    parsed = _parse_open_modal_turmas(link)
                    if parsed:
                        cid, uid, s, _, estrategia, bolsa, gratuito, turno = parsed
                        if course_id is None:
                            course_id = cid
                            slug = s
                        units.append(
                            Unit(
                                unit_id=uid,
                                city=city,
                                neighborhood=neighborhood,
                                phone=phone,
                                address=address,
                                estrategia=estrategia,
                                bolsa=bolsa,
                                gratuito=gratuito,
                                turno=turno,
                            )
                        )

        if course_id is None:
            # Try from Saiba Mais openModalInfo('Name', courseId)
            saiba = body.find("a", href=re.compile(r"openModalInfo"))
            if saiba and saiba.get("href"):
                m = re.search(r"openModalInfo\s*\([^,]+,\s*(\d+)\s*\)", saiba.get("href", ""))
                if m:
                    course_id = int(m.group(1))
            # Slug from course link if any
            curso_link = body.find("a", href=re.compile(r"/curso/"))
            if curso_link and curso_link.get("href"):
                path = curso_link["href"]
                if "/curso/" in path:
                    slug = path.split("/curso/")[-1].rstrip("/").split("/")[0]

        if course_id is not None and course_id not in seen_course_ids:
            seen_course_ids.add(course_id)
            courses.append(
                Course(
                    course_id=course_id,
                    name=name,
                    slug=slug or "",
                    modality=modality,
                    level=level,
                    area=area,
                    description=description,
                    workload_hours=workload,
                    units=units,
                )
            )

    return courses


def scrape_it_courses() -> list[Course]:
    """Fetch and parse SENAI IT free courses. Returns list of Course with units."""
    html = fetch_page()
    return parse_courses(html)


if __name__ == "__main__":
    courses = scrape_it_courses()
    print(f"Found {len(courses)} courses")
    for c in courses[:3]:
        print(f"  {c.course_id}: {c.name} ({len(c.units)} units)")

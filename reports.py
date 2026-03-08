"""Weekly report generation for SENAI Courses Advisor."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import html

import config
from models import Snapshot, Turma
from notifications import format_weekly_report, send_telegram_document


def generate_weekly_report(snapshot: Snapshot) -> str:
    """Generate comprehensive weekly report (plain text)."""
    return format_weekly_report(snapshot)


def generate_weekly_report_html(snapshot: Snapshot) -> str:
    """Generate an HTML version of the weekly report."""
    text = format_weekly_report(snapshot)
    date_str = snapshot.at.date().isoformat()
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>SENAI Courses Weekly Report - {date_str}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 1.5rem;
      line-height: 1.4;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>
{text}
</body>
</html>
"""


async def send_weekly_report(snapshot: Snapshot) -> None:
    """Generate and send weekly report via Telegram as an HTML document."""
    html = generate_weekly_report_html(snapshot)
    date_str = snapshot.at.date().isoformat()
    reports_dir: Path = config.DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"weekly_report_{date_str}.html"
    path.write_text(html, encoding="utf-8")
    await send_telegram_document(path, caption=f"SENAI Courses Weekly Report - {date_str}")


def generate_city_report_html(snapshot: Snapshot) -> str:
    """Generate an HTML report of available turmas grouped by city.

    Each city section contains a table:
    Course Name | Start Date | End Date | Available Spots | Horário
    """
    # Group turmas by city derived from unit_name ("Osasco - Centro" -> "Osasco")
    city_to_turmas: dict[str, list[Turma]] = {}
    for t in snapshot.turmas:
        city = (t.unit_name or "").split(" - ", 1)[0] or "Desconhecido"
        city_to_turmas.setdefault(city, []).append(t)

    date_str = snapshot.at.date().isoformat()

    sections: list[str] = []
    for city in sorted(city_to_turmas.keys()):
        rows: list[str] = []
        for turma in sorted(
            city_to_turmas[city],
            key=lambda x: (x.course_name or "", x.start_date or ""),
        ):
            course = html.escape(turma.course_name or "")
            start_date = html.escape(turma.start_date or "")
            end_date = html.escape(turma.end_date or "")
            spots_left = turma.spots_left if turma.spots_left is not None else 0
            spots_total = turma.spots_total if turma.spots_total is not None else 0
            horario = " ".join(
                part
                for part in [
                    turma.schedule_type or "",
                    turma.shift or "",
                ]
                if part
            )
            horario = html.escape(horario)
            rows.append(
                f"<tr>"
                f"<td>{course}</td>"
                f"<td>{start_date}</td>"
                f"<td>{end_date}</td>"
                f"<td>{spots_left}/{spots_total}</td>"
                f"<td>{horario}</td>"
                f"</tr>"
            )

        table_html = (
            "<table>"
            "<thead><tr>"
            "<th>Curso</th><th>Início</th><th>Fim</th><th>Vagas</th><th>Horário</th>"
            "</tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
        sections.append(f"<h2>{html.escape(city)}</h2>\n{table_html}")

    body = "\n\n".join(sections) if sections else "<p>Nenhuma turma encontrada.</p>"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>Cursos por cidade - {date_str}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 1.5rem;
      line-height: 1.4;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 2rem;
    }}
    th, td {{
      border: 1px solid #ddd;
      padding: 0.4rem 0.6rem;
      font-size: 0.9rem;
    }}
    th {{
      background: #f0f0f0;
      text-align: left;
    }}
    h2 {{
      margin-top: 1.5rem;
    }}
  </style>
</head>
<body>
<h1>Cursos por cidade - {date_str}</h1>
{body}
</body>
</html>
"""


async def send_city_report(snapshot: Snapshot) -> None:
    """Generate and send the city-based report via Telegram as HTML document."""
    html_report = generate_city_report_html(snapshot)
    date_str = snapshot.at.date().isoformat()
    reports_dir: Path = config.DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"city_report_{date_str}.html"
    path.write_text(html_report, encoding="utf-8")
    await send_telegram_document(path, caption=f"Cursos por cidade - {date_str}")


__all__ = [
    "generate_weekly_report",
    "generate_weekly_report_html",
    "send_weekly_report",
    "generate_city_report_html",
    "send_city_report",
]


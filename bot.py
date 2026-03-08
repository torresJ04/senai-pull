"""Telegram bot entrypoint for interactive commands.

Features:
- /start: shows a keyboard with:
  - Cursos por cidade
  - Trazer cursos disponíveis
  - Gerenciar alerta de cursos
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from models import Snapshot, Course
from reports import send_weekly_report, send_city_report
from scraper import scrape_it_courses, scrape_it_courses_for_city
from turmas_scraper import scrape_all_turmas
from watched_classes import load_watched_classes


MENU_KEYBOARD = ReplyKeyboardMarkup(
    [["Cursos por cidade", "Trazer cursos disponíveis"], ["Gerenciar alerta de cursos"]],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start - show main menu keyboard."""
    await update.effective_chat.send_message(
        "Escolha uma opção:",
        reply_markup=MENU_KEYBOARD,
    )


def _chunk_buttons(items: Iterable[str], size: int = 2) -> list[list[str]]:
    row: list[str] = []
    rows: list[list[str]] = []
    for item in items:
        row.append(item)
        if len(row) >= size:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def _merge_courses_by_id(existing: dict[int, Course], new_courses: list[Course]) -> None:
    """Merge courses into a dict keyed by course_id, merging units per course."""
    for course in new_courses:
        if course.course_id not in existing:
            existing[course.course_id] = course
            continue
        existing_course = existing[course.course_id]
        existing_unit_ids = {u.unit_id for u in existing_course.units}
        for unit in course.units:
            if unit.unit_id not in existing_unit_ids:
                existing_course.units.append(unit)


async def _handle_cursos_por_cidade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """First step: load courses and ask the user to pick a city or all.

    We only scrape full turmas once the user has chosen a city (or all),
    to keep this interaction fast.
    """
    await update.effective_chat.send_message(
        "Carregando cursos, por favor aguarde..."
    )
    courses = scrape_it_courses()

    # Store courses in user_data for the next step
    context.user_data["city_courses"] = courses
    context.user_data["city_mode"] = "await_city_choice"

    # Derive list of cities from units
    cities: set[str] = set()
    for course in courses:
        for unit in course.units:
            city = (unit.city or "").strip() or "Desconhecido"
            cities.add(city)

    if not cities:
        await update.effective_chat.send_message(
            "Nenhuma turma encontrada para montar o relatório por cidade."
        )
        context.user_data.pop("city_mode", None)
        return

    sorted_cities = sorted(cities)
    rows = _chunk_buttons(sorted_cities, size=2)
    rows.append(["Todas as cidades"])
    rows.append(["Cancelar"])
    keyboard = ReplyKeyboardMarkup(rows, resize_keyboard=True)

    await update.effective_chat.send_message(
        "Escolha uma cidade específica ou selecione *Todas as cidades*:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def _handle_city_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Second step: user picked a city (or all) for Cursos por cidade."""
    text = (update.message.text or "").strip()
    courses: list[Course] | None = context.user_data.get("city_courses")  # type: ignore[name-defined]
    if not courses:
        # Fallback: restart flow
        context.user_data.pop("city_mode", None)
        await _handle_cursos_por_cidade(update, context)
        return

    if text.lower().startswith("cancelar"):
        context.user_data.pop("city_mode", None)
        await update.effective_chat.send_message(
            "Operação cancelada.", reply_markup=MENU_KEYBOARD
        )
        return

    if text.lower().startswith("todas"):
        turmas = scrape_all_turmas(courses)
        snapshot = Snapshot(at=datetime.now(), courses=courses, turmas=turmas)
        await send_city_report(snapshot)
        await update.effective_chat.send_message(
            "Relatório de cursos por cidade (todas) enviado como arquivo HTML.",
            reply_markup=MENU_KEYBOARD,
        )
        context.user_data.pop("city_mode", None)
        return

    city = text
    # For a specific city, use the city-filtered listing page to capture all
    # courses that SENAI shows when that city filter is applied.
    city_courses = scrape_it_courses_for_city(city)
    turmas = scrape_all_turmas(city_courses)
    if not turmas:
        await update.effective_chat.send_message(
            f"Nenhuma turma encontrada para a cidade '{city}'. Tente novamente ou escolha outra opção.",
            reply_markup=MENU_KEYBOARD,
        )
        context.user_data.pop("city_mode", None)
        return

    filtered_snapshot = Snapshot(at=datetime.now(), courses=city_courses, turmas=turmas)
    await send_city_report(filtered_snapshot)
    await update.effective_chat.send_message(
        f"Relatório de cursos para {city} enviado como arquivo HTML.",
        reply_markup=MENU_KEYBOARD,
    )
    context.user_data.pop("city_mode", None)


async def _handle_trazer_cursos_disponiveis(update: Update) -> None:
    await update.effective_chat.send_message("Gerando relatório, por favor aguarde...")
    # Start from the global listing.
    base_courses = scrape_it_courses()
    courses_by_id: dict[int, Course] = {}
    _merge_courses_by_id(courses_by_id, base_courses)

    # Derive cities from the base listing, then enrich the course set using
    # the city-filtered pages, which often contain additional courses.
    cities: set[str] = set()
    for course in base_courses:
        for unit in course.units:
            city = (unit.city or "").strip()
            if city:
                cities.add(city)

    for city in sorted(cities):
        city_courses = scrape_it_courses_for_city(city)
        _merge_courses_by_id(courses_by_id, city_courses)

    all_courses = list(courses_by_id.values())
    turmas = scrape_all_turmas(all_courses)
    snapshot = Snapshot(at=datetime.now(), courses=all_courses, turmas=turmas)
    await send_weekly_report(snapshot)
    await update.effective_chat.send_message("Relatório enviado como arquivo HTML.")


async def _handle_gerenciar_alerta(update: Update) -> None:
    watched = load_watched_classes()
    if not watched:
        await update.effective_chat.send_message(
            "Nenhuma turma está sendo monitorada no momento.\n\n"
            "Por enquanto, use o comando de linha de comando para gerenciar alertas:\n"
            "`python cli.py watch` / `python cli.py unwatch`",
            parse_mode="Markdown",
        )
        return

    lines = ["🔔 Turmas com alerta ativo:", ""]
    for w in watched:
        lines.append(f"- {w.course_name} @ {w.unit_name} (spots atuais: {w.last_spots_left})")

    lines.append(
        "\nPor enquanto, use a CLI para adicionar/remover alertas:\n"
        "`python cli.py watch` / `python cli.py unwatch`"
    )

    await update.effective_chat.send_message("\n".join(lines), parse_mode="Markdown")


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text selections from the custom keyboard."""
    text_raw = (update.message.text or "").strip()
    text = text_raw.lower()

    # If we're in the middle of a city-selection flow, handle that first
    if context.user_data.get("city_mode") == "await_city_choice":
        await _handle_city_choice(update, context)
        return

    if text.startswith("cursos por cidade"):
        await _handle_cursos_por_cidade(update, context)
    elif text.startswith("trazer cursos disponiveis") or text.startswith(
        "trazer cursos disponíveis"
    ):
        await _handle_trazer_cursos_disponiveis(update)
    elif text.startswith("gerenciar alerta de cursos"):
        await _handle_gerenciar_alerta(update)
    else:
        await start(update, context)


def main() -> None:
    """Run the Telegram bot with polling."""
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured in .env")

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)
    )

    # This is a synchronous helper that manages the asyncio loop internally.
    application.run_polling()


if __name__ == "__main__":
    main()


## SENAI Courses Advisor – Current Status

### Implemented Features

- **Core scraping**
  - `scraper.py` scrapes all free IT courses and their units from the SENAI listing page, parsing:
    - Course metadata (name, slug, description, workload, badges).
    - Units with city, neighborhood, phone, address.
    - Full `openModalTurmas(...)` arguments per unit, including `estrategia`, `bolsa`, `gratuito`, `turno`.
  - `turmas_scraper.py` calls the real `/cursosturmas/` endpoint for each `(course_id, unit_id)` pair using those exact flags, and parses the returned HTML modals into `Turma` objects (start/end dates, spots, schedule, shift).
  - Turmas scraping is concurrency‑aware via a `ThreadPoolExecutor` with bounded workers and optional throttling.

- **State, diffs, and watched classes**
  - `state_manager.py` serializes/deserializes `Snapshot` objects (courses + turmas) to JSON, with São Paulo timezone handling and atomic writes, and computes:
    - `CourseDiff` (new/deleted/modified courses).
    - `TurmaDiff` (new/deleted turmas and spot changes) based on `Turma.key`.
  - `watched_classes.py` persists a list of `WatchedClass` entries, supports add/remove, and detects spot changes for watched turmas.

- **Notifications and reports**
  - `notifications.py`:
    - Async `send_telegram_message` (text) and `send_telegram_document` (files) using `python-telegram-bot`.
    - Formatters for course diffs, turma diffs, weekly report text, and spot‑change alerts.
  - `reports.py`:
    - `generate_weekly_report` + `generate_weekly_report_html`, and `send_weekly_report` which ships a full weekly HTML report file via Telegram.
    - `generate_city_report_html` + `send_city_report` to produce per‑city HTML tables:
      - `Curso | Início | Fim | Vagas | Horário` grouped by city, built from current turmas.

- **Main scheduler and CLI**
  - `main.py` orchestrates:
    - Periodic scraping, diffing, state persistence, watched‑class checks, and weekly report sending via `schedule`.
  - `cli.py` exposes:
    - `report` (generate & send weekly report now).
    - `check` (manual diff run).
    - `watch` / `unwatch` / `list_watched` for managing watched turmas interactively.

- **Telegram bot UI**
  - `bot.py` implements an interactive bot with:
    - `/start` → keyboard: `Cursos por cidade`, `Trazer cursos disponíveis`, `Gerenciar alerta de cursos`.
    - **Trazer cursos disponíveis**:
      - Scrapes all courses and turmas, builds a snapshot, and sends the weekly HTML report to the configured chat.
    - **Cursos por cidade**:
      - First step: scrapes only courses to build the list of cities quickly.
      - Prompts the user with buttons for each city, plus “Todas as cidades” and “Cancelar”.
      - On city selection:
        - Scrapes turmas only for that city (or all cities), builds a filtered snapshot, and sends a city‑based HTML report.
    - **Gerenciar alerta de cursos**:
      - Lists currently watched turmas and points to the CLI commands for adding/removing watches.

### Where We Stopped (Current Limitations)

- **Incomplete coverage of all “visually available” courses in some cities**
  - Example: For **Osasco**, the site visually shows multiple free courses with turmas (e.g. LPIC 1, Desenvolvimento de Jogos em Unity), but current reports sometimes only list a subset (e.g. only the Linux course).
  - Diagnostics show:
    - For many `(course_id, unit_id)` combinations, `/cursosturmas/` returns **no HTML at all**, and we log lines like:
      - `No turmas HTML returned for course_id=... unit_id=... slug=...`
    - For at least some courses (LPIC, Unity), manual DevTools inspection confirms that:
      - The POST payload we send (cursoId/escolaId/estrategia/bolsa/gratuito/turno) matches the browser’s request.
      - The response HTML uses the same `card-body` structure that our parser supports.
  - Despite this, the aggregated snapshot used for reports currently contains fewer turmas than expected for some cities, indicating that:
    - Either SENAI’s backend itself only returns turmas that match narrower eligibility rules than we see in the UI, or
    - There are still edge cases where specific course/unit responses are not being included in the final list (for example due to subtle differences in markup or unexpected empty responses at scrape time).

- **Why we paused here**
  - Further closing the gap between “what the UI seems to promise” and “what `/cursosturmas` returns at scrape time” would require:
    - Systematically capturing and comparing live network traffic for a wide range of courses/units against what the scraper receives (to distinguish backend filtering from scraper bugs).
    - Potentially relaxing or changing the filters (e.g. querying non‑gratuito turmas or other modalities), which goes beyond the original “free IT courses” scope and may conflict with SENAI’s server‑side constraints.
  - The current implementation is stable, performant, and consistent with the actual `/cursosturmas` responses it receives, but does **not guarantee** that every course visible in the marketing grid will appear in the free‑turmas reports for a given city.

### Suggested Next Steps

- Add a debug mode that, for a chosen city, logs **every** `(course_id, unit_id)` and:
  - The exact POST payload we send.
  - Whether `/cursosturmas` returned HTML or not.
  - How many turmas were parsed.
- Decide, product‑wise, whether reports should:
  - Reflect **only turmas that the backend exposes as free/bolsa** (current behavior), or
  - Also list courses that merely have a card/unit in the grid, even if `/cursosturmas` currently returns no free turmas for them.


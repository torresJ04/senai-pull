# SENAI Courses Advisor - Project Specification

## Project Overview

A Python application that monitors SENAI SP's free IT courses, tracks changes (new courses, deleted courses, spot availability), and sends notifications via Telegram. The system provides weekly reports organized by SENAI unit (Osasco, São Caetano, Santo Amaro, etc.) and real-time alerts for watched classes when spots become available.

## Target URL

Base URL: `https://www.sp.senai.br/cursos/cursos-livres/tecnologia-da-informacao-e-informatica?gratuito=1`

## Project Status

### Implemented Components

1. **Data Models** (`models.py`)
   - `Unit`: SENAI school locations with id, city, neighborhood, phone, address
   - `Course`: Course details with id, name, slug, modality, level, area, description, workload, units, URL
   - `Turma`: Class schedule with id, course_id, unit_id, dates, spots (total/left), schedule type, shift
   - `Snapshot`: Point-in-time snapshot of courses and turmas

2. **Web Scraper** (`scraper.py`)
   - Fetches IT courses listing page
   - Parses HTML to extract Course and Unit information
   - Extracts course_id, unit_id, slug from `openModalTurmas()` JavaScript calls

3. **Configuration** (`config.py`)
   - Loads environment variables from `.env`
   - Defines data directory structure
   - Telegram bot configuration
   - Scheduling parameters

4. **Dependencies** (`requirements.txt`)
   - requests, beautifulsoup4 for web scraping
   - python-telegram-bot for notifications
   - schedule for task scheduling
   - playwright (optional) for dynamic content

### Missing Components (TO BE IMPLEMENTED)

## 1. Turmas (Class Schedules) Scraping

The existing scraper only extracts courses and units. The turmas data needs to be scraped from the modal that appears when clicking "VER TURMAS".

### Implementation Requirements:

**Option A: JavaScript Modal Scraping (Preferred if API doesn't exist)**
- Use Playwright to automate browser interaction
- Click "VER TURMAS" button for each course/unit combination
- Wait for modal `#modalTurmas` to load
- Extract turma data from modal content
- Parse: start_date, end_date, spots_total, spots_left, schedule_type, shift, turma_id

**Option B: API Endpoint Discovery (Preferred if exists)**
- Inspect network requests when "VER TURMAS" is clicked
- Identify API endpoint (likely something like `/api/turmas/{course_id}/{unit_id}`)
- Make direct HTTP requests to fetch turma data as JSON
- Parse API response into Turma objects

**Expected Data Structure from HTML Modal:**
```html
<div id="modalTurmas" class="modal">
  <div class="modal-body">
    <div class="turma-item">
      <span class="data-inicio">Início: 15/03/2026</span>
      <span class="data-fim">Término: 20/04/2026</span>
      <span class="vagas">Vagas disponíveis: 12 de 30</span>
      <span class="horario">Segunda a Sexta - Noite (19h às 22h)</span>
    </div>
  </div>
</div>
```

**File to Create:** `turmas_scraper.py`
```python
def fetch_turmas(course_id: int, unit_id: int, slug: str) -> list[Turma]:
    """Fetch turmas for a specific course and unit."""
    pass

def scrape_all_turmas(courses: list[Course]) -> list[Turma]:
    """Scrape turmas for all courses and their units."""
    pass
```

## 2. State Management and Diffing

Track changes between snapshots to identify new courses, deleted courses, and spot changes.

**File to Create:** `state_manager.py`

```python
from dataclasses import dataclass
from models import Course, Turma, Snapshot

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

def load_state() -> Snapshot | None:
    """Load the last saved snapshot from STATE_FILE."""
    # Read from config.STATE_FILE (JSON)
    pass

def save_state(snapshot: Snapshot) -> None:
    """Save current snapshot to STATE_FILE."""
    # Write to config.STATE_FILE (JSON)
    pass

def diff_courses(old: list[Course], new: list[Course]) -> CourseDiff:
    """Compare two course lists and return differences."""
    # Compare by course_id
    pass

def diff_turmas(old: list[Turma], new: list[Turma]) -> TurmaDiff:
    """Compare two turma lists and return differences."""
    # Compare by turma.key (course_id_unit_id_turma_id)
    pass
```

## 3. Watched Classes Management

Allow monitoring specific turmas for spot changes with high-frequency checks.

**File to Create:** `watched_classes.py`

```python
from typing import Optional

@dataclass
class WatchedClass:
    """A class being actively monitored."""
    turma_key: str  # course_id_unit_id_turma_id
    course_name: str
    unit_name: str
    added_at: datetime
    last_spots_left: Optional[int] = None

def load_watched_classes() -> list[WatchedClass]:
    """Load watched classes from WATCHED_CLASSES_FILE."""
    pass

def save_watched_classes(watched: list[WatchedClass]) -> None:
    """Save watched classes to WATCHED_CLASSES_FILE."""
    pass

def add_watched_class(turma: Turma) -> None:
    """Add a turma to the watch list."""
    pass

def remove_watched_class(turma_key: str) -> None:
    """Remove a turma from the watch list."""
    pass

def check_watched_classes(current_turmas: list[Turma]) -> list[tuple[WatchedClass, Turma]]:
    """Check watched classes for spot changes. Returns list of (watched, current_turma) with changes."""
    pass
```

## 4. Telegram Notifications

Send formatted messages via Telegram bot.

**File to Create:** `notifications.py`

```python
from telegram import Bot
from telegram.error import TelegramError

async def send_telegram_message(message: str) -> bool:
    """Send a message via Telegram bot."""
    # Use config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID
    pass

def format_course_diff_message(diff: CourseDiff) -> str:
    """Format course differences as a readable message."""
    # Example:
    # 🆕 New Courses (3):
    # - Python Fundamentals (Presencial) - 40 hours
    #   Units: Osasco, Santo Amaro
    #
    # ❌ Removed Courses (1):
    # - Old Course Name
    pass

def format_turma_diff_message(diff: TurmaDiff) -> str:
    """Format turma differences as a readable message."""
    # Example:
    # 📅 New Classes (5):
    # - Python Fundamentals @ Osasco
    #   Start: 15/03/2026 | End: 20/05/2026
    #   Spots: 25/30 | Schedule: Segunda a Sexta - Noite
    pass

def format_weekly_report(snapshot: Snapshot) -> str:
    """Format a comprehensive weekly report organized by unit."""
    # Example:
    # 📊 SENAI Courses Weekly Report - 01/03/2026
    #
    # 🏫 Osasco - Centro
    # ├─ Python Fundamentals (40h) - 3 turmas
    # │  ├─ 15/03 - 20/05 | 25/30 spots | Seg-Sex Noite
    # │  └─ 22/03 - 27/05 | 18/30 spots | Sábados Manhã
    # └─ Data Science Intro (60h) - 2 turmas
    #
    # 🏫 Santo Amaro
    # └─ ...
    pass

def format_spot_change_alert(watched: WatchedClass, turma: Turma) -> str:
    """Format spot change alert for watched class."""
    # Example:
    # 🔔 Spot Change Alert!
    #
    # Course: Python Fundamentals
    # Unit: Osasco - Centro
    # Previous: 5 spots left
    # Current: 8 spots left (+3) ✅
    pass
```

## 5. Weekly Report Generation

Generate and send comprehensive reports on a scheduled basis.

**File to Create:** `reports.py`

```python
from datetime import datetime

def generate_weekly_report(snapshot: Snapshot) -> str:
    """Generate comprehensive weekly report."""
    # Group courses by unit
    # Show all active turmas for each unit
    # Include course details (name, hours, modality)
    # Include turma details (dates, spots, schedule)
    pass

async def send_weekly_report(snapshot: Snapshot) -> None:
    """Generate and send weekly report via Telegram."""
    message = format_weekly_report(snapshot)
    await send_telegram_message(message)
```

## 6. Main Application with Scheduling

Orchestrate all components with scheduled tasks.

**File to Create:** `main.py`

```python
import asyncio
import schedule
import time
from datetime import datetime
from scraper import scrape_it_courses
from turmas_scraper import scrape_all_turmas
from state_manager import load_state, save_state, diff_courses, diff_turmas
from watched_classes import load_watched_classes, check_watched_classes
from notifications import (
    send_telegram_message,
    format_course_diff_message,
    format_turma_diff_message,
    format_spot_change_alert,
)
from reports import send_weekly_report
from models import Snapshot
import config

async def check_courses_update() -> None:
    """Check for course and turma updates."""
    print(f"[{datetime.now()}] Checking for course updates...")

    # Scrape current data
    courses = scrape_it_courses()
    turmas = scrape_all_turmas(courses)
    current_snapshot = Snapshot(at=datetime.now(), courses=courses, turmas=turmas)

    # Load previous state
    previous_snapshot = load_state()

    if previous_snapshot:
        # Diff courses
        course_diff = diff_courses(previous_snapshot.courses, current_snapshot.courses)
        if course_diff.new_courses or course_diff.deleted_courses:
            message = format_course_diff_message(course_diff)
            await send_telegram_message(message)

        # Diff turmas
        turma_diff = diff_turmas(previous_snapshot.turmas, current_snapshot.turmas)
        if turma_diff.new_turmas or turma_diff.deleted_turmas or turma_diff.spot_changes:
            message = format_turma_diff_message(turma_diff)
            await send_telegram_message(message)

    # Save current state
    save_state(current_snapshot)
    print(f"[{datetime.now()}] Update check complete. Courses: {len(courses)}, Turmas: {len(turmas)}")

async def check_watched_classes_update() -> None:
    """Check watched classes for spot changes."""
    print(f"[{datetime.now()}] Checking watched classes...")

    # Load watched classes
    watched = load_watched_classes()
    if not watched:
        return

    # Get current turmas
    courses = scrape_it_courses()
    turmas = scrape_all_turmas(courses)

    # Check for changes
    changes = check_watched_classes(turmas)

    for watched_class, current_turma in changes:
        message = format_spot_change_alert(watched_class, current_turma)
        await send_telegram_message(message)

    print(f"[{datetime.now()}] Watched classes check complete. Changes: {len(changes)}")

async def send_scheduled_weekly_report() -> None:
    """Send the weekly report."""
    print(f"[{datetime.now()}] Generating weekly report...")
    snapshot = load_state()
    if snapshot:
        await send_weekly_report(snapshot)
    print(f"[{datetime.now()}] Weekly report sent.")

def schedule_tasks() -> None:
    """Set up scheduled tasks."""
    # Weekly report (e.g., Monday 9 AM)
    weekday_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][
        config.WEEKLY_REPORT_WEEKDAY
    ]
    schedule.every().__getattribute__(weekday_name).at(
        f"{config.WEEKLY_REPORT_HOUR:02d}:00"
    ).do(lambda: asyncio.run(send_scheduled_weekly_report()))

    # Daily course updates check (e.g., every day at 8 AM)
    schedule.every().day.at("08:00").do(lambda: asyncio.run(check_courses_update()))

    # Watched classes check (every N minutes)
    schedule.every(config.WATCHED_CLASS_CHECK_INTERVAL).minutes.do(
        lambda: asyncio.run(check_watched_classes_update())
    )

def main() -> None:
    """Main application entry point."""
    print("SENAI Courses Advisor starting...")
    print(f"Data directory: {config.DATA_DIR}")

    # Verify Telegram configuration
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("WARNING: Telegram not configured. Notifications will be disabled.")
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file.")

    # Schedule tasks
    schedule_tasks()
    print("Tasks scheduled. Running initial check...")

    # Run initial check
    asyncio.run(check_courses_update())

    # Main loop
    print("Entering main loop. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")

if __name__ == "__main__":
    main()
```

## 7. CLI Interface (Optional Enhancement)

**File to Create:** `cli.py`

```python
import click
import asyncio
from watched_classes import add_watched_class, remove_watched_class, load_watched_classes
from scraper import scrape_it_courses
from turmas_scraper import scrape_all_turmas
from reports import send_weekly_report
from models import Snapshot
from datetime import datetime

@click.group()
def cli():
    """SENAI Courses Advisor CLI."""
    pass

@cli.command()
def watch():
    """Interactively add a class to watch list."""
    # Show available courses and turmas
    # Prompt user to select one
    # Add to watched classes
    pass

@cli.command()
def unwatch():
    """Remove a class from watch list."""
    watched = load_watched_classes()
    # Show list and let user select one to remove
    pass

@cli.command()
def list_watched():
    """List all watched classes."""
    watched = load_watched_classes()
    for w in watched:
        click.echo(f"- {w.course_name} @ {w.unit_name} (added {w.added_at})")

@cli.command()
def report():
    """Generate and send weekly report now."""
    courses = scrape_it_courses()
    turmas = scrape_all_turmas(courses)
    snapshot = Snapshot(at=datetime.now(), courses=courses, turmas=turmas)
    asyncio.run(send_weekly_report(snapshot))
    click.echo("Report sent!")

@cli.command()
def check():
    """Run a manual check for updates."""
    from main import check_courses_update
    asyncio.run(check_courses_update())
    click.echo("Check complete!")

if __name__ == "__main__":
    cli()
```

## HTML Structure Reference

### Course Card Structure
```html
<div id="card-cursos">
  <div class="card-columns">
    <div class="card">
      <div class="card-body">
        <!-- Badges -->
        <span class="badge badge-pill badge-secondary">Presencial</span>
        <span class="badge badge-pill badge-secondary">Cursos Livres</span>
        <span class="badge badge-pill badge-secondary">Tecnologia da Informação e Informática</span>

        <!-- Course Info -->
        <h5 class="card-title">Course Name</h5>
        <p class="card-text">Description...</p>
        <p class="horario">Carga horária: <strong>32 horas</strong></p>

        <!-- Actions -->
        <a href="javascript:openModalInfo('Name', 110384);">Saiba Mais</a>
        <a data-toggle="collapse" data-target="#collapse-110384">Ver Unidades</a>
      </div>

      <!-- Units List -->
      <ul class="list-group verunidades collapse" id="collapse-110384">
        <li class="list-group-item">
          <strong>Barueri</strong> - Centro<br>
          (11) 4199-1930<br>
          ALAMEDA WAGHI SALLES NEMER, 124
          <a class="btn btn-turmas" href="javascript:openModalTurmas('Name', 'slug', 110384, 136, 'Presencial', 0, 1, 0);">
            VER TURMAS
          </a>
        </li>
      </ul>
    </div>
  </div>
</div>
```

### Key JavaScript Functions
- `openModalTurmas(name, slug, courseId, unitId, modality, p1, p2, p3)`
- `openModalInfo(name, courseId)`

## Data Flow

```
1. Scraper → Fetch HTML → Parse Courses/Units
2. Turmas Scraper → For each Course/Unit → Fetch Turmas
3. Create Snapshot (courses + turmas)
4. Load Previous Snapshot
5. Diff Snapshots → Detect Changes
6. Format Messages
7. Send Telegram Notifications
8. Save Current Snapshot
```

## Environment Variables (.env)

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_chat_id

# Scheduling
WEEKLY_REPORT_WEEKDAY=0  # 0=Monday, 6=Sunday
WEEKLY_REPORT_HOUR=9     # 24-hour format
WATCHED_CLASS_CHECK_INTERVAL=60  # minutes

# Data Storage
DATA_DIR=data  # optional, defaults to ./data
```

## Setup Instructions for AI

1. **Create missing files** listed in sections 1-7 above
2. **Implement turmas scraping** (prioritize API discovery over Playwright)
3. **Implement state management** with JSON serialization
4. **Implement Telegram integration** with async/await
5. **Implement scheduling** using the schedule library
6. **Add error handling** throughout (network errors, parsing errors, rate limiting)
7. **Add logging** using Python's logging module
8. **Test each component** independently before integration

## Testing Strategy

1. **Unit Tests:**
   - `test_scraper.py`: Test HTML parsing with sample HTML
   - `test_state_manager.py`: Test diffing logic
   - `test_notifications.py`: Test message formatting

2. **Integration Tests:**
   - Test full scraping pipeline
   - Test state save/load
   - Test Telegram sending (with test bot/chat)

3. **Manual Testing:**
   - Run initial scrape and verify data
   - Add a watched class
   - Wait for scheduled checks
   - Verify Telegram messages

## Important Implementation Notes

1. **Rate Limiting:** Add delays between requests to avoid being blocked
2. **Error Recovery:** If scraping fails, don't delete the previous state
3. **Telegram Limits:** Messages have a 4096 character limit, split long reports
4. **Data Persistence:** Use atomic writes (write to temp file, then rename)
5. **Logging:** Log all scraping attempts, changes detected, and notifications sent
6. **Graceful Shutdown:** Handle SIGINT/SIGTERM to finish current tasks
7. **Timezone:** All dates should be in São Paulo timezone (America/Sao_Paulo)

## Future Enhancements

1. Web dashboard for viewing courses/turmas
2. Email notifications as alternative to Telegram
3. Filter courses by specific criteria (workload, unit, dates)
4. Historical data visualization
5. Export reports to PDF/CSV
6. Multi-language support
7. Support for other course categories beyond IT

## Dependencies to Add

```txt
# Add to requirements.txt:
click>=8.0.0  # for CLI
pytest>=7.0.0  # for testing
python-dateutil>=2.8.0  # for date parsing
pytz>=2021.3  # for timezone handling
```

## Success Criteria

The project is complete when:
- ✅ Courses are scraped successfully from the listing page
- ✅ Turmas are scraped for each course/unit combination
- ✅ State is persisted between runs
- ✅ Changes are detected accurately
- ✅ Telegram notifications are sent for all change types
- ✅ Weekly reports are generated and organized by unit
- ✅ Watched classes are monitored with configurable intervals
- ✅ Application runs continuously with scheduling
- ✅ Error handling prevents crashes
- ✅ Logs provide visibility into operations

"""Configuration for SENAI Courses Advisor."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# SENAI IT free courses listing
BASE_URL = "https://www.sp.senai.br"
IT_COURSES_URL = (
    f"{BASE_URL}/cursos/cursos-livres/tecnologia-da-informacao-e-informatica?gratuito=1"
)

# Data directory for state and reports
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA_DIR / "courses_state.json"
WATCHED_CLASSES_FILE = DATA_DIR / "watched_classes.json"

# Telegram (optional)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Scheduling
WEEKLY_REPORT_WEEKDAY = int(os.getenv("WEEKLY_REPORT_WEEKDAY", "0"))  # Monday
WEEKLY_REPORT_HOUR = int(os.getenv("WEEKLY_REPORT_HOUR", "9"))
WATCHED_CLASS_CHECK_INTERVAL = int(os.getenv("WATCHED_CLASS_CHECK_INTERVAL", "60"))

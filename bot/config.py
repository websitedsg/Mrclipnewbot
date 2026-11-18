import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))

SITE_URL = os.getenv("MRCLIP_URL", "https://mrclip.gr").rstrip("/")
SUBMISSIONS_URL = os.getenv("SUBMISSIONS_URL", "").strip()

MIN_VIEWS = int(os.getenv("MIN_VIEWS", "1000"))
REFRESH_EVERY_HOURS = float(os.getenv("REFRESH_EVERY_HOURS", "5"))
REFRESH_TIMEOUT_MIN = float(os.getenv("REFRESH_TIMEOUT_MIN", "180"))

HEADLESS = _bool("HEADLESS", "true")
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "").strip() or None

DATA_DIR = os.getenv("DATA_DIR", "data")
PROFILE_DIR = os.path.join(DATA_DIR, "browser-profile")  # keeps you logged in
NOTIFIED_FILE = os.path.join(DATA_DIR, "notified.json")
os.makedirs(DATA_DIR, exist_ok=True)

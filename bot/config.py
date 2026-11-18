import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_ID = int(os.environ["TELEGRAM_ADMIN_ID"])

SITE_URL = os.getenv("MRCLIP_URL", "https://mrclip.gr").rstrip("/")
SITE_USER = os.getenv("MRCLIP_USERNAME", "")
SITE_PASS = os.getenv("MRCLIP_PASSWORD", "")

CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "10"))
REFRESH_INTERVAL_MIN = int(os.getenv("REFRESH_INTERVAL_MIN", "360"))
CLICK_DELAY_SEC = float(os.getenv("CLICK_DELAY_SEC", "3"))
AUTO_APPROVE = _bool("AUTO_APPROVE")
HEADLESS = _bool("HEADLESS", "true")

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

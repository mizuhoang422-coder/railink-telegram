# language: Python, file: config.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


def _load_dotenv():
    p = BASE_DIR / ".env"
    if not p.exists():
        return
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

# --- Telegram API ---
API_ID   = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "").strip()

# --- Control bot ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0") or "0")

# --- Proxy cho bot control (optional) ---
_proxy = os.getenv("BOT_PROXY", "").strip()
BOT_PROXY = _proxy or None

# --- Session strings cho cloud (optional) ---
_raw_sessions = os.getenv("SESSIONS", "").strip()
SESSIONS_FROM_ENV = []
if _raw_sessions:
    for line in _raw_sessions.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, s = line.split(":", 1)
        name, s = name.strip(), s.strip()
        if name and s:
            SESSIONS_FROM_ENV.append((name, s))

CLOUD_MODE = bool(SESSIONS_FROM_ENV)

# --- Paths ---
SESSIONS_DIR  = BASE_DIR / "sessions"
IMAGES_DIR    = BASE_DIR / "images"
LOGS_DIR      = BASE_DIR / "logs"
PROXIES_FILE  = BASE_DIR / "proxies.txt"
TARGETS_FILE  = BASE_DIR / "targets.txt"
MESSAGES_FILE = BASE_DIR / "messages.txt"
BIOS_FILE     = BASE_DIR / "bios.txt"
STATE_FILE    = BASE_DIR / "state.json"

# --- Anti-ban ---
MIN_DELAY        = int(os.getenv("MIN_DELAY", "1800") or "1800")
MAX_DELAY        = int(os.getenv("MAX_DELAY", "1800") or "1800")
TARGET_COOLDOWN  = int(os.getenv("TARGET_COOLDOWN", "1800") or "1800")
DAILY_MSG_CAP    = int(os.getenv("DAILY_MSG_CAP", "25") or "25")
BIO_ROTATE_EVERY = int(os.getenv("BIO_ROTATE_EVERY", "0") or "0")

CHECK_TOP_SELF = os.getenv("CHECK_TOP_SELF", "1").strip() not in ("0", "false", "False", "")

# --- HTTP health server ---
PORT = int(os.getenv("PORT", "0") or "0")

for d in (SESSIONS_DIR, IMAGES_DIR, LOGS_DIR):
    d.mkdir(exist_ok=True)

# language: Python, file: core/state.py
import json
from datetime import date
from config import STATE_FILE


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict):
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def daily_count(session_name: str) -> int:
    s = _load().get(session_name, {})
    if s.get("date") != str(date.today()):
        return 0
    return s.get("count", 0)


def bump_count(session_name: str, n: int = 1) -> int:
    data = _load()
    today = str(date.today())
    entry = data.get(session_name, {})
    if entry.get("date") != today:
        entry = {"date": today, "count": 0}
    entry["count"] += n
    data[session_name] = entry
    _save(data)
    return entry["count"]

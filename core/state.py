# language: Python, file: core/state.py
import json
import time
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


# ---------- target cooldown ----------

def target_last_sent(target: str) -> float:
    """Unix timestamp lần cuối target này bị gửi. 0 nếu chưa bao giờ."""
    return float(_load().get("_targets", {}).get(target, 0))


def mark_target_sent(target: str):
    """Đánh dấu target vừa gửi. Dọn entry cũ hơn 24h để state không phình."""
    data = _load()
    targets = data.setdefault("_targets", {})
    targets[target] = time.time()
    cutoff = time.time() - 86400
    data["_targets"] = {k: v for k, v in targets.items() if v > cutoff}
    _save(data)


def target_on_cooldown(target: str, cooldown_sec: int) -> bool:
    if cooldown_sec <= 0:
        return False
    return (time.time() - target_last_sent(target)) < cooldown_sec

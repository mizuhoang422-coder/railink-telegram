# language: Python, file: export_sessions.py
"""Xuất session file thành StringSession cho cloud deploy."""
import _force_ipv4  # noqa: F401
import asyncio
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH, SESSIONS_DIR


async def export_one(path: Path):
    c = TelegramClient(str(path), API_ID, API_HASH)
    await c.connect()
    try:
        if not await c.is_user_authorized():
            print(f"# {path.stem}: NOT AUTHORIZED")
            return None
        return StringSession.save(c.session)
    finally:
        await c.disconnect()


async def main():
    if not API_ID or not API_HASH:
        print("ERROR: API_ID / API_HASH chua set")
        return

    sessions = sorted(SESSIONS_DIR.glob("*.session"))
    if not sessions:
        print("Khong co .session nao trong sessions/")
        return

    lines = []
    for p in sessions:
        print(f"# {p.stem}...", flush=True)
        s = await export_one(p)
        if s:
            lines.append(f"{p.stem}:{s}")

    print()
    print("=" * 60)
    print("SESSIONS env var cho Render — copy toan bo phan duoi:")
    print("=" * 60)
    print()
    for line in lines:
        print(line)
    print()
    print("=" * 60)
    print(f"Tong: {len(lines)} session")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

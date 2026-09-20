# language: Python, file: login.py
import _force_ipv4  # noqa: F401
import asyncio
import getpass

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config import API_ID, API_HASH, SESSIONS_DIR


def _read_first_proxy():
    from core.manager import _read_lines, _parse_proxy
    from config import PROXIES_FILE
    lines = _read_lines(PROXIES_FILE)
    return _parse_proxy(lines[0]) if lines else None


async def interactive_login():
    if not API_ID or not API_HASH:
        print("[!] set API_ID and API_HASH in config.py first")
        return

    phone = input("Phone (+84...): ").strip()
    if not phone:
        return

    clean = phone.replace("+", "").replace(" ", "")
    session_path = SESSIONS_DIR / clean

    proxy = _read_first_proxy()
    client = TelegramClient(
        str(session_path), API_ID, API_HASH, proxy=proxy,
        device_model="Desktop", system_version="Windows 10", app_version="4.16.8",
    )

    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"[OK] already logged in as @{me.username or me.id}")
            return

        sent = await client.send_code_request(phone)
        code = input("OTP code: ").strip()
        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except SessionPasswordNeededError:
            pw = getpass.getpass("2FA password: ")
            await client.sign_in(password=pw)

        me = await client.get_me()
        print(f"[OK] logged in as @{me.username or me.id}")
        print(f"[OK] session saved: {session_path}.session")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(interactive_login())

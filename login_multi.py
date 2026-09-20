# language: Python, file: login_multi.py
import _force_ipv4  # noqa: F401
import asyncio
import getpass

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config import API_ID, API_HASH, SESSIONS_DIR


async def login_one(phone: str) -> bool:
    clean = phone.replace("+", "").replace(" ", "")
    session_path = SESSIONS_DIR / clean

    client = TelegramClient(
        str(session_path), API_ID, API_HASH,
        device_model="Desktop", system_version="Windows 10", app_version="4.16.8",
    )

    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"  [SKIP] {phone} — đã login as @{me.username or me.id} (id={me.id})")
            return True

        sent = await client.send_code_request(phone)
        code = input(f"  📩 OTP cho {phone}: ").strip()
        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except SessionPasswordNeededError:
            pw = getpass.getpass(f"  🔐 2FA cho {phone}: ")
            await client.sign_in(password=pw)

        me = await client.get_me()
        print(f"  ✅ {phone} → @{me.username or me.id}  (id={me.id})")
        return True
    except Exception as e:
        print(f"  ❌ {phone}: {type(e).__name__}: {e}")
        return False
    finally:
        await client.disconnect()


async def main():
    if not API_ID or not API_HASH:
        print("ERROR: API_ID / API_HASH chưa set trong config.py")
        return

    print()
    print("=" * 60)
    print("  LOGIN NHIỀU ACC")
    print("  Gõ số điện thoại (+84...) để login từng acc.")
    print("  Gõ 'xong' hoặc Enter trống để dừng và chạy bot.")
    print("=" * 60)
    print()

    count = 0
    while True:
        try:
            phone = input(f"[{count+1}] Phone (hoặc 'xong'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not phone or phone.lower() in ("xong", "done", "q", "exit"):
            break
        if not phone.startswith("+") or len(phone) < 8:
            print("  ⚠️  Sai định dạng. Nhập lại dạng +84...")
            continue
        ok = await login_one(phone)
        if ok:
            count += 1
        print()

    print("=" * 60)
    sessions = sorted(SESSIONS_DIR.glob("*.session"))
    print(f"  Đã login {count} acc trong phiên này")
    print(f"  Tổng session: {len(sessions)}")
    for s in sessions:
        print(f"    • {s.stem}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())

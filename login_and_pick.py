# language: Python, file: login_and_pick.py
import _force_ipv4  # noqa: F401
import asyncio
import getpass
import re

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config import API_ID, API_HASH, SESSIONS_DIR, BASE_DIR


async def login_one(phone):
    clean = phone.replace("+", "").replace(" ", "")
    path = SESSIONS_DIR / clean
    c = TelegramClient(str(path), API_ID, API_HASH,
        device_model="Desktop", system_version="Windows 10", app_version="4.16.8")
    await c.connect()
    try:
        if await c.is_user_authorized():
            me = await c.get_me()
            print(f"  [skip] {phone} - da login @{me.username or me.id} (id={me.id})")
            return me
        sent = await c.send_code_request(phone)
        code = input(f"  OTP cho {phone}: ").strip()
        try:
            await c.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except SessionPasswordNeededError:
            pw = getpass.getpass(f"  2FA cho {phone}: ")
            await c.sign_in(password=pw)
        me = await c.get_me()
        print(f"  [ok] {phone} -> @{me.username or me.id} (id={me.id})")
        return me
    except Exception as e:
        print(f"  [err] {phone}: {type(e).__name__}: {e}")
        return None
    finally:
        await c.disconnect()


def update_admin_id(new_id):
    cfg = BASE_DIR / "config.py"
    src = cfg.read_text(encoding="utf-8")
    src = re.sub(r"(?m)^ADMIN_ID\s*=\s*\d+.*$",
                 f"ADMIN_ID = {new_id}        # numeric telegram user id",
                 src)
    cfg.write_text(src, encoding="utf-8")


async def main():
    if not API_ID or not API_HASH:
        print("ERROR: API_ID / API_HASH chua set")
        return

    print()
    print("=" * 60)
    print("  BUOC 1 - LOGIN CAC ACC")
    print("  Go so dien thoai (+84...), roi Enter.")
    print("  Go 'xong' hoac Enter trong de dung.")
    print("=" * 60)
    print()

    logged = []
    while True:
        try:
            phone = input(f"[{len(logged)+1}] Phone: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not phone or phone.lower() in ("xong", "done", "q", "exit"):
            break
        if not phone.startswith("+") or len(phone) < 8:
            print("  Sai dinh dang. Nhap lai +84...")
            continue
        me = await login_one(phone)
        if me:
            logged.append((phone, me))
        print()

    if not logged:
        print("Khong co acc nao. Dung.")
        return

    print("=" * 60)
    print("  BUOC 2 - CHON ACC CHU (bam bot dieu khien)")
    print("=" * 60)
    print()
    for i, (phone, me) in enumerate(logged, 1):
        print(f"  [{i}] {phone}  @{me.username or '(none)'}  id={me.id}  {me.first_name}")
    print()
    try:
        pick = input("  Nhap so thu tu acc chu (Enter = acc 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        pick = ""

    idx = 0
    if pick:
        try:
            idx = int(pick) - 1
            if idx < 0 or idx >= len(logged):
                idx = 0
        except ValueError:
            idx = 0

    admin_phone, admin_me = logged[idx]
    update_admin_id(admin_me.id)

    print()
    print("=" * 60)
    print(f"  ACC CHU: {admin_phone}  @{admin_me.username or admin_me.id}  id={admin_me.id}")
    print(f"  Da ghi ADMIN_ID = {admin_me.id} vao config.py")
    workers = [p for i, (p, _) in enumerate(logged) if i != idx]
    if workers:
        print(f"  Worker ({len(workers)}): {', '.join(workers)}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())

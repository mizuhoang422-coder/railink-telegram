import _force_ipv4  # noqa: F401
import asyncio
from telethon import TelegramClient
from config import API_ID, API_HASH, SESSIONS_DIR, ADMIN_ID

PHONES = ["+84837258569", "+84911404475", "+84983733025"]

async def check(phone):
    clean = phone.replace("+", "").replace(" ", "")
    path = SESSIONS_DIR / clean
    if not path.with_suffix(".session").exists():
        return phone, None, "CHƯA LOGIN"
    c = TelegramClient(str(path), API_ID, API_HASH,
        device_model="Desktop", system_version="Windows 10", app_version="4.16.8")
    await c.connect()
    try:
        if not await c.is_user_authorized():
            return phone, None, "SESSION REVOKED"
        me = await c.get_me()
        return phone, me, None
    finally:
        await c.disconnect()

async def main():
    print()
    print("=" * 68)
    print(f"  ADMIN_ID trong config.py = {ADMIN_ID}")
    print("=" * 68)
    print()

    admin_found = None
    workers = []

    for phone in PHONES:
        p, me, err = await check(phone)
        if err:
            print(f"  ⚠️  {p}")
            print(f"      → {err}")
            print()
            continue

        role = "CHỦ (ADMIN)" if me.id == ADMIN_ID else "WORKER (dùng để gửi)"
        icon = "🔑" if me.id == ADMIN_ID else "👤"
        print(f"  {icon}  {p}")
        print(f"      username: @{me.username or '(không có)'}")
        print(f"      id:       {me.id}")
        print(f"      tên:      {me.first_name} {me.last_name or ''}".rstrip())
        print(f"      VAI TRÒ:  {role}")
        print()

        if me.id == ADMIN_ID:
            admin_found = p
        else:
            workers.append(p)

    print("=" * 68)
    if admin_found:
        print(f"  ✅ Acc CHỦ (bấm bot):  {admin_found}")
    else:
        print("  ❌ KHÔNG CÓ ACC NÀO LÀ CHỦ")
        print("     → Sửa ADMIN_ID trong config.py thành id của acc mày muốn làm chủ")
        print(f"     → Hiện tại ADMIN_ID = {ADMIN_ID}")

    if workers:
        print(f"  👥 Acc WORKER ({len(workers)}):  " + ", ".join(workers))
    else:
        print("  ⚠️  Chưa có acc nào làm worker (acc để gửi tin)")
    print("=" * 68)
    print()

asyncio.run(main())

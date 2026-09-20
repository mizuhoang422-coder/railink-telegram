import _force_ipv4  # noqa
import asyncio
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from config import API_ID, API_HASH, SESSIONS_DIR

async def check(acc):
    p = SESSIONS_DIR / acc
    c = TelegramClient(str(p), API_ID, API_HASH,
        device_model="Desktop", system_version="Windows 10", app_version="4.16.8")
    await c.connect()
    try:
        me = await c.get_me()
        full = await c(GetFullUserRequest(me.id))
        about = full.full_user.about or "(TRỐNG)"
        print(f"acc:    {acc}")
        print(f"user:   @{me.username or me.id}")
        print(f"bio:    {about}")
        print(f"len:    {len(about) if about != '(TRỐNG)' else 0}")
    finally:
        await c.disconnect()

if __name__ == "__main__":
    import sys
    acc = sys.argv[1] if len(sys.argv) > 1 else "84911404475"
    asyncio.run(check(acc))

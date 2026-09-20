# language: Python, file: core/account.py
import asyncio
import random
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.errors import FloodWaitError, PeerFloodError

from config import (
    API_ID, API_HASH, IMAGES_DIR, MIN_DELAY, MAX_DELAY,
    DAILY_MSG_CAP, BIO_ROTATE_EVERY, TARGET_COOLDOWN, CHECK_TOP_SELF,
)
from core.spintax import spintax
from core.state import (
    daily_count, bump_count,
    target_on_cooldown, mark_target_sent,
)

_PICK_LOCK = asyncio.Lock()


class AccountWorker:
    def __init__(self, source, proxy, messages, targets, bios, notify,
                 session_string=None, all_ids=None):
        if session_string:
            self.name = str(source)
            session_arg = StringSession(session_string)
        else:
            p = Path(source)
            self.name = p.stem
            session_arg = str(p)

        self.proxy    = proxy
        self.messages = messages
        self.targets  = targets
        self.bios     = bios
        self.notify   = notify
        # Set các user_id của toàn bộ acc team — dùng để phát hiện tin cuối có phải acc mình
        self.all_ids  = set(all_ids or [])

        self.client = TelegramClient(
            session_arg, API_ID, API_HASH, proxy=proxy,
            device_model="Desktop", system_version="Windows 10",
            app_version="4.16.8",
        )
        self.paused     = False
        self.running    = False
        self.sent       = 0
        self.errors     = 0
        self._since_bio = 0

    async def _top_is_self(self, entity) -> bool:
        """True nếu tin nhắn cuối cùng trong group là của 1 acc team mình."""
        if not CHECK_TOP_SELF or not self.all_ids:
            return False
        try:
            msgs = await self.client.get_messages(entity, limit=1)
        except Exception:
            return False
        if not msgs:
            return False
        sender = msgs[0].sender_id
        return sender in self.all_ids

    async def _resolve_target(self, target: str):
        t = target.strip()
        if not t:
            return None
        if t.startswith("https://t.me/") or t.startswith("@"):
            try:
                return await self.client.get_entity(t)
            except Exception as e:
                await self.notify(
                    f"❌ <b>{self.name}</b> bad target <code>{t}</code>: {type(e).__name__}"
                )
                return None
        return t

    async def _pick_target(self):
        """Pick 1 target (cooldown chưa hết → bỏ). Trong lock:
        - resolve target
        - check top-of-chat không phải acc mình
        - mark cooldown
        Trả về (target_raw, entity) hoặc (None, None).
        """
        async with _PICK_LOCK:
            candidates = [
                t for t in self.targets
                if not target_on_cooldown(t, TARGET_COOLDOWN)
            ]
            random.shuffle(candidates)

            for t in candidates:
                entity = await self._resolve_target(t)
                if entity is None:
                    continue

                # Tin cuối là acc mình → skip group này
                if await self._top_is_self(entity):
                    await self.notify(
                        f"⏭ <b>{self.name}</b> skip <code>{t}</code> "
                        f"(tin cuối là acc team)"
                    )
                    continue

                mark_target_sent(t)
                return t, entity

            return None, None

    async def rotate_bio(self):
        if not self.bios:
            return
        try:
            bio = random.choice(self.bios)[:70]
            await self.client(UpdateProfileRequest(about=bio))
            await self.notify(f"🛡 <b>{self.name}</b> — bio rotated")
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 10)
        except Exception as e:
            self.errors += 1
            await self.notify(f"❌ <b>{self.name}</b> bio err: <code>{type(e).__name__}</code>")

    async def send_one(self) -> bool:
        if not self.targets or not self.messages:
            await asyncio.sleep(30)
            return False

        target_raw, entity = await self._pick_target()
        if not target_raw:
            # hết target khả dụng (cooldown hết nhưng top là acc mình)
            await asyncio.sleep(60)
            return False

        text = spintax(random.choice(self.messages))
        images = [p for p in IMAGES_DIR.glob("*")
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]

        try:
            if images:
                await self.client.send_file(entity, random.choice(images), caption=text)
            else:
                await self.client.send_message(entity, text)

            self.sent += 1
            self._since_bio += 1
            count = bump_count(self.name)
            await self.notify(
                f"📊 <b>{self.name}</b> → <code>{target_raw}</code>  ({count}/{DAILY_MSG_CAP})"
            )

            if BIO_ROTATE_EVERY and self._since_bio >= BIO_ROTATE_EVERY:
                self._since_bio = 0
                await self.rotate_bio()
            return True

        except FloodWaitError as e:
            wait = e.seconds + random.randint(5, 30)
            await self.notify(f"⏳ <b>{self.name}</b> flood {e.seconds}s → ngủ {wait}s")
            await asyncio.sleep(wait)
            return False
        except PeerFloodError:
            await self.notify(f"🛑 <b>{self.name}</b> peer-flood — nghỉ 900s")
            await asyncio.sleep(900)
            return False
        except Exception as e:
            self.errors += 1
            await self.notify(
                f"❌ <b>{self.name}</b> send err: <code>{type(e).__name__}: {e}</code>"
            )
            return False

    async def run(self):
        self.running = True
        try:
            await self.client.start()
        except Exception as e:
            await self.notify(f"❌ <b>{self.name}</b> login failed: <code>{e}</code>")
            self.running = False
            return

        me = await self.client.get_me()
        self.all_ids.add(me.id)
        await self.notify(f"🚀 <b>{self.name}</b> online as @{me.username or me.id}")

        try:
            while self.running:
                if self.paused:
                    await asyncio.sleep(5)
                    continue
                if daily_count(self.name) >= DAILY_MSG_CAP:
                    await asyncio.sleep(600)
                    continue
                await self.send_one()
                await asyncio.sleep(random.randint(MIN_DELAY, MAX_DELAY))
        finally:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.running = False
            await self.notify(f"⛔ <b>{self.name}</b> offline")

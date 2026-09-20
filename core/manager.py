# language: Python, file: core/manager.py
import asyncio
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import (
    API_ID, API_HASH,
    SESSIONS_DIR, PROXIES_FILE, TARGETS_FILE, MESSAGES_FILE, BIOS_FILE,
    CLOUD_MODE, SESSIONS_FROM_ENV,
)
from core.account import AccountWorker


def _read_lines(path: Path):
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def _parse_proxy(line: str):
    line = line.strip()
    if "://" in line:
        from urllib.parse import urlparse
        u = urlparse(line)
        kind = u.scheme
        if kind not in ("socks5", "socks4", "http"):
            kind = "socks5"
        return (kind, u.hostname, u.port, True, u.username, u.password)
    parts = line.split(":")
    if len(parts) == 2:
        return ("socks5", parts[0], int(parts[1]), True, None, None)
    if len(parts) == 4:
        return ("socks5", parts[0], int(parts[1]), True, parts[2], parts[3])
    return None


class Manager:
    def __init__(self, notify):
        self.notify  = notify
        self.workers = {}
        self._tasks  = []

    def _load_files(self):
        targets  = _read_lines(TARGETS_FILE)
        messages = _read_lines(MESSAGES_FILE)
        bios     = _read_lines(BIOS_FILE)
        proxies  = [_parse_proxy(l) for l in _read_lines(PROXIES_FILE)]
        proxies  = [p for p in proxies if p]
        return targets, messages, bios, proxies

    def _iter_sessions(self):
        if CLOUD_MODE:
            return [(name, None, s) for (name, s) in SESSIONS_FROM_ENV]
        return [(p.stem, p, None) for p in sorted(SESSIONS_DIR.glob("*.session"))]

    async def _collect_all_ids(self) -> set:
        """Mở từng session 1 lần, lấy user_id. Dùng cho check top-of-chat."""
        ids = set()
        for name, path, sstr in self._iter_sessions():
            try:
                if sstr:
                    c = TelegramClient(StringSession(sstr), API_ID, API_HASH)
                else:
                    c = TelegramClient(str(path), API_ID, API_HASH)
                await c.connect()
                try:
                    if await c.is_user_authorized():
                        me = await c.get_me()
                        ids.add(me.id)
                finally:
                    await c.disconnect()
            except Exception:
                pass
        return ids

    async def load_new_sessions(self) -> int:
        targets, messages, bios, proxies = self._load_files()
        if not targets or not messages:
            return 0

        # Thu thập id toàn bộ acc team (chỉ 1 lần cho lần load đầu)
        all_ids = await self._collect_all_ids()

        added = 0
        for i, (name, path, sstr) in enumerate(self._iter_sessions()):
            if name in self.workers:
                continue
            proxy = proxies[i % len(proxies)] if proxies else None
            w = AccountWorker(
                name if sstr else path, proxy,
                messages, targets, bios, self.notify,
                session_string=sstr,
                all_ids=all_ids,
            )
            self.workers[name] = w
            self._tasks.append(asyncio.create_task(w.run(), name=f"worker:{name}"))
            added += 1
        return added

    async def start_all(self):
        targets, messages, _, _ = self._load_files()
        if not targets or not messages:
            await self.notify("❌ targets.txt hoặc messages.txt trống — không có gì chạy")
            return
        added = await self.load_new_sessions()
        if added == 0 and not self.workers:
            await self.notify("❌ Không có session nào để chạy")
            return
        if added:
            await self.notify(f"✅ Đã khởi động <b>{added}</b> tài khoản")

    async def stop_all(self):
        for w in self.workers.values():
            w.running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        self.workers.clear()
        await self.notify("⛔ Đã dừng tất cả worker")

    def pause(self, name=None):
        if name and name in self.workers:
            self.workers[name].paused = True
        else:
            for w in self.workers.values():
                w.paused = True

    def resume(self, name=None):
        if name and name in self.workers:
            self.workers[name].paused = False
        else:
            for w in self.workers.values():
                w.paused = False

    def get_worker(self, name):
        return self.workers.get(name)

    def reload_content(self):
        targets, messages, bios, _ = self._load_files()
        for w in self.workers.values():
            if targets:  w.targets  = targets
            if messages: w.messages = messages
            if bios:     w.bios     = bios

    async def rotate_bio_now(self, name: str) -> bool:
        w = self.workers.get(name)
        if not w:
            return False
        was_connected = False
        try:
            was_connected = w.client.is_connected()
        except Exception:
            pass
        try:
            if not was_connected:
                await w.client.connect()
            await w.rotate_bio()
        finally:
            if not was_connected:
                try: await w.client.disconnect()
                except Exception: pass
        return True

    async def rotate_bio_all(self) -> int:
        n = 0
        for name in list(self.workers.keys()):
            if await self.rotate_bio_now(name):
                n += 1
        return n

    def stats(self):
        out = []
        for name, w in self.workers.items():
            state = "⏸️" if w.paused else ("🟢" if w.running else "⚪")
            out.append((name, state, w.sent, w.errors))
        return out

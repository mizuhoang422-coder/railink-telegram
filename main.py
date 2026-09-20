# language: Python, file: main.py
import _force_ipv4  # noqa: F401
import asyncio
import os
import sys

from core.notify import notify
from core.manager import Manager


async def _health_server(port: int):
    from aiohttp import web

    async def ok(_):
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", ok)
    app.router.add_get("/health", ok)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[health] http://0.0.0.0:{port}/health", flush=True)
    while True:
        await asyncio.sleep(3600)


async def _run_bot_safe():
    """Bot chạy độc lập — crash không kéo health server chết."""
    try:
        from bot.control_bot import run_bot, attach
        manager = Manager(notify)
        attach(manager)
        await run_bot()
    except Exception as e:
        print(f"[bot] crashed: {type(e).__name__}: {e}", flush=True)
        # giữ process sống để Render không restart liên tục
        while True:
            await asyncio.sleep(3600)


async def run_all():
    port = int(os.getenv("PORT", "0") or "0")
    tasks = []

    # Health server FIRST — bind port ngay
    if port:
        tasks.append(asyncio.create_task(_health_server(port), name="health"))
        await asyncio.sleep(0.5)  # cho nó bind trước khi làm gì khác

    # Bot riêng — không kéo task khác chết
    tasks.append(asyncio.create_task(_run_bot_safe(), name="bot"))

    await asyncio.gather(*tasks)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "login":
        from login import interactive_login
        asyncio.run(interactive_login())
    elif cmd == "export":
        from export_sessions import main as exp
        asyncio.run(exp())
    elif cmd == "run":
        asyncio.run(run_all())
    else:
        print("usage: python main.py [login|run|export]")


if __name__ == "__main__":
    main()

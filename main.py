# language: Python, file: main.py
import _force_ipv4  # noqa: F401
import asyncio
import sys

from core.notify import notify
from core.manager import Manager


async def run_all():
    manager = Manager(notify)
    from bot.control_bot import run_bot, attach
    attach(manager)
    await run_bot()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "login":
        from login import interactive_login
        asyncio.run(interactive_login())
    elif cmd == "run":
        asyncio.run(run_all())
    else:
        print("usage: python main.py [login|run]")


if __name__ == "__main__":
    main()

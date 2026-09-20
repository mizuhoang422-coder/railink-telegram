# language: Python, file: core/notify.py
from aiogram import Bot
from config import ADMIN_ID

_bot = None


def bind(bot):
    global _bot
    _bot = bot


async def notify(msg: str):
    if _bot is None or not ADMIN_ID:
        return
    try:
        await _bot.send_message(ADMIN_ID, msg)
    except Exception:
        pass

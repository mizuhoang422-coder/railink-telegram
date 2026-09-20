# language: Python, file: core/spintax.py
import re
import random

_PATTERN = re.compile(r"\{([^{}]+)\}")


def spintax(text: str) -> str:
    while True:
        m = _PATTERN.search(text)
        if not m:
            return text
        choice = random.choice(m.group(1).split("|"))
        text = text[:m.start()] + choice + text[m.end():]

# language: Python, file: _ipv4_session.py
import socket
from aiohttp import TCPConnector, ClientSession
from aiogram.client.session.aiohttp import AiohttpSession


class IPv4Session(AiohttpSession):
    async def create_session(self):
        if self._session is None or self._session.closed:
            connector = TCPConnector(family=socket.AF_INET, ssl=True)
            self._session = ClientSession(connector=connector)
        return self._session

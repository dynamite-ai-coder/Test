import os
import json
from telethon import TelegramClient
from telethon.sessions import StringSession
from configuration import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION


_client = None


def get_client():
    global _client
    if _client is not None:
        return _client
    if not TELEGRAM_SESSION:
        raise RuntimeError("TELEGRAM_SESSION not configured")
    session = StringSession(TELEGRAM_SESSION)
    _client = TelegramClient(session, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    return _client


async def start_client():
    client = get_client()
    if not client.is_connected():
        await client.start()
        print("[TELETHON] Client connected")


async def stop_client():
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        _client = None
        print("[TELETHON] Client disconnected")


async def search_channel(channel):
    client = get_client()
    if not client.is_connected():
        await client.start()
    messages = []
    async for message in client.iter_messages(channel):
        messages.append(message)
    return messages


async def download_file(message, dest_path):
    client = get_client()
    await client.download_media(message, file=dest_path)


def is_connected():
    global _client
    return _client is not None and _client.is_connected()

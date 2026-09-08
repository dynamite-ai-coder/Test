import asyncio
from telethon import TelegramClient

API_ID = int(input("API_ID: "))
API_HASH = input("API_HASH: ")

client = TelegramClient("session", API_ID, API_HASH)

async def main():
    await client.start()
    me = await client.get_me()
    print(f"Zalogowano: {me.first_name} (@{me.username})")
    await client.disconnect()

asyncio.run(main())

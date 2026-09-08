import asyncio
from telethon import TelegramClient

API_ID = int(input("API_ID: "))
API_HASH = input("API_HASH: ")
PHONE = input("Numer telefonu: ")

client = TelegramClient("session", API_ID, API_HASH)

async def main():
    await client.start(phone=PHONE)
    me = await client.get_me()
    print(f"\nZalogowano: {me.first_name} (@{me.username})")

    with open("session.session", "rb") as f:
        data = f.read()

    print(f"\nSkopiuj poniższą wartość do zmiennej TELETHON_SESSION na Render:\n")
    print(data.hex())

asyncio.run(main())

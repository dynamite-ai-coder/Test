import os
import sys


def main():
    print("=== Telegram StringSession Generator ===")
    print()
    api_id = os.getenv("TELEGRAM_API_ID", "")
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    if not api_id:
        api_id = input("Enter API ID: ").strip()
    else:
        print(f"API ID: {api_id}")
    if not api_hash:
        api_hash = input("Enter API Hash: ").strip()
    else:
        print(f"API Hash: {api_hash}")
    phone = input("Enter phone number (with country code): ").strip()
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("Installing telethon...")
        os.system("pip install telethon")
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    print()
    print("Connecting to Telegram...")
    client.start(phone=phone)
    session_string = client.session.save()
    print()
    print("=" * 50)
    print("YOUR SESSION STRING (copy this to TELEGRAM_SESSION):")
    print("=" * 50)
    print(session_string)
    print("=" * 50)
    print()
    print("IMPORTANT: Keep this string secret!")
    print("Add it as TELEGRAM_SESSION environment variable on Render.")
    client.disconnect()


if __name__ == "__main__":
    main()

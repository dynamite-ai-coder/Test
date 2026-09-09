# Telegram → TeraBox

Telegram-controlled service that downloads .txt files from Telegram channels and uploads them to TeraBox.

## Architecture

```
Telegram user
    ↓
Telegram Bot (@Multi_url_bot)
    ↓
Flask webhook on Render
    ↓
Background job queue
    ↓
Telethon user client
    ↓
Telegram channel
    ↓
Find .txt files (10 MiB – 4 GiB)
    ↓
Download to disk
    ↓
TeraBox upload
    ↓
Delete local file
    ↓
Report status to Telegram
```

## Requirements

- Python 3.11+
- Telegram Bot Token (from @BotFather)
- Telegram API credentials (from https://my.telegram.org)
- Telethon StringSession
- TeraBox cookies

## Telegram Bot Setup

1. Open @BotFather on Telegram
2. Create new bot or use existing: @Multi_url_bot
3. Copy the bot token

## Telegram API Setup

1. Go to https://my.telegram.org
2. Create application
3. Copy API ID and API Hash

## StringSession Generation

```bash
pip install telethon
python session_generator.py
```

Follow prompts, then copy the session string to `TELEGRAM_SESSION` on Render.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| TELEGRAM_BOT_TOKEN | Bot token from @BotFather | required |
| TELEGRAM_API_ID | API ID from my.telegram.org | required |
| TELEGRAM_API_HASH | API Hash from my.telegram.org | required |
| TELEGRAM_SESSION | StringSession from session_generator.py | required |
| PUBLIC_URL | Render service URL | - |
| WEBHOOK_SECRET | Secret for webhook validation | - |
| ALLOWED_USER_ID | Telegram user ID (0 = all) | 0 |
| MIN_SIZE_BYTES | Minimum file size | 10485760 (10 MiB) |
| MAX_SIZE_BYTES | Maximum file size | 4294967296 (4 GiB) |
| DOWNLOAD_DIR | Temp download directory | /tmp/tg_downloads |
| DATA_DIR | Database directory | /data |
| TERABOX_NDUS | TeraBox ndus cookie | - |
| TERABOX_APP_ID | TeraBox app ID | 250528 |
| TERABOX_UPLOAD_ID | TeraBox upload ID | - |
| TERABOX_JS_TOKEN | TeraBox jsToken cookie | - |
| TERABOX_BROWSER_ID | TeraBox browserid cookie | - |
| TERABOX_REMOTE_DIR | TeraBox upload directory | / |

## Local / Termux Setup

```bash
pkg update && pkg install python
termux-setup-storage
cd ~/storage/downloads/tele
pip install -r requirements.txt
python app.py
```

## GitHub Setup

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

## Render Setup

See [DEPLOY_RENDER.md](DEPLOY_RENDER.md) for step-by-step instructions.

## Telegram Commands

| Command | Description |
|---------|-------------|
| /start | Welcome message |
| /help | Help |
| /whoami | Show your user ID |
| /status | App and worker status |
| /jobs | List recent jobs |
| /add @channel | Process a channel |
| /stop JOB_ID | Stop a running job |

## Security

- Never commit credentials to GitHub
- Use environment variables for all secrets
- The StringSession is sensitive - keep it secret
- WEBHOOK_SECRET validates incoming Telegram updates

## Known Limitations

- Files must be .txt format
- Size range: 10 MiB to 4 GiB
- Concurrency: 1 job at a time (large files)
- TeraBox upload depends on valid cookies

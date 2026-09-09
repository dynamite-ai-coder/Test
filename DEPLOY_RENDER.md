# Deploy to Render - Step by Step

## STEP 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create repository (e.g., `telegram-terabox`)
3. Do NOT initialize with README

## STEP 2: Push to GitHub

```bash
cd telegram-terabox
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/telegram-terabox.git
git push -u origin main
```

## STEP 3: Connect to Render

1. Go to https://dashboard.render.com
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Select the `telegram-terabox` repo

## STEP 4: Configure Service

- **Name**: telegram-terabox
- **Runtime**: Docker
- **Instance Type**: Starter (or higher for large files)
- **Port**: 10000

## STEP 5: Configure Environment Variables

Add these in Render Dashboard → Environment:

### Required:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION=your_session_string
```

### Optional (with defaults):
```
ALLOWED_USER_ID=0
MIN_SIZE_BYTES=10485760
MAX_SIZE_BYTES=4294967296
DOWNLOAD_DIR=/tmp/tg_downloads
DATA_DIR=/data
TERABOX_APP_ID=250528
TERABOX_REMOTE_DIR=/
```

### TeraBox (get from browser cookies):
```
TERABOX_NDUS=your_ndus
TERABOX_JS_TOKEN=your_jstoken
TERABOX_BROWSER_ID=your_browserid
TERABOX_UPLOAD_ID=your_upload_id
```

## STEP 6: Set PUBLIC_URL

After first deploy, copy the service URL and set:
```
PUBLIC_URL=https://telegram-terabox.onrender.com
```

## STEP 7: Generate Session String

Run locally:
```bash
pip install telethon
python session_generator.py
```

Enter your phone number when prompted. Copy the session string to `TELEGRAM_SESSION` on Render.

## STEP 8: Attach Persistent Disk

1. In Render Dashboard → your service → Settings
2. Scroll to "Persistent Disk"
3. Click "Add Disk"
4. Set mount path: `/data`
5. Set size: 10 GB (minimum recommended)

## STEP 9: Deploy

1. Click "Create Web Service"
2. Wait for first deploy to complete
3. Check logs for errors

## STEP 10: Verify

1. Open: `https://your-service.onrender.com/health`
2. Should return: `{"status": "ok"}`
3. Open Telegram, find @Multi_url_bot
4. Send: `/start`
5. Send: `/whoami` - note your user ID
6. Set `ALLOWED_USER_ID` to your user ID on Render
7. Redeploy

## STEP 11: Test

1. Send `/add @some_channel` to the bot
2. Check `/status` for progress
3. Verify files appear in TeraBox

## Troubleshooting

### Bot not responding
- Check TELEGRAM_BOT_TOKEN is correct
- Check PUBLIC_URL is set correctly
- Check webhook: `https://api.telegram.org/botTOKEN/getWebhookInfo`

### Files not uploading
- Check TeraBox cookies are valid
- Verify cookies in browser first
- Check upload logs in Render

### Job stuck
- Send `/stop JOB_ID`
- Check disk space on Render
- Review Render logs

### Session expired
- Generate new StringSession
- Update TELEGRAM_SESSION on Render
- Redeploy

## Important Notes

- The first deploy may take 2-3 minutes
- Render free tier sleeps after inactivity
- For production, use paid instance
- Monitor disk usage for large files
- TeraBox cookies expire - refresh periodically

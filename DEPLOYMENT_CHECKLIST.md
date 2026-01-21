# 🚀 Railway Deployment Checklist

## Pre-Deployment

- [x] Code pushed to GitHub: `DecentralizedJM/TIA-Service-Broadcaster`
- [x] Dockerfile configured
- [x] railway.toml configured
- [ ] Railway account created: https://railway.app

## Step 1: Deploy to Railway

### 1.1 Create Project
1. Go to: https://railway.app/new
2. Click **"Deploy from GitHub repo"**
3. Select: **`DecentralizedJM/TIA-Service-Broadcaster`**
4. Wait for initial build (will fail without env vars - that's expected)

### 1.2 Get Telegram Bot Token
1. Open Telegram → Message [@BotFather](https://t.me/BotFather)
2. Send: `/newbot`
3. Bot name: `Signal Broadcaster Bot`
4. Bot username: `your_signal_broadcaster_bot`
5. Copy token: `1234567890:ABCdef...`

### 1.3 Set Environment Variables

Go to Railway → **Variables** tab → Add these:

```bash
# Required (copy-paste these)
TELEGRAM_BOT_TOKEN=<paste_from_botfather>
ADMIN_TELEGRAM_ID=395803228
API_SECRET=eeojo2WLw3b4TC65K6WQXwp84f8OBpzmeQWmYb2rQB4

# Optional (Railway auto-sets PORT)
DATABASE_PATH=/app/data/broadcaster.db
```

**Important:** After adding variables, click **"Deploy"** to restart with new env vars.

### 1.4 Get Railway URL

After deployment succeeds:
1. Go to **Settings** tab
2. Scroll to **Domains**
3. Click **"Generate Domain"**
4. Copy the URL (e.g., `tia-service-broadcaster-production.up.railway.app`)

### 1.5 Set Webhook URL

Back in **Variables** tab, add:

```bash
WEBHOOK_URL=https://<your-railway-url>.up.railway.app
```

Save and let Railway redeploy.

### 1.6 Enable Persistent Storage

1. Go to **Settings** tab
2. Scroll to **Volumes**
3. Click **"New Volume"**
4. Mount path: `/app/data`
5. Click **"Add"**

## Step 2: Verify Deployment

### 2.1 Check Logs
Go to **Logs** tab. Should see:

```
🤖 TIA SERVICE BROADCASTER v1.0.0
Settings loaded - Admins: [395803228]
Database path: /app/data/broadcaster.db
BroadcasterAPI initialized
Telegram webhook mode: https://...
✅ Broadcaster ready! Port: 8000
```

### 2.2 Test Health Endpoint
Visit: `https://<your-railway-url>.up.railway.app/health`

Should return:
```json
{"status": "healthy"}
```

### 2.3 Test Root Endpoint
Visit: `https://<your-railway-url>.up.railway.app/`

Should show service info.

### 2.4 Test Telegram Bot
1. Open Telegram
2. Search for your bot: `@your_signal_broadcaster_bot`
3. Send: `/start`
4. Should get admin welcome message

## Step 3: Update SDK with Production URL

Once Railway is live, update the SDK:

```bash
cd /Users/jm/Mudrex-Trade-Ideas_Automation-SDK

# Use the helper script
./update_broadcaster_url.sh <your-railway-url>.up.railway.app

# Commit changes
git add tia_sdk/constants.py
git commit -m "Configure broadcaster URL for production"
git push origin main
```

## Step 4: Test End-to-End

### 4.1 Test SDK Connection

```bash
cd /Users/jm/Mudrex-Trade-Ideas_Automation-SDK
signal-sdk test
```

Should see: `✅ Connection successful!`

### 4.2 Test Signal Broadcasting

1. In Telegram, send to your broadcaster bot:
```
/signal BTCUSDT LONG Entry: Market TP: 50000 SL: 40000 Lev: 5x
```

2. Check Railway logs for:
```
Signal received: SIG-XXXXXX-BTCUSDT-XXXXXX
Broadcasting to X connected clients
```

3. Check SDK terminal for:
```
📡 Received signal: BTCUSDT LONG
✅ Trade executed successfully
```

## Production Checklist

- [ ] Railway deployment successful
- [ ] Health endpoint responding
- [ ] Telegram bot responding to `/start`
- [ ] Webhook configured
- [ ] Volume mounted for database persistence
- [ ] SDK updated with production URL
- [ ] SDK connection test passes
- [ ] End-to-end signal test successful

## Environment Variables Reference

### Required
```bash
TELEGRAM_BOT_TOKEN=<from_botfather>
ADMIN_TELEGRAM_ID=395803228
API_SECRET=eeojo2WLw3b4TC65K6WQXwp84f8OBpzmeQWmYb2rQB4
WEBHOOK_URL=https://<your-railway-url>.up.railway.app
```

### Optional (with defaults)
```bash
PORT=8000                                    # Railway sets this
HOST=0.0.0.0                                 # Default
DATABASE_PATH=/app/data/broadcaster.db       # Persisted in volume
WEBHOOK_PATH=/webhook                        # Default
```

## Troubleshooting

### "Cannot connect to broadcaster"
- Check Railway logs for errors
- Verify WEBHOOK_URL is set correctly
- Ensure bot token is valid (test with @BotFather)

### "Database errors"
- Ensure volume is mounted at `/app/data`
- Check DATABASE_PATH variable

### "WebSocket connection failed"
- Verify Railway domain is generated
- Check WebSocket URL in SDK constants
- Ensure API_SECRET matches between broadcaster and SDK

## Useful Commands

### View Railway Logs
```bash
railway logs
```

### Restart Service
```bash
railway restart
```

### Open Railway Dashboard
```bash
railway open
```

## URLs to Save

```
Broadcaster Repo: https://github.com/DecentralizedJM/TIA-Service-Broadcaster
SDK Repo: https://github.com/DecentralizedJM/Mudrex-Trade-Ideas_Automation-SDK
Railway Dashboard: https://railway.app/dashboard
Telegram Bot: @your_signal_broadcaster_bot

Production URLs:
- HTTP: https://<your-railway-url>.up.railway.app
- WebSocket: wss://<your-railway-url>.up.railway.app/ws
- Health: https://<your-railway-url>.up.railway.app/health

API Secret: eeojo2WLw3b4TC65K6WQXwp84f8OBpzmeQWmYb2rQB4
```

## Next Steps

After successful deployment:
1. ✅ Distribute SDK to clients
2. ✅ Clients run: `pip install git+https://github.com/DecentralizedJM/Mudrex-Trade-Ideas_Automation-SDK.git`
3. ✅ Clients run: `signal-sdk setup`
4. ✅ Clients run: `signal-sdk start`
5. ✅ You broadcast signals via Telegram bot
6. ✅ SDK clients auto-execute trades

---

**Status:** Ready for deployment! 🚀

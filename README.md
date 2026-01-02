# Mudrex TradeIdeas Automation Bot 🤖

**Centralized Telegram Signal Bot for Mudrex Futures Trading**

You post signals → All subscribers get auto-trades on their Mudrex accounts.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                 YOUR RAILWAY SERVER                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   You post signal  ───►  Bot receives via webhook            │
│   /signal LONG XRPUSDT...                                   │
│                                │                             │
│                                ▼                             │
│                    ┌─────────────────────────┐               │
│                    │   Encrypted Database    │               │
│                    │   - Subscriber APIs     │               │
│                    │   - Trade settings      │               │
│                    └─────────────────────────┘               │
│                                │                             │
│                    For each subscriber:                      │
│                    ├─► Execute on their Mudrex               │
│                    └─► Notify via Telegram DM                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Features

### For You (Admin)
- ✅ **Post signals** in your channel with simple commands
- ✅ **Auto-broadcast** to all subscribers instantly
- ✅ **Track stats** - see how many subscribers, trades executed
- ✅ **Railway hosted** - always online, no local setup

### For Subscribers
- ✅ **Simple registration** - just DM the bot
- ✅ **Set trade amount** - each user controls their own size
- ✅ **Set max leverage** - cap their own risk
- ✅ **Get notifications** - know when trades execute
- ✅ **Encrypted API keys** - AES-128 encryption at rest

## Signal Commands

Post these in your signal channel:

```bash
# New signal - Limit order
/signal LONG BTCUSDT entry=50000 sl=49000 tp=52000 lev=10x

# New signal - Market order
/signal SHORT ETHUSDT market sl=3800 tp=3500 lev=5x

# Close signal
/close SIG-20260103-001
```

## User Commands

Subscribers DM your bot:

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/register` | Connect Mudrex account |
| `/status` | View settings & stats |
| `/setamount 100` | Set trade size to 100 USDT |
| `/setleverage 10` | Set max leverage to 10x |
| `/unregister` | Stop receiving signals |

## Admin Commands

Only you can use these:

| Command | Description |
|---------|-------------|
| `/adminstats` | View subscriber count, trades |

---

## Deployment on Railway

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow prompts
3. Save the bot token

### 2. Get Your IDs

1. Message [@userinfobot](https://t.me/userinfobot) to get your Telegram ID
2. Create your signal channel/group
3. Add your bot as admin
4. Get channel ID (forward a message from channel to @userinfobot)

### 3. Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template)

Or manually:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
railway init

# Link to repo
railway link

# Set environment variables
railway variables set TELEGRAM_BOT_TOKEN="your_token"
railway variables set ADMIN_TELEGRAM_ID="your_id"
railway variables set SIGNAL_CHANNEL_ID="-100xxxxxxxx"
railway variables set ENCRYPTION_SECRET="$(openssl rand -hex 16)"

# Deploy
railway up
```

### 4. Set Webhook URL

After deployment, Railway gives you a URL like `https://your-app.up.railway.app`

Set it:
```bash
railway variables set WEBHOOK_URL="https://your-app.up.railway.app"
```

The bot will automatically register the webhook on startup.

---

## Local Development

### 1. Clone & Install

```bash
git clone https://github.com/DecentralizedJM/mudrex-tradeideas-automation-bot.git
cd mudrex-tradeideas-automation-bot
pip install -e .
```

### 2. Generate Encryption Secret

```bash
python -m signal_bot.run --generate-secret
```

### 3. Set Environment Variables

```bash
cp .env.example .env
# Edit .env with your values
```

### 4. Run in Polling Mode

```bash
python -m signal_bot.run --polling
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `ADMIN_TELEGRAM_ID` | ✅ | Your Telegram user ID |
| `SIGNAL_CHANNEL_ID` | ✅ | Channel ID where you post signals |
| `ENCRYPTION_SECRET` | ✅ | 32-char secret for API key encryption |
| `WEBHOOK_URL` | Production | Your Railway URL |
| `DATABASE_PATH` | No | SQLite path (default: subscribers.db) |
| `DEFAULT_TRADE_AMOUNT` | No | Default USDT per trade (default: 50) |
| `DEFAULT_MAX_LEVERAGE` | No | Default max leverage (default: 10) |

---

## Security

### API Key Encryption

All subscriber API keys are encrypted using:
- **Fernet** (AES-128-CBC with HMAC)
- **PBKDF2** key derivation (480,000 iterations)
- Keys only decrypted in memory when executing trades

### Best Practices

1. **Never share your ENCRYPTION_SECRET** - if compromised, rotate it and have users re-register
2. **Use Railway's encrypted variables** - they're not exposed in logs
3. **Bot deletes messages** containing API keys immediately after reading

---

## Project Structure

```
mudrex-tradeideas-automation-bot/
├── Dockerfile
├── Procfile
├── railway.toml
├── pyproject.toml
├── README.md
├── .env.example
└── src/
    └── signal_bot/
        ├── __init__.py
        ├── run.py              # Entry point
        ├── server.py           # FastAPI webhook server
        ├── settings.py         # Pydantic settings
        ├── telegram_bot.py     # Bot handlers
        ├── signal_parser.py    # Parse /signal commands
        ├── broadcaster.py      # Execute for all subscribers
        ├── database.py         # SQLite + encrypted storage
        └── crypto.py           # Fernet encryption
```

---

## Example Workflow

### 1. Subscriber Registers

```
User: /register
Bot: 🔐 Please send your Mudrex API Key...
User: abc123...
Bot: ✅ Now send your API Secret...
User: xyz789...
Bot: 💰 How much USDT per trade?
User: 100
Bot: 🎉 Registration Complete! Trade Amount: 100 USDT
```

### 2. You Post Signal

```
You (in signal channel):
/signal LONG XRPUSDT entry=2.50 sl=2.30 tp=3.00 lev=5x

Bot replies to you:
📡 Signal Broadcast Complete
✅ Success: 47
💰 Insufficient Balance: 3
❌ Failed: 0
Total: 50 subscribers
```

### 3. Subscribers Get DM

```
Bot DMs each subscriber:
✅ Trade Executed
📊 LONG XRPUSDT
📋 LIMIT @ 2.50
🛑 SL: 2.30
🎯 TP: 3.00
⚡ Leverage: 5x
```

---

## License

MIT License

## Disclaimer

⚠️ **Trading cryptocurrency futures involves significant risk. This bot executes trades automatically based on signals. Users are responsible for their own trading decisions and API key security. The developers are not responsible for any financial losses.**

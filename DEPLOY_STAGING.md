# Deploy Railway-staging Branch Separately on Railway

This guide shows how to deploy the `Railway-staging` branch as a separate service on Railway for testing, while keeping your production `railway-` branch deployment untouched.

## Prerequisites

1. A Railway account (same or different from production)
2. A separate Telegram bot for testing (create via @BotFather)
3. A separate Telegram channel/group for test signals
4. Access to the GitHub repository

## Step 1: Create a New Telegram Bot for Testing

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow the prompts
3. Choose a name like "Mudrex Test Bot" or "Mudrex Staging Bot"
4. Save the bot token (you'll need it in Step 4)
5. **Important:** This should be a DIFFERENT bot from your production bot

## Step 2: Create a Test Signal Channel/Group

1. Create a new Telegram channel or group for testing
2. Add your test bot as an administrator
3. Get your Telegram user ID (message [@userinfobot](https://t.me/userinfobot))
4. Get the channel ID:
   - Forward a message from your channel to [@userinfobot](https://t.me/userinfobot)
   - Or use the bot's `/chatid` command after adding it to the channel

## Step 3: Create a New Railway Project

### Option A: Using Railway Dashboard

1. Go to [Railway Dashboard](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository: `mudrex-trade-ideas-API-broadcaster`
5. **IMPORTANT:** After connecting, go to **Settings > Source** and change the branch to `Railway-staging`
6. Railway will automatically detect the Dockerfile and start building

### Option B: Using Railway CLI

```bash
# Install Railway CLI (if not already installed)
npm install -g @railway/cli

# Login to Railway
railway login

# Create a new project
railway init

# Link to your repo
railway link

# Set the branch to Railway-staging
railway variables set RAILWAY_GIT_BRANCH=Railway-staging

# Or set it in Railway dashboard: Settings > Source > Branch
```

## Step 4: Configure Environment Variables

In your new Railway project, go to **Variables** and set these:

### Required Variables

```bash
# Telegram Bot (TEST BOT - different from production)
TELEGRAM_BOT_TOKEN=your_test_bot_token_here

# Your Telegram User ID (same as production is fine)
ADMIN_TELEGRAM_ID=your_telegram_user_id

# Test Signal Channel ID (different from production)
SIGNAL_CHANNEL_ID=-100xxxxxxxxx

# Encryption Secret (generate a new one for staging)
ENCRYPTION_SECRET=$(openssl rand -hex 16)
# Or generate: python -m signal_bot.run --generate-secret
```

### Optional Variables

```bash
# Database path (default: subscribers.db)
DATABASE_PATH=/app/data/subscribers.db

# Default trade amount (default: 50)
DEFAULT_TRADE_AMOUNT=50

# Default max leverage (default: 10)
DEFAULT_MAX_LEVERAGE=10

# Webhook path (default: /webhook)
WEBHOOK_PATH=/webhook

# Port (Railway sets this automatically, but you can override)
PORT=8080
```

### Generate Encryption Secret

```bash
# Option 1: Using OpenSSL
openssl rand -hex 16

# Option 2: Using Python
python -m signal_bot.run --generate-secret
```

## Step 5: Set Up Persistent Volume for Database

1. Go to your Railway project **Settings**
2. Click **"Volumes"**
3. Click **"Add Volume"**
4. Set mount path: `/app/data`
5. This ensures your SQLite database persists across deployments

## Step 6: Configure Webhook URL

After Railway deploys your service:

1. Railway will provide a URL like: `https://your-staging-app.up.railway.app`
2. Go to **Variables** in Railway dashboard
3. Add/update:
   ```bash
   WEBHOOK_URL=https://your-staging-app.up.railway.app
   ```
4. The bot will automatically register the webhook on startup

## Step 7: Deploy and Verify

1. Railway will automatically deploy when you push to `Railway-staging` branch
2. Check the **Deployments** tab to see build logs
3. Once deployed, check the **Logs** tab for:
   ```
   Database connected successfully
   Webhook set: https://your-staging-app.up.railway.app/webhook
   ```

## Step 8: Test the Staging Bot

1. Send `/start` to your test bot in a private message
2. Register with test API credentials (use a test Mudrex account)
3. Post a test signal in your test channel:
   ```
   /signal LONG BTCUSDT entry=50000 sl=49000 tp=52000 lev=10x
   ```
4. Verify the bot responds and executes trades

## Step 9: Monitor Both Deployments

### Production (railway- branch)
- URL: `https://your-prod-app.up.railway.app`
- Bot: Your production bot
- Channel: Your production signal channel

### Staging (Railway-staging branch)
- URL: `https://your-staging-app.up.railway.app`
- Bot: Your test bot
- Channel: Your test signal channel

## Important Notes

1. **Separate Databases:** Each deployment has its own database, so subscribers are separate
2. **Separate Bots:** Use different Telegram bots to avoid conflicts
3. **Separate Channels:** Use different signal channels for testing
4. **Branch Protection:** The `railway-` branch remains untouched - only `Railway-staging` is used for staging
5. **Environment Isolation:** Staging and production are completely isolated

## Troubleshooting

### Bot not responding
- Check that `WEBHOOK_URL` is set correctly
- Verify webhook is registered: Check logs for "Webhook set: ..."
- Test webhook manually: `curl https://your-app.up.railway.app/health`

### Database issues
- Ensure volume is mounted at `/app/data`
- Check `DATABASE_PATH` variable matches mount path

### Build failures
- Check Railway build logs
- Verify `Railway-staging` branch exists and has latest code
- Ensure Dockerfile is present in the branch

## Quick Reference

```bash
# Check current branch in Railway
railway status

# View logs
railway logs

# Open Railway dashboard
railway open

# Set environment variable
railway variables set KEY=value

# View all variables
railway variables
```

## Testing Checklist

- [ ] Test bot created and token saved
- [ ] Test channel created and bot added as admin
- [ ] New Railway project created
- [ ] Branch set to `Railway-staging`
- [ ] All environment variables set
- [ ] Volume mounted at `/app/data`
- [ ] Webhook URL configured
- [ ] Bot responds to `/start`
- [ ] Registration works
- [ ] Signal posting works
- [ ] Trade execution works
- [ ] Manual mode expiration works (wait 5 minutes)
- [ ] Position check works (open position, then try signal)
- [ ] Admin stats show correct counts

---

**Remember:** Always test in staging before merging to production!

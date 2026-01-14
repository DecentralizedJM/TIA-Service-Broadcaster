# Quick Start: Deploy Staging Environment

## TL;DR - 5 Minute Setup

### 1. Create Test Bot (2 min)
```
1. Message @BotFather → /newbot
2. Name: "Mudrex Staging Bot"
3. Save token
```

### 2. Create Test Channel (1 min)
```
1. Create new Telegram channel
2. Add bot as admin
3. Get channel ID (forward message to @userinfobot)
```

### 3. Deploy on Railway (2 min)
```
1. Railway Dashboard → New Project
2. Connect GitHub repo
3. Settings → Source → Branch: Railway-staging
4. Variables → Add:
   - TELEGRAM_BOT_TOKEN (test bot token)
   - ADMIN_TELEGRAM_ID (your Telegram ID)
   - SIGNAL_CHANNEL_ID (test channel ID)
   - ENCRYPTION_SECRET (generate: openssl rand -hex 16)
5. Settings → Volumes → Add: /app/data
6. Wait for deploy → Copy URL
7. Variables → Add: WEBHOOK_URL=https://your-app.up.railway.app
```

### 4. Test (1 min)
```
1. DM test bot: /start
2. Register with test API keys
3. Post signal in test channel
4. Verify it works!
```

## Environment Variables Checklist

Copy-paste this list and fill in values:

```bash
# Required
TELEGRAM_BOT_TOKEN=                    # Test bot token from @BotFather
ADMIN_TELEGRAM_ID=                     # Your Telegram user ID
SIGNAL_CHANNEL_ID=                     # Test channel ID (negative number)
ENCRYPTION_SECRET=                     # Generate: openssl rand -hex 16

# Optional (has defaults)
DATABASE_PATH=/app/data/subscribers.db
DEFAULT_TRADE_AMOUNT=50
DEFAULT_MAX_LEVERAGE=10
WEBHOOK_PATH=/webhook
```

## Generate Encryption Secret

```bash
# Quick way
openssl rand -hex 16

# Or using Python
python -m signal_bot.run --generate-secret
```

## Verify Deployment

1. **Check Health:**
   ```bash
   curl https://your-staging-app.up.railway.app/health
   # Should return: {"status":"healthy"}
   ```

2. **Check Logs:**
   - Railway Dashboard → Your Project → Deployments → View Logs
   - Look for: "Webhook set: https://..."

3. **Test Bot:**
   - Send `/start` to your test bot
   - Should get welcome message

## Common Issues

| Issue | Solution |
|-------|----------|
| Bot not responding | Check WEBHOOK_URL is set correctly |
| Database errors | Ensure volume mounted at `/app/data` |
| Build fails | Verify branch is `Railway-staging` |
| Webhook not set | Check logs, verify TELEGRAM_BOT_TOKEN |

## Production vs Staging

| Item | Production | Staging |
|------|-----------|---------|
| Branch | `railway-` | `Railway-staging` |
| Bot | Production bot | Test bot |
| Channel | Production channel | Test channel |
| Database | Production DB | Staging DB |
| URL | `prod-app.up.railway.app` | `staging-app.up.railway.app` |

---

**Need more details?** See [DEPLOY_STAGING.md](./DEPLOY_STAGING.md)

# Deploying to Railway

This repository contains a Telegram signal bot that can run on Railway using **webhook mode** (recommended) or polling mode.

## Quick Deployment Steps

1. **Create Railway Project**
   - Go to [Railway.app](https://railway.app) and create a new project
   - Connect this GitHub repository
   - Select the `railway-` branch (not main)

2. **Configure Environment Variables**
   
   In Railway's Settings > Variables, add:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ADMIN_TELEGRAM_ID=your_telegram_user_id
   SIGNAL_CHANNEL_ID=your_channel_id (optional)
   ENCRYPTION_SECRET=your_32_char_encryption_key
   DEFAULT_TRADE_AMOUNT=50.0
   
   # Webhook settings (Railway provides these automatically)
   PORT=8080
   HOST=0.0.0.0
   WEBHOOK_PATH=/webhook
   ```

3. **Set Up Database Volume** (Important!)
   - Go to Railway Settings > Volumes
   - Create a new volume with mount path: `/app/data`
   - Set environment variable: `DATABASE_PATH=/app/data/subscribers.db`

4. **Deploy**
   - Railway will auto-build using Docker
   - The bot runs in **webhook mode** by default (better for production)
   - Health checks available at `/health`

## Webhook vs Polling Mode

### Webhook Mode (Default - Recommended)
- ✅ More efficient, lower resource usage
- ✅ Instant message processing
- ✅ Better for production deployment
- ✅ Works with Railway's web service type
- ⚠️ Requires public HTTPS URL (Railway provides this)

### Polling Mode (Local Development)
- ⚠️ Higher resource usage (constant polling)
- ⚠️ Slight message delay
- ✅ Works behind firewalls/NAT
- ⚠️ Should use "Worker" service type on Railway

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from @BotFather | `7764064104:AAF...` |
| `ADMIN_TELEGRAM_ID` | ✅ | Your Telegram user ID | `395803228` |
| `SIGNAL_CHANNEL_ID` | ❌ | Channel ID for /signal command | `-1003648245974` |
| `ENCRYPTION_SECRET` | ✅ | 32-char Fernet encryption key | Generate with `--generate-secret` |
| `DEFAULT_TRADE_AMOUNT` | ❌ | Default USDT per trade | `50.0` |
| `DATABASE_PATH` | ❌ | SQLite database location | `/app/data/subscribers.db` |
| `PORT` | ❌ | Server port (Railway sets this) | `8080` |
| `HOST` | ❌ | Server host | `0.0.0.0` |
| `WEBHOOK_PATH` | ❌ | Webhook endpoint path | `/webhook` |

## Railway Configuration Files

- **`Dockerfile`** - Multi-stage container build
- **`railway.toml`** - Railway-specific settings
- **`Procfile`** - Process definitions (web/worker)

## Setting Up Telegram Webhook

The bot automatically configures the Telegram webhook using Railway's provided domain. Railway exposes your service at:
```
https://your-app-name.up.railway.app
```

The webhook URL becomes:
```
https://your-app-name.up.railway.app/webhook
```

## Security Best Practices

1. **Never commit secrets** to the repository
2. **Use Railway's environment variables** for all sensitive data
3. **Enable Railway's built-in SSL** (automatic)
4. **Use strong encryption keys** (32+ characters)
5. **Monitor access logs** in Railway dashboard

## Troubleshooting

### Common Issues

**Bot not receiving messages:**
- Check webhook setup in Railway logs
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure Railway service is running and healthy

**Database errors:**
- Verify volume is mounted at `/app/data`
- Check `DATABASE_PATH` environment variable
- Ensure Railway persistent volume is configured

**API connection issues:**
- Check user's Mudrex API credentials
- Verify network connectivity from Railway
- Check Mudrex API rate limits

### Useful Commands

```bash
# Generate encryption secret locally
python -m signal_bot.run --generate-secret

# Test webhook locally (requires ngrok or similar)
python -m signal_bot.run  # webhook mode

# Run in polling mode locally
python -m signal_bot.run --polling

# Check health endpoint
curl https://your-app.up.railway.app/health
```

## Monitoring

- **Health Check**: `/health` endpoint
- **Stats**: `/` shows basic stats
- **Logs**: Available in Railway dashboard
- **Metrics**: Railway provides CPU/memory usage

## Scaling

Railway automatically handles:
- SSL certificates
- Load balancing (if you scale to multiple replicas)
- Auto-restarts on failure
- Resource monitoring

For high-volume usage, consider:
- Increasing Railway plan limits
- Monitoring Telegram API rate limits
- Using Redis for session storage (future enhancement)

---

**Note**: Keep the `main` branch protected. This `railway-` branch contains deployment-specific configurations that should not be merged back to main. 

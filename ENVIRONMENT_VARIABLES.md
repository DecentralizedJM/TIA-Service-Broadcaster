# Environment Variables Guide

Complete list of all environment variables required for Railway deployment.

## 📋 Quick Reference

### Required Variables (Must Set)
| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `ENCRYPTION_SECRET` | Secret for encrypting API keys (min 16 chars) | See [Generate Encryption Secret](#generate-encryption-secret) |
| `ADMIN_TELEGRAM_ID` | Your Telegram user ID | `123456789` |
| `SIGNAL_CHANNEL_ID` | Channel/group ID where signals are posted | `-1001234567890` |

### Optional Variables (Have Defaults)
| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_URL` | None | Public URL for Telegram webhook (set after deployment) |
| `WEBHOOK_PATH` | `/webhook` | Webhook endpoint path |
| `HOST` | `0.0.0.0` | Server host (Railway sets automatically) |
| `PORT` | `8000` | Server port (Railway sets automatically) |
| `DATABASE_PATH` | `subscribers.db` | Path to SQLite database file |
| `DEFAULT_TRADE_AMOUNT` | `50.0` | Default USDT amount per trade for new subscribers |
| `DEFAULT_MAX_LEVERAGE` | `10` | Default max leverage for new subscribers |
| `MIN_ORDER_VALUE` | `8.0` | Minimum order value in USDT (Mudrex requirement) |
| `ALLOW_REGISTRATION` | `true` | Enable/disable user registration |

---

## 🔧 Detailed Variable Descriptions

### 1. `TELEGRAM_BOT_TOKEN` (Required)

**Description:** Your Telegram bot token obtained from [@BotFather](https://t.me/botfather).

**How to get:**
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

**Example:**
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

**⚠️ Security:** Never share or commit this token. Keep it secret!

---

### 2. `ENCRYPTION_SECRET` (Required)

**Description:** Master secret for encrypting subscriber API keys. Must be at least 16 characters long.

**Minimum Length:** 16 characters

**Generate Encryption Secret:**

#### Option 1: Using OpenSSL (Recommended)
```bash
openssl rand -hex 16
```
This generates a 32-character hex string (16 bytes).

**Example output:**
```
a1b2c3d4e5f6789012345678901234ab
```

#### Option 2: Using Python
```bash
python -m signal_bot.run --generate-secret
```

This will output:
```
🔐 Generated Encryption Secret:

    a1b2c3d4e5f6789012345678901234ab

Add this to your environment variables:
    export ENCRYPTION_SECRET="a1b2c3d4e5f6789012345678901234ab"
```

#### Option 3: Manual Generation
```bash
# Generate 32-character random string
python -c "import secrets; print(secrets.token_hex(16))"
```

**Example:**
```bash
ENCRYPTION_SECRET=a1b2c3d4e5f6789012345678901234ab
```

**⚠️ Critical:** 
- **NEVER** share or commit this secret
- If compromised, all users must re-register
- Generate a **NEW** secret for each deployment (production vs staging)
- Use Railway's encrypted variables (they're not exposed in logs)

---

### 3. `ADMIN_TELEGRAM_ID` (Required)

**Description:** Your Telegram user ID. Only this user can post signals and use admin commands.

**How to get:**
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID (e.g., `123456789`)

**Example:**
```bash
ADMIN_TELEGRAM_ID=123456789
```

**Note:** This must be an integer (no quotes needed in Railway).

---

### 4. `SIGNAL_CHANNEL_ID` (Required)

**Description:** The Telegram channel or group ID where you post trading signals.

**How to get:**

#### For Groups:
1. Add your bot to the group as an administrator
2. Forward a message from the group to [@userinfobot](https://t.me/userinfobot)
3. It will show the chat ID (usually negative, like `-1001234567890`)

#### Using Bot Command:
1. After adding bot to group, use `/chatid` command
2. Bot will reply with the chat ID

#### For Channels:
1. Create or use your channel
2. Add bot as administrator
3. Forward a message from channel to [@userinfobot](https://t.me/userinfobot)
4. Copy the channel ID (usually starts with `-100`)

**Example:**
```bash
SIGNAL_CHANNEL_ID=-1001234567890
```

**Note:** 
- Usually negative for groups/channels
- Must be an integer (no quotes needed in Railway)
- Private chats are positive numbers, groups/channels are negative

---

### 5. `WEBHOOK_URL` (Optional - Set After Deployment)

**Description:** Public URL for Telegram webhook. Railway provides this after deployment.

**When to set:** After Railway gives you the deployment URL.

**Format:**
```
https://your-app-name.up.railway.app
```

**Example:**
```bash
WEBHOOK_URL=https://mudrex-bot-production.up.railway.app
```

**How to get:**
1. Deploy your app on Railway
2. Railway will provide a URL like: `https://your-app.up.railway.app`
3. Copy this URL and set it as `WEBHOOK_URL`
4. The bot will automatically register the webhook on startup

**Note:** 
- Don't include `/webhook` in the URL (that's handled by `WEBHOOK_PATH`)
- If not set, the bot will log a warning but continue (useful for local development)

---

### 6. `WEBHOOK_PATH` (Optional)

**Description:** Webhook endpoint path. Default is `/webhook`.

**Default:** `/webhook`

**Example:**
```bash
WEBHOOK_PATH=/webhook
```

**Note:** Usually you don't need to change this unless you have routing requirements.

---

### 7. `HOST` (Optional)

**Description:** Server host address. Railway sets this automatically.

**Default:** `0.0.0.0`

**Example:**
```bash
HOST=0.0.0.0
```

**Note:** Railway manages this automatically. Only override if needed.

---

### 8. `PORT` (Optional)

**Description:** Server port. Railway sets this automatically via `$PORT` environment variable.

**Default:** `8000`

**Example:**
```bash
PORT=8080
```

**Note:** Railway provides `$PORT` automatically. Your code should use `os.getenv('PORT', '8000')`.

---

### 9. `DATABASE_PATH` (Optional)

**Description:** Path to SQLite database file.

**Default:** `subscribers.db`

**Recommended for Railway:**
```bash
DATABASE_PATH=/app/data/subscribers.db
```

**Why `/app/data`:**
- Railway volumes are typically mounted at `/app/data`
- This ensures database persists across deployments
- Set up volume in Railway: Settings → Volumes → Mount path: `/app/data`

**Example:**
```bash
DATABASE_PATH=/app/data/subscribers.db
```

---

### 10. `DEFAULT_TRADE_AMOUNT` (Optional)

**Description:** Default USDT amount per trade for new subscribers.

**Default:** `50.0`

**Example:**
```bash
DEFAULT_TRADE_AMOUNT=50.0
```

**Recommendation:** 
- Minimum should be `20-25 USDT` to ensure successful execution
- Mudrex requires minimum order value of ~$7-8 USDT
- Higher leverage requires more margin

---

### 11. `DEFAULT_MAX_LEVERAGE` (Optional)

**Description:** Default maximum leverage for new subscribers.

**Default:** `10`

**Range:** `1-125` (Mudrex supports up to 125x)

**Example:**
```bash
DEFAULT_MAX_LEVERAGE=10
```

**Note:** Subscribers can change this with `/setleverage` command.

---

### 12. `MIN_ORDER_VALUE` (Optional)

**Description:** Minimum order value in USDT required by Mudrex.

**Default:** `8.0`

**Example:**
```bash
MIN_ORDER_VALUE=8.0
```

**Note:** This is enforced by Mudrex API. Don't change unless Mudrex changes requirements.

---

### 13. `ALLOW_REGISTRATION` (Optional)

**Description:** Enable or disable new user registration.

**Default:** `true`

**Options:**
- `true` - Allow new registrations
- `false` - Disable new registrations (existing users still work)

**Example:**
```bash
ALLOW_REGISTRATION=true
```

**Use case:** 
- Set to `false` to temporarily stop accepting new subscribers
- Useful for maintenance or when you want to limit growth

---

## 🚀 Railway Deployment Checklist

### Step 1: Generate Encryption Secret
```bash
# Generate a new secret
openssl rand -hex 16

# Copy the output (32 characters)
```

### Step 2: Get Telegram Credentials
- [ ] Bot token from @BotFather
- [ ] Your Telegram user ID from @userinfobot
- [ ] Channel/group ID (forward message to @userinfobot)

### Step 3: Set Required Variables in Railway
- [ ] `TELEGRAM_BOT_TOKEN` = Your bot token
- [ ] `ENCRYPTION_SECRET` = Generated secret (32 chars)
- [ ] `ADMIN_TELEGRAM_ID` = Your user ID
- [ ] `SIGNAL_CHANNEL_ID` = Your channel ID

### Step 4: Set Optional Variables (Recommended)
- [ ] `DATABASE_PATH` = `/app/data/subscribers.db`
- [ ] `DEFAULT_TRADE_AMOUNT` = `50.0` (or your preferred amount)
- [ ] `DEFAULT_MAX_LEVERAGE` = `10` (or your preferred leverage)

### Step 5: Set Up Volume (Important!)
- [ ] Go to Railway: Settings → Volumes
- [ ] Add Volume: Mount path = `/app/data`
- [ ] This ensures database persists

### Step 6: Deploy and Set Webhook URL
- [ ] Wait for Railway to deploy
- [ ] Copy your Railway URL (e.g., `https://your-app.up.railway.app`)
- [ ] Add variable: `WEBHOOK_URL` = Your Railway URL
- [ ] Railway will redeploy automatically
- [ ] Check logs for "Webhook set: ..." message

---

## 📝 Complete Example for Railway

Here's a complete example with all variables set:

```bash
# Required
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ENCRYPTION_SECRET=a1b2c3d4e5f6789012345678901234ab
ADMIN_TELEGRAM_ID=123456789
SIGNAL_CHANNEL_ID=-1001234567890

# Optional (Recommended)
DATABASE_PATH=/app/data/subscribers.db
DEFAULT_TRADE_AMOUNT=50.0
DEFAULT_MAX_LEVERAGE=10
WEBHOOK_URL=https://your-app.up.railway.app
WEBHOOK_PATH=/webhook
ALLOW_REGISTRATION=true
```

---

## 🔐 Security Best Practices

1. **Never commit secrets to Git**
   - Use Railway's encrypted variables
   - Never push `.env` files to repository

2. **Use different secrets for different environments**
   - Production: Generate one secret
   - Staging: Generate a different secret

3. **Rotate secrets if compromised**
   - If `ENCRYPTION_SECRET` is leaked, generate a new one
   - All users must re-register (old encrypted keys won't work)

4. **Railway's encrypted variables**
   - Railway encrypts variables at rest
   - They're not exposed in logs or build output
   - Use Railway dashboard, not CLI for sensitive values

5. **Access control**
   - Only set `ADMIN_TELEGRAM_ID` to your personal Telegram ID
   - Don't share bot tokens

---

## 🧪 Testing Variables

### Local Development (.env file)
Create a `.env` file in the project root:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
ENCRYPTION_SECRET=your_secret_here
ADMIN_TELEGRAM_ID=123456789
SIGNAL_CHANNEL_ID=-1001234567890
DATABASE_PATH=subscribers.db
```

**Note:** `.env` files are ignored by git (in `.gitignore`).

### Verify Variables are Loaded
Check logs on startup. You should see:
```
Settings loaded - Admin: 123456789
Encryption initialized
Database connected successfully
```

---

## ❓ Troubleshooting

### Bot not responding
- ✅ Check `TELEGRAM_BOT_TOKEN` is correct
- ✅ Verify `WEBHOOK_URL` is set and correct
- ✅ Check logs for "Webhook set: ..." message

### Encryption errors
- ✅ Verify `ENCRYPTION_SECRET` is at least 16 characters
- ✅ Check for typos in the secret
- ✅ Ensure same secret is used (don't change it after deployment)

### Database errors
- ✅ Check `DATABASE_PATH` matches volume mount path
- ✅ Verify volume is mounted at `/app/data`
- ✅ Check file permissions

### Signal channel not working
- ✅ Verify `SIGNAL_CHANNEL_ID` is correct (usually negative)
- ✅ Ensure bot is added as admin in the channel/group
- ✅ Check bot has permission to read messages

---

## 📞 Need Help?

If you encounter issues:
1. Check Railway deployment logs
2. Verify all required variables are set
3. Check variable names match exactly (case-sensitive in some systems)
4. Ensure no extra spaces in variable values

---

**Last Updated:** Based on codebase version 2.0.0

# Railway Variables - Quick Reference Card

Copy-paste this checklist and fill in your values.

---

## 🔐 Step 1: Generate Encryption Secret

```bash
# Run this command:
openssl rand -hex 16

# Copy the 32-character output (e.g., a1b2c3d4e5f6789012345678901234ab)
```

---

## 📋 Step 2: Fill in Required Variables

```bash
# ⚠️ REQUIRED - Fill these in:

TELEGRAM_BOT_TOKEN=                    # From @BotFather
ENCRYPTION_SECRET=                     # From Step 1 (32 chars)
ADMIN_TELEGRAM_ID=                     # Your Telegram user ID (from @userinfobot)
SIGNAL_CHANNEL_ID=                     # Your channel/group ID (negative number)
```

---

## 📋 Step 3: Optional Variables (Recommended)

```bash
# ✅ RECOMMENDED - Copy these as-is:

DATABASE_PATH=/app/data/subscribers.db
DEFAULT_TRADE_AMOUNT=50.0
DEFAULT_MAX_LEVERAGE=10
WEBHOOK_PATH=/webhook
ALLOW_REGISTRATION=true
```

```bash
# ⏳ SET AFTER DEPLOYMENT:

WEBHOOK_URL=                           # Set after Railway gives you URL
                                        # Format: https://your-app.up.railway.app
```

---

## 🚀 Complete Example (Fill in the blanks)

```bash
# ============================================
# REQUIRED VARIABLES
# ============================================
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ENCRYPTION_SECRET=a1b2c3d4e5f6789012345678901234ab
ADMIN_TELEGRAM_ID=123456789
SIGNAL_CHANNEL_ID=-1001234567890

# ============================================
# OPTIONAL VARIABLES (Recommended)
# ============================================
DATABASE_PATH=/app/data/subscribers.db
DEFAULT_TRADE_AMOUNT=50.0
DEFAULT_MAX_LEVERAGE=10
WEBHOOK_PATH=/webhook
ALLOW_REGISTRATION=true

# ============================================
# SET AFTER DEPLOYMENT
# ============================================
WEBHOOK_URL=https://your-app.up.railway.app
```

---

## 📝 How to Get Each Value

### 1. TELEGRAM_BOT_TOKEN
- Message @BotFather → `/newbot` → Follow prompts → Copy token

### 2. ENCRYPTION_SECRET  
- Run: `openssl rand -hex 16` → Copy output (32 characters)

### 3. ADMIN_TELEGRAM_ID
- Message @userinfobot → Copy your user ID (number, no quotes)

### 4. SIGNAL_CHANNEL_ID
- Add bot to channel/group as admin
- Forward message to @userinfobot → Copy chat ID (negative number)

### 5. WEBHOOK_URL
- After Railway deploys → Copy your app URL
- Format: `https://your-app-name.up.railway.app`

---

## ✅ Deployment Checklist

- [ ] Generated encryption secret (32 characters)
- [ ] Got bot token from @BotFather
- [ ] Got your Telegram user ID from @userinfobot
- [ ] Got channel ID (forward message to @userinfobot)
- [ ] Set all required variables in Railway
- [ ] Set `DATABASE_PATH=/app/data/subscribers.db`
- [ ] Created volume in Railway: Settings → Volumes → Mount: `/app/data`
- [ ] Deployed and got Railway URL
- [ ] Set `WEBHOOK_URL` to your Railway URL
- [ ] Checked logs for "Webhook set: ..." message
- [ ] Tested `/start` command with bot

---

## 🔒 Security Reminders

- ✅ Never commit secrets to Git
- ✅ Use different secrets for production vs staging
- ✅ Railway encrypts variables automatically
- ✅ Never share bot tokens or encryption secrets

---

**Need more details?** See [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)

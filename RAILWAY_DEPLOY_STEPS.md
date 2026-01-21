# 🚀 Railway Deployment - Step by Step

## ⚡ Quick Start (5 Minutes)

### **Step 1: Create Railway Account & Project**

1. **Go to Railway:** https://railway.app
2. **Sign up/Login** (use GitHub to connect)
3. **Click "New Project"** (top right)
4. **Select "Deploy from GitHub repo"**
5. **Authorize Railway** to access your GitHub (if first time)
6. **Select repository:** `DecentralizedJM/TIA-Service-Broadcaster`
7. **Click "Deploy Now"**

✅ Railway will start building (will fail initially - that's OK!)

---

### **Step 2: Get Telegram Bot Token**

1. **Open Telegram** (mobile or desktop)
2. **Search for:** `@BotFather`
3. **Start chat** and send: `/newbot`
4. **Bot name:** `Signal Broadcaster Bot` (or any name)
5. **Bot username:** `your_signal_broadcaster_bot` (must be unique, end with `_bot`)
6. **Copy the token** (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

💡 **Save this token** - you'll need it in Step 3!

---

### **Step 3: Set Environment Variables**

1. **In Railway dashboard**, click on your project
2. **Click "Variables" tab** (left sidebar)
3. **Click "New Variable"** button
4. **Add these variables ONE BY ONE:**

#### Variable 1:
```
Name: TELEGRAM_BOT_TOKEN
Value: <paste_your_token_from_step_2>
```
Click **"Add"**

#### Variable 2:
```
Name: ADMIN_TELEGRAM_ID
Value: 395803228
```
Click **"Add"**

#### Variable 3:
```
Name: DATABASE_PATH
Value: /app/data/broadcaster.db
```
Click **"Add"**

✅ **After adding all 3 variables**, Railway will auto-redeploy!

---

### **Step 4: Generate Railway Domain**

1. **Click "Settings" tab** (left sidebar)
2. **Scroll down** to **"Domains"** section
3. **Click "Generate Domain"** button
4. **Copy the domain** (e.g., `tia-service-broadcaster-production.up.railway.app`)

💡 **Save this URL** - you'll need it!

---

### **Step 5: Set Webhook URL**

1. **Go back to "Variables" tab**
2. **Click "New Variable"**
3. **Add:**

```
Name: WEBHOOK_URL
Value: https://<paste_your_domain_from_step_4>
```

**Example:**
```
Name: WEBHOOK_URL
Value: https://tia-service-broadcaster-production.up.railway.app
```

4. **Click "Add"**

✅ Railway will redeploy automatically!

---

### **Step 6: Enable Persistent Storage (Important!)**

1. **Click "Settings" tab**
2. **Scroll down** to **"Volumes"** section
3. **Click "New Volume"** button
4. **Mount path:** `/app/data`
5. **Click "Add"**

✅ This ensures your database persists across deployments!

---

### **Step 7: Verify Deployment**

#### 7.1 Check Logs
1. **Click "Deployments" tab** (or "Logs" tab)
2. **Look for these messages:**

```
🤖 TIA SERVICE BROADCASTER v1.0.0
Settings loaded - Admins: [395803228]
Database path: /app/data/broadcaster.db
BroadcasterAPI initialized
Telegram webhook mode: https://...
✅ Broadcaster ready! Port: 8000
```

✅ If you see "Broadcaster ready!" - **SUCCESS!**

#### 7.2 Test Health Endpoint
1. **Open browser**
2. **Visit:** `https://<your-domain>/health`
   - Replace `<your-domain>` with your Railway domain
   - Example: `https://tia-service-broadcaster-production.up.railway.app/health`
3. **Should see:** `{"status": "healthy"}`

✅ If you see healthy status - **SUCCESS!**

#### 7.3 Test Telegram Bot
1. **Open Telegram**
2. **Search for your bot** (the username you created in Step 2)
3. **Send:** `/start`
4. **Should get:** Admin welcome message

✅ If bot responds - **SUCCESS!**

---

### **Step 8: Update SDK with Production URL**

Once Railway is working, update the SDK:

1. **Open terminal**
2. **Run:**

```bash
cd /Users/jm/Mudrex-Trade-Ideas_Automation-SDK

# Replace <your-domain> with your Railway domain (without https://)
./update_broadcaster_url.sh <your-domain>.up.railway.app

# Example:
# ./update_broadcaster_url.sh tia-service-broadcaster-production.up.railway.app
```

3. **Commit and push:**

```bash
git add tia_sdk/constants.py
git commit -m "Configure broadcaster URL for production"
git push origin main
```

✅ SDK is now configured to connect to your Railway broadcaster!

---

## 🎯 Quick Reference

### **Your Railway URLs:**
```
HTTP: https://<your-domain>.up.railway.app
WebSocket: wss://<your-domain>.up.railway.app/ws
Health: https://<your-domain>.up.railway.app/health
```

### **Environment Variables Summary:**
```bash
TELEGRAM_BOT_TOKEN=<from_botfather>
ADMIN_TELEGRAM_ID=395803228
WEBHOOK_URL=https://<your-domain>.up.railway.app
DATABASE_PATH=/app/data/broadcaster.db
```

**Note:** This is a PUBLIC service - no API_SECRET needed! Anyone can connect via SDK.

### **Volume Mount:**
```
Mount Path: /app/data
```

---

## ❌ Troubleshooting

### **Build Failed?**
- Check **Logs** tab for error messages
- Make sure all environment variables are set correctly
- Verify `TELEGRAM_BOT_TOKEN` is valid (test with @BotFather)

### **Bot Not Responding?**
- Check **Logs** tab for errors
- Verify `WEBHOOK_URL` is set correctly (must include `https://`)
- Make sure domain is generated in Settings

### **Database Errors?**
- Ensure volume is mounted at `/app/data`
- Check `DATABASE_PATH` variable is set correctly

### **WebSocket Connection Failed?**
- Verify Railway domain is generated
- Check WebSocket URL format: `wss://<domain>/ws`
- Ensure `API_SECRET` matches in SDK constants

---

## ✅ Success Checklist

- [ ] Railway project created
- [ ] GitHub repo connected
- [ ] Telegram bot token obtained
- [ ] All environment variables set
- [ ] Railway domain generated
- [ ] Webhook URL configured
- [ ] Volume mounted at `/app/data`
- [ ] Logs show "Broadcaster ready!"
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] Telegram bot responds to `/start`
- [ ] SDK updated with production URL

---

## 🚀 Next Steps After Deployment

1. **Test signal broadcasting:**
   - Send `/signal BTCUSDT LONG Entry: Market TP: 50000 SL: 40000 Lev: 5x` to your bot
   - Check Railway logs for signal processing

2. **Distribute SDK to clients:**
   - Clients install: `pip install git+https://github.com/DecentralizedJM/Mudrex-Trade-Ideas_Automation-SDK.git`
   - Clients run: `signal-sdk setup`
   - Clients run: `signal-sdk start`

3. **Monitor:**
   - Check Railway logs regularly
   - Monitor SDK client connections
   - Track signal delivery success rate

---

**🎉 You're all set! Your broadcaster is live on Railway!**

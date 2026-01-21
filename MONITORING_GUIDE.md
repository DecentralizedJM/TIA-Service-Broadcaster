# 📊 Real-Time Monitoring Guide

## Overview

The broadcaster now includes comprehensive monitoring to track connected users and signal delivery in real-time.

---

## 🎯 Key Metrics Tracked

### 1. **Live Connections**
- Real-time WebSocket connections
- Active SDK clients receiving signals
- Connection timestamps
- Client identification

### 2. **Signal Delivery**
- Signals sent
- Signals delivered
- Delivery success rate
- Last 24h delivery stats

### 3. **Client Registration**
- Total registered clients
- Active clients in database
- Client connection history

---

## 📱 Telegram Admin Commands

### `/stats` - Quick Overview

Shows instant stats about your broadcaster:

```
📊 Broadcaster Statistics
━━━━━━━━━━━━━━━━━━━━

📡 Signals:
• Total Sent: 45
• Active Positions: 8
• Total Deliveries: 1,240
• Last 24h: 180 deliveries

👥 SDK Clients:
• 🟢 Live Now: 12
• Total Registered: 25
• Active in DB: 18

💡 Use /connectedusers for detailed info
━━━━━━━━━━━━━━━━━━━━
```

**What it shows:**
- **Live Now**: Real-time count of connected WebSocket clients
- **Total Registered**: All clients who ever registered
- **Active in DB**: Clients marked as active (even if not currently connected)

---

### `/connectedusers` - Detailed Connection Info

Shows all currently connected SDK clients:

```
👥 Connected Users (12)
━━━━━━━━━━━━━━━━━━━━

• sdk-abc123 (TG: 123456789)
  └ Connected: 2026-01-22 10:30

• sdk-def456
  └ Connected: 2026-01-22 09:15

• sdk-ghi789 (TG: 987654321)
  └ Connected: 2026-01-22 08:45

... and 9 more
```

**What it shows:**
- Client ID
- Telegram ID (if registered)
- Connection timestamp
- Truncated at 20 for readability

---

### `/activepositions` - Open Positions

Shows signals that haven't been closed yet:

```
📊 Active Positions (8)
━━━━━━━━━━━━━━━━━━━━

📈 SIG-220126-BTCUSDT-A1B2C3
   LONG BTCUSDT @ 45000
   SL: 43000 | TP: 48000
   Delivered to: 12 clients

📉 SIG-220126-ETHUSDT-D4E5F6
   SHORT ETHUSDT @ Market
   SL: NA | TP: NA
   Delivered to: 10 clients

...
```

---

## 🌐 HTTP API Endpoints

### `GET /` - Service Status

```bash
curl https://your-broadcaster.railway.app/
```

**Response:**
```json
{
  "service": "TIA Service Broadcaster",
  "version": "1.0.0",
  "status": "online",
  "stats": {
    "total_signals": 45,
    "active_signals": 8,
    "total_clients": 25,
    "active_clients": 18,
    "total_deliveries": 1240,
    "deliveries_24h": 180
  }
}
```

### `GET /health` - Health Check

```bash
curl https://your-broadcaster.railway.app/health
```

**Response:**
```json
{
  "status": "healthy"
}
```

---

## 📈 How It Works

### **Connection Tracking:**

1. **Client Connects:**
   ```
   SDK Client → WebSocket ws://broadcaster/ws?client_id=sdk-abc123
   ```

2. **Broadcaster Records:**
   ```python
   websocket_connections.add(websocket)
   websocket_clients[websocket] = "sdk-abc123"
   database.update_client_heartbeat("sdk-abc123")
   ```

3. **Real-Time Count:**
   ```python
   live_count = len(websocket_connections)  # Instant!
   ```

### **Signal Delivery Tracking:**

1. **Admin Broadcasts Signal:**
   ```
   You post: /signal BTCUSDT LONG Entry: 45000...
   ```

2. **Broadcaster Distributes:**
   ```python
   for websocket in websocket_connections:
       websocket.send_json(signal)
       database.record_signal_delivery(signal_id, client_id)
   ```

3. **Stats Updated:**
   ```
   Total deliveries incremented
   Per-signal delivery count tracked
   ```

---

## 🔍 Understanding the Metrics

### **Live Connections vs Active Clients**

| Metric | What It Means | Example |
|--------|---------------|---------|
| **Live Now** | Actually connected right now | 12 |
| **Total Registered** | Ever registered (lifetime) | 25 |
| **Active in DB** | Marked active (may be offline) | 18 |

**Scenario:**
- 25 users registered
- 18 are marked as "active" (haven't uninstalled)
- 12 are currently online and receiving signals

### **Signal Delivery Stats**

- **Total Deliveries**: All-time signal sends
- **Last 24h**: Deliveries in the past day
- **Per-Signal**: How many clients received each signal

---

## 💡 Use Cases

### **1. Check if Anyone is Listening**
```
You: /stats

Bot: 🟢 Live Now: 0

You: (No one connected yet, wait for users to start SDK)
```

### **2. Confirm Signal Reached Users**
After posting a signal:
```
Bot: 📡 Signal Broadcast Complete
     Broadcasted to 12 WebSocket clients
```

### **3. Identify Connected Users**
```
You: /connectedusers

Bot: Shows all 12 clients with their IDs
```

### **4. Track Growth Over Time**
```
Day 1: Live Now: 5
Day 2: Live Now: 12
Day 3: Live Now: 28
...
```

---

## 🚨 Troubleshooting

### **Issue: Live connections showing 0**

**Possible causes:**
1. No users have installed SDK yet
2. Users installed but haven't run `signal-sdk start`
3. WebSocket connection issues

**How to verify:**
```bash
# Check Railway logs
railway logs

# Look for:
"WebSocket client connected: sdk-abc123"
```

### **Issue: Connected users not receiving signals**

**Check:**
1. Railway logs for broadcast confirmation
2. Client-side SDK logs
3. WebSocket connection status

**Verify:**
```
You: /stats
Bot: 🟢 Live Now: 5  (Connections OK)

You: Post a signal
Bot: Broadcasted to 5 clients  (Delivery OK)
```

---

## 📊 Monitoring Best Practices

### **1. Regular Health Checks**
- Run `/stats` daily to monitor growth
- Check `/connectedusers` to verify active users
- Monitor Railway logs for errors

### **2. Signal Delivery Verification**
- After posting signals, verify delivery count matches live connections
- If mismatch, investigate WebSocket issues

### **3. Database Cleanup**
- Inactive clients remain in database (by design)
- Real-time connections are what matter

### **4. Scaling Considerations**
- Railway auto-scales based on connections
- Monitor if you exceed 100+ simultaneous connections
- Consider rate limiting if needed

---

## ✅ Summary

**Real-Time Monitoring Features:**
- ✅ Live WebSocket connection count
- ✅ Connected client identification
- ✅ Signal delivery tracking
- ✅ Per-signal delivery stats
- ✅ 24-hour delivery metrics
- ✅ Telegram admin commands
- ✅ HTTP API endpoints

**Admin Commands:**
- `/stats` - Quick overview
- `/connectedusers` - Detailed client info
- `/activepositions` - Open positions

**Everything you need to monitor your signal broadcaster in real-time!** 🚀

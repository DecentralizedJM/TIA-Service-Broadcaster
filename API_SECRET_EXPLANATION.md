# 🔐 API_SECRET Explained

## What is API_SECRET?

`API_SECRET` is a **shared secret** (like a password) that authenticates SDK clients when they connect to your broadcaster service.

---

## 🔒 Why Do We Need It?

### **Problem Without API_SECRET:**

```
┌─────────────────────────────────────────┐
│  Your Broadcaster (Public on Internet) │
│  wss://broadcaster.railway.app/ws      │
└──────────────┬──────────────────────────┘
               │
               │ Anyone can connect!
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐
│Hacker │ │Random │ │Your   │
│       │ │Person │ │Client │
└───────┘ └───────┘ └───────┘

❌ Everyone gets your signals!
❌ No control over who connects
❌ Service abuse possible
```

### **Solution With API_SECRET:**

```
┌─────────────────────────────────────────┐
│  Your Broadcaster (Protected)          │
│  wss://broadcaster.railway.app/ws       │
│                                         │
│  🔐 Checks: X-API-Secret header        │
└──────────────┬──────────────────────────┘
               │
               │ Only clients with correct secret!
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐
│Hacker │ │Random │ │Your   │
│❌ DENIED│ │❌ DENIED│ │✅ ALLOWED│
└───────┘ └───────┘ └───────┘
```

---

## 🔄 How It Works

### **Step 1: SDK Client Connects**

```python
# SDK sends API_SECRET in headers
headers = {
    "X-API-Secret": "eeojo2WLw3b4TC65K6WQXwp84f8OBpzmeQWmYb2rQB4"
}

websocket.connect(url, headers=headers)
```

### **Step 2: Broadcaster Verifies**

```python
# Broadcaster checks the secret
if x_api_secret != settings.api_secret:
    raise HTTPException(401, "Invalid API secret")  # ❌ Reject
else:
    # ✅ Allow connection
    websocket.accept()
```

### **Step 3: Connection Established**

```
✅ SDK client authenticated
✅ Can receive signals
✅ Can register with broadcaster
```

---

## 📍 Where It's Used

### **1. WebSocket Connection** (Real-time signals)

**SDK Side:**
```python
# tia_sdk/client.py
headers = {
    "X-API-Secret": self.config.broadcaster.api_secret
}
self.ws = await websockets.connect(url, extra_headers=headers)
```

**Broadcaster Side:**
```python
# src/broadcaster/api.py
@self.app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, x_api_secret: str = Header(...)):
    if x_api_secret != settings.api_secret:
        raise WebSocketDisconnect(code=1008, reason="Invalid API secret")
    await websocket.accept()  # ✅ Authenticated
```

### **2. REST API Endpoints** (Registration, Signal History)

**SDK Side:**
```python
# When registering or fetching signals
headers = {
    "X-API-Secret": "eeojo2WLw3b4TC65K6WQXwp84f8OBpzmeQWmYb2rQB4"
}
response = httpx.post(url, headers=headers)
```

**Broadcaster Side:**
```python
# src/broadcaster/api.py
async def verify_api_secret(x_api_secret: str = Header(...)):
    if x_api_secret != settings.api_secret:
        raise HTTPException(401, "Invalid API secret")
    return True

@app.post("/api/sdk/register")
async def register(authenticated: bool = Depends(verify_api_secret)):
    # Only runs if secret is correct
    ...
```

---

## 🔑 Key Points

### **1. Shared Secret Pattern**
- **Same secret** in both broadcaster (Railway) and SDK (client)
- Like a password that both sides know
- Not public - only you and your SDK clients have it

### **2. Where It Lives**

**Broadcaster (Railway):**
```
Environment Variable:
API_SECRET=eeojo2WLw3b4TC65K6WQXwp84f8OBpzmeQWmYb2rQB4
```

**SDK (Client Code):**
```python
# tia_sdk/constants.py
BROADCASTER_API_SECRET = "eeojo2WLw3b4TC65K6WQXwp84f8OBpzmeQWmYb2rQB4"
```

### **3. Security Benefits**

✅ **Access Control:** Only authorized clients connect
✅ **Signal Protection:** Your signals aren't public
✅ **Service Protection:** Prevents abuse/DoS
✅ **Client Tracking:** You know who's connected

---

## 🎯 Real-World Analogy

Think of `API_SECRET` like a **membership card**:

```
┌─────────────────────────────────────┐
│  EXCLUSIVE SIGNAL CLUB              │
│                                     │
│  🚪 Door Guard: "Show your card!"   │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐
│No Card│ │Wrong  │ │Valid  │
│❌ DENIED│ │Card ❌│ │Card ✅│
└───────┘ └───────┘ └───────┘
```

- **Without card:** Can't enter
- **Wrong card:** Rejected
- **Valid card:** Welcome! Receive signals

---

## 🔐 Security Best Practices

### **1. Generate Strong Secret**
```bash
# Use a long, random string (32+ characters)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### **2. Keep It Secret**
- ❌ Don't commit to public GitHub
- ❌ Don't share in public channels
- ✅ Only give to authorized SDK clients
- ✅ Store in environment variables

### **3. Rotate Periodically**
- Change secret every 3-6 months
- Update both Railway and SDK
- Revoke old secret

---

## 📊 Flow Diagram

```
┌─────────────────────────────────────────────┐
│  SDK CLIENT                                 │
│                                             │
│  1. Load API_SECRET from config            │
│  2. Connect to broadcaster                 │
│  3. Send: X-API-Secret: <secret>           │
└──────────────┬──────────────────────────────┘
               │
               │ HTTP/WebSocket Request
               │ Headers: X-API-Secret: ...
               │
               ▼
┌─────────────────────────────────────────────┐
│  BROADCASTER (Railway)                      │
│                                             │
│  1. Receive request                         │
│  2. Extract X-API-Secret header            │
│  3. Compare with stored API_SECRET         │
│                                             │
│  IF match:                                  │
│    ✅ Accept connection                     │
│    ✅ Allow access                          │
│                                             │
│  IF no match:                               │
│    ❌ Reject (401 Unauthorized)            │
│    ❌ Close connection                      │
└─────────────────────────────────────────────┘
```

---

## 💡 Summary

**API_SECRET is like a password that:**
- ✅ Protects your broadcaster from unauthorized access
- ✅ Ensures only your SDK clients can connect
- ✅ Prevents random people from receiving your signals
- ✅ Gives you control over who uses your service

**Without it:** Your service is public and unprotected
**With it:** Your service is secure and access-controlled

---

## 🚨 Important Notes

1. **Same Secret Everywhere:**
   - Railway environment variable
   - SDK constants file
   - Must match exactly!

2. **Not User Credentials:**
   - This is NOT the user's Mudrex API key
   - This is YOUR service's authentication secret
   - Users still provide their own Mudrex keys separately

3. **Pre-configured in SDK:**
   - Users don't need to know this secret
   - It's already in the SDK code
   - They just install and run

---

**Think of it as:** A bouncer at a club - only people with the right password get in! 🔐

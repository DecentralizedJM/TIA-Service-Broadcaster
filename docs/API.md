# API Documentation

## Authentication

All API endpoints (except `/health`) require authentication via `X-API-Secret` header:

```bash
curl -H "X-API-Secret: your_api_secret" https://broadcaster.railway.app/api/signals
```

## REST Endpoints

### GET `/`
Root endpoint with service info and statistics.

**Response:**
```json
{
  "service": "TIA Service Broadcaster",
  "version": "1.0.0",
  "status": "online",
  "stats": {
    "total_signals": 42,
    "active_signals": 5,
    "active_clients": 3,
    "total_deliveries": 126
  }
}
```

### GET `/health`
Health check (no authentication required).

**Response:**
```json
{
  "status": "healthy"
}
```

### POST `/api/sdk/register`
Register an SDK client.

**Request:**
```json
{
  "client_id": "unique-client-id",
  "telegram_id": 123456789  // Optional but recommended for admin notifications
}
```

**Response:**
```json
{
  "status": "registered",
  "client_id": "unique-client-id",
  "telegram_notifications": "enabled"  // If telegram_id provided
}
```

**Note:** Telegram ID enables admin to send notifications about your SDK's signal execution status. Useful for monitoring and debugging!

**Heartbeat:** No separate heartbeat endpoint needed! WebSocket ping/pong handles this automatically.

### GET `/api/signals`
Get signals.

**Query Parameters:**
- `active_only` (bool, default: true) - Only return active signals
- `limit` (int, default: 100) - Max number of signals

**Response:**
```json
{
  "signals": [
    {
      "signal_id": "SIG-200126-BTCUSDT-A1B2C3",
      "symbol": "BTCUSDT",
      "signal_type": "LONG",
      "order_type": "LIMIT",
      "entry_price": 45000,
      "stop_loss": 42000,
      "take_profit": 48000,
      "leverage": 10,
      "status": "ACTIVE",
      "created_at": "2026-01-20T10:30:00",
      "updated_at": "2026-01-20T10:30:00"
    }
  ],
  "count": 1
}
```

### GET `/api/signals/{signal_id}`
Get a specific signal by ID.

**Response:**
```json
{
  "signal": {
    "signal_id": "SIG-200126-BTCUSDT-A1B2C3",
    ...
  }
}
```

## WebSocket

### WS `/ws`
Real-time signal updates via WebSocket.

**Connection:**
```python
import websockets
import json

async with websockets.connect("ws://broadcaster/ws") as websocket:
    while True:
        message = await websocket.receive()
        data = json.loads(message)
        print(data)
```

**Message Types:**

#### NEW_SIGNAL
```json
{
  "type": "NEW_SIGNAL",
  "signal": {
    "signal_id": "SIG-200126-BTCUSDT-A1B2C3",
    "symbol": "BTCUSDT",
    "signal_type": "LONG",
    ...
  }
}
```

#### CLOSE_SIGNAL
```json
{
  "type": "CLOSE_SIGNAL",
  "signal_id": "SIG-200126-BTCUSDT-A1B2C3",
  "symbol": "BTCUSDT",
  "percentage": 100.0
}
```

#### EDIT_SLTP
```json
{
  "type": "EDIT_SLTP",
  "signal_id": "SIG-200126-BTCUSDT-A1B2C3",
  "symbol": "BTCUSDT",
  "stop_loss": 42500,
  "take_profit": 48500
}
```

#### UPDATE_LEVERAGE
```json
{
  "type": "UPDATE_LEVERAGE",
  "signal_id": "SIG-200126-BTCUSDT-A1B2C3",
  "symbol": "BTCUSDT",
  "leverage": 15
}
```

**Heartbeat:**
Send "ping" to keep connection alive:
```python
await websocket.send("ping")
# Receives: "pong"
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Invalid API secret"
}
```

### 404 Not Found
```json
{
  "detail": "Signal not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Registration failed"
}
```

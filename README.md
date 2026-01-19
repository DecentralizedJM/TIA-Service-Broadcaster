# TIA Service Broadcaster

**Signal Broadcasting Service for Mudrex Trade Ideas Automation**

A lightweight Telegram bot that broadcasts trading signals to connected SDK clients. Admins post signals via Telegram, and technical traders receive them via the SDK running on their local machines.

## 🎯 Purpose

- **Centralized Signal Distribution**: Admins broadcast signals from one place
- **Decentralized Execution**: Traders execute on their own machines with their own API keys
- **No API Key Storage**: Maximum security - keys never leave trader's machine
- **Real-time Updates**: WebSocket/webhook delivery to SDK clients

## 🏗️ Architecture

```
Admin (Telegram) → Broadcaster Bot → SDK Clients (Local)
                         ↓
                   Signal Database
                   (state tracking only)
```

## 🚀 Features

### Admin Commands (Telegram)
- `/signal` - Broadcast new trading signal
- `/close <ID> [%]` - Close position signal
- `/editsltp <ID>` - Update SL/TP
- `/leverage <ID> <lev>` - Update leverage
- `/activepositions` - List active signals
- `/broadcast <message>` - Broadcast message to SDK clients

### API Endpoints (for SDK)
- `POST /api/sdk/register` - Register SDK client (one-time, with optional Telegram ID)
- `WebSocket /ws` - Real-time signal stream (primary connection)
- `GET /api/signals` - Get all active signals (admin debugging only)
- `GET /api/signals/{signal_id}` - Get specific signal (admin debugging only)

## 📦 Installation

### Requirements
- Python 3.11+
- PostgreSQL or SQLite
- Telegram Bot Token

### Environment Variables
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id  # comma-separated for multiple
ENCRYPTION_SECRET=your_secret_key
DATABASE_URL=your_database_url
API_SECRET=shared_secret_for_sdk_auth
```

### Deploy to Railway
```bash
railway up
```

## 🔧 Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python -m src.broadcaster.run --polling

# Run tests
pytest tests/
```

## 📚 Documentation

- [API Documentation](docs/API.md)
- [Signal Format](docs/SIGNALS.md)
- [SDK Integration](docs/SDK.md)

## 🔒 Security

- **No API Keys Stored**: Broadcaster never stores Mudrex API keys
- **Encrypted Communication**: All SDK connections use shared secret
- **Admin-Only Commands**: Signal creation restricted to authorized admins
- **Rate Limiting**: Protection against abuse

## 🤝 Related Projects

- [Signal Automator SDK](https://github.com/DecentralizedJM/TIA-Service-SDK) - Client-side executor

## 📄 License

MIT License - See LICENSE file for details

## 👥 Authors

- [@DecentralizedJM](https://github.com/DecentralizedJM)

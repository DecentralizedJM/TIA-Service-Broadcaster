# Mudrex Trade Ideas Bot - Complete Documentation

**Version:** 2.0.0  
**Last Updated:** January 16, 2026  
**Branch:** Railway-staging

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [User Commands](#user-commands)
4. [Admin Commands](#admin-commands)
5. [Signal Formats](#signal-formats)
6. [Trade Execution Flow](#trade-execution-flow)
7. [Error Handling & Status Codes](#error-handling--status-codes)
8. [Expected Behaviors](#expected-behaviors)
9. [Background Tasks](#background-tasks)
10. [Database Schema](#database-schema)
11. [Rate Limiting & Capacity](#rate-limiting--capacity)
12. [Security](#security)
13. [Troubleshooting](#troubleshooting)

---

## System Overview

The Mudrex Trade Ideas Bot is a centralized Telegram bot that:
- Receives trading signals from admins in a designated channel
- Automatically executes trades on Mudrex Futures for all registered subscribers
- Supports both AUTO and MANUAL trade execution modes
- Encrypts and stores subscriber API keys securely
- Tracks trade history and statistics
- Provides real-time notifications to users

### Key Features

- **Centralized Signal Distribution**: One admin signal → executed for all subscribers
- **Parallel Execution**: Trades execute in parallel with rate limiting
- **Flexible Trade Modes**: AUTO (instant) or MANUAL (confirmation required)
- **Low Balance Handling**: Auto-adjusts trade amounts or skips if below minimum
- **Position Management**: Automatically skips signals if user already has open position
- **Daily Balance Checks**: Monitors subscriber balances twice daily and alerts if low
- **Secure Key Storage**: AES-128 encryption for API keys at rest

---

## Architecture

### Components

1. **Telegram Bot** (`telegram_bot.py`)
   - Handles user commands and messages
   - Processes signals from admin channel
   - Manages manual trade confirmations
   - Sends notifications with rate limiting

2. **Signal Parser** (`signal_parser.py`)
   - Parses various signal formats
   - Extracts trading parameters (symbol, direction, SL/TP, leverage)
   - Validates signal syntax

3. **Signal Broadcaster** (`broadcaster.py`)
   - Executes trades for all subscribers
   - Handles parallel execution with semaphore-based rate limiting
   - Manages balance checks and position validation
   - Converts errors to user-friendly messages

4. **Database** (`database.py`)
   - Stores subscriber data (encrypted API keys)
   - Tracks signals and trade history
   - Provides statistics and querying

5. **Crypto** (`crypto.py`)
   - Encrypts/decrypts API keys using Fernet (AES-128-CBC)
   - Secure key storage

6. **Server** (`server.py`)
   - FastAPI webhook server for Railway deployment
   - Non-blocking update processing

### Data Flow

```
Admin Channel Message
    ↓
Signal Parser (parse signal)
    ↓
Broadcast Signal
    ↓
For each subscriber:
    ├─ Check existing position → Skip if exists
    ├─ Check balance → Auto-adjust if low
    ├─ Validate symbol → Error if not found
    ├─ Set leverage
    ├─ Place order (MARKET or LIMIT)
    ├─ Record trade result
    └─ Send notification to user
```

---

## User Commands

All user commands work in **private DM** with the bot.

### `/start`
**Description:** Welcome message and status check

**Behavior:**
- If registered: Shows current settings (trade amount, leverage, total trades)
- If not registered: Shows welcome message with registration instructions

**Output Example:**
```
👋 Welcome back, John!

You're already registered.

**Your Settings:**
💰 Trade Amount: 50 USDT
⚡ Max Leverage: 10x
📊 Total Trades: 23
```

---

### `/register`
**Description:** Register your Mudrex account

**Flow:**
1. Bot asks for Mudrex API Key
2. User sends API Key
3. Bot asks for Mudrex API Secret
4. User sends API Secret
5. Bot asks for trade amount (or /skip for default)
6. Bot validates API credentials by checking balance
7. Bot saves encrypted keys and registers user

**Rate Limiting:** 5 attempts per 10 minutes per user

**Validation:**
- API Key: Must be alphanumeric, 32+ characters
- API Secret: Must be alphanumeric, 32+ characters
- Trade Amount: 1-10000 USDT (optional, defaults to 50 USDT)

**Default Settings:**
- Trade Amount: 50 USDT (or from `DEFAULT_TRADE_AMOUNT` env var)
- Max Leverage: 10x (or from `DEFAULT_MAX_LEVERAGE` env var)
- Trade Mode: AUTO

**Security:**
- API keys encrypted with Fernet before storage
- Messages containing keys are deleted after processing

---

### `/status`
**Description:** View your account status and settings

**Output:**
- Trade amount (USDT)
- Max leverage
- Total trades executed
- Total PnL
- Active status

**Requires:** Registration

---

### `/setamount <amount>`
**Description:** Change your trade amount per signal

**Parameters:**
- `<amount>`: Number between 1 and 10000 (USDT)

**Example:** `/setamount 100`

**Requires:** Registration

---

### `/setleverage <leverage>`
**Description:** Set maximum leverage cap

**Parameters:**
- `<leverage>`: Integer between 1 and 100

**Example:** `/setleverage 20`

**Behavior:**
- Applied cap on all future trades
- Actual leverage = min(signal_leverage, user_max_leverage)

**Requires:** Registration

---

### `/setmode <auto|manual>`
**Description:** Switch between AUTO and MANUAL trade modes

**Modes:**
- **AUTO**: Trades execute immediately when admin posts signal
- **MANUAL**: Bot sends confirmation request, user clicks "Execute Trade" to confirm

**Behavior:**
- Manual confirmations expire after 5 minutes
- Expired confirmations are automatically removed
- Background task checks every 30 seconds

**Requires:** Registration

---

### `/unregister`
**Description:** Delete your account and stop receiving signals

**Behavior:**
- Deletes subscriber record from database
- Encrypted API keys are permanently deleted
- User must re-register to use bot again

**Confirmation:** No confirmation required (instant deletion)

---

## Admin Commands

Admin commands work in **any chat** where the bot is present.

### `/adminstats`
**Description:** View system statistics

**Output:**
- Total subscribers
- Active subscribers
- Auto vs Manual mode counts
- Total trades executed
- Total PnL
- Active signals count
- Total signals count

**Restriction:** Admin only (verified by `ADMIN_TELEGRAM_ID`)

---

### `/activepositions`
**Description:** List all active signals with successful executions

**Behavior:**
- Only shows signals with `status = 'ACTIVE'`
- **Filter:** Must have at least one successful trade (SUCCESS or SUCCESS_REDUCED)
- Excludes signals where all subscribers failed

**Output Format:**
```
📊 Active Positions
━━━━━━━━━━━━━━━━━━━━

🆔 SIG-160126-BTCUSDT-ABC123
📈 LONG BTCUSDT
💵 Entry: 50000 | Lev: 10x
🛑 SL: 49000 | 🎯 TP: 52000
📅 2026-01-16
───────────────────
```

**Restriction:** Admin only

---

### `/message <text>`
**Description:** Broadcast a message to all active subscribers

**Behavior:**
- Sends message to all registered subscribers via DM
- Rate limited to 20 messages/second
- Runs in background task (non-blocking)

**Example:** `/message Important: Market update scheduled for tomorrow`

**Restriction:** Admin only

---

### `/chatid`
**Description:** Get the chat ID (useful for setup)

**Behavior:**
- Returns the current chat's ID
- Useful for finding `SIGNAL_CHANNEL_ID` during setup

**Works:** In any chat

---

## Signal Formats

Signals are posted by admin in the **designated signal channel**.

### New Signal

**Format 1: Inline Command**
```
/signal LONG BTCUSDT entry=50000 sl=49000 tp=52000 lev=10x
```

**Format 2: Multi-line Command**
```
/signal
BTCUSDT
LONG
Entry: 50000
SL: 49000
TP: 52000
Lev: 10x
```

**Format 3: Multi-line (No /signal prefix)**
```
BTCUSDT
LONG
Entry: Market
SL: NA
TP: NA
Lev: 10x
```

**Parameters:**
- **Symbol**: Any alphanumeric pair (2-15 characters), e.g., `BTCUSDT`, `XRPUSDT`, `DOGRUSDT`
- **Direction**: `LONG` or `SHORT`
- **Entry**: Price for limit orders, or `Market`/empty for market orders
- **SL (Stop Loss)**: Optional, can be `NA` or empty
- **TP (Take Profit)**: Optional, can be `NA` or empty
- **Lev (Leverage)**: Integer (1-100), defaults to 1 if not specified

**Notes:**
- SL and TP are optional (can be omitted or set to `NA`)
- Entry price determines order type: If specified = LIMIT, otherwise = MARKET
- Symbol must be supported on Mudrex (checked during execution)

---

### Close Signal

**Format:**
```
/close SIG-160126-BTCUSDT-ABC123
```

**Or:**
```
/close SIG-160126-BTCUSDT-ABC123 50%
```

**Behavior:**
- Closes positions for all AUTO mode subscribers
- Manual mode subscribers skipped
- If percentage specified (e.g., `50%`), closes partial position
- If no percentage, closes 100% of position

---

### Update Leverage

**Format:**
```
/leverage SIG-160126-BTCUSDT-ABC123 20x
```

**Behavior:**
- Updates leverage for all AUTO mode subscribers with open positions
- Manual mode subscribers skipped

---

### Edit SL/TP

**Format:**
```
/editsltp
SIG-160126-BTCUSDT-ABC123
SL: 49000
TP: 52000
```

**Parameters:**
- Can update just SL, just TP, or both
- Uses labeled parameters: `SL: <value>` and `TP: <value>`

**Behavior:**
- Updates SL/TP for all AUTO mode subscribers with open positions
- Manual mode subscribers skipped

---

## Trade Execution Flow

### AUTO Mode Flow

1. **Admin posts signal** → Bot parses signal
2. **Signal saved to database** with status `ACTIVE`
3. **For each AUTO subscriber**:
   - Check existing position → Skip if exists
   - Check balance → Auto-adjust if low
   - Validate symbol → Return error if not found
   - Set leverage (capped at user's max)
   - Place order (MARKET or LIMIT)
   - Record trade result
   - Send notification (if user-facing status)

4. **Admin receives broadcast summary**

### MANUAL Mode Flow

1. **Admin posts signal** → Bot parses signal
2. **Signal saved to database** with status `ACTIVE`
3. **For each MANUAL subscriber**:
   - Send confirmation message with inline buttons
   - Track confirmation (expires in 5 minutes)

4. **User clicks "Execute Trade"**:
   - Verify signal hasn't expired (5 minutes)
   - Reconstruct signal from database
   - Execute trade (same logic as AUTO)
   - Update message with result

5. **If user clicks "Skip"**:
   - Remove from pending confirmations
   - Show skip message

6. **If confirmation expires**:
   - Background task removes after 5 minutes
   - Message updated to show expiration

---

### Balance Handling

**Priority Order:**
1. **Check for existing position** → Skip if exists (POSITION_EXISTS)
2. **Check balance**:
   - If `balance <= 0` → INSUFFICIENT_BALANCE
   - If `balance < configured_amount` → Auto-adjust to available balance
   - Calculate notional value (margin × leverage)
   - If notional < MIN_ORDER_VALUE:
     - Check if can meet minimum → Adjust if possible
     - If cannot meet minimum → MIN_ORDER_NOT_MET

3. **Execute trade**:
   - If executed with reduced amount → SUCCESS_REDUCED
   - If executed with full amount → SUCCESS

**User Notifications:**
- **SUCCESS**: "✅ Trade Executed"
- **SUCCESS_REDUCED**: "✅ Trade Executed (Reduced Amount) - Please add funds"
- **INSUFFICIENT_BALANCE**: "No balance available (0 USDT)"
- **MIN_ORDER_NOT_MET**: "Tried to execute with available margin but minimum order value wasn't met"

**Admin Notifications:**
- **SYMBOL_NOT_FOUND**: Shown as count in summary (not sent to users)
- **API_ERROR**: Shown in summary with error details (not sent to users)

---

### Position Checking

**Behavior:**
- Before executing trade, bot checks for existing open positions
- If position exists for same symbol → Skip trade (POSITION_EXISTS)
- Applies to both AUTO and MANUAL modes
- Position check happens before balance check

**User Message:**
```
⏭️ Signal Skipped
━━━━━━━━━━━━━━━━━━━━
You already have an open position in BTCUSDT. Signal skipped to avoid duplicate positions.

Close your existing position first if you want to take this signal.
```

---

## Error Handling & Status Codes

### Trade Status Codes

| Status | Description | User Notified | Behavior |
|--------|-------------|---------------|----------|
| `SUCCESS` | Trade executed successfully | ✅ Yes | Order placed, SL/TP set if provided |
| `SUCCESS_REDUCED` | Trade executed with reduced amount (low balance) | ✅ Yes | Order placed with available balance |
| `INSUFFICIENT_BALANCE` | No balance (0 USDT) | ✅ Yes | Trade skipped, user notified |
| `MIN_ORDER_NOT_MET` | Balance too low even for minimum order | ✅ Yes | Trade skipped, user notified |
| `POSITION_EXISTS` | User already has open position | ✅ Yes | Trade skipped to avoid duplicates |
| `INVALID_KEY` | API key invalid or expired | ✅ Yes | User notified to re-register |
| `SYMBOL_NOT_FOUND` | Trading pair not available on Mudrex | ❌ No | Admin-only error, shown in summary |
| `API_ERROR` | Mudrex API error | ❌ No | Admin-only error, shown in summary |
| `PENDING_CONFIRMATION` | Waiting for manual confirmation | - | Manual mode only |
| `SKIPPED` | Trade skipped (manual mode, etc.) | - | Internal status |

### Error Handling Principles

1. **User-facing errors**: Only actionable errors are sent to users
   - SUCCESS, SUCCESS_REDUCED, INSUFFICIENT_BALANCE, MIN_ORDER_NOT_MET, INVALID_KEY, POSITION_EXISTS

2. **Admin-only errors**: Technical errors shown only in broadcast summary
   - SYMBOL_NOT_FOUND, API_ERROR

3. **Exception handling**:
   - All trade executions wrapped in try/except
   - Exceptions converted to TradeResult with API_ERROR status
   - Background tasks have error handlers

4. **Graceful degradation**:
   - If position check fails → Continue with trade (might be API issue)
   - If balance check fails → Return INSUFFICIENT_BALANCE
   - If symbol lookup fails → Return SYMBOL_NOT_FOUND

---

## Expected Behaviors

### Signal Processing

✅ **Expected:**
- Signal parsed correctly from various formats
- Signal saved to database with status ACTIVE
- All AUTO subscribers receive execution immediately
- All MANUAL subscribers receive confirmation requests

❌ **Not Expected:**
- Signals showing in `/activepositions` if all subscribers failed
- User notifications for admin errors (SYMBOL_NOT_FOUND, API_ERROR)

---

### Trade Execution

✅ **Expected (AUTO Mode):**
- Trade executes immediately when admin posts signal
- If position exists → Trade skipped with clear message
- If balance low → Trade executes with available balance (SUCCESS_REDUCED)
- If balance too low for minimum → Trade skipped with clear message (MIN_ORDER_NOT_MET)
- SL/TP set automatically if provided

✅ **Expected (MANUAL Mode):**
- User receives confirmation message with buttons
- User has 5 minutes to confirm
- After 5 minutes → Confirmation expires automatically
- User can click "Execute Trade" → Trade executes
- User can click "Skip" → Trade skipped

❌ **Not Expected:**
- Duplicate positions (position check prevents this)
- Trades executing with 0 balance
- Manual confirmations accepting after 5 minutes

---

### Balance Handling

✅ **Expected:**
- If balance >= configured amount → Trade executes with full amount (SUCCESS)
- If balance < configured amount but >= minimum → Trade executes with available balance (SUCCESS_REDUCED)
- If balance < minimum order value → Trade skipped (MIN_ORDER_NOT_MET)
- If balance = 0 → Trade skipped (INSUFFICIENT_BALANCE)

**Messages:**
- SUCCESS_REDUCED: "Trade executed with available amount. Please add funds to your futures wallet."
- MIN_ORDER_NOT_MET: "Tried to execute with available margin but minimum order value wasn't met. Please add funds."

---

### Position Management

✅ **Expected:**
- If user has open position in same symbol → Trade skipped (POSITION_EXISTS)
- User receives clear message about existing position
- Applies to both AUTO and MANUAL modes

---

### Low Balance Notifications

✅ **Expected:**
- Balance checked twice daily (every 12 hours)
- If balance < configured trade amount → User receives notification
- Notification includes:
  - Current balance
  - Configured amount
  - Instructions to add funds or reduce amount

**Frequency:** Twice per day (if balance remains low, user gets 2 notifications per day)

---

### Manual Mode Expiration

✅ **Expected:**
- Confirmation messages tracked with timestamp
- Background task checks every 30 seconds
- After 5 minutes → Message updated to show expiration
- Expired confirmations cannot be executed

---

### Error Notifications

✅ **User Receives:**
- Trade success/failure
- Low balance warnings
- Position exists (trade skipped)
- Invalid API key

❌ **User Does NOT Receive:**
- Symbol not found errors (admin-only)
- API errors (admin-only)
- Technical error details

---

### Database Consistency

✅ **Expected:**
- All trades recorded in `trade_history`
- `total_trades` incremented for SUCCESS and SUCCESS_REDUCED
- Signals marked as ACTIVE when created, CLOSED when `/close` executed
- Active signals query joins with trade_history to filter by success

---

## Background Tasks

### 1. Expiration Task
**Purpose:** Expire manual trade confirmations after 5 minutes

**Behavior:**
- Checks every 30 seconds
- Finds confirmations older than 5 minutes
- Updates message to show expiration
- Removes from tracking

**Error Handling:** Wrapped in error handler, logs critical errors

---

### 2. Balance Check Task
**Purpose:** Check subscriber balances twice daily and alert if low

**Behavior:**
- Waits 1 minute after startup before first check
- Checks every 12 hours
- For each subscriber:
  - Checks futures balance via Mudrex API
  - If balance < configured trade amount → Sends notification
  - Small delay (0.5s) between checks to avoid rate limits

**Notifications:**
- Sent if balance is lower than configured trade amount
- Includes current balance, configured amount, and instructions

**Error Handling:**
- Individual subscriber errors logged but don't stop task
- Task continues checking other subscribers
- Wrapped in error handler, logs critical errors

---

## Database Schema

### `subscribers` Table

| Column | Type | Description |
|--------|------|-------------|
| `telegram_id` | INTEGER | Primary key, Telegram user ID |
| `username` | TEXT | Telegram username (optional) |
| `api_key_encrypted` | TEXT | Encrypted Mudrex API Key |
| `api_secret_encrypted` | TEXT | Encrypted Mudrex API Secret |
| `trade_amount_usdt` | REAL | Amount per trade (USDT) |
| `max_leverage` | INTEGER | Maximum leverage cap |
| `is_active` | INTEGER | 1 = active, 0 = inactive |
| `trade_mode` | TEXT | 'AUTO' or 'MANUAL' |
| `created_at` | TEXT | ISO timestamp |
| `updated_at` | TEXT | ISO timestamp |
| `total_trades` | INTEGER | Count of successful trades |
| `total_pnl` | REAL | Total profit/loss |

---

### `signals` Table

| Column | Type | Description |
|--------|------|-------------|
| `signal_id` | TEXT | Primary key, e.g., SIG-160126-BTCUSDT-ABC123 |
| `symbol` | TEXT | Trading pair, e.g., BTCUSDT |
| `signal_type` | TEXT | 'LONG' or 'SHORT' |
| `order_type` | TEXT | 'MARKET' or 'LIMIT' |
| `entry_price` | REAL | Entry price (NULL for market orders) |
| `stop_loss` | REAL | Stop loss (0.0 if not set, stored as 0.0 in DB) |
| `take_profit` | REAL | Take profit (0.0 if not set, stored as 0.0 in DB) |
| `leverage` | INTEGER | Leverage multiplier |
| `status` | TEXT | 'ACTIVE' or 'CLOSED' |
| `created_at` | TEXT | ISO timestamp |
| `closed_at` | TEXT | ISO timestamp (NULL if active) |

**Note:** `stop_loss` and `take_profit` are stored as `0.0` in database when NULL (to satisfy NOT NULL constraint), converted back to `None` when reading.

---

### `trade_history` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `telegram_id` | INTEGER | Foreign key to subscribers |
| `signal_id` | TEXT | Foreign key to signals |
| `symbol` | TEXT | Trading pair |
| `side` | TEXT | 'LONG' or 'SHORT' |
| `order_type` | TEXT | 'MARKET' or 'LIMIT' |
| `quantity` | REAL | Order quantity |
| `entry_price` | REAL | Entry price |
| `status` | TEXT | Trade status (SUCCESS, SUCCESS_REDUCED, etc.) |
| `error_message` | TEXT | Error message if failed (NULL if success) |
| `executed_at` | TEXT | ISO timestamp |

**Indexes:**
- `idx_trade_history_telegram_id` on `telegram_id`
- `idx_trade_history_signal_id` on `signal_id`
- `idx_signals_status` on `status`

---

## Rate Limiting & Capacity

### Mudrex API Limits (per API key)

- **2 calls/second**
- **50 calls/minute**
- **1000 calls/hour**
- **10000 calls/day**

### System Rate Limiting

**Concurrent Trades:** Maximum 10 subscribers executing simultaneously
- Controlled by `asyncio.Semaphore(MAX_CONCURRENT_TRADES)`
- Each trade makes ~5-6 API calls:
  1. Check positions
  2. Get balance
  3. Get asset info
  4. Set leverage
  5. Place order
  6. Set SL/TP (if provided)

**Telegram Rate Limiting:**
- Notifications sent in batches of 20 messages/second
- 1 second delay between batches
- Runs in background tasks (non-blocking)

### Capacity Estimates

**Per Signal Broadcast:**
- 10 subscribers execute concurrently
- Each takes ~2.5-3 seconds (limited by 2 calls/sec per key)
- 100 subscribers: ~30 seconds total
- 500 subscribers: ~25-30 seconds total (as per code comment)
- 1000 subscribers: ~50-60 seconds total

**System Limits:**
- **Comfortable:** 500-1,000 subscribers per signal
- **Maximum:** 5,000+ subscribers (with longer processing times)

**Scaling Options:**
- Increase `MAX_CONCURRENT_TRADES` (currently 10)
- Optimize API calls (cache asset info)
- Horizontal scaling with subscriber sharding

---

## Security

### API Key Encryption

**Algorithm:** Fernet (AES-128-CBC)

**Process:**
1. User sends API key/secret via Telegram DM
2. Key encrypted using `ENCRYPTION_SECRET` (from environment)
3. Encrypted value stored in database
4. Original message deleted after processing

**Encryption Secret:**
- Must be at least 16 characters
- Should be unique per deployment
- Stored in environment variable (never in code)

### Security Features

1. **Parameterized SQL Queries**: Prevents SQL injection
2. **Rate Limiting**: Prevents abuse (5 registration attempts per 10 minutes)
3. **API Validation**: Validates API keys before saving
4. **Message Deletion**: Sensitive data deleted after processing
5. **Admin Verification**: Commands verified via `ADMIN_TELEGRAM_ID`

### Security Considerations

**Fixed Salt:**
- Encryption uses fixed salt: `b"mudrex_signal_bot_v2"`
- **Accepted Risk**: Changing salt would break decryption of all existing keys
- **Mitigation**: `ENCRYPTION_SECRET` is unique per deployment

**Key Rotation:**
- Not currently implemented
- Users must unregister and re-register to update keys
- **Future Enhancement**: Add `/rotatekeys` command

---

## Troubleshooting

### Common Issues

#### 1. Signal Not Executing

**Check:**
- Is user registered? (`/status`)
- Is user in AUTO mode? (`/setmode auto`)
- Does user have balance? (Check Mudrex account)
- Is symbol available on Mudrex? (Admin will see error in summary)

#### 2. Manual Mode Button Not Working

**Check:**
- Has 5 minutes passed? (Confirmations expire)
- Is signal still in database? (Check `/activepositions`)
- Check bot logs for errors

#### 3. Low Balance Notifications Not Received

**Check:**
- Balance check runs twice daily (every 12 hours)
- Notification sent only if balance < configured trade amount
- Check bot logs for balance check task

#### 4. Symbol Not Found Errors

**Behavior:**
- Admin sees error in broadcast summary
- Users do NOT receive notification (by design)
- Symbol may not be available on Mudrex Futures

#### 5. Trade Executing with Reduced Amount

**Expected Behavior:**
- If balance < configured amount but >= minimum order value
- Trade executes with available balance
- User receives SUCCESS_REDUCED notification

**To Fix:**
- Add funds to Mudrex Futures wallet, OR
- Reduce trade amount with `/setamount`

---

### Debugging

**Log Levels:**
- `INFO`: Normal operations (signals received, trades executed)
- `WARNING`: Non-critical issues (position check failed, balance low)
- `ERROR`: Trade failures, API errors
- `CRITICAL`: Background task crashes

**Key Log Messages:**
- `"Broadcasting signal {signal_id} to all subscribers"`
- `"Trade execution failed for {telegram_id}: {error}"`
- `"Balance check complete. {count}/{total} subscribers have low balance"`

---

## API Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Bot token from @BotFather |
| `ENCRYPTION_SECRET` | Yes | - | Secret for encrypting API keys (min 16 chars) |
| `ADMIN_TELEGRAM_ID` | Yes | - | Admin's Telegram user ID |
| `SIGNAL_CHANNEL_ID` | Yes | - | Channel/group ID where signals are posted |
| `WEBHOOK_URL` | No | None | Public URL for Telegram webhook |
| `WEBHOOK_PATH` | No | `/webhook` | Webhook endpoint path |
| `DEFAULT_TRADE_AMOUNT` | No | `50.0` | Default USDT amount per trade |
| `DEFAULT_MAX_LEVERAGE` | No | `10` | Default max leverage |
| `MIN_ORDER_VALUE` | No | `8.0` | Minimum order value (Mudrex requirement) |
| `ALLOW_REGISTRATION` | No | `true` | Enable/disable registration |
| `DATABASE_PATH` | No | `subscribers.db` | Path to SQLite database |

---

## Version History

### v2.0.0 (Current)
- Fixed indentation and try/except structure bugs
- Removed admin errors from user notifications
- Added exception handling to broadcast_close, broadcast_leverage, broadcast_edit_sl_tp
- Fixed `/activepositions` to only show signals with successful executions
- Improved admin broadcast summary (cleaner error reporting)
- Added error handling wrappers for background tasks
- Added webhook error handling

### Previous Fixes
- Fixed datetime shadowing bug in manual mode
- Fixed NULL constraint errors for SL/TP (None → 0.0 conversion)
- Added throttled notifications (20 msg/sec)
- Added rate limiting to close and leverage broadcasts
- Implemented non-blocking webhook processing
- Broadened signal parser symbol support

---

## Support

For issues or questions:
1. Check this documentation
2. Review bot logs (Railway dashboard)
3. Check `/adminstats` for system status
4. Verify environment variables are set correctly

---

**End of Documentation**

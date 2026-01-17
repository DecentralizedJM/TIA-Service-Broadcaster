#!/usr/bin/env python3
"""Add /help command to telegram_bot.py"""

help_method = '''
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display help information - different for admins and users."""
        user_id = update.effective_user.id
        is_admin = self._is_admin(user_id)
        
        if is_admin:
            # Admin Help
            help_text = """🤖 **Mudrex TradeIdeas Bot - Admin Commands**
━━━━━━━━━━━━━━━━━━━━

**📡 Signal Broadcasting:**
• `/signal` - Broadcast trading signals

**Format 1 - Multi-line:**
```
/signal
BTCUSDT
LONG
Entry: 45000
TP: 48000
SL: 42000
Lev: 10x
```

**Format 2 - Single-line:**
`/signal BTCUSDT LONG Entry: 45000 TP: 48000 SL: 42000 Lev: 10x`

**Format 3 - Market order:**
`/signal XRPUSDT SHORT Entry: Market TP: NA SL: NA Lev: 5x`

**Notes:**
- Entry: price or `Market`
- TP/SL: Use `NA` if not setting
- Lev: `5x`, `10x`, `20x`, etc.
- Each gets unique ID

**📊 Position Management:**
• `/close <ID> [%]` - Close positions
  `/close SIG-170126-BTCUSDT-A1B2C3`
  `/close SIG-170126-BTCUSDT-A1B2C3 50%`

• `/editsltp <ID>` - Edit SL/TP
```
/editsltp 
SIG-170126-BTCUSDT-A1B2C3
SL: 42000
TP: 48000
```

• `/leverage <ID> <lev>` - Update leverage
  `/leverage SIG-170126-BTCUSDT-A1B2C3 15x`

• `/activepositions` - Show active signals

**📢 Broadcasting:**
• `/message <text>` - Broadcast to subscribers

**📈 Statistics:**
• `/adminstats` - System statistics
• `/chatid` - Get chat/channel IDs
• `/help` - This message

━━━━━━━━━━━━━━━━━━━━
**Signal Behavior:**

AUTO Mode: Executes instantly
MANUAL Mode: "Execute" button (10 min)

**User Notifications:**
✅ Success/Low balance/Position exists
❌ Admin errors NOT sent to users

**Background:**
• Balance check: Every 12 hours
• Confirmation cleanup: Every 30 sec"""
        else:
            # User Help
            help_text = """🤖 **Mudrex TradeIdeas Bot - User Guide**
━━━━━━━━━━━━━━━━━━━━

**Getting Started:**

`/register` - Start registration
1. Mudrex API Key
2. Mudrex API Secret  
3. Trade amount (USDT/signal)

**Your Commands:**

• `/status` - View settings
  API status, trade amount, leverage, mode, trades

• `/setamount <amount>` - Change trade amount
  `/setamount 50` (50 USDT per signal)

• `/setleverage <max>` - Max leverage
  `/setleverage 10` (max 10x)

• `/setmode <AUTO|MANUAL>` - Execution mode
  
  **AUTO:** ⚡ Instant execution
  **MANUAL:** 👆 "Execute" button (10 min)

• `/unregister` - Remove account
• `/help` - This message

━━━━━━━━━━━━━━━━━━━━
**How It Works:**

📡 **Signals:**
1. Admin broadcasts
2. You receive notification
3. AUTO: Executes instantly
4. MANUAL: Shows button

💰 **Balance:**
- Auto balance checks
- Low balance? Reduces order size
- Daily warnings if needed

🛡️ **Safety:**
- No duplicate positions
- Respects max leverage
- Encrypted API keys
- Balance protection

━━━━━━━━━━━━━━━━━━━━
**Common Scenarios:**

💰 **Low Balance:**
"Order executed with reduced amount"
→ Top up wallet OR lower trade amount

⏭️ **Position Exists:**
"Position in BTCUSDT. Signal skipped"
→ Prevents duplicates (safety)

━━━━━━━━━━━━━━━━━━━━
**Tips:**
🔹 Start small to test
🔹 Use MANUAL mode initially
🔹 Check `/status` regularly  
🔹 Keep wallet funded
🔹 Set appropriate max leverage

**Questions?** Ask your admin!"""
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
'''

# Read file
with open('src/signal_bot/telegram_bot.py', 'r') as f:
    lines = f.readlines()

# Find insertion point (after chatid_command)
for i, line in enumerate(lines):
    if 'async def chatid_command' in line:
        # Find the end of this method (next async def or class end)
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith('async def') and not lines[j].strip().startswith('class '):
            j += 1
        # Insert help_command before next method
        lines.insert(j, help_method + '\n')
        print(f"Inserted help_command at line {j}")
        break

# Find CommandHandler("chatid") and add help handler after it
for i, line in enumerate(lines):
    if 'CommandHandler("chatid"' in line:
        lines.insert(i + 1, '        self.app.add_handler(CommandHandler("help", self.help_command))\n')
        print(f"Added CommandHandler at line {i+1}")
        break

# Write back
with open('src/signal_bot/telegram_bot.py', 'w') as f:
    f.writelines(lines)

print("✅ Successfully added /help command!")

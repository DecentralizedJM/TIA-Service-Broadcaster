"""
Telegram Bot - Admin commands only for signal broadcasting.

This bot only handles signal distribution, no trade execution!
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from typing import TYPE_CHECKING

from .settings import Settings
from .database import Database
from .signal_parser import SignalParser, format_signal_summary
from .models import Signal, SignalClose, SignalEditSLTP, SignalLeverage, SignalStatus

if TYPE_CHECKING:
    from .api import BroadcasterAPI

logger = logging.getLogger(__name__)


class BroadcasterBot:
    """Telegram bot for signal broadcasting (admin commands only)."""
    
    def __init__(self, settings: Settings, database: Database, api: 'BroadcasterAPI'):
        self.settings = settings
        self.db = database
        self.api = api
        self.app: Application = None
        
        logger.info(f"BroadcasterBot initialized - Admins: {settings.admin_ids}")
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return user_id in self.settings.admin_ids
    
    def build_application(self):
        """Build the Telegram application with handlers."""
        self.app = Application.builder().token(self.settings.telegram_bot_token).build()
        
        # Admin commands
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("activepositions", self.active_positions_command))
        
        # Signal parsing - listen to channel messages
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.message_handler
            )
        )
        
        logger.info("Telegram bot handlers registered")
    
    async def setup_webhook(self):
        """Set up webhook for production."""
        if self.settings.full_webhook_url:
            await self.app.bot.set_webhook(self.settings.full_webhook_url)
            logger.info(f"Webhook set: {self.settings.full_webhook_url}")
        else:
            logger.warning("No webhook URL configured")
    
    # ==================== Command Handlers ====================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text(
            "🤖 **TIA Service Broadcaster**\n\n"
            "Signal broadcasting service for Mudrex Trade Ideas.\n\n"
            "**Admin Commands:**\n"
            "/help - Command list\n"
            "/stats - System statistics\n"
            "/activepositions - Active signals\n\n"
            "**Broadcast Signals:**\n"
            "Post signals in this format:\n"
            "```\n"
            "/signal BTCUSDT LONG\n"
            "Entry: 45000\n"
            "TP: 48000\n"
            "SL: 42000\n"
            "Lev: 10x\n"
            "```\n\n"
            "SDK clients will receive signals automatically!",
            parse_mode="Markdown"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._is_admin(update.effective_user.id):
            return
        
        help_text = """🤖 **TIA Service Broadcaster - Admin Commands**
━━━━━━━━━━━━━━━━━━━━

**📡 Signal Broadcasting:**
• `/signal` - Broadcast new signal
  `/signal BTCUSDT LONG Entry: 45000 TP: 48000 SL: 42000 Lev: 10x`

**📊 Position Management:**
• `/close <ID> [%]` - Close position
  `/close SIG-170126-BTCUSDT-A1B2C3`
  `/close SIG-170126-BTCUSDT-A1B2C3 50%`

• `/editsltp <ID>` - Update SL/TP
  `/editsltp SIG-170126-BTCUSDT-A1B2C3`
  `SL: 42000`
  `TP: 48000`

• `/leverage <ID> <lev>` - Update leverage
  `/leverage SIG-170126-BTCUSDT-A1B2C3 15x`

• `/activepositions` - Show active signals

**📈 System:**
• `/stats` - Broadcaster statistics
• `/help` - This message

━━━━━━━━━━━━━━━━━━━━
All signals are automatically broadcasted to connected SDK clients!"""
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - broadcaster statistics."""
        if not self._is_admin(update.effective_user.id):
            return
        
        stats = await self.db.get_stats()
        
        stats_text = f"""📊 **Broadcaster Statistics**
━━━━━━━━━━━━━━━━━━━━

📡 **Signals:**
• Total: {stats.get('total_signals', 0)}
• Active: {stats.get('active_signals', 0)}
• Delivered: {stats.get('total_deliveries', 0)}

👥 **SDK Clients:**
• Connected: {stats.get('active_clients', 0)}

━━━━━━━━━━━━━━━━━━━━"""
        
        await update.message.reply_text(stats_text, parse_mode="Markdown")
    
    async def active_positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /activepositions command."""
        if not self._is_admin(update.effective_user.id):
            return
        
        signals = await self.db.get_active_signals()
        
        if not signals:
            await update.message.reply_text(
                "📊 **No Active Signals**\n\n"
                "There are currently no active signals.",
                parse_mode="Markdown"
            )
            return
        
        lines = ["📊 **Active Signals**", "━━━━━━━━━━━━━━━━━━━━"]
        
        for sig in signals:
            signal_id = sig.get("signal_id", "Unknown")
            symbol = sig.get("symbol", "Unknown")
            signal_type = sig.get("signal_type", "Unknown")
            entry = sig.get("entry_price") or "Market"
            sl = sig.get("stop_loss") or "Not set"
            tp = sig.get("take_profit") or "Not set"
            leverage = sig.get("leverage", 1)
            
            lines.append(f"\n🆔 `{signal_id}`")
            lines.append(f"📈 {signal_type} **{symbol}**")
            lines.append(f"💵 Entry: {entry} | Lev: {leverage}x")
            lines.append(f"🛑 SL: {sl} | 🎯 TP: {tp}")
            lines.append("───────────────────")
        
        lines.append(f"\n**Total: {len(signals)} active signal(s)**")
        
        response = "\n".join(lines)
        
        if len(response) > 4000:
            response = response[:3900] + "\n\n... (truncated)"
        
        await update.message.reply_text(response, parse_mode="Markdown")
    
    # ==================== Message Handler ====================
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages (signal commands)."""
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        
        # Only admins can broadcast signals
        if not self._is_admin(user_id):
            return
        
        message_text = update.message.text.strip()
        
        # Parse signal command
        try:
            parsed = SignalParser.parse(message_text)
            
            if isinstance(parsed, Signal):
                await self._handle_new_signal(update, parsed)
            elif isinstance(parsed, SignalClose):
                await self._handle_close_signal(update, parsed)
            elif isinstance(parsed, SignalEditSLTP):
                await self._handle_edit_sl_tp(update, parsed)
            elif isinstance(parsed, SignalLeverage):
                await self._handle_leverage_update(update, parsed)
        
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error processing signal: {str(e)}"
            )
    
    async def _handle_new_signal(self, update: Update, signal: Signal):
        """Handle new signal broadcast."""
        # Save signal to database
        success = await self.db.save_signal(signal)
        
        if not success:
            await update.message.reply_text("❌ Failed to save signal")
            return
        
        # Send confirmation to admin
        summary = format_signal_summary(signal)
        await update.message.reply_text(summary, parse_mode="Markdown")
        
        # Broadcast to SDK clients via API
        await self.api.broadcast_signal(signal)
        
        logger.info(f"Signal broadcasted: {signal.signal_id}")
    
    async def _handle_close_signal(self, update: Update, close: SignalClose):
        """Handle close signal command."""
        # Verify signal exists
        signal = await self.db.get_signal(close.signal_id)
        if not signal:
            await update.message.reply_text(f"❌ Signal {close.signal_id} not found")
            return
        
        # Update signal status
        await self.db.update_signal_status(close.signal_id, SignalStatus.CLOSED)
        
        # Broadcast close command to SDK clients
        await self.api.broadcast_close(close)
        
        percent_str = f" {close.percentage:.0f}%" if close.percentage < 100 else ""
        await update.message.reply_text(
            f"✅ Close signal{percent_str} broadcasted for {close.signal_id}",
            parse_mode="Markdown"
        )
        
        logger.info(f"Close broadcasted: {close.signal_id}")
    
    async def _handle_edit_sl_tp(self, update: Update, edit: SignalEditSLTP):
        """Handle SL/TP edit command."""
        # Verify signal exists
        signal = await self.db.get_signal(edit.signal_id)
        if not signal:
            await update.message.reply_text(f"❌ Signal {edit.signal_id} not found")
            return
        
        # Update signal in database
        await self.db.update_signal_sl_tp(edit.signal_id, edit.stop_loss, edit.take_profit)
        
        # Broadcast update to SDK clients
        await self.api.broadcast_edit_sl_tp(edit)
        
        sl_str = f"SL: {edit.stop_loss}" if edit.stop_loss else ""
        tp_str = f"TP: {edit.take_profit}" if edit.take_profit else ""
        sep = " & " if sl_str and tp_str else ""
        
        await update.message.reply_text(
            f"✅ SL/TP update broadcasted\n"
            f"🆔 {edit.signal_id}\n"
            f"Values: {sl_str}{sep}{tp_str}",
            parse_mode="Markdown"
        )
        
        logger.info(f"SL/TP update broadcasted: {edit.signal_id}")
    
    async def _handle_leverage_update(self, update: Update, lev: SignalLeverage):
        """Handle leverage update command."""
        # Verify signal exists
        signal = await self.db.get_signal(lev.signal_id)
        if not signal:
            await update.message.reply_text(f"❌ Signal {lev.signal_id} not found")
            return
        
        # Update signal in database
        await self.db.update_signal_leverage(lev.signal_id, lev.leverage)
        
        # Broadcast update to SDK clients
        await self.api.broadcast_leverage(lev)
        
        await update.message.reply_text(
            f"✅ Leverage update broadcasted\n"
            f"🆔 {lev.signal_id}\n"
            f"Leverage: {lev.leverage}x",
            parse_mode="Markdown"
        )
        
        logger.info(f"Leverage update broadcasted: {lev.signal_id}")

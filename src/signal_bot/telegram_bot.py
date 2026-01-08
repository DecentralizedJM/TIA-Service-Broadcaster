"""
Telegram Bot - Centralized signal bot with webhook support.

This bot:
1. Receives signals from admin in the signal channel
2. Handles user registration via DM
3. Broadcasts trades to all subscribers
4. Notifies users of execution results
"""

import asyncio
import json
import logging
from typing import Optional

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)

from .signal_parser import (
    SignalParser,
    Signal,
    SignalUpdate,
    SignalClose,
    SignalParseError,
    format_signal_summary,
)
from .broadcaster import (
    SignalBroadcaster,
    TradeStatus,
    format_broadcast_summary,
    format_user_trade_notification,
)
from .database import Database
from .settings import Settings

logger = logging.getLogger(__name__)

# Conversation states for registration
AWAITING_API_KEY, AWAITING_API_SECRET, AWAITING_AMOUNT = range(3)


class SignalBot:
    """
    Centralized Telegram Signal Bot.
    
    - Admin posts signals in channel → executes for all subscribers
    - Users DM to register with their Mudrex API keys
    - All API keys encrypted at rest
    """
    
    def __init__(self, settings: Settings, database: Database):
        """
        Initialize the signal bot.
        
        Args:
            settings: Application settings
            database: Database instance
        """
        self.settings = settings
        self.db = database
        self.broadcaster = SignalBroadcaster(database)
        self.app: Optional[Application] = None
        self.bot: Optional[Bot] = None
        
        logger.info(f"SignalBot initialized - Admin: {settings.admin_telegram_id}")
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is the admin."""
        return user_id == self.settings.admin_telegram_id
    
    def _is_signal_channel(self, chat_id: int) -> bool:
        """Check if message is from the signal channel."""
        return chat_id == self.settings.signal_channel_id
    
    # ==================== User Commands ====================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        
        # Check if already registered
        subscriber = await self.db.get_subscriber(user.id)
        
        if subscriber and subscriber.is_active:
            await update.message.reply_text(
                f"👋 Welcome back, {user.first_name}!\n\n"
                f"You're already registered.\n\n"
                f"**Your Settings:**\n"
                f"💰 Trade Amount: {subscriber.trade_amount_usdt} USDT\n"
                f"⚡ Max Leverage: {subscriber.max_leverage}x\n"
                f"📊 Total Trades: {subscriber.total_trades}\n\n"
                f"**Commands:**\n"
                f"/status - View your settings\n"
                f"/setamount - Change trade amount\n"
                f"/setleverage - Change max leverage\n"
                f"/unregister - Stop receiving signals",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"🤖 **Mudrex TradeIdeas Bot**\n\n"
                f"Welcome, {user.first_name}!\n\n"
                f"I auto-execute trading signals on your Mudrex account.\n\n"
                f"**To get started:**\n"
                f"/register - Connect your Mudrex account\n\n"
                f"**You'll need:**\n"
                f"• Mudrex API Key\n"
                f"• Mudrex API Secret\n\n"
                f"🔒 Your API keys are encrypted and stored securely.",
                parse_mode="Markdown"
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        user = update.effective_user
        subscriber = await self.db.get_subscriber(user.id)
        
        if not subscriber or not subscriber.is_active:
            await update.message.reply_text(
                "❌ You're not registered.\n\nUse /register to get started."
            )
            return
        
        await update.message.reply_text(
            f"📊 **Your Status**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Trade Amount: **{subscriber.trade_amount_usdt} USDT**\n"
            f"⚡ Max Leverage: **{subscriber.max_leverage}x**\n"
            f"📈 Total Trades: **{subscriber.total_trades}**\n"
            f"💵 Total PnL: **${subscriber.total_pnl:.2f}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Status: Active",
            parse_mode="Markdown"
        )
    
    # ==================== Registration Flow ====================
    
    async def register_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start registration - ask for API key."""
        if not self.settings.allow_registration:
            await update.message.reply_text(
                "❌ Registration is currently closed."
            )
            return ConversationHandler.END
        
        # Check if already registered
        subscriber = await self.db.get_subscriber(update.effective_user.id)
        if subscriber and subscriber.is_active:
            await update.message.reply_text(
                "⚠️ You're already registered!\n\n"
                "Use /unregister first if you want to re-register."
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            "🔑 **Registration Step 1/3**\n\n"
            "Please send your **Mudrex API Key**.\n\n"
            "You can get this from:\n"
            "Mudrex → Settings → API Keys\n\n"
            "🔒 Your key will be encrypted.\n\n"
            "/cancel to abort",
            parse_mode="Markdown"
        )
        return AWAITING_API_KEY
    
    async def register_api_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive API key, ask for secret."""
        api_key = update.message.text.strip()
        
        # Basic validation
        if len(api_key) < 10:
            await update.message.reply_text(
                "❌ That doesn't look like a valid API key.\n"
                "Please try again or /cancel"
            )
            return AWAITING_API_KEY
        
        # Store temporarily
        context.user_data['api_key'] = api_key
        
        # Delete the message with the API key for security
        try:
            await update.message.delete()
        except:
            pass
        
        await update.message.reply_text(
            "✅ API Key received!\n\n"
            "🔐 **Registration Step 2/3**\n\n"
            "Now send your **Mudrex API Secret**.\n\n"
            "🔒 Your secret will be encrypted.\n\n"
            "/cancel to abort",
            parse_mode="Markdown"
        )
        return AWAITING_API_SECRET
    
    async def register_api_secret(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive API secret, ask for trade amount."""
        api_secret = update.message.text.strip()
        
        # Basic validation
        if len(api_secret) < 10:
            await update.message.reply_text(
                "❌ That doesn't look like a valid API secret.\n"
                "Please try again or /cancel"
            )
            return AWAITING_API_SECRET
        
        # Store temporarily
        context.user_data['api_secret'] = api_secret
        
        # Delete the message with the secret for security
        try:
            await update.message.delete()
        except:
            pass
        
        await update.message.reply_text(
            "✅ API Secret received!\n\n"
            "💰 **Registration Step 3/3**\n\n"
            "How much **USDT** do you want to trade per signal?\n\n"
            f"Default: {self.settings.default_trade_amount} USDT\n\n"
            "Send a number (e.g., `50` or `100`) or /skip for default\n\n"
            "/cancel to abort",
            parse_mode="Markdown"
        )
        return AWAITING_AMOUNT
    
    async def register_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive trade amount, complete registration."""
        text = update.message.text.strip()
        
        # Parse amount
        try:
            amount = float(text)
            if amount < 1:
                raise ValueError("Too small")
            if amount > 10000:
                raise ValueError("Too large")
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid amount between 1 and 10000.\n"
                "Or use /skip for default."
            )
            return AWAITING_AMOUNT
        
        # Complete registration
        return await self._complete_registration(update, context, amount)
    
    async def register_skip_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip amount, use default."""
        return await self._complete_registration(
            update, context, self.settings.default_trade_amount
        )
    
    async def _complete_registration(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        amount: float
    ):
        """Complete the registration process."""
        user = update.effective_user
        api_key = context.user_data.get('api_key')
        api_secret = context.user_data.get('api_secret')
        
        if not api_key or not api_secret:
            await update.message.reply_text(
                "❌ Registration failed. Please try again with /register"
            )
            return ConversationHandler.END
        
        # Validate API credentials by making a test call
        await update.message.reply_text("🔄 Validating your API credentials...")
        
        try:
            import asyncio
            from mudrex import MudrexClient
            
            def validate_api(secret: str):
                """Sync validation - runs in thread."""
                client = MudrexClient(api_secret=secret)
                return client.wallet.get_futures_balance()
            
            # Run in thread with 15 second timeout
            try:
                balance = await asyncio.wait_for(
                    asyncio.to_thread(validate_api, api_secret),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                await update.message.reply_text(
                    "❌ **Validation timed out!**\n\n"
                    "The API request took too long. Please check:\n"
                    "1. Your API secret is correct\n"
                    "2. Mudrex API is accessible\n\n"
                    "Try again with /register",
                    parse_mode="Markdown"
                )
                return ConversationHandler.END
            
            if balance is None:
                await update.message.reply_text(
                    "❌ **Invalid API credentials!**\n\n"
                    "Could not connect to Mudrex. Please check:\n"
                    "1. Your API secret is correct\n"
                    "2. API has Futures trading permission\n\n"
                    "Try again with /register",
                    parse_mode="Markdown"
                )
                return ConversationHandler.END
                
            logger.info(f"API validated for {user.id}: Balance = {balance.balance} USDT")
            
        except Exception as e:
            logger.error(f"API validation failed for {user.id}: {e}")
            # Don't use Markdown - error messages may contain special chars
            await update.message.reply_text(
                f"❌ API validation failed!\n\n"
                f"Error: {str(e)[:100]}\n\n"
                f"Please check your credentials and try /register again."
            )
            return ConversationHandler.END
        
        # Save to database (encrypted)
        try:
            subscriber = await self.db.add_subscriber(
                telegram_id=user.id,
                username=user.username,
                api_key=api_key,
                api_secret=api_secret,
                trade_amount_usdt=amount,
                max_leverage=self.settings.default_max_leverage,
            )
            
            # Clear temporary data
            context.user_data.clear()
            
            await update.message.reply_text(
                f"🎉 Registration Complete!\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Trade Amount: {amount} USDT\n"
                f"⚡ Max Leverage: {self.settings.default_max_leverage}x\n"
                f"🤖 Mode: AUTO (trades execute automatically)\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ IMPORTANT WARNING ⚠️\n"
                f"When Mudrex Trading Team publishes a trade idea, "
                f"it will be AUTO-EXECUTED in your Mudrex Futures account!\n\n"
                f"📊 Your funds are at risk. Only use amounts you can afford to lose.\n\n"
                f"Commands:\n"
                f"/status - View your settings\n"
                f"/setamount - Change trade amount\n"
                f"/setleverage - Change max leverage\n"
                f"/setmode - Switch between auto/manual mode\n"
                f"/unregister - Stop receiving signals"
            )
            
            logger.info(f"New subscriber registered: {user.id} (@{user.username})")
            
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            await update.message.reply_text(
                f"❌ Registration failed: {e}\n\nPlease try again with /register"
            )
        
        return ConversationHandler.END
    
    async def register_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel registration."""
        context.user_data.clear()
        await update.message.reply_text("❌ Registration cancelled.")
        return ConversationHandler.END
    
    # ==================== Settings Commands ====================
    
    async def setamount_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setamount command."""
        user = update.effective_user
        subscriber = await self.db.get_subscriber(user.id)
        
        if not subscriber or not subscriber.is_active:
            await update.message.reply_text("❌ You're not registered. Use /register first.")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                f"💰 Current trade amount: **{subscriber.trade_amount_usdt} USDT**\n\n"
                f"Usage: `/setamount <amount>`\n"
                f"Example: `/setamount 100`",
                parse_mode="Markdown"
            )
            return
        
        try:
            amount = float(args[0])
            if amount < 1 or amount > 10000:
                raise ValueError("Out of range")
            
            await self.db.update_trade_amount(user.id, amount)
            await update.message.reply_text(
                f"✅ Trade amount updated to **{amount} USDT**",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid amount between 1 and 10000")
    
    async def setleverage_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setleverage command."""
        user = update.effective_user
        subscriber = await self.db.get_subscriber(user.id)
        
        if not subscriber or not subscriber.is_active:
            await update.message.reply_text("❌ You're not registered. Use /register first.")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                f"⚡ Current max leverage: **{subscriber.max_leverage}x**\n\n"
                f"Usage: `/setleverage <amount>`\n"
                f"Example: `/setleverage 10`",
                parse_mode="Markdown"
            )
            return
        
        try:
            leverage = int(args[0])
            if leverage < 1 or leverage > 125:
                raise ValueError("Out of range")
            
            await self.db.update_max_leverage(user.id, leverage)
            await update.message.reply_text(
                f"✅ Max leverage updated to **{leverage}x**",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid leverage between 1 and 125")
    
    async def unregister_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unregister command."""
        user = update.effective_user
        
        success = await self.db.deactivate_subscriber(user.id)
        
        if success:
            await update.message.reply_text(
                "✅ You've been unregistered.\n\n"
                "You will no longer receive trading signals.\n"
                "Use /register to sign up again."
            )
        else:
            await update.message.reply_text("❌ You're not registered.")
    
    async def setmode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setmode command to switch between AUTO and MANUAL trade modes."""
        user = update.effective_user
        subscriber = await self.db.get_subscriber(user.id)
        
        if not subscriber or not subscriber.is_active:
            await update.message.reply_text("❌ You're not registered. Use /register first.")
            return
        
        args = context.args
        if not args:
            mode_emoji = "🤖" if subscriber.trade_mode == "AUTO" else "👆"
            await update.message.reply_text(
                f"{mode_emoji} Current trade mode: **{subscriber.trade_mode}**\n\n"
                f"**Available modes:**\n"
                f"🤖 `AUTO` - Trades execute automatically\n"
                f"👆 `MANUAL` - You'll be asked to confirm each trade\n\n"
                f"Usage: `/setmode auto` or `/setmode manual`",
                parse_mode="Markdown"
            )
            return
        
        mode = args[0].upper()
        if mode not in ["AUTO", "MANUAL"]:
            await update.message.reply_text(
                "❌ Invalid mode. Use `/setmode auto` or `/setmode manual`",
                parse_mode="Markdown"
            )
            return
        
        await self.db.update_trade_mode(user.id, mode)
        
        if mode == "AUTO":
            await update.message.reply_text(
                "🤖 **Trade mode set to AUTO**\n\n"
                "Trades will be executed automatically when signals are published.\n\n"
                "⚠️ Make sure you trust the signal source!",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "👆 **Trade mode set to MANUAL**\n\n"
                "You'll receive a confirmation prompt for each trade signal.\n\n"
                "You can approve or reject each trade individually.",
                parse_mode="Markdown"
            )
    
    # ==================== Admin Commands ====================
    
    async def admin_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command (admin only)."""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin only command.")
            return
        
        stats = await self.db.get_subscriber_stats()
        
        await update.message.reply_text(
            f"📊 **Bot Statistics**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Total Subscribers: {stats['total']}\n"
            f"✅ Active: {stats['active']}\n"
            f"🤖 AUTO Mode: {stats['auto_mode']}\n"
            f"👆 MANUAL Mode: {stats['manual_mode']}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
    
    async def admin_broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command (admin only)."""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin only command.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📢 **Broadcast Message**\n\n"
                "Usage: `/broadcast <message>`\n\n"
                "This will send a message to all active subscribers.",
                parse_mode="Markdown"
            )
            return
        
        message = " ".join(context.args)
        subscribers = await self.db.get_active_subscribers()
        
        sent = 0
        failed = 0
        
        for sub in subscribers:
            try:
                await self.bot.send_message(
                    chat_id=sub.telegram_id,
                    text=f"📢 **Announcement**\n\n{message}",
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {sub.telegram_id}: {e}")
                failed += 1
        
        await update.message.reply_text(
            f"📢 Broadcast complete!\n\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}"
        )
    
    # ==================== Signal Handling ====================
    
    async def handle_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages from the signal channel."""
        message = update.channel_post
        if not message or not message.text:
            return
        
        # Only process from signal channel
        if not self._is_signal_channel(message.chat_id):
            return
        
        # Try to parse as signal
        try:
            signal = SignalParser.parse(message.text)
        except SignalParseError:
            # Not a signal, ignore
            return
        
        logger.info(f"Signal received from channel: {signal.signal_id}")
        
        # Broadcast to all subscribers
        await self._broadcast_signal(signal, message.chat_id)
    
    async def handle_admin_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle DM from admin - can also trigger signals."""
        message = update.message
        if not message or not message.text:
            return
        
        # Log what we're checking
        logger.info(f"Signal check - chat_id: {message.chat_id}, user_id: {update.effective_user.id}, is_channel: {message.chat.type == 'channel'}, is_admin_dm: {self._is_admin(update.effective_user.id)}")
        
        # Only process from admin
        if not self._is_admin(update.effective_user.id):
            return
        
        # Try to parse as signal
        try:
            signal = SignalParser.parse(message.text)
        except SignalParseError:
            # Not a signal, ignore (let other handlers deal with it)
            return
        
        logger.info(f"Signal received from admin DM: {signal.signal_id}")
        
        # Confirm to admin
        await message.reply_text(
            f"📡 Signal detected!\n\n"
            f"{format_signal_summary(signal)}\n\n"
            f"Broadcasting to all AUTO subscribers..."
        )
        
        # Broadcast to all subscribers
        await self._broadcast_signal(signal, message.chat_id)
    
    async def _broadcast_signal(self, signal: Signal, source_chat_id: int):
        """Broadcast a signal to all subscribers."""
        # Execute trades for AUTO subscribers
        results = await self.broadcaster.broadcast_signal(signal)
        
        # Send summary to admin
        summary = format_broadcast_summary(signal, results)
        try:
            await self.bot.send_message(
                chat_id=self.settings.admin_telegram_id,
                text=summary,
            )
        except Exception as e:
            logger.error(f"Failed to send broadcast summary to admin: {e}")
        
        # Notify each user of their trade result
        for result in results:
            notification = format_user_trade_notification(signal, result)
            try:
                await self.bot.send_message(
                    chat_id=result.telegram_id,
                    text=notification,
                )
            except Exception as e:
                logger.error(f"Failed to notify user {result.telegram_id}: {e}")
    
    # ==================== Bot Setup ====================
    
    async def setup(self, webhook_url: Optional[str] = None):
        """Set up the bot with handlers."""
        builder = Application.builder().token(self.settings.telegram_bot_token)
        self.app = builder.build()
        self.bot = self.app.bot
        
        # Registration conversation handler
        registration_handler = ConversationHandler(
            entry_points=[CommandHandler("register", self.register_start)],
            states={
                AWAITING_API_KEY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_api_key),
                ],
                AWAITING_API_SECRET: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_api_secret),
                ],
                AWAITING_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_amount),
                    CommandHandler("skip", self.register_skip_amount),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.register_cancel)],
        )
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(registration_handler)
        self.app.add_handler(CommandHandler("setamount", self.setamount_command))
        self.app.add_handler(CommandHandler("setleverage", self.setleverage_command))
        self.app.add_handler(CommandHandler("setmode", self.setmode_command))
        self.app.add_handler(CommandHandler("unregister", self.unregister_command))
        
        # Admin commands
        self.app.add_handler(CommandHandler("stats", self.admin_stats_command))
        self.app.add_handler(CommandHandler("broadcast", self.admin_broadcast_command))
        
        # Channel message handler (for signals)
        self.app.add_handler(MessageHandler(
            filters.UpdateType.CHANNEL_POST,
            self.handle_channel_message
        ))
        
        # Admin DM handler (for testing signals)
        self.app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE,
            self.handle_admin_dm
        ))
        
        # Set webhook if URL provided
        if webhook_url:
            await self.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set: {webhook_url}")
        
        return self.app
    
    async def process_update(self, update_data: dict):
        """Process an incoming update from webhook."""
        if not self.app:
            raise RuntimeError("Bot not set up. Call setup() first.")
        
        update = Update.de_json(update_data, self.bot)
        await self.app.process_update(update)

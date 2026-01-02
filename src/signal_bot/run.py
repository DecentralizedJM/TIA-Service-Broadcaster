"""
Run Script - Main entry point for the Signal Bot.

Supports two modes:
1. Webhook mode (default) - For Railway deployment
2. Polling mode - For local development
"""

import argparse
import logging
import sys
import uvicorn

from .settings import get_settings, Settings
from .database import Database
from .crypto import init_crypto
from .telegram_bot import SignalBot


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    # Quiet down some noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)


def print_banner():
    """Print startup banner."""
    print("""
╔═══════════════════════════════════════════════════════════╗
║       🤖 MUDREX TRADEIDEAS AUTOMATION BOT v2.0.0         ║
║                                                           ║
║   Centralized Telegram Signal Bot for Mudrex Futures     ║
╚═══════════════════════════════════════════════════════════╝
    """)


def run_webhook_server(settings: Settings):
    """Run the webhook server (production mode)."""
    from .server import app
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


async def run_polling_mode(settings: Settings):
    """Run in polling mode (development)."""
    import asyncio
    
    # Initialize crypto
    init_crypto(settings.encryption_secret)
    
    # Connect to database
    database = Database(settings.database_path)
    await database.connect()
    
    try:
        # Create and run bot
        bot = SignalBot(settings, database)
        bot.run_polling()
    finally:
        await database.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Mudrex TradeIdeas Bot - Auto-trade Telegram signals on Mudrex"
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--polling',
        action='store_true',
        help='Run in polling mode (for local development)'
    )
    
    parser.add_argument(
        '--generate-secret',
        action='store_true',
        help='Generate a secure encryption secret'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Handle --generate-secret
    if args.generate_secret:
        from .crypto import generate_master_secret
        secret = generate_master_secret()
        print(f"\n🔐 Generated Encryption Secret:\n\n    {secret}\n")
        print("Add this to your environment variables:")
        print(f"    export ENCRYPTION_SECRET=\"{secret}\"\n")
        return
    
    # Print banner
    print_banner()
    
    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        print("\n❌ Missing required environment variables:")
        print("    TELEGRAM_BOT_TOKEN")
        print("    ENCRYPTION_SECRET")
        print("    ADMIN_TELEGRAM_ID")
        print("    SIGNAL_CHANNEL_ID")
        print("\nRun with --generate-secret to create an encryption secret.")
        sys.exit(1)
    
    logger.info(f"Admin Telegram ID: {settings.admin_telegram_id}")
    logger.info(f"Signal Channel ID: {settings.signal_channel_id}")
    logger.info(f"Default Trade Amount: {settings.default_trade_amount} USDT")
    
    if args.polling:
        # Run in polling mode
        logger.info("Starting in POLLING mode (for development)...")
        import asyncio
        asyncio.run(run_polling_mode(settings))
    else:
        # Run webhook server
        logger.info("Starting in WEBHOOK mode (for production)...")
        logger.info(f"Server: {settings.host}:{settings.port}")
        if settings.webhook_url:
            logger.info(f"Webhook URL: {settings.full_webhook_url}")
        run_webhook_server(settings)


if __name__ == '__main__':
    main()

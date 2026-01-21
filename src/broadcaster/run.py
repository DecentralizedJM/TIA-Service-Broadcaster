"""
Main runner for TIA Service Broadcaster.

Runs both Telegram bot and FastAPI server.
"""

import asyncio
import logging
import sys
import uvicorn
from contextlib import asynccontextmanager

from .settings import get_settings
from .database import Database
from .api import BroadcasterAPI
from .telegram_bot import BroadcasterBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# Global instances
database: Database = None
api: BroadcasterAPI = None
bot: BroadcasterBot = None


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager for FastAPI app."""
    global database, api, bot
    
    logger.info("=" * 63)
    logger.info("║       🤖 TIA SERVICE BROADCASTER v1.0.0         ║")
    logger.info("║                                                 ║")
    logger.info("║   Signal Broadcasting for Mudrex Trade Ideas   ║")
    logger.info("=" * 63)
    
    try:
        # Load settings
        settings = get_settings()
        logger.info(f"Settings loaded - Admins: {settings.admin_ids}")
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        logger.error("Make sure all required environment variables are set:")
        logger.error("  TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID")
        raise
    
    # Initialize database
    database = Database(settings.database_path)
    logger.info(f"Database path: {settings.database_path}")
    await database.connect()
    
    # Initialize API
    api = BroadcasterAPI(database)
    logger.info("BroadcasterAPI initialized")
    
    # Initialize Telegram bot
    bot = BroadcasterBot(settings, database, api)
    bot.build_application()
    
    # Start bot
    await bot.app.initialize()
    await bot.app.start()
    
    # Set up webhook for Telegram
    if settings.webhook_url:
        await bot.setup_webhook()
        logger.info(f"Telegram webhook mode: {settings.full_webhook_url}")
    else:
        # Start polling in background
        logger.info("Starting Telegram bot in polling mode")
        asyncio.create_task(bot.app.updater.start_polling())
    
    logger.info(f"✅ Broadcaster ready! Port: {settings.port}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await bot.app.stop()
    await bot.app.shutdown()
    await database.close()
    logger.info("Shutdown complete")


async def process_update_safely(update_data: dict):
    """Process Telegram update with error handling."""
    try:
        from telegram import Update
        update = Update.de_json(update_data, bot.app.bot)
        await bot.app.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)


def setup_webhook_route(app):
    """Set up webhook route for Telegram."""
    @app.post("/webhook")
    async def telegram_webhook(update: dict):
        """Handle Telegram webhook."""
        asyncio.create_task(process_update_safely(update))
        return {"status": "ok"}


def main():
    """Main entry point."""
    settings = get_settings()
    
    # Create FastAPI app with lifespan
    from fastapi import FastAPI
    app = FastAPI(lifespan=lifespan)
    
    # Mount broadcaster API routes
    @app.on_event("startup")
    async def startup():
        global api
        # Mount the API routes after initialization
        pass
    
    # Add webhook route for Telegram
    setup_webhook_route(app)
    
    # Mount API app routes
    @app.get("/")
    async def root():
        """Root endpoint."""
        if api:
            return await api.app.routes[0].endpoint()
        return {"service": "TIA Service Broadcaster", "status": "starting"}
    
    @app.get("/health")
    async def health():
        """Health check."""
        return {"status": "healthy"}
    
    # Start server
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

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
        logger.info(f"Processing webhook update: {update_data.get('update_id', 'unknown')}")
        
        # Log message details if present
        if 'message' in update_data:
            msg = update_data['message']
            chat_id = msg.get('chat', {}).get('id', 'unknown')
            user_id = msg.get('from', {}).get('id', 'unknown')
            text = msg.get('text', '')[:50] if msg.get('text') else '[no text]'
            logger.info(f"  Message from user={user_id} in chat={chat_id}: '{text}'")
        
        from telegram import Update
        update = Update.de_json(update_data, bot.app.bot)
        await bot.app.process_update(update)
        logger.info(f"  Update processed successfully")
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
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    app = FastAPI(lifespan=lifespan)
    
    # Add webhook route for Telegram
    setup_webhook_route(app)
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with service info and stats."""
        if api and api.db:
            try:
                stats = await api.db.get_stats()
                return {
                    "service": "TIA Service Broadcaster",
                    "version": "1.0.0",
                    "status": "online",
                    "stats": stats
                }
            except Exception:
                pass
        return {"service": "TIA Service Broadcaster", "status": "starting"}
    
    @app.get("/health")
    async def health():
        """Health check."""
        return {"status": "healthy"}
    
    # WebSocket endpoint for SDK clients
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, client_id: str = "unknown"):
        """
        WebSocket endpoint for real-time signal updates.
        SDK clients connect here to receive signals.
        """
        if not api:
            await websocket.close(code=1011, reason="Server not ready")
            return
        
        await websocket.accept()
        api.websocket_connections.add(websocket)
        api.websocket_clients[websocket] = client_id
        
        # Update last heartbeat in database
        await api.db.update_client_heartbeat(client_id)
        
        logger.info(f"WebSocket client connected: {client_id}. Total: {len(api.websocket_connections)}")
        
        try:
            while True:
                data = await websocket.receive_text()
                
                if data == "ping":
                    await websocket.send_text("pong")
                    await api.db.update_client_heartbeat(client_id)
        
        except WebSocketDisconnect:
            api.websocket_connections.discard(websocket)
            api.websocket_clients.pop(websocket, None)
            logger.info(f"WebSocket client disconnected: {client_id}. Total: {len(api.websocket_connections)}")
        
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
            if websocket in api.websocket_connections:
                api.websocket_connections.discard(websocket)
                api.websocket_clients.pop(websocket, None)
    
    # API endpoints for SDK
    @app.get("/api/signals")
    async def get_signals(active_only: bool = True, limit: int = 100):
        """Get signals."""
        if not api:
            return {"signals": [], "count": 0}
        if active_only:
            signals = await api.db.get_active_signals()
        else:
            signals = await api.db.get_all_signals(limit=limit)
        return {"signals": signals, "count": len(signals)}
    
    @app.get("/api/signals/{signal_id}")
    async def get_signal(signal_id: str):
        """Get a specific signal."""
        if not api:
            return {"error": "Server not ready"}
        signal = await api.db.get_signal(signal_id)
        if signal:
            return {"signal": signal}
        return {"error": "Signal not found"}
    
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

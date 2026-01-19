"""
FastAPI - REST and WebSocket API for SDK clients.
"""

import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Set
from datetime import datetime

from .settings import Settings, get_settings
from .database import Database
from .models import Signal, SignalClose, SignalEditSLTP, SignalLeverage, SDKClient

logger = logging.getLogger(__name__)


# ==================== Request/Response Models ====================

class ClientRegisterRequest(BaseModel):
    """SDK client registration request."""
    client_id: str
    telegram_id: Optional[int] = None


class HeartbeatRequest(BaseModel):
    """Client heartbeat request."""
    client_id: str


# ==================== Authentication ====================

async def verify_api_secret(x_api_secret: str = Header(...)):
    """Verify API secret from SDK client."""
    settings = get_settings()
    if x_api_secret != settings.api_secret:
        raise HTTPException(status_code=401, detail="Invalid API secret")
    return True


# ==================== Broadcaster API ====================

class BroadcasterAPI:
    """FastAPI app for SDK client connections."""
    
    def __init__(self, database: Database):
        self.db = database
        self.app = FastAPI(title="TIA Service Broadcaster", version="1.0.0")
        self.websocket_connections: Set[WebSocket] = set()
        
        # Register routes
        self._register_routes()
        
        logger.info("BroadcasterAPI initialized")
    
    def _register_routes(self):
        """Register FastAPI routes."""
        
        @self.app.get("/")
        async def root():
            """Health check endpoint."""
            stats = await self.db.get_stats()
            return {
                "service": "TIA Service Broadcaster",
                "version": "1.0.0",
                "status": "online",
                "stats": stats
            }
        
        @self.app.get("/health")
        async def health():
            """Health check for Railway."""
            return {"status": "healthy"}
        
        @self.app.post("/api/sdk/register")
        async def register_client(
            request: ClientRegisterRequest,
            authenticated: bool = Depends(verify_api_secret)
        ):
            """Register an SDK client."""
            client = SDKClient(
                client_id=request.client_id,
                telegram_id=request.telegram_id,
                connected_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow(),
                active=True
            )
            
            success = await self.db.register_client(client)
            if success:
                return {"status": "registered", "client_id": request.client_id}
            else:
                raise HTTPException(status_code=500, detail="Registration failed")
        
        @self.app.post("/api/sdk/heartbeat")
        async def heartbeat(
            request: HeartbeatRequest,
            authenticated: bool = Depends(verify_api_secret)
        ):
            """Update client heartbeat."""
            success = await self.db.update_client_heartbeat(request.client_id)
            if success:
                return {"status": "ok"}
            else:
                raise HTTPException(status_code=404, detail="Client not found")
        
        @self.app.get("/api/signals")
        async def get_signals(
            active_only: bool = True,
            limit: int = 100,
            authenticated: bool = Depends(verify_api_secret)
        ):
            """Get signals (active or all)."""
            if active_only:
                signals = await self.db.get_active_signals()
            else:
                signals = await self.db.get_all_signals(limit=limit)
            
            return {"signals": signals, "count": len(signals)}
        
        @self.app.get("/api/signals/{signal_id}")
        async def get_signal(
            signal_id: str,
            authenticated: bool = Depends(verify_api_secret)
        ):
            """Get a specific signal by ID."""
            signal = await self.db.get_signal(signal_id)
            if signal:
                return {"signal": signal}
            else:
                raise HTTPException(status_code=404, detail="Signal not found")
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time signal updates."""
            await websocket.accept()
            self.websocket_connections.add(websocket)
            logger.info(f"WebSocket client connected. Total: {len(self.websocket_connections)}")
            
            try:
                # Keep connection alive and handle messages
                while True:
                    # Receive messages (for heartbeat/ping-pong)
                    data = await websocket.receive_text()
                    
                    if data == "ping":
                        await websocket.send_text("pong")
            
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
                logger.info(f"WebSocket client disconnected. Total: {len(self.websocket_connections)}")
            
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
    
    # ==================== Broadcasting Methods ====================
    
    async def broadcast_signal(self, signal: Signal):
        """Broadcast new signal to all connected SDK clients."""
        message = {
            "type": "NEW_SIGNAL",
            "signal": signal.to_dict()
        }
        await self._broadcast_to_websockets(message)
        logger.info(f"Broadcasted signal to {len(self.websocket_connections)} WebSocket clients")
    
    async def broadcast_close(self, close: SignalClose):
        """Broadcast close command to SDK clients."""
        message = {
            "type": "CLOSE_SIGNAL",
            "signal_id": close.signal_id,
            "symbol": close.symbol,
            "percentage": close.percentage
        }
        await self._broadcast_to_websockets(message)
        logger.info(f"Broadcasted close for {close.signal_id}")
    
    async def broadcast_edit_sl_tp(self, edit: SignalEditSLTP):
        """Broadcast SL/TP update to SDK clients."""
        message = {
            "type": "EDIT_SLTP",
            "signal_id": edit.signal_id,
            "symbol": edit.symbol,
            "stop_loss": edit.stop_loss,
            "take_profit": edit.take_profit
        }
        await self._broadcast_to_websockets(message)
        logger.info(f"Broadcasted SL/TP update for {edit.signal_id}")
    
    async def broadcast_leverage(self, lev: SignalLeverage):
        """Broadcast leverage update to SDK clients."""
        message = {
            "type": "UPDATE_LEVERAGE",
            "signal_id": lev.signal_id,
            "symbol": lev.symbol,
            "leverage": lev.leverage
        }
        await self._broadcast_to_websockets(message)
        logger.info(f"Broadcasted leverage update for {lev.signal_id}")
    
    async def _broadcast_to_websockets(self, message: dict):
        """Send message to all connected WebSocket clients."""
        if not self.websocket_connections:
            logger.debug("No WebSocket clients connected")
            return
        
        disconnected = set()
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to WebSocket client: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.websocket_connections.discard(ws)

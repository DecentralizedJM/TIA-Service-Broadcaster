"""
FastAPI - REST and WebSocket API for SDK clients.
"""

import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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
    """
    SDK client registration request.
    
    telegram_id: Optional Telegram ID for admin notifications
                 (e.g., "Signal executed successfully on your SDK")
    """
    client_id: str
    telegram_id: Optional[int] = None


# ==================== Broadcaster API ====================
# Note: This is a PUBLIC service - anyone can connect via SDK
# No authentication required - signals are broadcast to all connected clients

class BroadcasterAPI:
    """FastAPI app for SDK client connections."""
    
    def __init__(self, database: Database):
        self.db = database
        self.app = FastAPI(title="TIA Service Broadcaster", version="1.0.0")
        self.websocket_connections: Set[WebSocket] = set()
        # Track WebSocket connections with client info: websocket -> client_id
        self.websocket_clients: Dict[WebSocket, str] = {}
        
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
            request: ClientRegisterRequest
        ):
            """
            Register an SDK client.
            
            Telegram ID is optional but recommended - allows admin to:
            - Send notifications about signal execution
            - Debug issues ("Did you receive signal X?")
            - Monitor SDK health
            
            Note: Heartbeat is handled via WebSocket ping/pong automatically.
            """
            client = SDKClient(
                client_id=request.client_id,
                telegram_id=request.telegram_id,
                connected_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow(),
                active=True
            )
            
            success = await self.db.register_client(client)
            if success:
                msg = {"status": "registered", "client_id": request.client_id}
                if request.telegram_id:
                    msg["telegram_notifications"] = "enabled"
                return msg
            else:
                raise HTTPException(status_code=500, detail="Registration failed")
        
        @self.app.get("/api/signals")
        async def get_signals(
            active_only: bool = True,
            limit: int = 100
        ):
            """Get signals (active or all)."""
            if active_only:
                signals = await self.db.get_active_signals()
            else:
                signals = await self.db.get_all_signals(limit=limit)
            
            return {"signals": signals, "count": len(signals)}
        
        @self.app.get("/api/signals/{signal_id}")
        async def get_signal(
            signal_id: str
        ):
            """Get a specific signal by ID."""
            signal = await self.db.get_signal(signal_id)
            if signal:
                return {"signal": signal}
            else:
                raise HTTPException(status_code=404, detail="Signal not found")
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, client_id: str = "unknown"):
            """
            WebSocket endpoint for real-time signal updates.
            
            This is the primary connection for SDK clients. Signals are pushed
            in real-time as admins broadcast them via Telegram.
            
            Query params:
                client_id: Unique client identifier
            
            Heartbeat: Send "ping" to receive "pong" (keeps connection alive)
            """
            await websocket.accept()
            self.websocket_connections.add(websocket)
            self.websocket_clients[websocket] = client_id
            
            # Update last heartbeat in database
            await self.db.update_client_heartbeat(client_id)
            
            logger.info(f"WebSocket client connected: {client_id}. Total: {len(self.websocket_connections)}")
            
            try:
                # Keep connection alive and handle messages
                while True:
                    # Receive messages (for ping/pong heartbeat)
                    data = await websocket.receive_text()
                    
                    if data == "ping":
                        await websocket.send_text("pong")
                        # Update heartbeat in database
                        await self.db.update_client_heartbeat(client_id)
            
            except WebSocketDisconnect:
                self.websocket_connections.discard(websocket)
                self.websocket_clients.pop(websocket, None)
                logger.info(f"WebSocket client disconnected: {client_id}. Total: {len(self.websocket_connections)}")
            
            except Exception as e:
                logger.error(f"WebSocket error for {client_id}: {e}")
                if websocket in self.websocket_connections:
                    self.websocket_connections.discard(websocket)
                    self.websocket_clients.pop(websocket, None)
    
    # ==================== Broadcasting Methods ====================
    
    async def broadcast_signal(self, signal: Signal):
        """Broadcast new signal to all connected SDK clients."""
        message = {
            "type": "NEW_SIGNAL",
            "signal": signal.to_dict()
        }
        delivered_count = await self._broadcast_to_websockets(message, signal.signal_id)
        logger.info(f"Broadcasted signal {signal.signal_id} to {delivered_count}/{len(self.websocket_connections)} WebSocket clients")
        return delivered_count
    
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
    
    async def _broadcast_to_websockets(self, message: dict, signal_id: Optional[str] = None) -> int:
        """
        Send message to all connected WebSocket clients.
        
        Returns:
            Number of successfully delivered messages
        """
        if not self.websocket_connections:
            logger.debug("No WebSocket clients connected")
            return 0
        
        disconnected = set()
        delivered_count = 0
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(message)
                delivered_count += 1
                
                # Track delivery in database if signal_id provided
                if signal_id and websocket in self.websocket_clients:
                    client_id = self.websocket_clients[websocket]
                    await self.db.record_signal_delivery(signal_id, client_id)
                    
            except Exception as e:
                client_id = self.websocket_clients.get(websocket, "unknown")
                logger.error(f"Failed to send to WebSocket client {client_id}: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.websocket_connections.discard(ws)
            self.websocket_clients.pop(ws, None)
        
        return delivered_count
    
    def get_connected_clients(self) -> List[str]:
        """Get list of currently connected client IDs."""
        return list(self.websocket_clients.values())
    
    def get_connection_count(self) -> int:
        """Get current WebSocket connection count."""
        return len(self.websocket_connections)

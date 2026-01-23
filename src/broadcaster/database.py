"""
Database - Signal and SDK client storage.

Only stores signals and client connections - NO API keys!
"""

import aiosqlite
import logging
from datetime import datetime
from typing import List, Optional, Dict

from .models import Signal, SignalStatus, SDKClient

logger = logging.getLogger(__name__)


class Database:
    """Database manager for signals and SDK clients."""
    
    def __init__(self, db_path: str = "signals.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Connect to database and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._init_schema()
        logger.info(f"Database connected: {self.db_path}")
    
    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            logger.info("Database connection closed")
    
    async def _init_schema(self):
        """Initialize database schema."""
        async with self._connection.execute("PRAGMA foreign_keys = ON"):
            pass
        
        # Signals table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                order_type TEXT NOT NULL,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                leverage INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # SDK clients table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS sdk_clients (
                client_id TEXT PRIMARY KEY,
                telegram_id INTEGER,
                connected_at TEXT NOT NULL,
                last_heartbeat TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        # Signal delivery tracking (which clients received which signals)
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS signal_delivery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                client_id TEXT NOT NULL,
                delivered_at TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id),
                FOREIGN KEY (client_id) REFERENCES sdk_clients(client_id)
            )
        """)
        
        await self._connection.commit()
        logger.info("Database schema initialized")
    
    # ==================== Signal Management ====================
    
    async def save_signal(self, signal: Signal) -> bool:
        """Save a new signal."""
        try:
            await self._connection.execute("""
                INSERT INTO signals 
                (signal_id, symbol, signal_type, order_type, entry_price, 
                 stop_loss, take_profit, leverage, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.signal_id,
                signal.symbol,
                signal.signal_type.value,
                signal.order_type.value,
                signal.entry_price,
                signal.stop_loss,
                signal.take_profit,
                signal.leverage,
                signal.status.value,
                signal.created_at.isoformat() if signal.created_at else datetime.utcnow().isoformat(),
                signal.updated_at.isoformat() if signal.updated_at else datetime.utcnow().isoformat()
            ))
            await self._connection.commit()
            logger.info(f"Signal saved: {signal.signal_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save signal: {e}")
            return False
    
    async def get_signal(self, signal_id: str) -> Optional[Dict]:
        """Get a signal by ID."""
        async with self._connection.execute(
            "SELECT * FROM signals WHERE signal_id = ?", (signal_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_active_signals(self) -> List[Dict]:
        """Get all active signals."""
        async with self._connection.execute(
            "SELECT * FROM signals WHERE status = ? ORDER BY created_at DESC",
            (SignalStatus.ACTIVE.value,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_all_signals(self, limit: int = 100) -> List[Dict]:
        """Get all signals (active and closed)."""
        async with self._connection.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_signal_status(self, signal_id: str, status: SignalStatus) -> bool:
        """Update signal status."""
        try:
            await self._connection.execute("""
                UPDATE signals 
                SET status = ?, updated_at = ?
                WHERE signal_id = ?
            """, (status.value, datetime.utcnow().isoformat(), signal_id))
            await self._connection.commit()
            logger.info(f"Signal {signal_id} status updated to {status.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to update signal status: {e}")
            return False
    
    async def update_signal_sl_tp(self, signal_id: str, stop_loss: Optional[float], take_profit: Optional[float]) -> bool:
        """Update signal SL/TP."""
        try:
            updates = []
            params = []
            
            if stop_loss is not None:
                updates.append("stop_loss = ?")
                params.append(stop_loss)
            
            if take_profit is not None:
                updates.append("take_profit = ?")
                params.append(take_profit)
            
            if not updates:
                return False
            
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(signal_id)
            
            query = f"UPDATE signals SET {', '.join(updates)} WHERE signal_id = ?"
            await self._connection.execute(query, params)
            await self._connection.commit()
            logger.info(f"Signal {signal_id} SL/TP updated")
            return True
        except Exception as e:
            logger.error(f"Failed to update signal SL/TP: {e}")
            return False
    
    async def update_signal_leverage(self, signal_id: str, leverage: int) -> bool:
        """Update signal leverage."""
        try:
            await self._connection.execute("""
                UPDATE signals 
                SET leverage = ?, updated_at = ?
                WHERE signal_id = ?
            """, (leverage, datetime.utcnow().isoformat(), signal_id))
            await self._connection.commit()
            logger.info(f"Signal {signal_id} leverage updated to {leverage}x")
            return True
        except Exception as e:
            logger.error(f"Failed to update signal leverage: {e}")
            return False
    
    # ==================== SDK Client Management ====================
    
    async def register_client(self, client: SDKClient) -> bool:
        """Register or update an SDK client."""
        try:
            await self._connection.execute("""
                INSERT OR REPLACE INTO sdk_clients 
                (client_id, telegram_id, connected_at, last_heartbeat, active)
                VALUES (?, ?, ?, ?, ?)
            """, (
                client.client_id,
                client.telegram_id,
                client.connected_at.isoformat(),
                client.last_heartbeat.isoformat(),
                1 if client.active else 0
            ))
            await self._connection.commit()
            logger.info(f"SDK client registered: {client.client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register SDK client: {e}")
            return False
    
    async def update_client_heartbeat(self, client_id: str) -> bool:
        """Update client heartbeat timestamp."""
        try:
            await self._connection.execute("""
                UPDATE sdk_clients 
                SET last_heartbeat = ?
                WHERE client_id = ?
            """, (datetime.utcnow().isoformat(), client_id))
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update client heartbeat: {e}")
            return False
    
    async def get_client(self, client_id: str) -> Optional[Dict]:
        """Get a specific SDK client by ID."""
        async with self._connection.execute(
            "SELECT * FROM sdk_clients WHERE client_id = ?", (client_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_active_clients(self) -> List[Dict]:
        """Get all active SDK clients."""
        async with self._connection.execute(
            "SELECT * FROM sdk_clients WHERE active = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def deactivate_client(self, client_id: str) -> bool:
        """Deactivate an SDK client."""
        try:
            await self._connection.execute("""
                UPDATE sdk_clients 
                SET active = 0
                WHERE client_id = ?
            """, (client_id,))
            await self._connection.commit()
            logger.info(f"SDK client deactivated: {client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate client: {e}")
            return False
    
    # ==================== Signal Delivery Tracking ====================
    
    async def record_delivery(self, signal_id: str, client_id: str) -> bool:
        """Record that a signal was delivered to a client."""
        try:
            await self._connection.execute("""
                INSERT INTO signal_delivery 
                (signal_id, client_id, delivered_at)
                VALUES (?, ?, ?)
            """, (signal_id, client_id, datetime.utcnow().isoformat()))
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record delivery: {e}")
            return False
    
    async def record_signal_delivery(self, signal_id: str, client_id: str) -> bool:
        """Record that a signal was delivered to a client."""
        try:
            await self._connection.execute("""
                INSERT INTO signal_delivery (signal_id, client_id, delivered_at, acknowledged)
                VALUES (?, ?, ?, 0)
            """, (signal_id, client_id, datetime.utcnow().isoformat()))
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record signal delivery: {e}")
            return False
    
    async def get_signal_delivery_stats(self, signal_id: str) -> Dict:
        """Get delivery statistics for a specific signal."""
        stats = {}
        
        async with self._connection.execute(
            "SELECT COUNT(*) FROM signal_delivery WHERE signal_id = ?", (signal_id,)
        ) as cursor:
            row = await cursor.fetchone()
            stats["delivered_count"] = row[0]
        
        async with self._connection.execute(
            "SELECT COUNT(*) FROM signal_delivery WHERE signal_id = ? AND acknowledged = 1", (signal_id,)
        ) as cursor:
            row = await cursor.fetchone()
            stats["acknowledged_count"] = row[0]
        
        return stats
    
    async def get_stats(self) -> Dict:
        """Get broadcaster statistics."""
        stats = {}
        
        async with self._connection.execute("SELECT COUNT(*) FROM signals") as cursor:
            row = await cursor.fetchone()
            stats["total_signals"] = row[0]
        
        async with self._connection.execute(
            "SELECT COUNT(*) FROM signals WHERE status = ?", (SignalStatus.ACTIVE.value,)
        ) as cursor:
            row = await cursor.fetchone()
            stats["active_signals"] = row[0]
        
        async with self._connection.execute("SELECT COUNT(*) FROM sdk_clients") as cursor:
            row = await cursor.fetchone()
            stats["total_clients"] = row[0]
        
        async with self._connection.execute("SELECT COUNT(*) FROM sdk_clients WHERE active = 1") as cursor:
            row = await cursor.fetchone()
            stats["active_clients"] = row[0]
        
        async with self._connection.execute("SELECT COUNT(*) FROM signal_delivery") as cursor:
            row = await cursor.fetchone()
            stats["total_deliveries"] = row[0]
        
        # Get recent delivery stats (last 24 hours)
        async with self._connection.execute("""
            SELECT COUNT(*) FROM signal_delivery 
            WHERE datetime(delivered_at) > datetime('now', '-1 day')
        """) as cursor:
            row = await cursor.fetchone()
            stats["deliveries_24h"] = row[0]
        
        return stats
    
    async def get_clients_who_received_signal(self, signal_id: str) -> List[str]:
        """
        Get list of client_ids who received (delivered) a given signal.
        Used to filter clients when closing positions - only close for clients who actually received the signal.
        """
        async with self._connection.execute(
            "SELECT DISTINCT client_id FROM signal_delivery WHERE signal_id = ?", (signal_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def get_clients_who_acknowledged_signal(self, signal_id: str) -> List[str]:
        """
        Get list of client_ids who acknowledged a given signal.
        More strict than received - only clients who confirmed they got and processed the signal.
        """
        async with self._connection.execute(
            "SELECT DISTINCT client_id FROM signal_delivery WHERE signal_id = ? AND acknowledged = 1", (signal_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

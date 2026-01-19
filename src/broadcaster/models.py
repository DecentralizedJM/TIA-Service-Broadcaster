"""
Data models for signals and SDK client management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SignalType(str, Enum):
    """Signal type enum."""
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    """Order type enum."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class SignalStatus(str, Enum):
    """Signal status enum."""
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class Signal:
    """Trading signal."""
    signal_id: str
    symbol: str
    signal_type: SignalType
    order_type: OrderType
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: int = 1
    status: SignalStatus = SignalStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "order_type": self.order_type.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "leverage": self.leverage,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class SignalClose:
    """Signal close command."""
    signal_id: str
    symbol: str
    percentage: float = 100.0  # Default to full close


@dataclass
class SignalEditSLTP:
    """Signal SL/TP edit command."""
    signal_id: str
    symbol: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class SignalLeverage:
    """Signal leverage update command."""
    signal_id: str
    symbol: str
    leverage: int


@dataclass
class SDKClient:
    """SDK client connection info."""
    client_id: str
    telegram_id: Optional[int] = None  # Optional Telegram ID for notifications
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    active: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "client_id": self.client_id,
            "telegram_id": self.telegram_id,
            "connected_at": self.connected_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "active": self.active,
        }

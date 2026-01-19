"""
Signal Parser - Parse trading signals from Telegram messages.

Reused from existing bot with minimal modifications for broadcaster.
"""

import re
import uuid
from datetime import datetime
from typing import Optional, Union

from .models import (
    Signal, SignalClose, SignalEditSLTP, SignalLeverage,
    SignalType, OrderType, SignalStatus
)


class SignalParseError(Exception):
    """Raised when signal parsing fails."""
    pass


class SignalParser:
    """Parse trading signals from Telegram messages."""
    
    # Signal ID pattern: SIG-DDMMYY-SYMBOL-UUID (e.g., SIG-030126-BTCUSDT-59797F)
    SIGNAL_ID_PATTERN = r"SIG-\d{6}-[A-Z0-9]+(?:-[A-Z0-9]{6})?"
    
    # Regex patterns
    SIGNAL_PATTERN = re.compile(
        r"/signal\s+(LONG|SHORT)\s+([A-Z0-9]+)",
        re.IGNORECASE
    )
    SIGNAL_PATTERN_ALT = re.compile(
        r"/signal\s+([A-Z0-9]+)\s+(LONG|SHORT)",
        re.IGNORECASE
    )
    
    # Multi-line signal pattern
    MULTILINE_SIGNAL_PATTERN = re.compile(
        r"^([A-Z0-9]{2,15})\s*\n\s*(LONG|SHORT)",
        re.IGNORECASE | re.MULTILINE
    )
    
    CLOSE_PATTERN = re.compile(
        rf"/close\s+({SIGNAL_ID_PATTERN})(?:\s+(\d+(?:\.\d+)?)%?)?",
        re.IGNORECASE
    )
    
    LEVERAGE_PATTERN = re.compile(
        rf"/leverage\s+({SIGNAL_ID_PATTERN})\s+(\d+)x?",
        re.IGNORECASE
    )
    
    EDIT_SLTP_PATTERN = re.compile(
        rf"/editsltp\s+({SIGNAL_ID_PATTERN})",
        re.IGNORECASE
    )
    
    # Parameter patterns
    PARAM_PATTERNS = {
        'entry': re.compile(r'entry[=:\s]+([\d.]+)', re.IGNORECASE),
        'sl': re.compile(r'sl[=:\s]+([\d.]+)', re.IGNORECASE),
        'tp': re.compile(r'tp[=:\s]+([\d.]+)', re.IGNORECASE),
        'lev': re.compile(r'lev(?:erage)?[=:\s]+(\d+)x?', re.IGNORECASE),
    }
    
    @classmethod
    def _generate_signal_id(cls, symbol: str) -> str:
        """Generate a unique signal ID."""
        date_str = datetime.now().strftime("%d%m%y")
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"SIG-{date_str}-{symbol.upper()}-{unique_suffix}"
    
    @classmethod
    def _extract_param(cls, text: str, param_name: str) -> Optional[float]:
        """Extract a parameter value from text."""
        pattern = cls.PARAM_PATTERNS.get(param_name)
        if not pattern:
            return None
        
        match = pattern.search(text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
    
    @classmethod
    def _is_market_order(cls, params_text: str) -> bool:
        """Check if this is a market order."""
        return 'market' in params_text.lower() or cls._extract_param(params_text, 'entry') is None
    
    @classmethod
    def parse_signal(cls, message: str) -> Optional[Signal]:
        """Parse a /signal command."""
        text = message.strip()
        symbol = None
        signal_type_str = None
        
        # Try pattern 1: /signal LONG BTCUSDT
        match = cls.SIGNAL_PATTERN.match(text)
        if match:
            signal_type_str = match.group(1).upper()
            symbol = match.group(2).upper()
        else:
            # Try pattern 2: /signal BTCUSDT LONG
            match = cls.SIGNAL_PATTERN_ALT.match(text)
            if match:
                symbol = match.group(1).upper()
                signal_type_str = match.group(2).upper()
            else:
                # Try pattern 3: Multi-line format
                match = cls.MULTILINE_SIGNAL_PATTERN.search(text)
                if match:
                    symbol = match.group(1).upper()
                    signal_type_str = match.group(2).upper()
                else:
                    return None
        
        params_text = text
        
        # Parse signal type
        signal_type = SignalType.LONG if signal_type_str == "LONG" else SignalType.SHORT
        
        # Determine order type
        is_market = cls._is_market_order(params_text)
        order_type = OrderType.MARKET if is_market else OrderType.LIMIT
        
        # Extract parameters
        entry_price = cls._extract_param(params_text, 'entry')
        stop_loss = cls._extract_param(params_text, 'sl')
        take_profit = cls._extract_param(params_text, 'tp')
        leverage = cls._extract_param(params_text, 'lev')
        
        # If entry price is provided, it's a limit order
        if entry_price is not None:
            order_type = OrderType.LIMIT
        
        # Default leverage if not specified
        if leverage is None:
            leverage = 1
        
        return Signal(
            signal_id=cls._generate_signal_id(symbol),
            symbol=symbol,
            signal_type=signal_type,
            order_type=order_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=int(leverage),
            status=SignalStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @classmethod
    def parse_close(cls, message: str) -> Optional[SignalClose]:
        """Parse a /close command."""
        match = cls.CLOSE_PATTERN.match(message.strip())
        if match:
            signal_id = match.group(1).upper()
            symbol = cls.extract_symbol_from_id(signal_id)
            percent = float(match.group(2)) if match.group(2) else 100.0
            
            if not symbol:
                return None
                
            return SignalClose(
                signal_id=signal_id, 
                symbol=symbol,
                percentage=percent
            )
        return None
    
    @classmethod
    def parse_leverage(cls, message: str) -> Optional[SignalLeverage]:
        """Parse a /leverage command."""
        match = cls.LEVERAGE_PATTERN.match(message.strip())
        if match:
            signal_id = match.group(1).upper()
            leverage = int(match.group(2))
            symbol = cls.extract_symbol_from_id(signal_id)
            
            if not symbol:
                return None
                
            return SignalLeverage(
                signal_id=signal_id,
                symbol=symbol,
                leverage=leverage
            )
        return None
    
    @classmethod
    def parse_edit_sl_tp(cls, message: str) -> Optional[SignalEditSLTP]:
        """Parse a /editsltp command."""
        text = message.strip()
        
        match = cls.EDIT_SLTP_PATTERN.search(text)
        if not match:
            return None
            
        signal_id = match.group(1).upper()
        
        symbol = cls.extract_symbol_from_id(signal_id)
        if not symbol:
            return None
        
        # Extract SL and TP using labeled parameter patterns
        sl_match = cls.PARAM_PATTERNS['sl'].search(text)
        tp_match = cls.PARAM_PATTERNS['tp'].search(text)
        
        stop_loss = float(sl_match.group(1)) if sl_match else None
        take_profit = float(tp_match.group(1)) if tp_match else None
        
        # Must have at least one of SL or TP
        if stop_loss is None and take_profit is None:
            return None
        
        return SignalEditSLTP(
            signal_id=signal_id,
            symbol=symbol,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    @classmethod
    def extract_symbol_from_id(cls, signal_id: str) -> Optional[str]:
        """Extract the trading symbol from a signal ID."""
        parts = signal_id.split("-")
        if len(parts) >= 3:
            return parts[2].upper()
        return None
    
    @classmethod
    def parse(cls, message: str) -> Optional[Union[Signal, SignalClose, SignalEditSLTP, SignalLeverage]]:
        """Parse any signal command."""
        message = message.strip()
        
        lower_msg = message.lower()
        if lower_msg.startswith('/signal'):
            return cls.parse_signal(message)
        elif lower_msg.startswith('/close'):
            return cls.parse_close(message)
        elif lower_msg.startswith('/leverage'):
            return cls.parse_leverage(message)
        elif lower_msg.startswith('/editsltp'):
            return cls.parse_edit_sl_tp(message)
        
        # Try to parse as multi-line signal (no /signal prefix)
        return cls.parse_signal(message)


def format_signal_summary(signal: Signal) -> str:
    """Format a signal for display."""
    order_type_str = "MARKET" if signal.order_type == OrderType.MARKET else f"LIMIT @ {signal.entry_price}"
    
    return f"""
📊 **Signal Broadcast**
━━━━━━━━━━━━━━━━━━━━
🆔 ID: `{signal.signal_id}`
📈 {signal.signal_type.value} {signal.symbol}
📋 Order: {order_type_str}
🛑 Stop Loss: {signal.stop_loss or 'None'}
🎯 Take Profit: {signal.take_profit or 'None'}
⚡ Leverage: {signal.leverage}x
━━━━━━━━━━━━━━━━━━━━
""".strip()

"""
Signal Broadcaster - Execute trades for all subscribers when a signal is received.

This is the core of the centralized system:
1. Receive signal from admin
2. Loop through all active subscribers
3. Execute trade on each subscriber's Mudrex account
4. Notify each subscriber of result via Telegram DM
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import httpx

from .database import Database, Subscriber
from .signal_parser import Signal, SignalType, OrderType, SignalUpdate, SignalClose

logger = logging.getLogger(__name__)

# Mudrex API base URL
MUDREX_API_BASE = "https://trade.mudrex.com/fapi/v1"


class TradeStatus(Enum):
    SUCCESS = "SUCCESS"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    API_ERROR = "API_ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class TradeResult:
    """Result of a trade execution for one subscriber."""
    subscriber_id: int
    username: Optional[str]
    status: TradeStatus
    message: str
    order_id: Optional[str] = None


class MudrexTrader:
    """Execute trades on Mudrex for a single user."""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self.client.aclose()
    
    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "X-Authentication": self.api_secret,
            "Content-Type": "application/json",
        }
    
    async def get_balance(self) -> float:
        """Get available USDT balance."""
        try:
            resp = await self.client.get(
                f"{MUDREX_API_BASE}/wallet",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("available_balance", 0))
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        try:
            resp = await self.client.patch(
                f"{MUDREX_API_BASE}/leverage?is_symbol",
                headers=self._headers(),
                json={"symbol": symbol, "leverage": leverage},
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Optional[str]:
        """
        Create an order on Mudrex.
        
        Returns order_id on success, None on failure.
        """
        try:
            payload = {
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "quantity": quantity,
            }
            
            if price and order_type == "LIMIT":
                payload["price"] = price
            if stop_loss:
                payload["stop_loss"] = stop_loss
            if take_profit:
                payload["take_profit"] = take_profit
            
            resp = await self.client.post(
                f"{MUDREX_API_BASE}/orders?is_symbol",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("order_id")
        except httpx.HTTPStatusError as e:
            logger.error(f"Order failed: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return None


class SignalBroadcaster:
    """
    Broadcast signals to all subscribers.
    
    Executes trades in parallel for all active subscribers.
    """
    
    def __init__(self, database: Database):
        self.db = database
    
    async def broadcast_signal(self, signal: Signal) -> List[TradeResult]:
        """
        Execute a signal for all active subscribers.
        
        Args:
            signal: The parsed trading signal
            
        Returns:
            List of trade results for each subscriber
        """
        logger.info(f"Broadcasting signal {signal.signal_id} to all subscribers")
        
        # Get all active subscribers
        subscribers = await self.db.get_active_subscribers()
        
        if not subscribers:
            logger.warning("No active subscribers to broadcast to")
            return []
        
        logger.info(f"Executing for {len(subscribers)} subscribers")
        
        # Save signal to database
        await self.db.save_signal(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            signal_type=signal.signal_type.value,
            order_type=signal.order_type.value,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            leverage=signal.leverage,
        )
        
        # Execute for all subscribers in parallel
        tasks = [
            self._execute_for_subscriber(signal, subscriber)
            for subscriber in subscribers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        trade_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Trade failed for subscriber: {result}")
                trade_results.append(TradeResult(
                    subscriber_id=subscribers[i].telegram_id,
                    username=subscribers[i].username,
                    status=TradeStatus.API_ERROR,
                    message=str(result),
                ))
            else:
                trade_results.append(result)
        
        # Log summary
        success_count = sum(1 for r in trade_results if r.status == TradeStatus.SUCCESS)
        logger.info(f"Signal {signal.signal_id}: {success_count}/{len(trade_results)} successful")
        
        return trade_results
    
    async def _execute_for_subscriber(
        self,
        signal: Signal,
        subscriber: Subscriber,
    ) -> TradeResult:
        """Execute a signal for a single subscriber."""
        trader = MudrexTrader(subscriber.api_key, subscriber.api_secret)
        
        try:
            # Check balance
            balance = await trader.get_balance()
            if balance < subscriber.trade_amount_usdt:
                await self.db.record_trade(
                    telegram_id=subscriber.telegram_id,
                    signal_id=signal.signal_id,
                    symbol=signal.symbol,
                    side=signal.signal_type.value,
                    order_type=signal.order_type.value,
                    status="INSUFFICIENT_BALANCE",
                    error_message=f"Balance: {balance:.2f} USDT",
                )
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.INSUFFICIENT_BALANCE,
                    message=f"Insufficient balance: {balance:.2f} USDT",
                )
            
            # Set leverage (capped at subscriber's max)
            leverage = min(signal.leverage, subscriber.max_leverage)
            await trader.set_leverage(signal.symbol, leverage)
            
            # Determine order params
            side = "BUY" if signal.signal_type == SignalType.LONG else "SELL"
            order_type = "MARKET" if signal.order_type == OrderType.MARKET else "LIMIT"
            
            # Create order
            order_id = await trader.create_order(
                symbol=signal.symbol,
                side=side,
                order_type=order_type,
                quantity=subscriber.trade_amount_usdt,
                price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
            )
            
            if order_id:
                await self.db.record_trade(
                    telegram_id=subscriber.telegram_id,
                    signal_id=signal.signal_id,
                    symbol=signal.symbol,
                    side=side,
                    order_type=order_type,
                    status="SUCCESS",
                    quantity=subscriber.trade_amount_usdt,
                    entry_price=signal.entry_price,
                )
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SUCCESS,
                    message=f"{side} {signal.symbol} @ {order_type}",
                    order_id=order_id,
                )
            else:
                await self.db.record_trade(
                    telegram_id=subscriber.telegram_id,
                    signal_id=signal.signal_id,
                    symbol=signal.symbol,
                    side=side,
                    order_type=order_type,
                    status="API_ERROR",
                    error_message="Order creation failed",
                )
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.API_ERROR,
                    message="Order creation failed",
                )
        
        finally:
            await trader.close()
    
    async def broadcast_close(self, close: SignalClose) -> List[TradeResult]:
        """
        Broadcast a close signal to all subscribers.
        
        Note: This is more complex as we need to track which subscribers
        have open positions for this signal. For MVP, we'll mark the signal
        as closed and subscribers can manage manually.
        """
        logger.info(f"Broadcasting close for signal {close.signal_id}")
        
        await self.db.close_signal(close.signal_id)
        
        # For MVP, just mark as closed. Position closing would require
        # tracking position IDs per subscriber, which we can add later.
        return []


def format_broadcast_summary(signal: Signal, results: List[TradeResult]) -> str:
    """Format broadcast results for admin notification."""
    success = sum(1 for r in results if r.status == TradeStatus.SUCCESS)
    failed = sum(1 for r in results if r.status == TradeStatus.API_ERROR)
    insufficient = sum(1 for r in results if r.status == TradeStatus.INSUFFICIENT_BALANCE)
    
    return f"""
📡 **Signal Broadcast Complete**
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: `{signal.signal_id}`
📊 {signal.signal_type.value} {signal.symbol}

**Results:**
✅ Success: {success}
💰 Insufficient Balance: {insufficient}
❌ Failed: {failed}
━━━━━━━━━━━━━━━━━━━━
Total: {len(results)} subscribers
""".strip()


def format_user_trade_notification(signal: Signal, result: TradeResult) -> str:
    """Format trade result notification for a subscriber."""
    if result.status == TradeStatus.SUCCESS:
        return f"""
✅ **Trade Executed**
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: `{signal.signal_id}`
📊 {signal.signal_type.value} {signal.symbol}
📋 {signal.order_type.value}
🛑 SL: {signal.stop_loss}
🎯 TP: {signal.take_profit}
⚡ Leverage: {signal.leverage}x
━━━━━━━━━━━━━━━━━━━━
""".strip()
    
    elif result.status == TradeStatus.INSUFFICIENT_BALANCE:
        return f"""
💰 **Trade Skipped - Insufficient Balance**
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: `{signal.signal_id}`
📊 {signal.signal_type.value} {signal.symbol}

{result.message}

Top up your Mudrex wallet to receive future signals.
━━━━━━━━━━━━━━━━━━━━
""".strip()
    
    else:
        return f"""
❌ **Trade Failed**
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: `{signal.signal_id}`
📊 {signal.signal_type.value} {signal.symbol}

Error: {result.message}
━━━━━━━━━━━━━━━━━━━━
""".strip()

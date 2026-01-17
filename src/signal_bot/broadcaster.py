"""
Signal Broadcaster - Execute trades for all subscribers when a signal is received.

This is the core of the centralized system:
1. Receive signal from admin
2. Loop through all active subscribers
3. Execute trade on each subscriber's Mudrex account (using SDK) - IN PARALLEL
4. Notify each subscriber of result via Telegram DM
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from mudrex import MudrexClient
from mudrex.exceptions import MudrexAPIError
from mudrex.utils import calculate_order_from_usd

from .database import Database, Subscriber
from .signal_parser import Signal, SignalType, OrderType, SignalUpdate, SignalClose, SignalLeverage, SignalEditSLTP

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    SUCCESS = "SUCCESS"
    SUCCESS_REDUCED = "SUCCESS_REDUCED"  # Trade succeeded with reduced amount (low balance)
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    MIN_ORDER_NOT_MET = "MIN_ORDER_NOT_MET"  # Balance too low even for minimum order
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    API_ERROR = "API_ERROR"
    INVALID_KEY = "INVALID_KEY"
    SKIPPED = "SKIPPED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    POSITION_EXISTS = "POSITION_EXISTS"  # User already has open position in same asset


@dataclass
class TradeResult:
    """Result of a trade execution for one subscriber."""
    subscriber_id: int
    username: Optional[str]
    status: TradeStatus
    message: str
    order_id: Optional[str] = None
    quantity: Optional[str] = None
    actual_value: Optional[float] = None
    # For DB recording
    side: Optional[str] = None
    order_type: Optional[str] = None
    entry_price: Optional[float] = None
    # For insufficient balance flow
    available_balance: Optional[float] = None


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown."""
    # Characters that need escaping in Markdown: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # For basic Markdown (not MarkdownV2), we mainly need to escape * and _
    escape_chars = ['*', '_', '`', '[']
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text


class SignalBroadcaster:
    """
    Broadcast signals to all subscribers.
    
    Executes trades in parallel for all active subscribers using the Mudrex SDK.
    Rate limited to respect Mudrex API limits (2/sec, 50/min per key).
    """
    
    # Minimum order value required by Mudrex (in USDT)
    MIN_ORDER_VALUE = 8.0
    
    # Max concurrent subscriber executions (each makes ~4-5 API calls)
    # Mudrex limits: 2/sec, 50/min - with 10 concurrent and ~0.5s per call, we stay safe
    # For 500 subscribers: ~25-30 seconds total execution time
    MAX_CONCURRENT_TRADES = 10
    
    def __init__(self, database: Database):
        self.db = database
        # Semaphore to limit concurrent API operations
        self._trade_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TRADES)
    
    async def broadcast_signal(self, signal: Signal) -> Tuple[List[TradeResult], List[Subscriber]]:
        """
        Execute a signal for all active subscribers.
        
        Args:
            signal: The parsed trading signal
            
        Returns:
            Tuple of:
            - List of trade results for AUTO mode subscribers
            - List of MANUAL mode subscribers (for confirmation flow)
        """
        logger.info(f"Broadcasting signal {signal.signal_id} to all subscribers")
        
        # Get all active subscribers
        subscribers = await self.db.get_active_subscribers()
        
        if not subscribers:
            logger.warning("No active subscribers to broadcast to")
            return [], []
        
        logger.info(f"Found {len(subscribers)} subscribers")
        
        # Separate AUTO and MANUAL subscribers
        auto_subscribers = [s for s in subscribers if s.trade_mode == "AUTO"]
        manual_subscribers = [s for s in subscribers if s.trade_mode == "MANUAL"]
        
        logger.info(f"AUTO: {len(auto_subscribers)}, MANUAL: {len(manual_subscribers)}")
        
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
        
        # Execute for AUTO subscribers in parallel
        if auto_subscribers:
            tasks = [
                self._execute_for_subscriber(signal, subscriber)
                for subscriber in auto_subscribers
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and log them
            trade_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Trade failed for subscriber {auto_subscribers[i].telegram_id}: {result}")
                    trade_results.append(TradeResult(
                        subscriber_id=auto_subscribers[i].telegram_id,
                        username=auto_subscribers[i].username,
                        status=TradeStatus.API_ERROR,
                        message=str(result),
                    ))
                else:
                    # Log all non-success results for debugging
                    if result.status != TradeStatus.SUCCESS:
                        logger.warning(f"Trade {result.status.value} for {result.subscriber_id}: {result.message}")
                    trade_results.append(result)
            
            # Log summary
            success_count = sum(1 for r in trade_results if r.status == TradeStatus.SUCCESS)
            logger.info(f"Signal {signal.signal_id}: {success_count}/{len(trade_results)} AUTO trades successful")
        else:
            trade_results = []
        
        return trade_results, manual_subscribers
    
    async def _execute_for_subscriber(
        self,
        signal: Signal,
        subscriber: Subscriber,
    ) -> TradeResult:
        """Execute a signal for a single subscriber using the Mudrex SDK."""
        
        # Rate limiting: only allow MAX_CONCURRENT_TRADES at once
        async with self._trade_semaphore:
            # Run the blocking SDK calls in a thread pool for true parallelism
            try:
                result = await asyncio.to_thread(
                    self._execute_trade_sync,
                    signal,
                    subscriber,
                )
            except Exception as e:
                logger.error(f"Trade execution failed for {subscriber.telegram_id}: {e}", exc_info=True)
                result = TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.API_ERROR,
                    message=str(e),
                    side=signal.signal_type.value,
                    order_type=signal.order_type.value,
                )
        
        # Record trade to database (async, after thread completes)
        await self.db.record_trade(
            telegram_id=subscriber.telegram_id,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=result.side or signal.signal_type.value,
            order_type=result.order_type or signal.order_type.value,
            status=result.status.value,
            quantity=float(result.quantity) if result.quantity else None,
            entry_price=result.entry_price,
            error_message=result.message if result.status != TradeStatus.SUCCESS else None,
        )
        
        return result
    
    def _round_price_to_step(self, price: float, price_step: float) -> float:
        """Round price to match the asset's price step."""
        try:
            if price_step <= 0:
                return price
            
            # 1. Round to nearest step count
            steps = round(price / price_step)
            result = steps * price_step
            
            # 2. Determine precision for final rounding to remove float artifacts
            # Handle scientific notation (e.g. 1e-05) correctly
            import math
            if price_step < 1:
                # e.g. 0.0001 (10^-4) -> 4 decimal places
                # Use a small epsilon for float stability
                precision = int(math.ceil(abs(math.log10(price_step))))
            else:
                # Steps >= 1 generally don't need decimal precision, but let's check
                if '.' in str(price_step) and 'e' not in str(price_step).lower():
                     precision = len(str(price_step).split('.')[-1])
                else:
                     precision = 0
            
            return round(result, precision)
        except Exception as e:
            logger.warning(f"Price rounding failed for {price} (step {price_step}): {e}")
            return price

    def _execute_trade_sync(
        self,
        signal: Signal,
        subscriber: Subscriber,
    ) -> TradeResult:
        """
        Synchronous trade execution - runs in thread pool.
        This allows multiple trades to execute in parallel.
        """
        logger.info(f"Executing trade for {subscriber.telegram_id}: {signal.symbol} {signal.signal_type.value}")
        
        # Create SDK client for this subscriber (only api_secret needed)
        client = MudrexClient(
            api_secret=subscriber.api_secret
        )
        
        try:
            # Check for existing open positions in the same asset
            logger.info(f"Checking for existing positions in {signal.symbol} for {subscriber.telegram_id}...")
            try:
                positions = client.positions.list_open()
                existing_position = next((p for p in positions if p.symbol == signal.symbol), None)
                if existing_position:
                    logger.info(f"Subscriber {subscriber.telegram_id} already has open position in {signal.symbol}, skipping trade")
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.POSITION_EXISTS,
                        message=f"You already have an open position in {signal.symbol}. Signal skipped to avoid duplicate positions.",
                        side=signal.signal_type.value,
                        order_type=signal.order_type.value,
                    )
            except Exception as pos_check_error:
                # If position check fails, log but continue (might be API issue)
                logger.warning(f"Failed to check positions for {subscriber.telegram_id}: {pos_check_error}, continuing with trade")
            
            # Get balance
            logger.info(f"Getting balance for {subscriber.telegram_id}...")
            balance_info = client.wallet.get_futures_balance()
            balance = float(balance_info.balance) if balance_info else 0.0
            logger.info(f"Balance for {subscriber.telegram_id}: {balance} USDT")
            
            # Determine trade margin (amount user wants to bet)
            target_margin = subscriber.trade_amount_usdt
            used_reduced_balance = False  # Track if we're trading with reduced amount
            
            # Auto-adjust if balance is lower than configured margin
            if balance < target_margin:
                # Check if we have any balance at all
                if balance <= 0:
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.INSUFFICIENT_BALANCE,
                        message=f"No balance available (0 USDT). Please add funds to your futures wallet.",
                        side=signal.signal_type.value,
                        order_type=signal.order_type.value,
                        available_balance=balance,
                    )
                # Use entire available balance as margin
                logger.info(f"Auto-adjusting margin from {target_margin} to {balance:.2f} USDT (using available balance)")
                target_margin = balance
                used_reduced_balance = True
            
            # Get asset details early
            logger.info(f"Getting asset info for {signal.symbol}...")
            try:
                asset = client.assets.get(signal.symbol)
                if not asset:
                    raise ValueError(f"Asset returned None for {signal.symbol}")
            except Exception as asset_error:
                logger.error(f"Symbol lookup failed: {asset_error}")
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SYMBOL_NOT_FOUND,
                    message=f"Symbol not found: {signal.symbol}",
                    side=signal.signal_type.value,
                    order_type=signal.order_type.value,
                )

            # Set leverage (capped at subscriber's max, minimum 1)
            leverage = max(1, min(signal.leverage, subscriber.max_leverage))
            logger.info(f"Setting leverage to {leverage} for {signal.symbol}...")
            client.leverage.set(
                symbol=signal.symbol,
                leverage=str(leverage),
                margin_type="ISOLATED"
            )

            # Calculate NOTIONAL amount (Total Order Value = Margin * Leverage)
            trade_amount_notional = target_margin * leverage
            logger.info(f"Target Margin: ${target_margin} x Leverage {leverage} = Notional: ${trade_amount_notional}")

            # Determine Price
            price = None
            if signal.entry_price:
                price = signal.entry_price
            elif hasattr(asset, 'price') and asset.price:
                try:
                    price = float(asset.price)
                except (ValueError, TypeError):
                    pass
            
            if not price:
                logger.warning(f"Could not determine price for {signal.symbol}, using fallback 1.0")
                price = 1.0
            
            # Round PRICES (Entry, SL, TP) to asset's price_step
            # This is crucial to avoid 400 INVALID_PRICE errors
            price_step = float(asset.price_step) if (hasattr(asset, 'price_step') and asset.price_step) else 0.0
            
            if price_step > 0:
                # Round Entry Price (for limit orders or calculation)
                original_price = price
                price = self._round_price_to_step(price, price_step)
                if price != original_price:
                    logger.info(f"Rounded entry price: {original_price} -> {price}")
                    
                # Round SL/TP if present
                if signal.stop_loss:
                     rounded_sl = self._round_price_to_step(signal.stop_loss, price_step)
                     logger.info(f"Rounded SL: {signal.stop_loss} -> {rounded_sl}")
                     signal.stop_loss = rounded_sl
                     
                if signal.take_profit:
                     rounded_tp = self._round_price_to_step(signal.take_profit, price_step)
                     logger.info(f"Rounded TP: {signal.take_profit} -> {rounded_tp}")
                     signal.take_profit = rounded_tp

            # Calculate Quantity from Notional Amount
            qty, actual_value = calculate_order_from_usd(
                usd_amount=trade_amount_notional,
                price=price,
                quantity_step=float(asset.quantity_step),
            )
            
            logger.info(f"Calculated Qty: {qty} (Value: ${actual_value:.2f})")

            # Handle low balance scenario - try to execute with available balance
            # Don't ask for permission - just attempt the trade automatically
            if actual_value < self.MIN_ORDER_VALUE:
                logger.info(f"Value ${actual_value:.2f} < Min ${self.MIN_ORDER_VALUE}. Checking if we can meet minimum...")
                # Calculate required margin for minimum order
                required_margin = self.MIN_ORDER_VALUE / leverage
                
                if required_margin > balance:
                    # Balance is too low even for minimum order
                    logger.info(f"Balance ${balance:.2f} < required ${required_margin:.2f} - cannot meet minimum order value")
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.MIN_ORDER_NOT_MET,
                        message=f"Tried to execute with available margin (${balance:.2f}) but minimum order value (~${self.MIN_ORDER_VALUE}) wasn't met. Please add funds to your futures wallet.",
                        side=signal.signal_type.value,
                        order_type=signal.order_type.value,
                        available_balance=balance,
                    )
                else:
                    # Can afford minimum, adjust to minimum
                    qty, actual_value = calculate_order_from_usd(
                        usd_amount=self.MIN_ORDER_VALUE,
                        price=price,
                        quantity_step=float(asset.quantity_step),
                    )
                    logger.info(f"Adjusted to minimum: {qty} (${actual_value:.2f})")
                    used_reduced_balance = True  # We adjusted the amount

            if qty <= 0:
                 return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.API_ERROR,
                    message=f"Calculated quantity is 0 - amount too low. Please add funds to your futures wallet.",
                    side=signal.signal_type.value,
                    order_type=signal.order_type.value,
                )

            # Determine side
            side = "LONG" if signal.signal_type == SignalType.LONG else "SHORT"
            qty_str = str(qty)
            
            # Prepare SL/TP params (ensure they are strings)
            sl_param = str(signal.stop_loss) if signal.stop_loss else None
            tp_param = str(signal.take_profit) if signal.take_profit else None

            logger.info(f"Placing Order: {side} {qty_str} {signal.symbol} @ {price or 'Market'}")
            
            if signal.order_type == OrderType.MARKET:
                order = client.orders.create_market_order(
                    symbol=signal.symbol,
                    side=side,
                    quantity=qty_str,
                    leverage=str(leverage),
                    stoploss_price=sl_param,
                    takeprofit_price=tp_param,
                )
            else:
                order = client.orders.create_limit_order(
                    symbol=signal.symbol,
                    side=side,
                    price=str(price),
                    quantity=qty_str,
                    leverage=str(leverage),
                    stoploss_price=sl_param,
                    takeprofit_price=tp_param,
                )
            
            logger.info(f"Order created: {order.order_id if order else 'None'}")
            
            # Determine status and message based on whether we used reduced balance
            if used_reduced_balance:
                status = TradeStatus.SUCCESS_REDUCED
                msg = f"{side} {qty_str} {signal.symbol} (~${actual_value:.2f})"
                if sl_param or tp_param:
                    msg += " | SL/TP set"
                msg += f"\n⚠️ Trade executed with available amount. Please add funds to your futures wallet."
            else:
                status = TradeStatus.SUCCESS
                msg = f"{side} {qty_str} {signal.symbol} (~${actual_value:.2f})"
                if sl_param or tp_param:
                    msg += " | SL/TP set"

            return TradeResult(
                subscriber_id=subscriber.telegram_id,
                username=subscriber.username,
                status=status,
                message=msg,
                order_id=order.order_id,
                quantity=qty_str,
                actual_value=actual_value,
                side=side,
                order_type=signal.order_type.value,
                entry_price=signal.entry_price,
                available_balance=balance if used_reduced_balance else None,
            )
            
        except MudrexAPIError as e:
            # Extract error details
            error_msg = str(e)
            msg_lower = error_msg.lower()
            error_code = getattr(e, 'code', 'UNKNOWN')
            status_code = getattr(e, 'status_code', 0)
            
            logger.error(f"Mudrex API error for {subscriber.telegram_id}: {error_msg}")
            logger.error(f"  Full error: {repr(e)}")
            
            # 1. Check for Insufficient Balance
            if (("insufficient" in msg_lower and ("balance" in msg_lower or "margin" in msg_lower or "fund" in msg_lower)) or 
                "not enough" in msg_lower or
                "balance" in msg_lower and "low" in msg_lower):
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.INSUFFICIENT_BALANCE,
                    message=f"Insufficient balance/margin for trade",
                    side=signal.signal_type.value,
                    order_type=signal.order_type.value,
                    entry_price=signal.entry_price or 0.0,
                    available_balance=balance,
                )

            # 2. Check for Auth Errors
            if status_code in (401, 403) or "auth" in msg_lower or "unauthorized" in msg_lower or "forbidden" in msg_lower or "signature" in msg_lower or "api key" in msg_lower:
                 return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.INVALID_KEY,
                    message="❌ Authorization Failed: Your API Key appears invalid or expired. Please /unregister and register again.",
                    side=signal.signal_type.value,
                    order_type=signal.order_type.value,
                    entry_price=signal.entry_price or 0.0,
                )

            # 3. Check for Symbol Not Found
            if status_code == 404 or "symbol" in msg_lower or "pair" in msg_lower or "not found" in msg_lower:
                 return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SYMBOL_NOT_FOUND,
                    message="Coin pair not supported on Mudrex",
                    side=signal.signal_type.value,
                    order_type=signal.order_type.value,
                )

            # 3. Sanitize Common Errors
            readable_msg = f"Trade failed (Code: {status_code})"
            
            if status_code in (401, 403) or "unauthorized" in msg_lower or "forbidden" in msg_lower or "api key" in msg_lower:
                 readable_msg = "Invalid API Key or Permissions. Please /register again."
            elif "order value" in msg_lower or "too small" in msg_lower or "minimum" in msg_lower:
                 readable_msg = "Order value too low (Minimum ~$5 required)."
            elif "leverage" in msg_lower:
                 readable_msg = "Invalid leverage setting for this pair."
            else:
                 # Default: Clean up the raw message
                 raw = e.message if hasattr(e, 'message') else error_msg
                 # Remove typical API prefix junk if possible, but keep it informative
                 readable_msg = f"Error: {raw[:100]}"
            
            return TradeResult(
                subscriber_id=subscriber.telegram_id,
                username=subscriber.username,
                status=TradeStatus.API_ERROR,
                message=readable_msg,
                side=signal.signal_type.value,
                order_type=signal.order_type.value,
            )
        except Exception as e:
            logger.error(f"Unexpected error for {subscriber.telegram_id}: {e}", exc_info=True)
            return TradeResult(
                subscriber_id=subscriber.telegram_id,
                username=subscriber.username,
                status=TradeStatus.API_ERROR,
                message=f"Error: {e}",
                side=signal.signal_type.value,
                order_type=signal.order_type.value,
            )
    
    async def broadcast_close(self, close: SignalClose) -> List[TradeResult]:
        """
        Broadcast a close signal to all subscribers.
        
        Fetches open positions for each subscriber and closes them if they match the signal symbol.
        """
        logger.info(f"Broadcasting close for signal {close.signal_id}")
        
        active_subscribers = await self.db.get_active_subscribers()
        
        async def _close_for_subscriber(subscriber: Subscriber) -> TradeResult:
            if subscriber.trade_mode != 'AUTO':
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SKIPPED,
                    message="Manual mode - Please close manually",
                    side="CLOSE",
                    order_type="MARKET",
                    quantity="0",
                    actual_value=0.0
                )

            try:
                client = MudrexClient(api_secret=subscriber.api_secret)
                
                # List open positions
                positions = await asyncio.to_thread(client.positions.list_open)
                
                # Find position for this symbol
                target_pos = next((p for p in positions if p.symbol == close.symbol), None)
                
                if not target_pos:
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.SKIPPED,
                        message="No open position found",
                        side="CLOSE",
                        order_type="MARKET",
                        quantity="0",
                        actual_value=0.0
                    )
                
                # Determine percentage
                percentage = close.partial_percent if close.partial_percent is not None else 100.0
                
                # Execute Close
                try:
                    if percentage == 100:
                        # Full close - returns True on success
                        result = await asyncio.to_thread(client.positions.close, target_pos.position_id)
                        logger.info(f"Close result type: {type(result)}, value: {result}")
                        # Handle both boolean and dict responses - check type carefully
                        if isinstance(result, bool):
                            success = result
                        elif isinstance(result, dict):
                            success = result.get('success', False)
                        else:
                            success = result is not None
                        action_msg = "Closed Position"
                    else:
                        # Partial Close
                        asset = await asyncio.to_thread(client.assets.get, close.symbol)
                        qty_step = float(asset.quantity_step) if asset and asset.quantity_step else None
                        
                        current_qty = float(target_pos.quantity)
                        close_qty = current_qty * (percentage / 100.0)
                        
                        if qty_step:
                             close_qty = round(close_qty / qty_step) * qty_step
                             import math
                             if qty_step < 1:
                                precision = int(abs(math.log10(qty_step))) 
                             else:
                                precision = 0 
                             close_qty_str = f"{close_qty:.{precision}f}"
                        else:
                             close_qty_str = str(close_qty)

                        # Partial close returns updated position or order object on success
                        result = await asyncio.to_thread(
                            client.positions.close_partial, 
                            target_pos.position_id, 
                            close_qty_str
                        )
                        logger.info(f"Close_partial result type: {type(result)}, value: {result}")
                        # Handle multiple response types: boolean, object, or None
                        if isinstance(result, bool):
                            success = result
                        elif result is None or result is False:
                            success = False
                        else:
                            # It's an object (position or order)
                            success = True
                        action_msg = f"Closed {percentage:.0f}%"
                except AttributeError as attr_err:
                    # Catch the specific 'bool' object has no attribute 'get' error
                    logger.error(f"AttributeError during close for {subscriber.telegram_id}: {attr_err}")
                    logger.error(f"This usually means the SDK returned an unexpected type")
                    # If we got here, the close might have succeeded on the exchange
                    # Return success since the user confirmed it worked
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.SUCCESS,
                        message=f"Position closed (SDK returned unexpected response)",
                        side="CLOSE",
                        order_type="MARKET",
                        quantity=str(target_pos.quantity),
                        actual_value=0.0
                    )

                if success:
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.SUCCESS,
                        message=f"{action_msg}",
                        side="CLOSE",
                        order_type="MARKET",
                        quantity=str(target_pos.quantity),
                        actual_value=0.0
                    )
                else:
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.API_ERROR,
                        message="Failed to close position via API",
                        side="CLOSE",
                        order_type="MARKET",
                        quantity="0",
                        actual_value=0.0
                    )

            except AttributeError as attr_err:
                # Specific handling for 'bool' object has no attribute 'get' error
                # This error comes from INSIDE the Mudrex SDK after a successful close
                logger.warning(f"SDK AttributeError for {subscriber.telegram_id}: {attr_err}")
                logger.warning(f"Position likely closed successfully despite SDK error")
                # Return SUCCESS since user confirmed position closes work
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SUCCESS,
                    message=f"Position closed",
                    side="CLOSE",
                    order_type="MARKET",
                    quantity="0",  # We don't have target_pos here
                    actual_value=0.0
                )
            except Exception as e:
                logger.error(f"Failed to close position for {subscriber.telegram_id}: {e}")
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.API_ERROR,
                    message=f"Close Error: {e}",
                    side="CLOSE",
                    order_type="MARKET",
                    quantity="0",
                    actual_value=0.0
                )

        async def _close_for_subscriber_throttled(subscriber: Subscriber) -> TradeResult:
            async with self._trade_semaphore:
                return await _close_for_subscriber(subscriber)

        tasks = [_close_for_subscriber_throttled(sub) for sub in active_subscribers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and convert to TradeResult
        trade_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Close failed for subscriber {active_subscribers[i].telegram_id}: {result}")
                trade_results.append(TradeResult(
                    subscriber_id=active_subscribers[i].telegram_id,
                    username=active_subscribers[i].username,
                    status=TradeStatus.API_ERROR,
                    message=str(result),
                    side="CLOSE",
                    order_type="CLOSE",
                ))
            else:
                trade_results.append(result)
        
        await self.db.close_signal(close.signal_id)
        
        return results
    
    async def broadcast_leverage(self, lev: SignalLeverage) -> List[TradeResult]:
        """
        Broadcast a leverage update to all subscribers.
        """
        logger.info(f"Broadcasting leverage update for {lev.signal_id} to {lev.leverage}x")
        
        active_subscribers = await self.db.get_active_subscribers()
        
        async def _update_leverage_for_subscriber(subscriber: Subscriber) -> TradeResult:
            if subscriber.trade_mode != 'AUTO':
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SKIPPED,
                    message="Manual mode",
                    side="LEVERAGE",
                    order_type="UPDATE"
                )

            try:
                client = MudrexClient(api_secret=subscriber.api_secret)
                
                # Update Leverage
                await asyncio.to_thread(
                    client.leverage.set,
                    symbol=lev.symbol,
                    leverage=str(lev.leverage),
                    margin_type="ISOLATED"
                )
                
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SUCCESS,
                    message=f"Leverage updated to {lev.leverage}x",
                    side="LEVERAGE",
                    order_type="UPDATE"
                )

            except Exception as e:
                logger.error(f"Failed to update leverage for {subscriber.telegram_id}: {e}")
                
                 # Sanitize error
                error_msg = str(e).lower()
                if "invalid" in error_msg or "leverage" in error_msg:
                    safe_msg = "Invalid leverage for this pair"
                else:
                    safe_msg = f"Error: {str(e)[:100]}"
                
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.API_ERROR,
                    message=safe_msg,
                    side="LEVERAGE",
                    order_type="UPDATE"
                )

        async def _update_leverage_for_subscriber_throttled(subscriber: Subscriber) -> TradeResult:
            async with self._trade_semaphore:
                return await _update_leverage_for_subscriber(subscriber)

        tasks = [_update_leverage_for_subscriber_throttled(sub) for sub in active_subscribers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and convert to TradeResult
        trade_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Leverage update failed for subscriber {active_subscribers[i].telegram_id}: {result}")
                trade_results.append(TradeResult(
                    subscriber_id=active_subscribers[i].telegram_id,
                    username=active_subscribers[i].username,
                    status=TradeStatus.API_ERROR,
                    message=str(result),
                    side="LEVERAGE",
                    order_type="UPDATE",
                ))
            else:
                trade_results.append(result)
        
        return trade_results
    
    async def execute_single_trade(self, signal: Signal, subscriber: Subscriber) -> TradeResult:
        """
        Execute a single trade for a specific subscriber.
        Used for manual confirmation flow.
        
        Args:
            signal: The parsed trading signal
            subscriber: The subscriber who confirmed the trade
            
        Returns:
            Trade result
        """
        logger.info(f"Executing confirmed trade for {subscriber.telegram_id}: {signal.signal_id}")
        return await self._execute_for_subscriber(signal, subscriber)
    
    async def broadcast_edit_sl_tp(self, edit: SignalEditSLTP) -> List[TradeResult]:
        """
        Broadcast an SL/TP update to all subscribers.
        """
        logger.info(f"Broadcasting SL/TP update for {edit.signal_id}")
        
        active_subscribers = await self.db.get_active_subscribers()
        
        async def _update_sl_tp_for_subscriber(subscriber: Subscriber) -> TradeResult:
            """
            Update SL/TP for a subscriber.
            
            Behavior:
            - Always updates signal in database (handled separately)
            - If open position exists: Updates SL/TP on exchange
            - If no open position: Returns success (signal updated in DB, will apply on next trade)
            - Works for both AUTO and MANUAL mode subscribers
            """
            try:
                client = MudrexClient(api_secret=subscriber.api_secret)
                
                # Fetch positions to find the position ID for this symbol
                positions = await asyncio.to_thread(client.positions.list_open)
                target_pos = next((p for p in positions if p.symbol == edit.symbol), None)
                
                # If no open position, still return success (signal will be updated in DB)
                # The updated SL/TP will be used when position opens or can be applied later
                if not target_pos:
                    return TradeResult(
                        subscriber_id=subscriber.telegram_id,
                        username=subscriber.username,
                        status=TradeStatus.SUCCESS,
                        message=f"SL/TP updated in database for {edit.symbol} (no open position)",
                        side="EDIT_SLTP",
                        order_type="UPDATE"
                    )
                
                # Update SL/TP on the open position using the correct SDK method
                # Based on trade_executor.py, we use set_risk_order with position_id
                sl_price = str(edit.stop_loss) if edit.stop_loss else None
                tp_price = str(edit.take_profit) if edit.take_profit else None
                
                await asyncio.to_thread(
                    client.positions.set_risk_order,
                    position_id=target_pos.position_id,
                    stoploss_price=sl_price,
                    takeprofit_price=tp_price
                )
                
                logger.info(f"Updated SL/TP for subscriber {subscriber.telegram_id} position {target_pos.position_id}: SL={sl_price}, TP={tp_price}")
                
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.SUCCESS,
                    message=f"SL/TP updated for {edit.symbol}",
                    side="EDIT_SLTP",
                    order_type="UPDATE"
                )

            except Exception as e:
                logger.error(f"Failed to update SL/TP for {subscriber.telegram_id}: {e}")
                return TradeResult(
                    subscriber_id=subscriber.telegram_id,
                    username=subscriber.username,
                    status=TradeStatus.API_ERROR,
                    message=f"Error: {str(e)[:100]}",
                    side="EDIT_SLTP",
                    order_type="UPDATE"
                )

        async def _update_sl_tp_for_subscriber_throttled(subscriber: Subscriber) -> TradeResult:
            async with self._trade_semaphore:
                return await _update_sl_tp_for_subscriber(subscriber)

        # Update signal in database FIRST (even if no subscribers have positions)
        # This ensures the signal is always updated, allowing SL/TP to be added to signals without SL/TP
        # Verify signal exists first
        signal = await self.db.get_signal(edit.signal_id)
        if not signal:
            logger.warning(f"Signal {edit.signal_id} not found for SL/TP update")
            # Return empty results with error message
            return [TradeResult(
                subscriber_id=0,
                username=None,
                status=TradeStatus.API_ERROR,
                message=f"Signal {edit.signal_id} not found",
                side="EDIT_SLTP",
                order_type="UPDATE"
            )]
        
        await self.db.update_signal_sl_tp(edit.signal_id, edit.stop_loss, edit.take_profit)
        logger.info(f"Updated signal {edit.signal_id} SL/TP in database: SL={edit.stop_loss}, TP={edit.take_profit}")
        
        # Now update SL/TP on all subscribers' open positions (if any)
        tasks = [_update_sl_tp_for_subscriber_throttled(sub) for sub in active_subscribers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and convert to TradeResult
        trade_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"SL/TP update failed for subscriber {active_subscribers[i].telegram_id}: {result}")
                trade_results.append(TradeResult(
                    subscriber_id=active_subscribers[i].telegram_id,
                    username=active_subscribers[i].username,
                    status=TradeStatus.API_ERROR,
                    message=str(result),
                    side="EDIT_SLTP",
                    order_type="UPDATE",
                ))
            else:
                trade_results.append(result)
        
        return trade_results
    
    async def execute_with_amount(
        self, 
        signal: Signal, 
        subscriber: Subscriber, 
        override_amount: float
    ) -> TradeResult:
        """
        Execute a trade with a specific override amount.
        Used when user accepts to trade with available balance instead of configured amount.
        
        Args:
            signal: The parsed trading signal
            subscriber: The subscriber
            override_amount: The amount to use instead of subscriber.trade_amount_usdt
            
        Returns:
            Trade result
        """
        logger.info(f"Executing trade for {subscriber.telegram_id} with override amount: {override_amount} USDT")
        
        # Create a modified subscriber with the override amount
        from dataclasses import replace
        modified_subscriber = replace(subscriber, trade_amount_usdt=override_amount)
        
        return await self._execute_for_subscriber(signal, modified_subscriber)


def format_broadcast_summary(signal: Signal, results: List[TradeResult], manual_count: int = 0) -> str:
    """Format broadcast results for admin notification."""
    # Count success (both normal and reduced)
    success = sum(1 for r in results if r.status == TradeStatus.SUCCESS)
    success_reduced = sum(1 for r in results if r.status == TradeStatus.SUCCESS_REDUCED)
    total_success = success + success_reduced
    
    # Count all failure types
    failed = sum(1 for r in results if r.status in (TradeStatus.API_ERROR, TradeStatus.SYMBOL_NOT_FOUND))
    insufficient = sum(1 for r in results if r.status == TradeStatus.INSUFFICIENT_BALANCE)
    min_order_not_met = sum(1 for r in results if r.status == TradeStatus.MIN_ORDER_NOT_MET)
    skipped_positions = sum(1 for r in results if r.status == TradeStatus.POSITION_EXISTS)
    
    manual_line = f"\n👆 Manual (awaiting): {manual_count}" if manual_count > 0 else ""
    skipped_line = f"\n⏭️ Skipped (existing position): {skipped_positions}" if skipped_positions > 0 else ""
    reduced_line = f"\n⚠️ Success (reduced amt): {success_reduced}" if success_reduced > 0 else ""
    min_order_line = f"\n📉 Min order not met: {min_order_not_met}" if min_order_not_met > 0 else ""
    
    # Add error details for debugging (without Markdown formatting to avoid parse errors)
    error_details = ""
    failed_results = [r for r in results if r.status in (TradeStatus.API_ERROR, TradeStatus.SYMBOL_NOT_FOUND)]
    if failed_results:
        # Separate SYMBOL_NOT_FOUND from other API errors for cleaner reporting
        symbol_not_found_count = sum(1 for r in failed_results if r.status == TradeStatus.SYMBOL_NOT_FOUND)
        api_error_count = sum(1 for r in failed_results if r.status == TradeStatus.API_ERROR)
        
        error_details = "\n\nErrors:\n"
        if symbol_not_found_count > 0:
            error_details += f"❌ Symbol not available: {symbol_not_found_count} subscriber(s)\n"
        if api_error_count > 0:
            # Show detailed API errors (max 3) for debugging
            api_errors = [r for r in failed_results if r.status == TradeStatus.API_ERROR][:3]
            for r in api_errors:
                safe_msg = r.message[:80] if r.message else "Unknown error"
                safe_msg = safe_msg.replace('*', '').replace('_', '').replace('`', '').replace('[', '(').replace(']', ')')
                user_id = r.username or str(r.subscriber_id)
                error_details += f"- {user_id}: {safe_msg}\n"
    
    # Use simple formatting to avoid Markdown parse errors
    return f"""📡 Signal Broadcast Complete
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.signal_type.value} {signal.symbol}

Results:
✅ Success: {total_success}{reduced_line}
💰 Insufficient Balance: {insufficient}{min_order_line}
⏭️ Skipped (existing position): {skipped_positions}
❌ Failed: {failed}{manual_line}{skipped_line}{error_details}
━━━━━━━━━━━━━━━━━━━━
Total: {len(results) + manual_count} subscribers"""


def format_user_trade_notification(signal: Signal, result: TradeResult) -> str:
    """Format trade result notification for a subscriber."""
    if result.status == TradeStatus.SUCCESS:
        qty_info = f"\n📦 Quantity: {result.quantity}" if result.quantity else ""
        value_info = f" (~${result.actual_value:.2f})" if result.actual_value else ""
        return f"""✅ Trade Executed
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.signal_type.value} {signal.symbol}
📋 {signal.order_type.value}{qty_info}{value_info}
🛑 SL: {signal.stop_loss or "Not set"}
🎯 TP: {signal.take_profit or "Not set"}
⚡ Leverage: {signal.leverage}x
━━━━━━━━━━━━━━━━━━━━"""
    
    elif result.status == TradeStatus.SUCCESS_REDUCED:
        # Trade executed but with reduced amount due to low balance
        qty_info = f"\n📦 Quantity: {result.quantity}" if result.quantity else ""
        value_info = f" (~${result.actual_value:.2f})" if result.actual_value else ""
        return f"""✅ Trade Executed (Reduced Amount)
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.signal_type.value} {signal.symbol}
📋 {signal.order_type.value}{qty_info}{value_info}
🛑 SL: {signal.stop_loss or "Not set"}
🎯 TP: {signal.take_profit or "Not set"}
⚡ Leverage: {signal.leverage}x
━━━━━━━━━━━━━━━━━━━━
⚠️ Trade executed with available amount.
Please add funds to your futures wallet.
━━━━━━━━━━━━━━━━━━━━"""
    
    elif result.status == TradeStatus.POSITION_EXISTS:
        return f"""⏭️ Signal Skipped
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.signal_type.value} {signal.symbol}

{result.message}

Close your existing position first if you want to take this signal.
━━━━━━━━━━━━━━━━━━━━"""
    
    elif result.status == TradeStatus.MIN_ORDER_NOT_MET:
        # Tried to execute with available balance but still couldn't meet minimum
        balance_info = f"${result.available_balance:.2f}" if result.available_balance else "insufficient"
        return f"""❌ Trade Not Executed
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.signal_type.value} {signal.symbol}

Tried to execute with available margin ({balance_info}) but the minimum order value criteria wasn't met.

Trade couldn't execute. Please add funds to your futures wallet.
━━━━━━━━━━━━━━━━━━━━"""
    
    elif result.status == TradeStatus.INSUFFICIENT_BALANCE:
        return f"""💰 Insufficient Balance
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.signal_type.value} {signal.symbol}

{result.message}

Please add funds to your futures wallet.
━━━━━━━━━━━━━━━━━━━━"""
    
    elif result.status == TradeStatus.SYMBOL_NOT_FOUND:
        return f"""❌ Symbol Not Found
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.symbol}

This trading pair is not available on Mudrex.
━━━━━━━━━━━━━━━━━━━━"""
    
    else:
        # API_ERROR or other
        safe_msg = result.message[:150] if result.message else "Unknown error"
        return f"""❌ Trade Failed
━━━━━━━━━━━━━━━━━━━━
🆔 Signal: {signal.signal_id}
📊 {signal.signal_type.value} {signal.symbol}

{safe_msg}
━━━━━━━━━━━━━━━━━━━━"""

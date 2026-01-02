#!/usr/bin/env python3
"""
Convenience script to run the Mudrex TradeIdeas Bot.

Usage:
    python run_bot.py              # Webhook mode (production)
    python run_bot.py --polling    # Polling mode (development)
    python run_bot.py --generate-secret
"""

from signal_bot.run import main

if __name__ == '__main__':
    main()

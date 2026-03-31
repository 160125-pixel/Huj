#!/usr/bin/env python3
"""Entry point for the Solana Memecoin Telegram Bot."""

import logging
from bot.telegram_bot import run_bot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

if __name__ == "__main__":
    run_bot()

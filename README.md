# Solana Memecoin Telegram Bot

A Telegram bot that creates Solana memecoins with dumb randomly-generated names, absurd supplies, and hilarious descriptions.

## Setup

1. **Clone and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   Fill in your `.env`:
   - `TELEGRAM_BOT_TOKEN` — Get from [@BotFather](https://t.me/BotFather)
   - `SOLANA_RPC_URL` — Defaults to devnet
   - `SOLANA_PRIVATE_KEY` — Base58 encoded private key of the wallet that pays for token creation

3. **Run the bot:**
   ```bash
   python main.py
   ```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/preview` | Preview a random memecoin (free) |
| `/preview <name>` | Preview with a custom name |
| `/create` | Deploy a random memecoin on Solana (costs SOL) |
| `/create <name>` | Deploy with a custom name |
| `/help` | Show help |

## How It Works

1. Generates a dumb name from random prefix + suffix combos (e.g. `DOGEPUMP`, `PEPELAMBO`, `CHONKWAGMI`)
2. Picks an absurdly large supply (e.g. 69,420,000,000,000)
3. Creates an SPL token on Solana
4. Mints the entire supply to your wallet
5. You're now a "crypto founder"

## Disclaimer

This is for fun / educational purposes. These tokens have zero value. NFA. DYOR.

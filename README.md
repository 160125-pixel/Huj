# Solana Copy Trade Bot

A Telegram bot that finds the most profitable Solana traders, tracks their wallets in real-time, and copies their trades automatically via Jupiter.

## Features

- **Top Trader Discovery** — Find wallets with the highest winrates via Birdeye
- **Wallet Tracking** — Monitor tracked wallets for new buys/sells in real-time
- **Trade Copying** — One-tap copy trades via Jupiter V6 aggregator
- **Portfolio Tracker** — View holdings, PnL per token, and total performance
- **Quick Buy/Sell** — Buy with preset SOL amounts, sell by percentage (25/50/100%)
- **Swap Alerts** — Get notified when tracked wallets make trades, with copy buttons

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```

| Variable | Where to get it |
|----------|----------------|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) |
| `SOLANA_PRIVATE_KEY` | Your wallet (base58 encoded) |
| `HELIUS_API_KEY` | [helius.dev](https://helius.dev) (free tier) |
| `BIRDEYE_API_KEY` | [birdeye.so](https://birdeye.so) (for trader data) |

### 3. Run
```bash
python main.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Main menu with all buttons |
| `/top` | Top traders leaderboard |
| `/track <address>` | Track a wallet |
| `/untrack <address>` | Stop tracking |
| `/portfolio` | View holdings + PnL |
| `/buy <mint> <sol>` | Buy a token |
| `/sell <mint> [pct]` | Sell a token |

## Architecture

```
bot/
  config.py          — Environment config
  top_traders.py     — Trader discovery via Birdeye API
  wallet_tracker.py  — Real-time wallet monitoring via RPC polling
  trade_copier.py    — Trade execution via Jupiter V6 API
  portfolio.py       — Holdings tracking + PnL calculation
  telegram_bot.py    — Telegram UI with inline buttons
main.py              — Entry point
```

## Flow

```
Discover Top Traders → Track Wallets → Detect Swaps → Copy Trades → Track PnL
```

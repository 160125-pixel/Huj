# Solana Memecoin Launcher Bot

A Telegram bot that finds trending memes, creates Solana memecoins with realistic profiles, auto-creates Telegram channels, and targets 10-20K market cap at launch.

## What It Does

1. **Scans trends** — Pulls trending topics from Reddit, CoinGecko, and curated meme lists
2. **Creates tokens** — Deploys SPL tokens on Solana with calculated tokenomics
3. **Generates profiles** — Realistic descriptions, taglines, roadmaps, and channel bios
4. **Creates channels** — Auto-creates a Telegram group for each coin with pinned info
5. **Targets market cap** — Calculates supply, price, and liquidity for $10-20K launch

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_API_ID` | From [my.telegram.org/apps](https://my.telegram.org/apps) |
| `TELEGRAM_API_HASH` | From [my.telegram.org/apps](https://my.telegram.org/apps) |
| `TELEGRAM_PHONE` | Phone number linked to Telegram account |
| `SOLANA_RPC_URL` | Solana RPC (defaults to devnet) |
| `SOLANA_PRIVATE_KEY` | Base58 wallet private key |
| `TARGET_MCAP_MIN` | Min target market cap in USD (default: 10000) |
| `TARGET_MCAP_MAX` | Max target market cap in USD (default: 20000) |
| `SOL_PRICE_USD` | Current SOL price for LP calculations (default: 150) |

### 3. Authenticate Telethon
First run will prompt for your Telegram phone code (one-time):
```bash
python main.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and help |
| `/trending` | Show currently trending memes and topics |
| `/preview` | Preview a coin from a random trending meme |
| `/preview <name>` | Preview with a custom name |
| `/launch` | Full launch: token + channel from trending meme |
| `/launch <name>` | Full launch with custom name |
| `/help` | Show help |

## Architecture

```
bot/
  config.py              — Environment config
  trending.py            — Trending meme scanner (Reddit, CoinGecko)
  description_generator.py — Realistic description/bio generator
  solana_memecoin.py     — SPL token creation + tokenomics calculator
  channel_creator.py     — Telegram channel auto-creator (Telethon)
  telegram_bot.py        — Main bot commands and launch flow
main.py                  — Entry point
```

## Launch Flow

```
/launch → Scan Trends → Pick Meme → Deploy Token → Generate Profile → Create Channel → Done
```

Each launch outputs:
- Token contract address + explorer link
- Tokenomics (supply, price, LP needed)
- Telegram channel with invite link
- Pinned message with full project info + roadmap

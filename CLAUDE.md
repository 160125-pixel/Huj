# CLAUDE.md

## Project Overview

Solana Copy Trade Bot — a Python Telegram bot that discovers profitable Solana traders via Birdeye, monitors their wallets in real-time, and copies their trades through the Jupiter V6 aggregator. Includes a portfolio tracker with PnL calculations.

## Architecture

```
main.py                  — Entry point; configures logging, calls run_bot()
bot/
  config.py              — Env var loading via python-dotenv, trading defaults
  top_traders.py         — Trader discovery via Birdeye API (winrate/PnL ranking)
  wallet_tracker.py      — RPC polling for tracked wallets, swap event parsing
  trade_copier.py        — Trade execution via Jupiter V6 quote+swap API
  portfolio.py           — Token holdings, price fetching, cost basis & PnL
  telegram_bot.py        — Telegram UI: commands, inline buttons, swap notifications
```

### Data Flow

```
Discover Top Traders (Birdeye) → Track Wallets (RPC polling) → Detect Swaps → Copy Trades (Jupiter V6) → Track PnL (Portfolio)
```

### Key Module Responsibilities

- **config.py**: All env vars in one place. `get_rpc_url()` / `get_ws_url()` return Helius endpoints when `HELIUS_API_KEY` is set, otherwise fall back to public RPC.
- **wallet_tracker.py**: Maintains module-level `_tracked_wallets` dict and `_swap_callbacks` list. Polling loop runs every 3s per wallet. Parses token balance changes from `getParsedTransaction` to detect BUY/SELL on Jupiter, Raydium, Orca, and Pump.fun.
- **trade_copier.py**: Two-step Jupiter flow: GET `/quote` → POST `/swap` → sign with `solders` → send via `solana` RPC client.
- **portfolio.py**: Module-level `_trade_history` dict for cost basis. Fetches all token accounts via `getTokenAccountsByOwner`, enriches with Birdeye price/metadata.
- **telegram_bot.py**: Single-file UI layer. All message builders return `(str, InlineKeyboardMarkup)` tuples. `run_bot()` registers command + callback handlers and starts polling.

## Tech Stack

- **Python 3.10+**
- **python-telegram-bot 21.6** — async Telegram bot framework
- **solana 0.35.0 / solders 0.21.0** — Solana RPC client and transaction types
- **aiohttp 3.11.18** — async HTTP for Birdeye and Jupiter APIs
- **python-dotenv** — `.env` file loading
- **base58** — Solana key encoding

## Setup & Running

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in API keys
python main.py
```

### Required Environment Variables

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `SOLANA_PRIVATE_KEY` | Base58-encoded wallet private key (the wallet that copies trades) |
| `HELIUS_API_KEY` | Helius RPC (recommended for reliable transaction parsing) |
| `BIRDEYE_API_KEY` | Birdeye API (required for trader discovery and token prices) |

### Optional Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SOLANA_RPC_URL` | `https://api.mainnet-beta.solana.com` | Fallback RPC |
| `SOLANA_WS_URL` | `wss://api.mainnet-beta.solana.com` | Fallback WebSocket |
| `MAX_BUY_SOL` | `0.5` | Max SOL per copy trade |
| `SLIPPAGE_BPS` | `300` | Slippage tolerance (300 = 3%) |
| `PRIORITY_FEE` | `100000` | Priority fee in lamports |
| `AUTO_COPY` | `false` | Auto-execute copy trades without confirmation |

## Conventions

### Code Style
- Pure Python, no framework beyond python-telegram-bot for the UI layer.
- Async throughout: all external API calls use `aiohttp` sessions with explicit timeouts.
- Dataclasses for structured data (`TraderStats`, `SwapEvent`, `TokenHolding`, `PortfolioSummary`).
- Module-level mutable state (dicts/lists) for in-memory tracking — no database.
- Logging via standard `logging` module; INFO level by default.

### Telegram Bot Patterns
- All message content is HTML (`ParseMode.HTML`).
- Every screen returns a `(text, InlineKeyboardMarkup)` tuple from a `build_*_msg()` function.
- Button callback data uses underscore-delimited format: `action_param1_param2` (e.g., `sell_<mint>_<pct>`, `track_<address>`).
- Loading states: send a "Loading..." message first, then `edit_text()` with results.

### External APIs
- **Birdeye** (`public-api.birdeye.so`): requires `X-API-KEY` + `x-chain: solana` headers.
- **Jupiter V6** (`quote-api.jup.ag/v6`): GET `/quote` for price, POST `/swap` for transaction bytes.
- **Solana RPC**: used via `solana.rpc.api.Client` (synchronous) for on-chain reads and transaction sending.

### Security Notes
- `.env` is gitignored. Never commit secrets.
- `SOLANA_PRIVATE_KEY` is the hot wallet key — treat as highly sensitive.
- The `.env.example` file documents all variables with placeholder values.

## Common Tasks

### Adding a new Telegram command
1. Write the handler in `bot/telegram_bot.py` following existing patterns (async, `Update` + `ContextTypes.DEFAULT_TYPE` args).
2. Register it in `run_bot()` with `_app.add_handler(CommandHandler("name", handler_func))`.

### Adding a new inline button action
1. Add a `build_*_msg()` function returning `(text, InlineKeyboardMarkup)`.
2. Add an `elif data.startswith("prefix_"):` branch in `button_handler()`.

### Adding a new DEX for swap detection
1. Add the program ID constant in `bot/wallet_tracker.py`.
2. Add a case in `_identify_dex()`.

### Modifying trade execution
- Quote parameters: `get_jupiter_quote()` in `bot/trade_copier.py`.
- Swap signing/sending: `execute_jupiter_swap()` in the same file.
- Position sizing caps: `copy_trade()` uses `MAX_BUY_SOL` from config.

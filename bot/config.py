import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot API (for the command bot)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Telegram MTProto API (for channel creation via Telethon)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")

# Solana
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")

# Market cap settings
TARGET_MCAP_MIN = int(os.getenv("TARGET_MCAP_MIN", "10000"))   # $10k
TARGET_MCAP_MAX = int(os.getenv("TARGET_MCAP_MAX", "20000"))   # $20k
INITIAL_SOL_PRICE_USD = float(os.getenv("SOL_PRICE_USD", "150.0"))

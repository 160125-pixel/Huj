import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Solana RPC (Helius recommended for websocket + getParsedTransaction)
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
SOLANA_WS_URL = os.getenv("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")

# Your wallet (the one that copies trades)
SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")

# Trading settings
MAX_BUY_SOL = float(os.getenv("MAX_BUY_SOL", "0.5"))        # Max SOL per copy trade
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "300"))          # 3% slippage
PRIORITY_FEE_LAMPORTS = int(os.getenv("PRIORITY_FEE", "100000"))  # Priority fee
AUTO_COPY = os.getenv("AUTO_COPY", "false").lower() == "true"

# Birdeye API (for trader discovery + token data)
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "")

# Jupiter API
JUPITER_API_URL = "https://quote-api.jup.ag/v6"

# Helius RPC (with API key if available)
def get_rpc_url() -> str:
    if HELIUS_API_KEY:
        return f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    return SOLANA_RPC_URL

def get_ws_url() -> str:
    if HELIUS_API_KEY:
        return f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    return SOLANA_WS_URL

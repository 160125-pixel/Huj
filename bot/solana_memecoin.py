"""
Solana memecoin creator via pump.fun.

Launches tokens through pump.fun's API with market cap targeting
of 10-20k USD at launch.
"""

import random
import base58
import json
import logging

import aiohttp
from solders.keypair import Keypair

from bot.config import (
    SOLANA_RPC_URL, SOLANA_PRIVATE_KEY,
    TARGET_MCAP_MIN, TARGET_MCAP_MAX, INITIAL_SOL_PRICE_USD,
)

logger = logging.getLogger(__name__)

PUMPFUN_API_URL = "https://pumpportal.fun/api"


def get_payer_keypair() -> Keypair:
    if not SOLANA_PRIVATE_KEY:
        raise ValueError("SOLANA_PRIVATE_KEY not set in environment")
    return Keypair.from_bytes(base58.b58decode(SOLANA_PRIVATE_KEY))


def calculate_tokenomics(target_mcap: float, sol_price: float) -> dict:
    """
    Calculate initial buy amount in SOL to hit target market cap on pump.fun.

    Pump.fun uses a bonding curve — the initial buy sets the starting price.
    We calculate how much SOL to put in as the initial dev buy to reach
    the desired market cap range.
    """
    # Max supply is 1 billion (pump.fun default)
    supply = 1_000_000_000

    price_per_token = target_mcap / supply

    # Initial dev buy in SOL to set the market cap
    # On pump.fun, the initial buy seeds the bonding curve
    initial_buy_usd = target_mcap * 0.01  # ~1% of target mcap as initial buy
    initial_buy_sol = round(initial_buy_usd / sol_price, 4)

    # Ensure minimum buy (pump.fun requires > 0 SOL)
    initial_buy_sol = max(initial_buy_sol, 0.1)

    return {
        "total_supply": supply,
        "decimals": 6,  # pump.fun uses 6 decimals
        "price_per_token_usd": price_per_token,
        "initial_buy_sol": initial_buy_sol,
        "initial_buy_usd": round(initial_buy_sol * sol_price, 2),
        "target_mcap": target_mcap,
    }


async def create_memecoin(name: str, ticker: str, description: str,
                          category: str = "meme") -> dict:
    """
    Create and deploy a memecoin on pump.fun.

    Steps:
    1. Generate a new mint keypair
    2. Calculate tokenomics for target market cap
    3. Call pump.fun API to create the token
    4. Return full details with pump.fun links

    Args:
        name: Token name
        ticker: Ticker symbol (without $)
        description: Token description
        category: Trend category

    Returns:
        Dict with token details, pump.fun links, and tokenomics
    """
    payer = get_payer_keypair()
    mint_keypair = Keypair()

    target_mcap = random.uniform(TARGET_MCAP_MIN, TARGET_MCAP_MAX)
    tokenomics = calculate_tokenomics(target_mcap, INITIAL_SOL_PRICE_USD)

    # Clean ticker (pump.fun wants it without $)
    clean_ticker = ticker.replace("$", "").strip()

    # Build the pump.fun create request
    form_data = aiohttp.FormData()
    form_data.add_field("action", "create")
    form_data.add_field("tokenMetadata", json.dumps({
        "name": name,
        "symbol": clean_ticker,
        "description": description,
    }))
    form_data.add_field("mint", base58.b58encode(bytes(mint_keypair)).decode())
    form_data.add_field("denominatedInSol", "true")
    form_data.add_field("amount", str(tokenomics["initial_buy_sol"]))
    form_data.add_field("slippage", "15")
    form_data.add_field("priorityFee", "0.005")
    form_data.add_field("pool", "pump")

    # Sign with payer private key
    payer_b58 = base58.b58encode(bytes(payer)).decode()

    async with aiohttp.ClientSession() as session:
        # Request the transaction from pump.fun portal API
        trade_payload = {
            "publicKey": str(payer.pubkey()),
            "action": "create",
            "tokenMetadata": {
                "name": name,
                "symbol": clean_ticker,
                "description": description,
            },
            "mint": base58.b58encode(bytes(mint_keypair)).decode(),
            "denominatedInSol": True,
            "amount": tokenomics["initial_buy_sol"],
            "slippage": 15,
            "priorityFee": 0.005,
            "pool": "pump",
        }

        async with session.post(
            f"{PUMPFUN_API_URL}/trade-local",
            json=trade_payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"Pump.fun API error ({resp.status}): {error_text}")

            tx_bytes = await resp.read()

        # Sign and send the transaction
        from solders.transaction import VersionedTransaction
        from solana.rpc.api import Client

        tx = VersionedTransaction.from_bytes(tx_bytes)
        # Create a new signed transaction
        signed_tx = VersionedTransaction(tx.message, [payer, mint_keypair])

        client = Client(SOLANA_RPC_URL)
        tx_resp = client.send_transaction(signed_tx)
        tx_signature = str(tx_resp.value)

    mint_address = str(mint_keypair.pubkey())

    return {
        "name": name,
        "ticker": f"${clean_ticker}",
        "category": category,
        "supply": tokenomics["total_supply"],
        "decimals": tokenomics["decimals"],
        "mint_address": mint_address,
        "tx_signature": tx_signature,
        "pumpfun_url": f"https://pump.fun/coin/{mint_address}",
        "explorer_url": f"https://solscan.io/token/{mint_address}",
        "tx_url": f"https://solscan.io/tx/{tx_signature}",
        "phantom_url": f"https://phantom.app/ul/browse/https://pump.fun/coin/{mint_address}",
        "rpc_url": SOLANA_RPC_URL,
        "tokenomics": tokenomics,
    }


def preview_memecoin(name: str, ticker: str, category: str = "meme") -> dict:
    """Preview tokenomics without deploying on-chain."""
    target_mcap = random.uniform(TARGET_MCAP_MIN, TARGET_MCAP_MAX)
    tokenomics = calculate_tokenomics(target_mcap, INITIAL_SOL_PRICE_USD)

    return {
        "name": name,
        "ticker": ticker,
        "category": category,
        "supply": tokenomics["total_supply"],
        "tokenomics": tokenomics,
    }

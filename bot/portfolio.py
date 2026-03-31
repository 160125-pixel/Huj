"""
Portfolio tracker.

Tracks token holdings, calculates PnL, and provides portfolio overview.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from solana.rpc.api import Client
from solders.keypair import Keypair
import base58

from bot.config import (
    SOLANA_PRIVATE_KEY, BIRDEYE_API_KEY, get_rpc_url,
)

logger = logging.getLogger(__name__)

BIRDEYE_BASE = "https://public-api.birdeye.so"


@dataclass
class TokenHolding:
    mint: str
    symbol: str = "???"
    name: str = ""
    balance: float = 0.0
    decimals: int = 9
    price_usd: float = 0.0
    value_usd: float = 0.0
    cost_basis_usd: float = 0.0
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class PortfolioSummary:
    sol_balance: float = 0.0
    sol_value_usd: float = 0.0
    token_count: int = 0
    total_value_usd: float = 0.0
    total_pnl_usd: float = 0.0
    holdings: list[TokenHolding] = field(default_factory=list)


# Trade history for cost basis tracking
_trade_history: dict[str, list[dict]] = {}


def record_trade(mint: str, action: str, amount: float, sol_amount: float, price_usd: float):
    """Record a trade for cost basis calculation."""
    if mint not in _trade_history:
        _trade_history[mint] = []
    _trade_history[mint].append({
        "action": action,
        "amount": amount,
        "sol_amount": sol_amount,
        "price_usd": price_usd,
        "timestamp": int(time.time()),
    })


def get_cost_basis(mint: str) -> float:
    """Calculate average cost basis for a token."""
    trades = _trade_history.get(mint, [])
    total_spent = 0
    total_bought = 0
    for t in trades:
        if t["action"] == "BUY":
            total_spent += t["sol_amount"] * t.get("price_usd", 0)
            total_bought += t["amount"]
    return total_spent


def get_payer_pubkey() -> str:
    if not SOLANA_PRIVATE_KEY:
        return ""
    kp = Keypair.from_bytes(base58.b58decode(SOLANA_PRIVATE_KEY))
    return str(kp.pubkey())


async def fetch_token_price(session: aiohttp.ClientSession, mint: str) -> dict:
    """Fetch current price for a token from Birdeye."""
    if not BIRDEYE_API_KEY:
        return {}

    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    try:
        url = f"{BIRDEYE_BASE}/defi/price"
        params = {"address": mint}
        async with session.get(url, headers=headers, params=params,
                               timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()
            return data.get("data", {})
    except Exception:
        return {}


async def fetch_token_metadata(session: aiohttp.ClientSession, mint: str) -> dict:
    """Fetch token metadata (name, symbol) from Birdeye."""
    if not BIRDEYE_API_KEY:
        return {}

    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    try:
        url = f"{BIRDEYE_BASE}/defi/token_overview"
        params = {"address": mint}
        async with session.get(url, headers=headers, params=params,
                               timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()
            return data.get("data", {})
    except Exception:
        return {}


async def get_sol_price(session: aiohttp.ClientSession) -> float:
    """Fetch SOL price in USD."""
    from bot.wallet_tracker import SOL_MINT
    price_data = await fetch_token_price(session, SOL_MINT)
    return price_data.get("value", 150.0)


async def get_portfolio() -> PortfolioSummary:
    """
    Get full portfolio overview:
    - SOL balance
    - All token holdings with current value
    - PnL per token and total
    """
    pubkey = get_payer_pubkey()
    if not pubkey:
        raise ValueError("SOLANA_PRIVATE_KEY not set")

    client = Client(get_rpc_url())
    summary = PortfolioSummary()

    # Get SOL balance
    from solders.pubkey import Pubkey
    sol_resp = client.get_balance(Pubkey.from_string(pubkey))
    summary.sol_balance = sol_resp.value / 1e9

    # Get all token accounts
    token_resp = client.get_token_accounts_by_owner_json_parsed(
        Pubkey.from_string(pubkey),
        opts={"programId": Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")},
    )

    holdings = []
    async with aiohttp.ClientSession() as session:
        # SOL price
        sol_price = await get_sol_price(session)
        summary.sol_value_usd = round(summary.sol_balance * sol_price, 2)
        summary.total_value_usd = summary.sol_value_usd

        for account in token_resp.value:
            parsed = account.account.data.parsed
            info = parsed["info"]
            mint = info["mint"]
            amount = float(info["tokenAmount"]["uiAmount"] or 0)
            decimals = info["tokenAmount"]["decimals"]

            if amount <= 0:
                continue

            # Get price and metadata
            price_data = await fetch_token_price(session, mint)
            meta = await fetch_token_metadata(session, mint)

            price = price_data.get("value", 0)
            value = round(amount * price, 2)
            cost = get_cost_basis(mint)
            pnl = round(value - cost, 2) if cost > 0 else 0
            pnl_pct = round((pnl / cost) * 100, 1) if cost > 0 else 0

            holding = TokenHolding(
                mint=mint,
                symbol=meta.get("symbol", "???"),
                name=meta.get("name", "Unknown"),
                balance=amount,
                decimals=decimals,
                price_usd=price,
                value_usd=value,
                cost_basis_usd=cost,
                pnl_usd=pnl,
                pnl_pct=pnl_pct,
            )
            holdings.append(holding)
            summary.total_value_usd += value
            summary.total_pnl_usd += pnl

    # Sort by value descending
    holdings.sort(key=lambda h: h.value_usd, reverse=True)
    summary.holdings = holdings
    summary.token_count = len(holdings)
    summary.total_value_usd = round(summary.total_value_usd, 2)
    summary.total_pnl_usd = round(summary.total_pnl_usd, 2)

    return summary

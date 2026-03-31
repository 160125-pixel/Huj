"""
Top trader discovery.

Finds the most profitable Solana wallets by analyzing on-chain trading
history via Birdeye and Helius APIs. Ranks by winrate, PnL, and trade count.
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

import aiohttp

from bot.config import BIRDEYE_API_KEY, get_rpc_url

logger = logging.getLogger(__name__)

BIRDEYE_BASE = "https://public-api.birdeye.so"

# Well-known profitable wallets (fallback / seed list)
KNOWN_TRADERS = [
    {"address": "CdMKoYGC3Cg1FuBMfTBASxgvmJrm69WFfFhd3FMUhi8R", "label": "Smart Degen 1"},
    {"address": "6vRx3iAbMYvFMBo5EKkGGxRM5gFBPcig4csL7QRJKLQQ", "label": "Smart Degen 2"},
    {"address": "5rVQGRbHJGfPagMwHATRB5MxfHBpyyFXSqVHi3unjDcC", "label": "Smart Degen 3"},
]


@dataclass
class TraderStats:
    address: str
    label: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    winrate: float = 0.0
    total_pnl_usd: float = 0.0
    avg_trade_size_usd: float = 0.0
    last_active: str = ""
    tokens_traded: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


async def fetch_trader_stats_birdeye(session: aiohttp.ClientSession,
                                      wallet: str) -> Optional[TraderStats]:
    """Fetch trading stats for a wallet via Birdeye API."""
    if not BIRDEYE_API_KEY:
        return None

    headers = {
        "X-API-KEY": BIRDEYE_API_KEY,
        "x-chain": "solana",
    }

    try:
        # Get trader's token trade history
        url = f"{BIRDEYE_BASE}/trader/gainers-losers"
        params = {"address": wallet, "type": "1W"}
        async with session.get(url, headers=headers, params=params,
                               timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                logger.debug(f"Birdeye returned {resp.status} for {wallet[:8]}")
                return None
            data = await resp.json()

        trades = data.get("data", {}).get("items", [])
        if not trades:
            return None

        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        total_volume = sum(abs(t.get("volume", 0)) for t in trades)

        return TraderStats(
            address=wallet,
            total_trades=len(trades),
            winning_trades=wins,
            winrate=round((wins / len(trades)) * 100, 1) if trades else 0,
            total_pnl_usd=round(total_pnl, 2),
            avg_trade_size_usd=round(total_volume / len(trades), 2) if trades else 0,
            tokens_traded=[t.get("symbol", "") for t in trades[:5]],
        )
    except Exception as e:
        logger.debug(f"Birdeye stats fetch failed for {wallet[:8]}: {e}")
        return None


async def fetch_top_traders_birdeye(session: aiohttp.ClientSession,
                                     time_range: str = "1W") -> list[TraderStats]:
    """
    Fetch top traders from Birdeye leaderboard.
    time_range: 1H, 4H, 1D, 1W, 1M
    """
    if not BIRDEYE_API_KEY:
        return []

    headers = {
        "X-API-KEY": BIRDEYE_API_KEY,
        "x-chain": "solana",
    }

    try:
        url = f"{BIRDEYE_BASE}/trader/gainers-losers"
        params = {"type": time_range, "sort_by": "PnL", "sort_type": "desc", "limit": 20}
        async with session.get(url, headers=headers, params=params,
                               timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        items = data.get("data", {}).get("items", [])
        traders = []
        for item in items:
            addr = item.get("address", "")
            if not addr:
                continue
            pnl = item.get("pnl", 0)
            trades_count = item.get("trade_count", 0)
            wins = item.get("win_count", 0)
            traders.append(TraderStats(
                address=addr,
                total_trades=trades_count,
                winning_trades=wins,
                winrate=round((wins / trades_count) * 100, 1) if trades_count > 0 else 0,
                total_pnl_usd=round(pnl, 2),
            ))
        return traders

    except Exception as e:
        logger.warning(f"Birdeye top traders fetch failed: {e}")
        return []


async def discover_top_traders(time_range: str = "1W") -> list[TraderStats]:
    """
    Discover top traders from multiple sources.
    Returns sorted by winrate (descending), minimum 5 trades.
    """
    all_traders = []

    async with aiohttp.ClientSession() as session:
        # Birdeye leaderboard
        birdeye_traders = await fetch_top_traders_birdeye(session, time_range)
        all_traders.extend(birdeye_traders)

        # Also check our known wallets
        for known in KNOWN_TRADERS:
            stats = await fetch_trader_stats_birdeye(session, known["address"])
            if stats:
                stats.label = known["label"]
                all_traders.append(stats)

    # Deduplicate by address
    seen = set()
    unique = []
    for t in all_traders:
        if t.address not in seen:
            seen.add(t.address)
            unique.append(t)

    # Filter: at least 5 trades, sort by winrate then PnL
    filtered = [t for t in unique if t.total_trades >= 5]
    filtered.sort(key=lambda t: (t.winrate, t.total_pnl_usd), reverse=True)

    return filtered[:20]


async def get_trader_stats(wallet: str) -> Optional[TraderStats]:
    """Get stats for a specific wallet."""
    async with aiohttp.ClientSession() as session:
        stats = await fetch_trader_stats_birdeye(session, wallet)
        if stats:
            # Check if it's a known wallet
            for known in KNOWN_TRADERS:
                if known["address"] == wallet:
                    stats.label = known["label"]
            return stats
    return TraderStats(address=wallet, label="Unknown")

"""
Wallet tracker.

Monitors Solana wallets in real-time for new transactions (buys/sells).
When a tracked wallet makes a swap, it emits events so the copy trader
can replicate the trade.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Callable, Optional

import aiohttp
from solana.rpc.api import Client

from bot.config import get_rpc_url, get_ws_url, HELIUS_API_KEY

logger = logging.getLogger(__name__)

# Known DEX program IDs
JUPITER_V6 = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
RAYDIUM_AMM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CLMM = "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK"
ORCA_WHIRLPOOL = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
PUMPFUN = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

SOL_MINT = "So11111111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

STABLE_MINTS = {SOL_MINT, USDC_MINT, "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}  # +USDT


@dataclass
class SwapEvent:
    """Represents a detected swap transaction."""
    wallet: str
    signature: str
    action: str            # "BUY" or "SELL"
    token_mint: str
    token_symbol: str
    amount_token: float
    amount_sol: float
    price_usd: float
    dex: str
    timestamp: int


# Tracked wallets: address -> label
_tracked_wallets: dict[str, str] = {}

# Callbacks for swap events
_swap_callbacks: list[Callable] = []

# Background task reference
_tracker_task: Optional[asyncio.Task] = None


def add_tracked_wallet(address: str, label: str = ""):
    """Add a wallet to track."""
    _tracked_wallets[address] = label or address[:8]


def remove_tracked_wallet(address: str):
    """Remove a wallet from tracking."""
    _tracked_wallets.pop(address, None)


def get_tracked_wallets() -> dict[str, str]:
    """Get all tracked wallets."""
    return _tracked_wallets.copy()


def on_swap(callback: Callable):
    """Register a callback for swap events."""
    _swap_callbacks.append(callback)


def _identify_dex(program_ids: list[str]) -> str:
    """Identify which DEX was used from program IDs."""
    for pid in program_ids:
        if pid == JUPITER_V6:
            return "Jupiter"
        if pid == RAYDIUM_AMM or pid == RAYDIUM_CLMM:
            return "Raydium"
        if pid == ORCA_WHIRLPOOL:
            return "Orca"
        if pid == PUMPFUN:
            return "Pump.fun"
    return "Unknown"


def _parse_swap_from_tx(wallet: str, tx_data: dict) -> Optional[SwapEvent]:
    """Parse a transaction to extract swap details."""
    try:
        meta = tx_data.get("meta", {})
        if meta.get("err"):
            return None

        tx = tx_data.get("transaction", {})
        msg = tx.get("message", {})
        account_keys = msg.get("accountKeys", [])
        if isinstance(account_keys[0], dict):
            program_ids = [k.get("pubkey", "") for k in account_keys]
        else:
            program_ids = account_keys

        dex = _identify_dex(program_ids)
        if dex == "Unknown":
            return None

        # Parse token balance changes
        pre_balances = meta.get("preTokenBalances", [])
        post_balances = meta.get("postTokenBalances", [])

        # Find what changed for our wallet
        token_changes = {}
        for post in post_balances:
            owner = post.get("owner", "")
            if owner != wallet:
                continue
            mint = post.get("mint", "")
            post_amount = float(post.get("uiTokenAmount", {}).get("uiAmount") or 0)

            # Find pre-balance
            pre_amount = 0
            for pre in pre_balances:
                if pre.get("owner") == wallet and pre.get("mint") == mint:
                    pre_amount = float(pre.get("uiTokenAmount", {}).get("uiAmount") or 0)
                    break

            delta = post_amount - pre_amount
            if abs(delta) > 0:
                token_changes[mint] = delta

        # Also check for new accounts (tokens not in pre but in post)
        pre_mints = {b.get("mint") for b in pre_balances if b.get("owner") == wallet}
        for post in post_balances:
            if post.get("owner") == wallet and post.get("mint") not in pre_mints:
                mint = post.get("mint", "")
                amount = float(post.get("uiTokenAmount", {}).get("uiAmount") or 0)
                if amount > 0:
                    token_changes[mint] = amount

        if not token_changes:
            return None

        # Determine buy or sell: if we gained a non-stable token, it's a BUY
        sol_change = 0
        token_mint = ""
        token_amount = 0

        for mint, delta in token_changes.items():
            if mint in STABLE_MINTS:
                sol_change = delta
            else:
                token_mint = mint
                token_amount = delta

        if not token_mint:
            return None

        # SOL balance change (lamports)
        pre_sol = meta.get("preBalances", [])
        post_sol = meta.get("postBalances", [])
        # Find wallet index
        wallet_idx = None
        for i, key in enumerate(program_ids):
            if key == wallet:
                wallet_idx = i
                break

        if wallet_idx is not None and wallet_idx < len(pre_sol):
            sol_delta = (post_sol[wallet_idx] - pre_sol[wallet_idx]) / 1e9
        else:
            sol_delta = sol_change

        action = "BUY" if token_amount > 0 else "SELL"

        sig = tx_data.get("transaction", {}).get("signatures", [""])[0]

        return SwapEvent(
            wallet=wallet,
            signature=sig,
            action=action,
            token_mint=token_mint,
            token_symbol="",
            amount_token=abs(token_amount),
            amount_sol=abs(sol_delta),
            price_usd=0,
            dex=dex,
            timestamp=tx_data.get("blockTime", 0),
        )

    except Exception as e:
        logger.debug(f"Failed to parse tx: {e}")
        return None


async def poll_wallet_transactions(wallet: str):
    """Poll for new transactions from a tracked wallet using RPC."""
    client = Client(get_rpc_url())
    last_sig = None

    while wallet in _tracked_wallets:
        try:
            # Get latest signatures
            sigs_resp = client.get_signatures_for_address(
                wallet, limit=5, before=None
            )
            sigs = sigs_resp.value
            if not sigs:
                await asyncio.sleep(3)
                continue

            newest_sig = str(sigs[0].signature)
            if last_sig is None:
                last_sig = newest_sig
                await asyncio.sleep(3)
                continue

            if newest_sig == last_sig:
                await asyncio.sleep(3)
                continue

            # Process new transactions
            for sig_info in sigs:
                sig = str(sig_info.signature)
                if sig == last_sig:
                    break

                # Fetch full transaction
                from solders.signature import Signature
                tx_resp = client.get_transaction(
                    Signature.from_string(sig),
                    max_supported_transaction_version=0
                )
                if tx_resp.value is None:
                    continue

                tx_data = json.loads(tx_resp.value.to_json())
                swap = _parse_swap_from_tx(wallet, tx_data)
                if swap:
                    swap.signature = sig
                    logger.info(
                        f"Detected {swap.action} by {wallet[:8]}: "
                        f"{swap.amount_token:.4f} of {swap.token_mint[:8]} on {swap.dex}"
                    )
                    for cb in _swap_callbacks:
                        try:
                            await cb(swap)
                        except Exception as e:
                            logger.error(f"Swap callback error: {e}")

            last_sig = newest_sig

        except Exception as e:
            logger.error(f"Wallet poll error for {wallet[:8]}: {e}")

        await asyncio.sleep(3)


async def start_tracking():
    """Start background polling for all tracked wallets."""
    tasks = []
    for wallet in _tracked_wallets:
        task = asyncio.create_task(poll_wallet_transactions(wallet))
        tasks.append(task)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def start_tracker_background():
    """Start the wallet tracker in the background."""
    global _tracker_task
    if _tracker_task and not _tracker_task.done():
        return

    loop = asyncio.get_event_loop()
    _tracker_task = loop.create_task(start_tracking())


def restart_tracker():
    """Restart tracking (call after adding/removing wallets)."""
    global _tracker_task
    if _tracker_task and not _tracker_task.done():
        _tracker_task.cancel()
    start_tracker_background()

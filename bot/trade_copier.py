"""
Trade copier.

Executes copy trades via Jupiter V6 API when tracked wallets make swaps.
Handles slippage, priority fees, and position sizing.
"""

import logging
import base58

import aiohttp
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from bot.config import (
    SOLANA_PRIVATE_KEY, MAX_BUY_SOL, SLIPPAGE_BPS,
    PRIORITY_FEE_LAMPORTS, JUPITER_API_URL, get_rpc_url,
)
from bot.wallet_tracker import SwapEvent, SOL_MINT

logger = logging.getLogger(__name__)


def get_payer_keypair() -> Keypair:
    if not SOLANA_PRIVATE_KEY:
        raise ValueError("SOLANA_PRIVATE_KEY not set")
    return Keypair.from_bytes(base58.b58decode(SOLANA_PRIVATE_KEY))


async def get_jupiter_quote(input_mint: str, output_mint: str,
                             amount_lamports: int) -> dict:
    """Get a swap quote from Jupiter."""
    async with aiohttp.ClientSession() as session:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": SLIPPAGE_BPS,
            "onlyDirectRoutes": "false",
        }
        async with session.get(
            f"{JUPITER_API_URL}/quote",
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"Jupiter quote failed ({resp.status}): {error}")
            return await resp.json()


async def execute_jupiter_swap(input_mint: str, output_mint: str,
                                amount_lamports: int) -> dict:
    """
    Execute a swap through Jupiter V6.

    Returns:
        Dict with tx_signature, input_amount, output_amount, price_impact
    """
    payer = get_payer_keypair()

    # Step 1: Get quote
    quote = await get_jupiter_quote(input_mint, output_mint, amount_lamports)

    # Step 2: Get swap transaction
    async with aiohttp.ClientSession() as session:
        swap_body = {
            "quoteResponse": quote,
            "userPublicKey": str(payer.pubkey()),
            "wrapAndUnwrapSol": True,
            "prioritizationFeeLamports": PRIORITY_FEE_LAMPORTS,
        }
        async with session.post(
            f"{JUPITER_API_URL}/swap",
            json=swap_body,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"Jupiter swap failed ({resp.status}): {error}")
            swap_data = await resp.json()

    # Step 3: Deserialize, sign, and send
    swap_tx_b64 = swap_data["swapTransaction"]
    import base64
    tx_bytes = base64.b64decode(swap_tx_b64)
    tx = VersionedTransaction.from_bytes(tx_bytes)
    signed_tx = VersionedTransaction(tx.message, [payer])

    client = Client(get_rpc_url())
    tx_resp = client.send_transaction(signed_tx)
    tx_signature = str(tx_resp.value)

    out_amount = int(quote.get("outAmount", 0))
    in_amount = int(quote.get("inAmount", 0))
    price_impact = float(quote.get("priceImpactPct", 0))

    return {
        "tx_signature": tx_signature,
        "input_mint": input_mint,
        "output_mint": output_mint,
        "input_amount": in_amount,
        "output_amount": out_amount,
        "price_impact_pct": price_impact,
        "route": quote.get("routePlan", []),
        "tx_url": f"https://solscan.io/tx/{tx_signature}",
    }


async def copy_trade(swap: SwapEvent, max_sol: float = None) -> dict:
    """
    Copy a detected swap from a tracked wallet.

    For BUY: we buy the same token with SOL (capped at max_sol)
    For SELL: we sell the same token for SOL (sell our full balance)

    Args:
        swap: The detected swap event to copy
        max_sol: Max SOL to spend on a buy (defaults to MAX_BUY_SOL)

    Returns:
        Dict with trade execution details
    """
    if max_sol is None:
        max_sol = MAX_BUY_SOL

    if swap.action == "BUY":
        # Buy: SOL -> token
        # Cap the buy amount
        buy_sol = min(swap.amount_sol, max_sol)
        amount_lamports = int(buy_sol * 1e9)

        logger.info(f"Copying BUY: {buy_sol} SOL -> {swap.token_mint[:8]}")
        result = await execute_jupiter_swap(SOL_MINT, swap.token_mint, amount_lamports)
        result["action"] = "BUY"
        result["sol_spent"] = buy_sol
        return result

    elif swap.action == "SELL":
        # Sell: token -> SOL
        # Get our token balance first
        client = Client(get_rpc_url())
        payer = get_payer_keypair()

        # Get token accounts
        from solders.pubkey import Pubkey
        token_resp = client.get_token_accounts_by_owner_json_parsed(
            payer.pubkey(),
            opts={"mint": Pubkey.from_string(swap.token_mint)},
        )
        accounts = token_resp.value
        if not accounts:
            raise Exception(f"No token balance found for {swap.token_mint[:8]}")

        # Get balance
        account_data = accounts[0].account.data
        parsed = account_data.parsed
        amount = int(parsed["info"]["tokenAmount"]["amount"])

        if amount == 0:
            raise Exception("Token balance is 0, nothing to sell")

        logger.info(f"Copying SELL: {swap.token_mint[:8]} -> SOL")
        result = await execute_jupiter_swap(swap.token_mint, SOL_MINT, amount)
        result["action"] = "SELL"
        result["tokens_sold"] = amount
        return result

    else:
        raise ValueError(f"Unknown swap action: {swap.action}")


async def manual_buy(token_mint: str, sol_amount: float) -> dict:
    """Manually buy a token with a specified SOL amount."""
    amount_lamports = int(sol_amount * 1e9)
    result = await execute_jupiter_swap(SOL_MINT, token_mint, amount_lamports)
    result["action"] = "BUY"
    result["sol_spent"] = sol_amount
    return result


async def manual_sell(token_mint: str, percentage: float = 100.0) -> dict:
    """Manually sell a token (percentage of holdings)."""
    client = Client(get_rpc_url())
    payer = get_payer_keypair()

    from solders.pubkey import Pubkey
    token_resp = client.get_token_accounts_by_owner_json_parsed(
        payer.pubkey(),
        opts={"mint": Pubkey.from_string(token_mint)},
    )
    accounts = token_resp.value
    if not accounts:
        raise Exception("No token balance found")

    parsed = accounts[0].account.data.parsed
    amount = int(parsed["info"]["tokenAmount"]["amount"])
    sell_amount = int(amount * (percentage / 100))

    if sell_amount == 0:
        raise Exception("Nothing to sell")

    result = await execute_jupiter_swap(token_mint, SOL_MINT, sell_amount)
    result["action"] = "SELL"
    result["tokens_sold"] = sell_amount
    result["sell_pct"] = percentage
    return result

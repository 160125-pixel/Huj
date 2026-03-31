"""
Solana memecoin creator with market cap targeting.

Creates SPL tokens on Solana, calculates supply and initial liquidity
to hit a target market cap of 10-20k USD at launch.
"""

import random
import base58
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.system_program import CreateAccountParams, create_account
from solders.transaction import Transaction
from solders.message import Message
from spl.token.instructions import (
    InitializeMintParams,
    MintToParams,
    initialize_mint,
    mint_to,
    get_associated_token_address,
    create_associated_token_account,
)
from spl.token.constants import TOKEN_PROGRAM_ID

from bot.config import (
    SOLANA_RPC_URL, SOLANA_PRIVATE_KEY,
    TARGET_MCAP_MIN, TARGET_MCAP_MAX, INITIAL_SOL_PRICE_USD,
)


def get_client() -> Client:
    return Client(SOLANA_RPC_URL)


def get_payer_keypair() -> Keypair:
    if not SOLANA_PRIVATE_KEY:
        raise ValueError("SOLANA_PRIVATE_KEY not set in environment")
    return Keypair.from_bytes(base58.b58decode(SOLANA_PRIVATE_KEY))


def calculate_tokenomics(target_mcap: float, sol_price: float) -> dict:
    """
    Calculate supply, initial price, and liquidity needed for target market cap.

    For a memecoin launching at $10-20k market cap:
    - Pick a large total supply (looks attractive to buyers)
    - Set initial token price = target_mcap / supply
    - Calculate SOL needed for initial liquidity pool

    Returns:
        Dict with supply, price_per_token, liquidity_sol, liquidity_usd, etc.
    """
    # Large supply looks more attractive (psychological effect)
    supply = random.choice([
        1_000_000_000,       # 1B
        10_000_000_000,      # 10B
        100_000_000_000,     # 100B
        420_690_000_000,     # 420.69B (meme number)
        690_000_000_000,     # 690B
        1_000_000_000_000,   # 1T
    ])

    # Price per token at target mcap
    price_per_token = target_mcap / supply

    # Initial liquidity: we seed the pool with some tokens + SOL
    # Typical AMM: liquidity_tokens * liquidity_sol = k (constant product)
    # We put ~10% of supply into the pool + equivalent SOL value
    pool_token_pct = 0.10
    pool_tokens = int(supply * pool_token_pct)
    pool_value_usd = pool_tokens * price_per_token
    liquidity_sol = pool_value_usd / sol_price

    return {
        "total_supply": supply,
        "decimals": 9,
        "price_per_token_usd": price_per_token,
        "pool_token_amount": pool_tokens,
        "pool_token_pct": pool_token_pct,
        "liquidity_sol": round(liquidity_sol, 4),
        "liquidity_usd": round(pool_value_usd, 2),
        "target_mcap": target_mcap,
    }


def create_memecoin(name: str, ticker: str, category: str = "meme") -> dict:
    """
    Create and deploy a memecoin on Solana.

    1. Calculate tokenomics for 10-20k market cap
    2. Create SPL token mint
    3. Mint supply to creator wallet
    4. Return full details including liquidity requirements

    Args:
        name: Token name
        ticker: Token ticker symbol
        category: Trend category for description generation

    Returns:
        Dict with all token + deployment details
    """
    client = get_client()
    payer = get_payer_keypair()

    # Target a random market cap in the 10-20k range
    target_mcap = random.uniform(TARGET_MCAP_MIN, TARGET_MCAP_MAX)
    tokenomics = calculate_tokenomics(target_mcap, INITIAL_SOL_PRICE_USD)

    supply = tokenomics["total_supply"]
    decimals = tokenomics["decimals"]

    # Create new mint
    mint_keypair = Keypair()
    mint_pubkey = mint_keypair.pubkey()

    min_balance = client.get_minimum_balance_for_rent_exemption(82).value

    # Build transaction with all instructions
    create_account_ix = create_account(
        CreateAccountParams(
            from_pubkey=payer.pubkey(),
            to_pubkey=mint_pubkey,
            lamports=min_balance,
            space=82,
            owner=TOKEN_PROGRAM_ID,
        )
    )

    init_mint_ix = initialize_mint(
        InitializeMintParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=mint_pubkey,
            decimals=decimals,
            mint_authority=payer.pubkey(),
            freeze_authority=payer.pubkey(),
        )
    )

    ata = get_associated_token_address(payer.pubkey(), mint_pubkey)
    create_ata_ix = create_associated_token_account(
        payer=payer.pubkey(),
        owner=payer.pubkey(),
        mint=mint_pubkey,
    )

    raw_amount = supply * (10 ** decimals)
    mint_to_ix = mint_to(
        MintToParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=mint_pubkey,
            dest=ata,
            mint_authority=payer.pubkey(),
            amount=raw_amount,
            signers=[payer.pubkey()],
        )
    )

    recent_blockhash = client.get_latest_blockhash().value.blockhash

    msg = Message.new_with_blockhash(
        [create_account_ix, init_mint_ix, create_ata_ix, mint_to_ix],
        payer.pubkey(),
        recent_blockhash,
    )
    tx = Transaction.new_unsigned(msg)
    tx.sign([payer, mint_keypair], recent_blockhash)

    tx_resp = client.send_transaction(tx)
    tx_signature = str(tx_resp.value)

    # Build explorer URL
    cluster_param = "?cluster=devnet" if "devnet" in SOLANA_RPC_URL else ""
    explorer_base = "https://explorer.solana.com"

    return {
        "name": name,
        "ticker": ticker,
        "category": category,
        "supply": supply,
        "decimals": decimals,
        "mint_address": str(mint_pubkey),
        "token_account": str(ata),
        "tx_signature": tx_signature,
        "explorer_url": f"{explorer_base}/address/{str(mint_pubkey)}{cluster_param}",
        "tx_url": f"{explorer_base}/tx/{tx_signature}{cluster_param}",
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

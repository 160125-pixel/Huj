"""
Solana memecoin creator — the dumb way.

Creates an SPL token on Solana with a ridiculous supply,
mints it all to the creator's wallet, and calls it a "memecoin".
That's it. That's the whole thing.
"""

import random
import base58
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import CreateAccountParams, create_account
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
from spl.token.instructions import (
    InitializeMintParams,
    MintToParams,
    initialize_mint,
    mint_to,
    get_associated_token_address,
    create_associated_token_account,
)
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID

from bot.config import SOLANA_RPC_URL, SOLANA_PRIVATE_KEY

# Dumb memecoin name generator
PREFIXES = [
    "DOGE", "PEPE", "MOON", "ROCKET", "BONK", "WIF", "SHIB",
    "FROG", "CAT", "CHAD", "GIGA", "TURBO", "MEGA", "BABY",
    "DARK", "ELON", "TRUMP", "BASED", "DEGEN", "APE", "WOJAK",
    "SMOL", "THICC", "CHONK", "FLOKI", "SNEK", "MONKE", "HODL",
]

SUFFIXES = [
    "INU", "COIN", "TOKEN", "SWAP", "MOON", "ROCKET", "PUMP",
    "LAMBO", "WAGMI", "NGMI", "GM", "GN", "SER", "FREN",
    "TENDIES", "STONKS", "YOLO", "COPE", "SEETHE", "MALD",
    "2.0", "AI", "GPT", "CHAIN", "FI", "DAO", "VERSE",
]

DUMB_DESCRIPTIONS = [
    "To the moon! (or to zero, probably zero)",
    "Not financial advice (it's literally a meme)",
    "1000x potential* (*potential to lose everything)",
    "The next big thing in losing money speedrun",
    "Community driven (by pure degeneracy)",
    "Backed by nothing, fueled by vibes",
    "Whitepaper: trust me bro",
    "Rug pull resistant** (**not actually resistant)",
    "Making millionaires* (*of the devs only)",
    "Built different (built worse actually)",
    "Deflationary* (*your wallet balance deflates)",
    "Utility: makes you mass text your friends at 3am",
]


def generate_dumb_name() -> tuple[str, str]:
    """Generate a hilariously dumb memecoin name and ticker."""
    prefix = random.choice(PREFIXES)
    suffix = random.choice(SUFFIXES)
    name = f"{prefix}{suffix}"
    ticker = f"${name[:6].upper()}"
    return name, ticker


def generate_dumb_supply() -> int:
    """Generate an absurdly large token supply because why not."""
    bases = [420, 69, 1337, 80085, 42069, 69420]
    multipliers = [1_000_000, 1_000_000_000, 1_000_000_000_000]
    return random.choice(bases) * random.choice(multipliers)


def generate_dumb_description() -> str:
    """Pick a random dumb description."""
    return random.choice(DUMB_DESCRIPTIONS)


def get_client() -> Client:
    """Create a Solana RPC client."""
    return Client(SOLANA_RPC_URL)


def get_payer_keypair() -> Keypair:
    """Load the payer keypair from the private key."""
    if not SOLANA_PRIVATE_KEY:
        raise ValueError("SOLANA_PRIVATE_KEY not set in environment")
    secret_key = base58.b58decode(SOLANA_PRIVATE_KEY)
    return Keypair.from_bytes(secret_key)


def create_memecoin(custom_name: str | None = None) -> dict:
    """
    Create a memecoin on Solana. The dumb way.

    1. Generate a new mint keypair
    2. Create the mint account
    3. Initialize it as an SPL token
    4. Create an associated token account for the payer
    5. Mint an absurd amount of tokens
    6. Return the details

    Args:
        custom_name: Optional custom name. If None, generates a dumb random one.

    Returns:
        Dict with token details (name, ticker, supply, mint address, etc.)
    """
    client = get_client()
    payer = get_payer_keypair()

    # Generate token identity
    if custom_name:
        name = custom_name.upper().replace(" ", "")
        ticker = f"${name[:6]}"
    else:
        name, ticker = generate_dumb_name()

    supply = generate_dumb_supply()
    description = generate_dumb_description()
    decimals = 9

    # Create new mint keypair
    mint_keypair = Keypair()
    mint_pubkey = mint_keypair.pubkey()

    # Calculate minimum rent exemption for mint account (82 bytes for SPL Token mint)
    min_balance_resp = client.get_minimum_balance_for_rent_exemption(82)
    min_balance = min_balance_resp.value

    # Build transaction
    # 1. Create account for the mint
    create_account_ix = create_account(
        CreateAccountParams(
            from_pubkey=payer.pubkey(),
            to_pubkey=mint_pubkey,
            lamports=min_balance,
            space=82,
            owner=TOKEN_PROGRAM_ID,
        )
    )

    # 2. Initialize the mint
    init_mint_ix = initialize_mint(
        InitializeMintParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=mint_pubkey,
            decimals=decimals,
            mint_authority=payer.pubkey(),
            freeze_authority=payer.pubkey(),
        )
    )

    # 3. Create associated token account for payer
    ata = get_associated_token_address(payer.pubkey(), mint_pubkey)
    create_ata_ix = create_associated_token_account(
        payer=payer.pubkey(),
        owner=payer.pubkey(),
        mint=mint_pubkey,
    )

    # 4. Mint tokens to the payer's ATA
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

    # Get recent blockhash
    recent_blockhash_resp = client.get_latest_blockhash()
    recent_blockhash = recent_blockhash_resp.value.blockhash

    # Build and sign transaction
    msg = Message.new_with_blockhash(
        [create_account_ix, init_mint_ix, create_ata_ix, mint_to_ix],
        payer.pubkey(),
        recent_blockhash,
    )
    tx = Transaction.new_unsigned(msg)
    tx.sign([payer, mint_keypair], recent_blockhash)

    # Send transaction
    tx_resp = client.send_transaction(tx)
    tx_signature = str(tx_resp.value)

    return {
        "name": name,
        "ticker": ticker,
        "supply": supply,
        "decimals": decimals,
        "description": description,
        "mint_address": str(mint_pubkey),
        "token_account": str(ata),
        "tx_signature": tx_signature,
        "rpc_url": SOLANA_RPC_URL,
    }


def preview_memecoin(custom_name: str | None = None) -> dict:
    """
    Preview a memecoin without actually creating it on-chain.
    Good for laughs without spending SOL.
    """
    if custom_name:
        name = custom_name.upper().replace(" ", "")
        ticker = f"${name[:6]}"
    else:
        name, ticker = generate_dumb_name()

    return {
        "name": name,
        "ticker": ticker,
        "supply": generate_dumb_supply(),
        "description": generate_dumb_description(),
        "status": "PREVIEW (not deployed yet, relax)",
    }

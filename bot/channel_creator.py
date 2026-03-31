"""
Telegram channel auto-creator.

Uses Telethon (MTProto API) to programmatically create Telegram
channels/groups for each launched memecoin.
"""

import logging
from typing import Optional

from telethon import TelegramClient
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditPhotoRequest,
)
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import InputChannel

from bot.config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

logger = logging.getLogger(__name__)

# Persistent Telethon client (reused across calls)
_client: Optional[TelegramClient] = None


async def get_telethon_client() -> TelegramClient:
    """Get or create the Telethon client. Reuses a single session."""
    global _client
    if _client is None or not _client.is_connected():
        _client = TelegramClient("memecoin_session", TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await _client.start(phone=TELEGRAM_PHONE)
    return _client


async def create_coin_channel(
    name: str,
    ticker: str,
    bio: str,
    first_message: str,
) -> dict:
    """
    Create a Telegram channel for a memecoin.

    Args:
        name: Coin name (used as channel title)
        ticker: Coin ticker (e.g. $PEPE)
        bio: Channel about/description text
        first_message: First pinned message in the channel

    Returns:
        Dict with channel_id, channel_title, invite_link
    """
    client = await get_telethon_client()

    channel_title = f"{name} ({ticker}) Official"

    # Truncate bio to Telegram's 255-char about limit
    channel_about = bio[:255]

    # Create the channel (broadcast = supergroup channel)
    result = await client(CreateChannelRequest(
        title=channel_title,
        about=channel_about,
        megagroup=True,  # supergroup (allows chat), set False for broadcast-only
    ))

    # Extract the created channel
    channel = result.chats[0]
    channel_id = channel.id

    # Generate invite link
    invite = await client(ExportChatInviteRequest(
        peer=channel,
        expire_date=None,
        usage_limit=None,
    ))
    invite_link = invite.link

    # Send first message and pin it
    msg = await client.send_message(channel, first_message)
    await client.pin_message(channel, msg.id)

    logger.info(f"Created channel: {channel_title} -> {invite_link}")

    return {
        "channel_id": channel_id,
        "channel_title": channel_title,
        "invite_link": invite_link,
    }


def build_first_message(name: str, ticker: str, mint_address: str,
                        description: str, supply: int, roadmap: list[str],
                        explorer_url: str) -> str:
    """Build the first pinned message for a new coin channel."""
    roadmap_text = ""
    phase_names = ["Phase 1", "Phase 2", "Phase 3", "Phase 4"]
    for i, item in enumerate(roadmap):
        phase = phase_names[i] if i < len(phase_names) else f"Phase {i+1}"
        roadmap_text += f"  {phase}: {item}\n"

    return (
        f"Welcome to {name} ({ticker})!\n"
        f"{'=' * 40}\n\n"
        f"{description}\n\n"
        f"TOKEN INFO\n"
        f"  Name: {name}\n"
        f"  Ticker: {ticker}\n"
        f"  Supply: {supply:,}\n"
        f"  Blockchain: Solana\n"
        f"  Contract: {mint_address}\n\n"
        f"LINKS\n"
        f"  Explorer: {explorer_url}\n\n"
        f"ROADMAP\n"
        f"{roadmap_text}\n"
        f"Join the community. LFG!\n"
    )


async def close_client():
    """Gracefully disconnect the Telethon client."""
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        _client = None

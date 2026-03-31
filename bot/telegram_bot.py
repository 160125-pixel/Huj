"""
Telegram bot for creating Solana memecoins.

Commands:
  /start       - Welcome message
  /create      - Create a memecoin on-chain (costs SOL)
  /create NAME - Create a memecoin with a custom name
  /preview     - Preview a random memecoin without deploying
  /preview NAME- Preview with custom name
  /help        - Show help
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from bot.config import TELEGRAM_BOT_TOKEN
from bot.solana_memecoin import create_memecoin, preview_memecoin

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    welcome = (
        "Welcome to the MEMECOIN FACTORY\n\n"
        "I create Solana memecoins. They're dumb. You've been warned.\n\n"
        "Commands:\n"
        "/preview - Preview a random memecoin (free, no SOL needed)\n"
        "/preview <name> - Preview with custom name\n"
        "/create - Deploy a random memecoin ON-CHAIN (costs SOL!)\n"
        "/create <name> - Deploy with custom name\n"
        "/help - Show this message again\n\n"
        "NFA. DYOR. Probably don't though."
    )
    await update.message.reply_text(welcome)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help text."""
    await start_command(update, context)


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Preview a memecoin without deploying."""
    custom_name = " ".join(context.args) if context.args else None

    try:
        coin = preview_memecoin(custom_name)
        msg = (
            f"MEMECOIN PREVIEW\n\n"
            f"Name: {coin['name']}\n"
            f"Ticker: {coin['ticker']}\n"
            f"Supply: {coin['supply']:,}\n"
            f"Vibe: {coin['description']}\n\n"
            f"{coin['status']}\n\n"
            f"Want to deploy this degen masterpiece? Use /create"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Preview failed: {e}")
        await update.message.reply_text(f"Preview failed (even that broke): {e}")


async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create and deploy a memecoin on Solana."""
    custom_name = " ".join(context.args) if context.args else None

    await update.message.reply_text(
        "Deploying your memecoin to Solana...\n"
        "This is actually happening. No take-backs."
    )

    try:
        coin = create_memecoin(custom_name)

        explorer_base = "https://explorer.solana.com"
        cluster_param = ""
        if "devnet" in coin["rpc_url"]:
            cluster_param = "?cluster=devnet"

        msg = (
            f"YOUR MEMECOIN IS LIVE\n\n"
            f"Name: {coin['name']}\n"
            f"Ticker: {coin['ticker']}\n"
            f"Supply: {coin['supply']:,}\n"
            f"Decimals: {coin['decimals']}\n"
            f"Vibe: {coin['description']}\n\n"
            f"Mint: {coin['mint_address']}\n"
            f"Token Account: {coin['token_account']}\n\n"
            f"Explorer: {explorer_base}/address/{coin['mint_address']}{cluster_param}\n"
            f"TX: {explorer_base}/tx/{coin['tx_signature']}{cluster_param}\n\n"
            f"Congrats, you're now a crypto founder. Update your LinkedIn."
        )
        await update.message.reply_text(msg)

    except ValueError as e:
        await update.message.reply_text(
            f"Config error: {e}\n\nMake sure your .env is set up properly."
        )
    except Exception as e:
        logger.error(f"Create failed: {e}")
        await update.message.reply_text(
            f"Creation failed: {e}\n\n"
            "Make sure you have SOL in your wallet. "
            "Even memecoins aren't free (sadly)."
        )


def run_bot() -> None:
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not set! Get one from @BotFather on Telegram."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("preview", preview_command))
    app.add_handler(CommandHandler("create", create_command))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

"""
Telegram bot for creating Solana memecoins.

Commands:
  /start       - Welcome message
  /trending    - See what's hot right now
  /preview     - Preview a coin based on a trending meme
  /preview X   - Preview with custom name
  /launch      - Create coin + Telegram channel from trending meme
  /launch X    - Create coin + channel with custom name
  /help        - Show help
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from bot.config import TELEGRAM_BOT_TOKEN
from bot.trending import get_trending_topics, pick_trending_name
from bot.description_generator import generate_full_profile, generate_description
from bot.solana_memecoin import create_memecoin, preview_memecoin
from bot.channel_creator import (
    create_coin_channel,
    build_first_message,
    close_client,
)

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "SOLANA MEMECOIN LAUNCHER\n\n"
        "I create memecoins based on trending memes, deploy them on Solana, "
        "and auto-create Telegram channels — all in one go.\n\n"
        "COMMANDS:\n"
        "/trending — See what's trending right now\n"
        "/preview — Preview a coin from a trending meme\n"
        "/preview <name> — Preview with a custom name\n"
        "/launch — Full launch: coin + channel from trending meme\n"
        "/launch <name> — Full launch with custom name\n"
        "/help — Show this message\n\n"
        "Coins launch at $10-20K market cap with calculated tokenomics."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_command(update, context)


async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current trending topics that could be turned into coins."""
    await update.message.reply_text("Scanning trending topics...")

    try:
        trends = await get_trending_topics()
        if not trends:
            await update.message.reply_text("Couldn't fetch trends right now. Try again later.")
            return

        lines = ["TRENDING NOW\n"]
        for i, t in enumerate(trends[:15], 1):
            source = t.get("source", t.get("category", ""))
            lines.append(f"{i}. {t['name']} — {t.get('description', '')[:60]} [{source}]")

        lines.append(f"\nUse /launch to create a coin from a trending topic!")
        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        logger.error(f"Trending failed: {e}")
        await update.message.reply_text(f"Failed to fetch trends: {e}")


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Preview a coin without deploying."""
    custom_name = " ".join(context.args).strip() if context.args else None

    try:
        if custom_name:
            name = custom_name.upper().replace(" ", "")
            ticker = f"${name[:6]}"
            category = "meme"
        else:
            trends = await get_trending_topics()
            trend = pick_trending_name(trends)
            name = trend["name"]
            ticker = f"${name[:6]}"
            category = trend.get("category", "meme")

        coin = preview_memecoin(name, ticker, category)
        profile = generate_full_profile(name, ticker, category, mint_address="TBD")
        t = coin["tokenomics"]

        roadmap_text = "\n".join(f"  • {r}" for r in profile["roadmap"])

        msg = (
            f"COIN PREVIEW\n\n"
            f"Name: {coin['name']}\n"
            f"Ticker: {coin['ticker']}\n"
            f"Category: {category}\n\n"
            f"TOKENOMICS\n"
            f"  Supply: {t['total_supply']:,}\n"
            f"  Target MCap: ${t['target_mcap']:,.0f}\n"
            f"  Price/Token: ${t['price_per_token_usd']:.10f}\n"
            f"  Initial LP: {t['liquidity_sol']} SOL (${t['liquidity_usd']:,.2f})\n"
            f"  Pool Allocation: {t['pool_token_pct']*100:.0f}% of supply\n\n"
            f"DESCRIPTION\n{profile['description']}\n\n"
            f"ROADMAP\n{roadmap_text}\n\n"
            f"Ready to deploy? Use /launch {name}"
        )
        await update.message.reply_text(msg)

    except Exception as e:
        logger.error(f"Preview failed: {e}")
        await update.message.reply_text(f"Preview failed: {e}")


async def launch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Full launch: create coin on-chain + create Telegram channel."""
    custom_name = " ".join(context.args).strip() if context.args else None

    try:
        # Step 1: Pick name from trends or use custom
        if custom_name:
            name = custom_name.upper().replace(" ", "")
            ticker = f"${name[:6]}"
            category = "meme"
        else:
            await update.message.reply_text("Finding a trending meme...")
            trends = await get_trending_topics()
            trend = pick_trending_name(trends)
            name = trend["name"]
            ticker = f"${name[:6]}"
            category = trend.get("category", "meme")

        await update.message.reply_text(
            f"Launching {name} ({ticker})...\n\n"
            f"Step 1/3: Deploying token on Solana..."
        )

        # Step 2: Deploy on-chain
        coin = create_memecoin(name, ticker, category)
        t = coin["tokenomics"]

        await update.message.reply_text(
            f"Token deployed!\n"
            f"  Mint: {coin['mint_address']}\n"
            f"  Supply: {t['total_supply']:,}\n"
            f"  Target MCap: ${t['target_mcap']:,.0f}\n\n"
            f"Step 2/3: Generating profile..."
        )

        # Step 3: Generate description & profile
        profile = generate_full_profile(name, ticker, category, coin["mint_address"])

        await update.message.reply_text(
            f"Profile ready!\n\n"
            f"Step 3/3: Creating Telegram channel..."
        )

        # Step 4: Create Telegram channel
        first_msg = build_first_message(
            name=name,
            ticker=ticker,
            mint_address=coin["mint_address"],
            description=profile["description"],
            supply=coin["supply"],
            roadmap=profile["roadmap"],
            explorer_url=coin["explorer_url"],
        )

        channel = await create_coin_channel(
            name=name,
            ticker=ticker,
            bio=profile["channel_bio"],
            first_message=first_msg,
        )

        # Final summary
        roadmap_text = "\n".join(f"  • {r}" for r in profile["roadmap"])

        summary = (
            f"LAUNCH COMPLETE!\n"
            f"{'=' * 35}\n\n"
            f"TOKEN\n"
            f"  Name: {name}\n"
            f"  Ticker: {ticker}\n"
            f"  Supply: {t['total_supply']:,}\n"
            f"  Target MCap: ${t['target_mcap']:,.0f}\n"
            f"  Price/Token: ${t['price_per_token_usd']:.10f}\n"
            f"  LP Needed: {t['liquidity_sol']} SOL (${t['liquidity_usd']:,.2f})\n\n"
            f"CONTRACTS\n"
            f"  Mint: {coin['mint_address']}\n"
            f"  Explorer: {coin['explorer_url']}\n"
            f"  TX: {coin['tx_url']}\n\n"
            f"TELEGRAM CHANNEL\n"
            f"  {channel['channel_title']}\n"
            f"  {channel['invite_link']}\n\n"
            f"DESCRIPTION\n{profile['description']}\n\n"
            f"ROADMAP\n{roadmap_text}\n\n"
            f"Next steps:\n"
            f"  1. Add {t['liquidity_sol']} SOL to liquidity pool\n"
            f"  2. Share the channel link\n"
            f"  3. LFG"
        )
        await update.message.reply_text(summary)

    except ValueError as e:
        await update.message.reply_text(f"Config error: {e}\nCheck your .env file.")
    except Exception as e:
        logger.error(f"Launch failed: {e}", exc_info=True)
        await update.message.reply_text(
            f"Launch failed: {e}\n\n"
            "Make sure you have:\n"
            "  • SOL in your wallet\n"
            "  • Telethon credentials set in .env\n"
            "  • Authorized the phone number"
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
    app.add_handler(CommandHandler("trending", trending_command))
    app.add_handler(CommandHandler("preview", preview_command))
    app.add_handler(CommandHandler("launch", launch_command))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

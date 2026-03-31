"""
Telegram bot for creating Solana memecoins.
Full button-driven UI with rich HTML messages.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from bot.config import TELEGRAM_BOT_TOKEN, SOLANA_RPC_URL
from bot.trending import get_trending_topics, pick_trending_name
from bot.description_generator import generate_full_profile
from bot.solana_memecoin import create_memecoin, preview_memecoin

logger = logging.getLogger(__name__)


# ─── Message Builders ────────────────────────────────────────────────

def build_welcome_msg() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🚀 <b>SOLANA MEMECOIN LAUNCHER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Create memecoins from trending memes,\n"
        "deploy on Solana, all in one tap.\n\n"
        "📊 Coins launch at <b>$10-20K</b> market cap\n"
        "⚡ Launched on <b>pump.fun</b>\n"
        "🎯 Calculated tokenomics\n\n"
        "👇 <b>Choose an action below</b>"
    )
    keyboard = [
        [
            InlineKeyboardButton("🔥 Trending", callback_data="trending"),
            InlineKeyboardButton("👀 Preview", callback_data="preview_random"),
        ],
        [
            InlineKeyboardButton("🚀 Launch Coin", callback_data="launch_random"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_trending_msg(trends: list[dict]) -> tuple[str, InlineKeyboardMarkup]:
    lines = ["🔥 <b>TRENDING NOW</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, t in enumerate(trends[:10], 1):
        source = t.get("source", t.get("category", ""))
        desc = t.get("description", "")[:50]
        lines.append(f"<b>{i}.</b> <code>{t['name']}</code> — {desc} <i>[{source}]</i>")

    lines.append("\n👇 <b>Tap a coin to preview or launch it</b>")
    text = "\n".join(lines)

    # Build buttons: 2 per row, each trend gets a preview button
    keyboard = []
    row = []
    for i, t in enumerate(trends[:10]):
        row.append(InlineKeyboardButton(
            f"👀 {t['name']}", callback_data=f"preview_{t['name']}_{t.get('category', 'meme')}"
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="trending"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])

    return text, InlineKeyboardMarkup(keyboard)


def build_preview_msg(coin: dict, profile: dict) -> tuple[str, InlineKeyboardMarkup]:
    t = coin["tokenomics"]
    name = coin["name"]
    ticker = coin["ticker"]
    category = coin.get("category", "meme")

    roadmap_text = "\n".join(f"   ├ {r}" for r in profile["roadmap"][:-1])
    roadmap_text += f"\n   └ {profile['roadmap'][-1]}"

    text = (
        f"👀 <b>COIN PREVIEW</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🪙 <b>{name}</b>  •  <code>{ticker}</code>\n"
        f"🏷 Category: <i>{category}</i>\n"
        f"💬 <i>{profile['tagline']}</i>\n\n"

        f"📊 <b>TOKENOMICS</b>\n"
        f"   ├ Supply: <b>{t['total_supply']:,}</b>\n"
        f"   ├ MCap: <b>${t['target_mcap']:,.0f}</b>\n"
        f"   ├ Price: <code>${t['price_per_token_usd']:.10f}</code>\n"
        f"   └ Dev Buy: <b>{t['initial_buy_sol']} SOL</b> (${t['initial_buy_usd']:,.2f})\n\n"

        f"🎰 <b>PLATFORM</b>\n"
        f"   └ pump.fun (bonding curve)\n\n"

        f"📝 <b>ABOUT</b>\n"
        f"<i>{profile['description']}</i>\n\n"

        f"🗺 <b>ROADMAP</b>\n"
        f"{roadmap_text}\n\n"

        f"⚠️ <i>Preview only — not deployed yet</i>"
    )

    keyboard = [
        [
            InlineKeyboardButton("🚀 Launch This Coin", callback_data=f"launch_{name}_{category}"),
        ],
        [
            InlineKeyboardButton("🔄 New Preview", callback_data="preview_random"),
            InlineKeyboardButton("🔥 Trending", callback_data="trending"),
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_launch_msg(coin: dict, profile: dict) -> tuple[str, InlineKeyboardMarkup]:
    t = coin["tokenomics"]
    name = coin["name"]
    ticker = coin["ticker"]
    mint = coin["mint_address"]

    roadmap_text = "\n".join(f"   ├ {r}" for r in profile["roadmap"][:-1])
    roadmap_text += f"\n   └ {profile['roadmap'][-1]}"

    text = (
        f"✅ <b>LAUNCH SUCCESSFUL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🪙 <b>{name}</b>  •  <code>{ticker}</code>\n"
        f"💬 <i>{profile['tagline']}</i>\n\n"

        f"📊 <b>TOKENOMICS</b>\n"
        f"   ├ Supply: <b>{t['total_supply']:,}</b>\n"
        f"   ├ MCap: <b>${t['target_mcap']:,.0f}</b>\n"
        f"   ├ Price: <code>${t['price_per_token_usd']:.10f}</code>\n"
        f"   └ Dev Buy: <b>{t['initial_buy_sol']} SOL</b> (${t['initial_buy_usd']:,.2f})\n\n"

        f"📋 <b>CONTRACT</b>\n"
        f"   <code>{mint}</code>\n"
        f"   Platform: <b>pump.fun</b>\n\n"

        f"📝 <b>ABOUT</b>\n"
        f"<i>{profile['description']}</i>\n\n"

        f"🗺 <b>ROADMAP</b>\n"
        f"{roadmap_text}\n\n"

        f"💡 <b>Next:</b> Share the pump.fun link!"
    )

    pumpfun_url = coin["pumpfun_url"]
    phantom_url = coin["phantom_url"]
    explorer_url = coin["explorer_url"]

    keyboard = [
        [
            InlineKeyboardButton("💰 Buy on Pump.fun", url=pumpfun_url),
        ],
        [
            InlineKeyboardButton("👻 Open in Phantom", url=phantom_url),
        ],
        [
            InlineKeyboardButton("📊 Chart", url=pumpfun_url),
            InlineKeyboardButton("🔍 Explorer", url=explorer_url),
        ],
        [
            InlineKeyboardButton("📋 Copy CA", callback_data=f"copy_{mint}"),
        ],
        [
            InlineKeyboardButton("🚀 Launch Another", callback_data="launch_random"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_help_msg() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "❓ <b>HOW IT WORKS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "1️⃣ <b>Trending</b> — Scans Reddit & CoinGecko\n"
        "   for hot memes to turn into coins\n\n"

        "2️⃣ <b>Preview</b> — See tokenomics, description\n"
        "   & roadmap before spending any SOL\n\n"

        "3️⃣ <b>Launch</b> — Deploys on pump.fun\n"
        "   at $10-20K target market cap\n\n"

        "4️⃣ <b>Buy/Sell</b> — Direct links to pump.fun\n"
        "   & Phantom wallet for trading\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Commands</b>\n"
        "   /start — Main menu\n"
        "   /trending — See trends\n"
        "   /preview — Preview a coin\n"
        "   /launch — Deploy a coin\n"
        "   /launch NAME — Deploy custom coin\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("🔥 Trending", callback_data="trending"),
            InlineKeyboardButton("🚀 Launch", callback_data="launch_random"),
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_deploying_msg(name: str, ticker: str, step: int) -> str:
    steps = [
        ("🔍", "Finding trending meme...", "⏳"),
        ("📡", "Deploying on pump.fun...", "⏳"),
        ("📝", "Generating profile...", "⏳"),
    ]
    lines = [
        f"🚀 <b>LAUNCHING {name}</b>  •  <code>{ticker}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    for i, (icon, desc, pending) in enumerate(steps):
        if i < step:
            lines.append(f"   ✅ {desc}")
        elif i == step:
            lines.append(f"   ⏳ {desc}")
        else:
            lines.append(f"   ⬜ {desc}")

    return "\n".join(lines)


# ─── Handlers ────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, keyboard = build_welcome_msg()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, keyboard = build_help_msg()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loading = await update.message.reply_text("🔍 <b>Scanning trends...</b>", parse_mode=ParseMode.HTML)
    try:
        trends = await get_trending_topics()
        context.user_data["trends"] = trends
        text, keyboard = build_trending_msg(trends)
        await loading.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Trending failed: {e}")
        await loading.edit_text(f"❌ Failed to fetch trends: {e}")


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    custom_name = " ".join(context.args).strip() if context.args else None
    await _do_preview(update.message, context, custom_name=custom_name)


async def launch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    custom_name = " ".join(context.args).strip() if context.args else None
    await _do_launch(update.message, context, custom_name=custom_name)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline button presses."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        text, keyboard = build_welcome_msg()
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "help":
        text, keyboard = build_help_msg()
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "trending":
        await query.edit_message_text("🔍 <b>Scanning trends...</b>", parse_mode=ParseMode.HTML)
        try:
            trends = await get_trending_topics()
            context.user_data["trends"] = trends
            text, keyboard = build_trending_msg(trends)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as e:
            await query.edit_message_text(f"❌ Failed: {e}")

    elif data == "preview_random":
        await _do_preview(query.message, context, edit=True)

    elif data.startswith("preview_"):
        parts = data.split("_", 2)
        if len(parts) >= 3:
            name = parts[1]
            category = parts[2]
        else:
            name = parts[1]
            category = "meme"
        await _do_preview(query.message, context, custom_name=name, category=category, edit=True)

    elif data == "launch_random":
        await _do_launch(query.message, context, edit=True)

    elif data.startswith("launch_"):
        parts = data.split("_", 2)
        if len(parts) >= 3:
            name = parts[1]
            category = parts[2]
        else:
            name = parts[1]
            category = "meme"
        await _do_launch(query.message, context, custom_name=name, category=category, edit=True)

    elif data.startswith("copy_"):
        mint = data[5:]
        await query.answer(text=f"📋 CA: {mint}", show_alert=True)


# ─── Core Logic ──────────────────────────────────────────────────────

async def _do_preview(message, context, custom_name=None, category=None, edit=False):
    """Preview a coin. Works for both commands and button callbacks."""
    try:
        if custom_name:
            name = custom_name.upper().replace(" ", "")
            ticker = f"${name[:6]}"
            cat = category or "meme"
        else:
            trends = context.user_data.get("trends") or await get_trending_topics()
            context.user_data["trends"] = trends
            trend = pick_trending_name(trends)
            name = trend["name"]
            ticker = f"${name[:6]}"
            cat = trend.get("category", "meme")

        coin = preview_memecoin(name, ticker, cat)
        profile = generate_full_profile(name, ticker, cat, mint_address="TBD")
        text, keyboard = build_preview_msg(coin, profile)

        if edit:
            await message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Preview failed: {e}")
        err = f"❌ Preview failed: {e}"
        if edit:
            await message.edit_text(err)
        else:
            await message.reply_text(err)


async def _do_launch(message, context, custom_name=None, category=None, edit=False):
    """Full launch: deploy token on Solana. Works for both commands and buttons."""
    try:
        # Resolve name
        if custom_name:
            name = custom_name.upper().replace(" ", "")
            ticker = f"${name[:6]}"
            cat = category or "meme"
        else:
            trends = context.user_data.get("trends") or await get_trending_topics()
            context.user_data["trends"] = trends
            trend = pick_trending_name(trends)
            name = trend["name"]
            ticker = f"${name[:6]}"
            cat = trend.get("category", "meme")

        # Step 1: Show deploying status
        deploying_text = build_deploying_msg(name, ticker, 1)
        if edit:
            await message.edit_text(deploying_text, parse_mode=ParseMode.HTML)
        else:
            message = await message.reply_text(deploying_text, parse_mode=ParseMode.HTML)

        # Step 2: Generate profile first (need description for pump.fun)
        profile = generate_full_profile(name, ticker, cat, mint_address="TBD")

        # Step 3: Deploy on pump.fun
        coin = await create_memecoin(name, ticker, profile["description"], cat)

        await message.edit_text(build_deploying_msg(name, ticker, 2), parse_mode=ParseMode.HTML)
        # Update profile with actual mint address
        profile = generate_full_profile(name, ticker, cat, coin["mint_address"])

        # Done — show full launch card with buttons
        text, keyboard = build_launch_msg(coin, profile)
        await message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except ValueError as e:
        err = f"⚠️ <b>Config error:</b> {e}\n\nCheck your <code>.env</code> file."
        try:
            await message.edit_text(err, parse_mode=ParseMode.HTML)
        except Exception:
            await message.reply_text(err, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Launch failed: {e}", exc_info=True)
        err = (
            f"❌ <b>Launch failed:</b> {e}\n\n"
            "Make sure you have:\n"
            "  • SOL in your wallet (for pump.fun fees)\n"
            "  • Valid private key in .env"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Try Again", callback_data="launch_random")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
        ])
        try:
            await message.edit_text(err, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            await message.reply_text(err, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# ─── Bot Runner ──────────────────────────────────────────────────────

def run_bot() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set! Get one from @BotFather.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("trending", trending_command))
    app.add_handler(CommandHandler("preview", preview_command))
    app.add_handler(CommandHandler("launch", launch_command))

    # Button callbacks
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

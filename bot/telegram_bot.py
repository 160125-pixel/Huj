"""
Solana Copy Trading Bot — Telegram UI.

Button-driven interface for discovering top traders, tracking wallets,
copying trades, and monitoring portfolio.
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from bot.config import TELEGRAM_BOT_TOKEN, MAX_BUY_SOL, AUTO_COPY
from bot.top_traders import discover_top_traders, get_trader_stats, TraderStats
from bot.wallet_tracker import (
    add_tracked_wallet, remove_tracked_wallet, get_tracked_wallets,
    on_swap, SwapEvent, restart_tracker,
)
from bot.trade_copier import copy_trade, manual_buy, manual_sell
from bot.portfolio import get_portfolio, record_trade

logger = logging.getLogger(__name__)

# Store bot app reference for sending notifications
_app = None


# ─── Message Builders ────────────────────────────────────────────────

def build_home_msg() -> tuple[str, InlineKeyboardMarkup]:
    tracked = get_tracked_wallets()
    text = (
        "🤖 <b>SOLANA COPY TRADE BOT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Copy the best Solana traders automatically.\n"
        "Find top wallets, track them, and mirror\n"
        "their trades in real-time.\n\n"
        f"📡 Tracking: <b>{len(tracked)}</b> wallets\n"
        f"💰 Max buy: <b>{MAX_BUY_SOL} SOL</b>\n"
        f"🔄 Auto-copy: <b>{'ON' if AUTO_COPY else 'OFF'}</b>\n\n"
        "👇 <b>Choose an action</b>"
    )
    keyboard = [
        [
            InlineKeyboardButton("🏆 Top Traders", callback_data="top_traders"),
            InlineKeyboardButton("📡 Tracked", callback_data="tracked_wallets"),
        ],
        [
            InlineKeyboardButton("💼 Portfolio", callback_data="portfolio"),
        ],
        [
            InlineKeyboardButton("💰 Buy Token", callback_data="buy_prompt"),
            InlineKeyboardButton("💸 Sell Token", callback_data="sell_prompt"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_top_traders_msg(traders: list[TraderStats]) -> tuple[str, InlineKeyboardMarkup]:
    if not traders:
        text = (
            "🏆 <b>TOP TRADERS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ No traders found.\n\n"
            "Set your <code>BIRDEYE_API_KEY</code> in .env\n"
            "to discover top wallets automatically."
        )
        keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
        return text, InlineKeyboardMarkup(keyboard)

    lines = ["🏆 <b>TOP TRADERS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, t in enumerate(traders[:10], 1):
        label = t.label or f"{t.address[:6]}...{t.address[-4:]}"
        pnl_icon = "🟢" if t.total_pnl_usd >= 0 else "🔴"
        lines.append(
            f"<b>{i}.</b> {label}\n"
            f"   {pnl_icon} PnL: <b>${t.total_pnl_usd:,.0f}</b>  •  "
            f"WR: <b>{t.winrate}%</b>  •  "
            f"Trades: {t.total_trades}"
        )

    lines.append("\n👇 <b>Tap to track a wallet</b>")
    text = "\n".join(lines)

    keyboard = []
    row = []
    for i, t in enumerate(traders[:10]):
        short = t.label or f"{t.address[:6]}"
        row.append(InlineKeyboardButton(
            f"📡 {short}", callback_data=f"track_{t.address}"
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="top_traders"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])
    return text, InlineKeyboardMarkup(keyboard)


def build_tracked_msg() -> tuple[str, InlineKeyboardMarkup]:
    wallets = get_tracked_wallets()
    if not wallets:
        text = (
            "📡 <b>TRACKED WALLETS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "No wallets being tracked.\n\n"
            "Use 🏆 <b>Top Traders</b> to find wallets,\n"
            "or use /track &lt;address&gt; to add one."
        )
        keyboard = [
            [InlineKeyboardButton("🏆 Find Traders", callback_data="top_traders")],
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
        ]
        return text, InlineKeyboardMarkup(keyboard)

    lines = ["📡 <b>TRACKED WALLETS</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"]
    for addr, label in wallets.items():
        short_addr = f"{addr[:6]}...{addr[-4:]}"
        lines.append(f"🟢 <b>{label}</b>\n   <code>{short_addr}</code>")

    text = "\n".join(lines)

    keyboard = []
    for addr, label in wallets.items():
        keyboard.append([
            InlineKeyboardButton(f"👤 {label}", callback_data=f"stats_{addr}"),
            InlineKeyboardButton("❌ Remove", callback_data=f"untrack_{addr}"),
        ])

    keyboard.append([
        InlineKeyboardButton("🏆 Add More", callback_data="top_traders"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])
    return text, InlineKeyboardMarkup(keyboard)


def build_portfolio_msg(portfolio) -> tuple[str, InlineKeyboardMarkup]:
    pnl_icon = "🟢" if portfolio.total_pnl_usd >= 0 else "🔴"

    lines = [
        "💼 <b>PORTFOLIO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"◎ SOL: <b>{portfolio.sol_balance:.4f}</b> (${portfolio.sol_value_usd:,.2f})\n"
        f"🪙 Tokens: <b>{portfolio.token_count}</b>\n"
        f"💰 Total Value: <b>${portfolio.total_value_usd:,.2f}</b>\n"
        f"{pnl_icon} Total PnL: <b>${portfolio.total_pnl_usd:,.2f}</b>\n\n"
    ]

    if portfolio.holdings:
        lines.append("<b>HOLDINGS</b>\n")
        for h in portfolio.holdings[:10]:
            h_pnl = "🟢" if h.pnl_usd >= 0 else "🔴"
            pnl_str = f"{h_pnl} ${h.pnl_usd:,.2f} ({h.pnl_pct:+.1f}%)" if h.cost_basis_usd > 0 else "—"
            lines.append(
                f"  <b>{h.symbol}</b>  •  {h.balance:,.2f}\n"
                f"    💲 ${h.value_usd:,.2f}  •  PnL: {pnl_str}"
            )
        lines.append("")

    text = "\n".join(lines)

    # Build sell buttons for each holding
    keyboard = []
    for h in portfolio.holdings[:8]:
        keyboard.append([
            InlineKeyboardButton(
                f"💸 Sell {h.symbol} (25%)", callback_data=f"sell_{h.mint}_25"
            ),
            InlineKeyboardButton(
                f"💸 50%", callback_data=f"sell_{h.mint}_50"
            ),
            InlineKeyboardButton(
                f"💸 100%", callback_data=f"sell_{h.mint}_100"
            ),
        ])

    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="portfolio"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])
    return text, InlineKeyboardMarkup(keyboard)


def build_swap_notification(swap: SwapEvent, label: str) -> tuple[str, InlineKeyboardMarkup]:
    """Build a notification message when a tracked wallet swaps."""
    icon = "🟢 BUY" if swap.action == "BUY" else "🔴 SELL"
    text = (
        f"🔔 <b>SWAP DETECTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Trader: <b>{label}</b>\n"
        f"📋 Action: <b>{icon}</b>\n"
        f"🪙 Token: <code>{swap.token_mint[:8]}...{swap.token_mint[-4:]}</code>\n"
        f"💰 Amount: <b>{swap.amount_sol:.4f} SOL</b>\n"
        f"🏪 DEX: {swap.dex}\n\n"
        f"👇 <b>Copy this trade?</b>"
    )
    keyboard = [
        [
            InlineKeyboardButton(
                f"📋 Copy ({min(swap.amount_sol, MAX_BUY_SOL):.2f} SOL)",
                callback_data=f"copy_{swap.action}_{swap.token_mint}_{swap.amount_sol:.4f}"
            ),
        ],
        [
            InlineKeyboardButton("💰 Buy 0.1 SOL", callback_data=f"quickbuy_{swap.token_mint}_0.1"),
            InlineKeyboardButton("💰 Buy 0.5 SOL", callback_data=f"quickbuy_{swap.token_mint}_0.5"),
            InlineKeyboardButton("💰 Buy 1 SOL", callback_data=f"quickbuy_{swap.token_mint}_1"),
        ],
        [
            InlineKeyboardButton("📊 Chart", url=f"https://birdeye.so/token/{swap.token_mint}?chain=solana"),
            InlineKeyboardButton("🔍 TX", url=f"https://solscan.io/tx/{swap.signature}"),
        ],
        [
            InlineKeyboardButton("❌ Skip", callback_data="dismiss"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_trade_result_msg(result: dict, action: str) -> tuple[str, InlineKeyboardMarkup]:
    """Build a trade execution result message."""
    icon = "🟢" if action == "BUY" else "🔴"
    text = (
        f"{icon} <b>TRADE EXECUTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Action: <b>{action}</b>\n"
        f"Token: <code>{result.get('output_mint', result.get('input_mint', ''))[:8]}...</code>\n"
    )
    if action == "BUY":
        text += f"Spent: <b>{result.get('sol_spent', 0):.4f} SOL</b>\n"
    else:
        text += f"Received: check explorer\n"

    text += (
        f"Impact: {result.get('price_impact_pct', 0):.2f}%\n\n"
        f"🔗 <a href=\"{result['tx_url']}\">View Transaction</a>"
    )

    keyboard = [
        [
            InlineKeyboardButton("💼 Portfolio", callback_data="portfolio"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_settings_msg() -> tuple[str, InlineKeyboardMarkup]:
    wallets = get_tracked_wallets()
    text = (
        "⚙️ <b>SETTINGS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Max buy per trade: <b>{MAX_BUY_SOL} SOL</b>\n"
        f"📡 Tracked wallets: <b>{len(wallets)}</b>\n"
        f"🔄 Auto-copy: <b>{'ON' if AUTO_COPY else 'OFF'}</b>\n\n"
        "⚠️ Edit <code>.env</code> to change:\n"
        "   • <code>MAX_BUY_SOL</code> — max SOL per trade\n"
        "   • <code>SLIPPAGE_BPS</code> — slippage (300 = 3%)\n"
        "   • <code>AUTO_COPY</code> — auto-copy trades\n"
        "   • <code>BIRDEYE_API_KEY</code> — for trader data\n"
        "   • <code>HELIUS_API_KEY</code> — for faster RPC"
    )
    keyboard = [
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def build_help_msg() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "❓ <b>HOW IT WORKS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "1️⃣ <b>Discover</b> — Find top traders by\n"
        "   winrate and PnL from Birdeye data\n\n"

        "2️⃣ <b>Track</b> — Monitor their wallets for\n"
        "   new buys and sells in real-time\n\n"

        "3️⃣ <b>Copy</b> — Replicate their trades\n"
        "   via Jupiter with one tap\n\n"

        "4️⃣ <b>Portfolio</b> — Track your holdings,\n"
        "   PnL, and sell with quick buttons\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Commands</b>\n"
        "   /start — Main menu\n"
        "   /top — Top traders leaderboard\n"
        "   /track &lt;address&gt; — Track a wallet\n"
        "   /untrack &lt;address&gt; — Untrack wallet\n"
        "   /portfolio — View portfolio\n"
        "   /buy &lt;mint&gt; &lt;sol&gt; — Buy token\n"
        "   /sell &lt;mint&gt; &lt;pct&gt; — Sell token\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("🏆 Top Traders", callback_data="top_traders"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


# ─── Swap Notification Handler ────────────────────────────────────────

async def handle_swap_event(swap: SwapEvent):
    """Called by wallet tracker when a swap is detected."""
    if _app is None:
        return

    wallets = get_tracked_wallets()
    label = wallets.get(swap.wallet, swap.wallet[:8])
    text, keyboard = build_swap_notification(swap, label)

    # Send to all users who started the bot (simplified: broadcast)
    # In production, you'd store chat IDs. For now, we use context.
    # This will be sent via the job queue if auto-copy is on.
    if AUTO_COPY:
        try:
            result = await copy_trade(swap)
            logger.info(f"Auto-copied {swap.action}: {result['tx_url']}")
        except Exception as e:
            logger.error(f"Auto-copy failed: {e}")


# ─── Command Handlers ────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Store chat_id for notifications
    context.bot_data.setdefault("chat_ids", set()).add(update.effective_chat.id)
    text, keyboard = build_home_msg()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, keyboard = build_help_msg()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loading = await update.message.reply_text("🏆 <b>Loading top traders...</b>", parse_mode=ParseMode.HTML)
    try:
        traders = await discover_top_traders()
        context.bot_data["traders"] = traders
        text, keyboard = build_top_traders_msg(traders)
        await loading.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception as e:
        await loading.edit_text(f"❌ Failed: {e}")


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /track <wallet_address> [label]")
        return

    address = context.args[0]
    label = " ".join(context.args[1:]) if len(context.args) > 1 else f"{address[:6]}...{address[-4:]}"

    add_tracked_wallet(address, label)
    restart_tracker()

    await update.message.reply_text(
        f"📡 Now tracking: <b>{label}</b>\n<code>{address}</code>",
        parse_mode=ParseMode.HTML,
    )


async def untrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /untrack <wallet_address>")
        return

    address = context.args[0]
    remove_tracked_wallet(address)
    restart_tracker()

    await update.message.reply_text(f"❌ Stopped tracking <code>{address[:8]}...</code>", parse_mode=ParseMode.HTML)


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loading = await update.message.reply_text("💼 <b>Loading portfolio...</b>", parse_mode=ParseMode.HTML)
    try:
        portfolio = await get_portfolio()
        text, keyboard = build_portfolio_msg(portfolio)
        await loading.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception as e:
        await loading.edit_text(f"❌ Failed: {e}")


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /buy <token_mint> <sol_amount>")
        return

    mint = context.args[0]
    try:
        sol_amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid SOL amount")
        return

    loading = await update.message.reply_text(
        f"💰 <b>Buying with {sol_amount} SOL...</b>", parse_mode=ParseMode.HTML
    )
    try:
        result = await manual_buy(mint, sol_amount)
        text, keyboard = build_trade_result_msg(result, "BUY")
        await loading.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                                disable_web_page_preview=True)
    except Exception as e:
        await loading.edit_text(f"❌ Buy failed: {e}")


async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /sell <token_mint> [percentage]")
        return

    mint = context.args[0]
    pct = float(context.args[1]) if len(context.args) > 1 else 100.0

    loading = await update.message.reply_text(
        f"💸 <b>Selling {pct}%...</b>", parse_mode=ParseMode.HTML
    )
    try:
        result = await manual_sell(mint, pct)
        text, keyboard = build_trade_result_msg(result, "SELL")
        await loading.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                                disable_web_page_preview=True)
    except Exception as e:
        await loading.edit_text(f"❌ Sell failed: {e}")


# ─── Button Handler ──────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        if data == "home":
            text, keyboard = build_home_msg()
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data == "help":
            text, keyboard = build_help_msg()
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data == "settings":
            text, keyboard = build_settings_msg()
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data == "top_traders":
            await query.edit_message_text("🏆 <b>Loading top traders...</b>", parse_mode=ParseMode.HTML)
            traders = await discover_top_traders()
            context.bot_data["traders"] = traders
            text, keyboard = build_top_traders_msg(traders)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data == "tracked_wallets":
            text, keyboard = build_tracked_msg()
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data.startswith("track_"):
            address = data[6:]
            label = f"{address[:6]}...{address[-4:]}"
            # Check if we have trader stats with a label
            traders = context.bot_data.get("traders", [])
            for t in traders:
                if t.address == address and t.label:
                    label = t.label
                    break

            add_tracked_wallet(address, label)
            restart_tracker()

            await query.answer(f"📡 Now tracking {label}", show_alert=True)
            text, keyboard = build_tracked_msg()
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data.startswith("untrack_"):
            address = data[8:]
            remove_tracked_wallet(address)
            restart_tracker()
            text, keyboard = build_tracked_msg()
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data.startswith("stats_"):
            address = data[6:]
            await query.edit_message_text("📊 <b>Loading stats...</b>", parse_mode=ParseMode.HTML)
            stats = await get_trader_stats(address)
            pnl_icon = "🟢" if stats.total_pnl_usd >= 0 else "🔴"
            label = stats.label or f"{address[:6]}...{address[-4:]}"
            text = (
                f"👤 <b>{label}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📋 Address: <code>{address}</code>\n\n"
                f"📊 Trades: <b>{stats.total_trades}</b>\n"
                f"✅ Wins: <b>{stats.winning_trades}</b>\n"
                f"🎯 Winrate: <b>{stats.winrate}%</b>\n"
                f"{pnl_icon} PnL: <b>${stats.total_pnl_usd:,.2f}</b>\n"
                f"💰 Avg Size: <b>${stats.avg_trade_size_usd:,.2f}</b>\n"
            )
            if stats.tokens_traded:
                text += f"\n🪙 Recent: {', '.join(stats.tokens_traded[:5])}"

            keyboard = [
                [
                    InlineKeyboardButton("📡 Track", callback_data=f"track_{address}"),
                    InlineKeyboardButton("🔍 Solscan", url=f"https://solscan.io/account/{address}"),
                ],
                [
                    InlineKeyboardButton("🏆 Top Traders", callback_data="top_traders"),
                    InlineKeyboardButton("🏠 Home", callback_data="home"),
                ],
            ]
            await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                          reply_markup=InlineKeyboardMarkup(keyboard))

        elif data == "portfolio":
            await query.edit_message_text("💼 <b>Loading portfolio...</b>", parse_mode=ParseMode.HTML)
            portfolio = await get_portfolio()
            text, keyboard = build_portfolio_msg(portfolio)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        elif data.startswith("sell_"):
            parts = data.split("_")
            # sell_<mint>_<pct>
            mint = parts[1]
            pct = float(parts[2])
            await query.edit_message_text(f"💸 <b>Selling {pct}%...</b>", parse_mode=ParseMode.HTML)
            result = await manual_sell(mint, pct)
            text, keyboard = build_trade_result_msg(result, "SELL")
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                                          disable_web_page_preview=True)

        elif data.startswith("quickbuy_"):
            parts = data.split("_")
            # quickbuy_<mint>_<sol>
            mint = parts[1]
            sol = float(parts[2])
            await query.edit_message_text(f"💰 <b>Buying with {sol} SOL...</b>", parse_mode=ParseMode.HTML)
            result = await manual_buy(mint, sol)
            text, keyboard = build_trade_result_msg(result, "BUY")
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                                          disable_web_page_preview=True)

        elif data.startswith("copy_"):
            parts = data.split("_")
            # copy_<action>_<mint>_<sol>
            action = parts[1]
            mint = parts[2]
            sol = float(parts[3])
            capped_sol = min(sol, MAX_BUY_SOL)

            await query.edit_message_text(
                f"📋 <b>Copying {action}...</b>", parse_mode=ParseMode.HTML
            )

            if action == "BUY":
                result = await manual_buy(mint, capped_sol)
            else:
                result = await manual_sell(mint)

            text, keyboard = build_trade_result_msg(result, action)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                                          disable_web_page_preview=True)

        elif data == "buy_prompt":
            text = (
                "💰 <b>BUY TOKEN</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Send a command:\n"
                "<code>/buy &lt;token_mint&gt; &lt;sol_amount&gt;</code>\n\n"
                "Example:\n"
                "<code>/buy EPjFWdd5AufqSSqeM2q... 0.5</code>"
            )
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
            await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                          reply_markup=InlineKeyboardMarkup(keyboard))

        elif data == "sell_prompt":
            text = (
                "💸 <b>SELL TOKEN</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Send a command:\n"
                "<code>/sell &lt;token_mint&gt; [percentage]</code>\n\n"
                "Example:\n"
                "<code>/sell EPjFWdd5AufqSSqeM2q... 50</code>\n\n"
                "Or use the 💼 Portfolio to sell with buttons."
            )
            keyboard = [
                [InlineKeyboardButton("💼 Portfolio", callback_data="portfolio")],
                [InlineKeyboardButton("🏠 Home", callback_data="home")],
            ]
            await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                          reply_markup=InlineKeyboardMarkup(keyboard))

        elif data == "dismiss":
            await query.delete_message()

    except Exception as e:
        logger.error(f"Button handler error: {e}", exc_info=True)
        keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
        try:
            await query.edit_message_text(
                f"❌ Error: {e}", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            pass


# ─── Bot Runner ──────────────────────────────────────────────────────

def run_bot() -> None:
    global _app
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set! Get one from @BotFather.")

    _app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register swap event handler
    on_swap(handle_swap_event)

    # Commands
    _app.add_handler(CommandHandler("start", start_command))
    _app.add_handler(CommandHandler("help", help_command))
    _app.add_handler(CommandHandler("top", top_command))
    _app.add_handler(CommandHandler("track", track_command))
    _app.add_handler(CommandHandler("untrack", untrack_command))
    _app.add_handler(CommandHandler("portfolio", portfolio_command))
    _app.add_handler(CommandHandler("buy", buy_command))
    _app.add_handler(CommandHandler("sell", sell_command))

    # Button callbacks
    _app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Copy Trade Bot is running. Press Ctrl+C to stop.")
    _app.run_polling(allowed_updates=Update.ALL_TYPES)

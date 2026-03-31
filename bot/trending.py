"""
Trending meme/topic detector.

Scrapes trending topics from CoinGecko trending, Reddit meme subs,
and Google Trends to find what's hot right now for coin inspiration.
"""

import asyncio
import random
import logging
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Fallback trending themes when APIs are unreachable
FALLBACK_TRENDS = [
    {"name": "PEPE", "category": "meme", "description": "The iconic green frog taking over crypto"},
    {"name": "DOGE", "category": "meme", "description": "The original memecoin dog"},
    {"name": "WOJAK", "category": "meme", "description": "The feelings guy of the internet"},
    {"name": "CHAD", "category": "meme", "description": "The ultimate sigma grindset"},
    {"name": "NYAN", "category": "meme", "description": "Rainbow cat from the early internet era"},
    {"name": "STONKS", "category": "finance", "description": "When the market only goes up"},
    {"name": "HODL", "category": "crypto", "description": "Diamond hands never sell"},
    {"name": "GIGA", "category": "meme", "description": "Gigachad energy in token form"},
    {"name": "MONKE", "category": "meme", "description": "Return to monke, reject modernity"},
    {"name": "SNEK", "category": "meme", "description": "Danger noodle vibes"},
    {"name": "BODEN", "category": "political", "description": "Political meme season is here"},
    {"name": "WIF", "category": "meme", "description": "Dog wif hat energy"},
    {"name": "POPCAT", "category": "meme", "description": "The clicking cat meme goes blockchain"},
    {"name": "MOG", "category": "meme", "description": "Mogging the entire market"},
    {"name": "BRETT", "category": "meme", "description": "Boy's club frog on the blockchain"},
]

# Meme-related subreddits to scan
MEME_SUBREDDITS = ["memes", "dankmemes", "cryptocurrency", "CryptoMoonShots"]


async def fetch_reddit_trending(session: aiohttp.ClientSession) -> list[dict]:
    """Fetch trending posts from meme subreddits via Reddit JSON API."""
    trends = []
    headers = {"User-Agent": "MemecoinBot/1.0"}

    for sub in MEME_SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    post_data = post.get("data", {})
                    title = post_data.get("title", "")
                    score = post_data.get("score", 0)
                    if score > 500:
                        # Extract potential coin names from high-engagement posts
                        words = [w.strip("!?.#@$,").upper() for w in title.split() if len(w) >= 3 and len(w) <= 10]
                        for word in words[:3]:
                            if word.isalpha():
                                trends.append({
                                    "name": word,
                                    "category": "reddit_trending",
                                    "description": title[:100],
                                    "score": score,
                                    "source": f"r/{sub}",
                                })
        except Exception as e:
            logger.debug(f"Reddit fetch failed for r/{sub}: {e}")
            continue

    return trends


async def fetch_coingecko_trending(session: aiohttp.ClientSession) -> list[dict]:
    """Fetch trending coins from CoinGecko for name inspiration."""
    trends = []
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return trends
            data = await resp.json()
            coins = data.get("coins", [])
            for coin in coins:
                item = coin.get("item", {})
                name = item.get("name", "").upper().replace(" ", "")
                symbol = item.get("symbol", "").upper()
                trends.append({
                    "name": symbol if len(symbol) >= 3 else name,
                    "category": "crypto_trending",
                    "description": f"Trending on CoinGecko - {item.get('name', '')}",
                    "score": item.get("score", 0),
                    "source": "coingecko",
                })
    except Exception as e:
        logger.debug(f"CoinGecko fetch failed: {e}")

    return trends


async def get_trending_topics() -> list[dict]:
    """
    Fetch trending topics from multiple sources.
    Returns a list of trend dicts with name, category, description.
    Falls back to curated list if APIs fail.
    """
    all_trends = []

    try:
        async with aiohttp.ClientSession() as session:
            reddit_task = fetch_reddit_trending(session)
            coingecko_task = fetch_coingecko_trending(session)
            results = await asyncio.gather(reddit_task, coingecko_task, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_trends.extend(result)
    except Exception as e:
        logger.warning(f"Trending fetch failed, using fallbacks: {e}")

    if not all_trends:
        all_trends = FALLBACK_TRENDS.copy()

    # Deduplicate by name
    seen = set()
    unique = []
    for t in all_trends:
        if t["name"] not in seen:
            seen.add(t["name"])
            unique.append(t)

    # Sort by score if available, otherwise shuffle
    unique.sort(key=lambda x: x.get("score", random.randint(0, 100)), reverse=True)
    return unique[:20]


def pick_trending_name(trends: list[dict]) -> dict:
    """Pick a random trend from the top results, weighted towards higher scores."""
    if not trends:
        return random.choice(FALLBACK_TRENDS)

    # Weight towards the top trends
    top = trends[:min(10, len(trends))]
    return random.choice(top)

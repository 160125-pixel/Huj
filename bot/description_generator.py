"""
Realistic memecoin description generator.

Generates professional-sounding project descriptions, taglines,
and bios for memecoin projects based on current trends.
"""

import random

# Project narrative templates
NARRATIVE_TEMPLATES = [
    "The first community-driven {theme} token on Solana. Built by the people, for the people. "
    "Our mission is to bring the power of {theme} to the decentralized world.",

    "{name} is a next-generation meme token leveraging Solana's high-speed, low-cost "
    "infrastructure. Our community is growing fast — join us before everyone else does.",

    "Born from the internet's favorite meme, {name} brings {theme} culture to DeFi. "
    "Fair launch. No presale. 100% community owned.",

    "{name} isn't just a token — it's a movement. Powered by Solana, fueled by the "
    "community. We're building the most based ecosystem in crypto.",

    "What started as a meme is now a mission. {name} is uniting degens, diamond hands, "
    "and meme lovers under one token. Solana-fast, community-first.",

    "Introducing {name}: the {theme} revolution on Solana. Zero VC funding. Zero insider "
    "allocation. Just pure, unfiltered community energy.",

    "{name} Protocol — where {theme} meets DeFi innovation. Holders get rewarded. "
    "Community gets heard. Devs stay based. This is the way.",

    "They said memecoins are dead. We said hold our beer. {name} is here to prove that "
    "{theme} + Solana = inevitable.",
]

# Theme descriptors based on categories
THEME_MAP = {
    "meme": ["meme", "internet culture", "viral content", "meme economy", "degen culture"],
    "crypto": ["crypto", "DeFi", "blockchain", "decentralized finance", "web3"],
    "political": ["political meme", "political satire", "political culture", "grassroots"],
    "finance": ["financial meme", "trading culture", "market meme", "retail trading"],
    "reddit_trending": ["trending culture", "viral internet", "community meme", "social media"],
    "crypto_trending": ["trending crypto", "emerging DeFi", "hot market", "momentum trading"],
}

# Taglines
TAGLINES = [
    "The people's token.",
    "By degens, for degens.",
    "Community first. Always.",
    "Fast. Fair. Fun.",
    "Solana speed. Meme energy.",
    "Diamond hands only.",
    "Built on vibes and Solana.",
    "The next chapter of meme finance.",
    "Not your average memecoin.",
    "Where memes become value.",
    "Fair launch. Pure community.",
    "Zero insiders. All community.",
]

# Roadmap phases for extra legitimacy
ROADMAP_ITEMS = [
    ["Token launch & fair distribution", "Community building & social growth",
     "DEX listings & liquidity", "Partnerships & ecosystem expansion"],
    ["Stealth launch on Solana", "Community takeover & organic growth",
     "CEX listing applications", "NFT collection & staking"],
    ["Fair launch & initial liquidity", "Marketing push & influencer outreach",
     "Cross-chain bridge development", "DAO governance implementation"],
    ["Token deployment & LP lock", "Community growth to 10K holders",
     "Merch store & brand development", "Tier-1 CEX listings"],
]

# Bio templates for Telegram channels
BIO_TEMPLATES = [
    "{name} ({ticker}) — {tagline}\n\nOfficial community channel.\nContract: {mint}\n\n{description_short}",
    "{ticker} | {tagline}\n\n{description_short}\n\nCA: {mint}\nCommunity-driven. Fair launch.",
    "Welcome to {name} ({ticker})\n{tagline}\n\n{description_short}\n\nCA: {mint}",
    "{name} — {tagline}\n{description_short}\n\nMint: {mint}\nPowered by Solana",
]


def generate_description(name: str, category: str = "meme") -> str:
    """Generate a realistic project description."""
    themes = THEME_MAP.get(category, THEME_MAP["meme"])
    theme = random.choice(themes)
    template = random.choice(NARRATIVE_TEMPLATES)
    return template.format(name=name, theme=theme)


def generate_tagline() -> str:
    """Generate a catchy tagline."""
    return random.choice(TAGLINES)


def generate_roadmap() -> list[str]:
    """Generate a roadmap."""
    return random.choice(ROADMAP_ITEMS)


def generate_channel_bio(name: str, ticker: str, mint_address: str,
                         description: str) -> str:
    """Generate a Telegram channel bio/about text."""
    tagline = generate_tagline()
    # Shorten description for bio (Telegram has a 255 char limit for about)
    description_short = description[:120] + "..." if len(description) > 120 else description
    template = random.choice(BIO_TEMPLATES)
    bio = template.format(
        name=name,
        ticker=ticker,
        tagline=tagline,
        mint=mint_address,
        description_short=description_short,
    )
    # Telegram channel about limit is 255 chars
    return bio[:255]


def generate_full_profile(name: str, ticker: str, category: str = "meme",
                          mint_address: str = "") -> dict:
    """Generate a complete coin profile with description, tagline, bio, roadmap."""
    description = generate_description(name, category)
    tagline = generate_tagline()
    roadmap = generate_roadmap()
    bio = generate_channel_bio(name, ticker, mint_address, description)

    return {
        "description": description,
        "tagline": tagline,
        "roadmap": roadmap,
        "channel_bio": bio,
    }

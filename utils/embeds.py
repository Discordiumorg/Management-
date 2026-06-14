import discord
from datetime import datetime, timezone


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=description, color=0x2ECC71, timestamp=datetime.now(timezone.utc))


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, color=0xE74C3C, timestamp=datetime.now(timezone.utc))


def info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"ℹ️ {title}", description=description, color=0x3498DB, timestamp=datetime.now(timezone.utc))


def warning_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"⚠️ {title}", description=description, color=0xF39C12, timestamp=datetime.now(timezone.utc))


def log_embed(action: str, target: discord.Member, moderator: discord.Member, reason: str, color: int, **extra) -> discord.Embed:
    embed = discord.Embed(title=f"📋 {action}", color=color, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Benutzer", value=f"{target.mention} (`{target.id}`)", inline=True)
    embed.add_field(name="Moderator", value=f"{moderator.mention} (`{moderator.id}`)", inline=True)
    embed.add_field(name="Grund", value=reason, inline=False)
    for k, v in extra.items():
        embed.add_field(name=k, value=str(v), inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    return embed

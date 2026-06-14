import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

import database

load_dotenv()

COGS = [
    "cogs.manage_self",
    "cogs.manage_user",
    "cogs.messages",
    "cogs.permissions",
    "cogs.apply",
    "cogs.monthly_reset",
    "cogs.roster",
    "cogs.duty",
    "cogs.announce",
]


def get_guild_ids() -> list[int]:
    """Read GUILD_IDS (comma-separated) or fall back to GUILD_ID from .env."""
    raw = os.getenv("GUILD_IDS") or os.getenv("GUILD_ID") or ""
    ids = [int(g.strip()) for g in raw.split(",") if g.strip().isdigit()]
    return ids


class StaffBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await database.init_db()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                print(f"[✓] Cog loaded: {cog}")
            except Exception as e:
                print(f"[✗] Failed to load {cog}: {e}")

        guild_ids = get_guild_ids()
        if guild_ids:
            for gid in guild_ids:
                guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"[✓] Slash commands synced to guild {gid}")
        else:
            await self.tree.sync()
            print("[✓] Slash commands synced globally")

    async def on_ready(self):
        print(f"[✓] Logged in as {self.user} (ID: {self.user.id})")
        print(f"[✓] Active in {len(self.guilds)} server(s): {[g.name for g in self.guilds]}")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="Staff Management")
        )

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.CheckFailure):
            return
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: `{error}`",
            color=0xE74C3C,
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            pass


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN not set in .env!")
        return

    bot = StaffBot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())

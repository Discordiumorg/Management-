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
]


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
                print(f"[✓] Cog geladen: {cog}")
            except Exception as e:
                print(f"[✗] Fehler beim Laden von {cog}: {e}")

        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"[✓] Slash Commands zu Guild {guild_id} synchronisiert")
        else:
            await self.tree.sync()
            print("[✓] Slash Commands global synchronisiert")

    async def on_ready(self):
        print(f"[✓] Bot eingeloggt als {self.user} (ID: {self.user.id})")
        print(f"[✓] In {len(self.guilds)} Server(n) aktiv")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="Staff Management")
        )

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.CheckFailure):
            return
        embed = discord.Embed(
            title="❌ Fehler",
            description=f"Ein Fehler ist aufgetreten: `{error}`",
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
        print("FEHLER: DISCORD_TOKEN nicht in .env gesetzt!")
        return

    bot = StaffBot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())

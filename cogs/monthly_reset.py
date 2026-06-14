import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import asyncio

import database


class MonthlyReset(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.monthly_reset_task.start()

    def cog_unload(self):
        self.monthly_reset_task.cancel()

    def _seconds_until_next_month(self) -> float:
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return (next_month - now).total_seconds()

    @tasks.loop(hours=1)
    async def monthly_reset_task(self):
        now = datetime.now(timezone.utc)
        # Only run on the 1st of the month at 00:xx
        if now.day != 1 or now.hour != 0:
            return

        guild_ids = await database.get_all_guild_ids()
        for guild_id in guild_ids:
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue

            deleted = await database.reset_all_infractions(guild_id)
            config = await database.get_config(guild_id)
            log_channel_id = config.get("log_channel_id")

            if log_channel_id:
                channel = guild.get_channel(int(log_channel_id))
                if channel:
                    embed = discord.Embed(
                        title="🔄 Monatlicher Reset",
                        description=(
                            f"Alle Infractions wurden für den neuen Monat zurückgesetzt.\n\n"
                            f"**Gelöschte Infractions:** {deleted}\n"
                            f"**Datum:** <t:{int(now.timestamp())}:F>"
                        ),
                        color=0x5865F2,
                        timestamp=now,
                    )
                    embed.set_footer(text="Automatischer monatlicher Reset")
                    await channel.send(embed=embed)

    @monthly_reset_task.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()
        # Align the loop to start at the top of the next hour
        now = datetime.now(timezone.utc)
        seconds_to_next_hour = 3600 - (now.minute * 60 + now.second)
        await asyncio.sleep(seconds_to_next_hour)


async def setup(bot: commands.Bot):
    await bot.add_cog(MonthlyReset(bot))

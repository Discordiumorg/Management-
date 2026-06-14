import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import asyncio

import database
from utils import cross_server


class MonthlyReset(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.monthly_reset_task.start()
        self.loa_expiry_task.start()

    def cog_unload(self):
        self.monthly_reset_task.cancel()
        self.loa_expiry_task.cancel()

    # ── Monthly infraction reset ──────────────────────────────────────────────

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
                        title="🔄 Monthly Reset",
                        description=(
                            f"All infractions have been reset for the new month.\n\n"
                            f"**Deleted Infractions:** {deleted}\n"
                            f"**Date:** <t:{int(now.timestamp())}:F>"
                        ),
                        color=0x5865F2,
                        timestamp=now,
                    )
                    embed.set_footer(text="Automatic monthly reset")
                    await channel.send(embed=embed)

    @monthly_reset_task.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()
        # Align the loop to start at the top of the next hour
        now = datetime.now(timezone.utc)
        seconds_to_next_hour = 3600 - (now.minute * 60 + now.second)
        await asyncio.sleep(seconds_to_next_hour)

    # ── LOA expiry check every 30 minutes ────────────────────────────────────

    @tasks.loop(minutes=30)
    async def loa_expiry_task(self):
        now = datetime.now(timezone.utc)
        guild_ids = await database.get_all_guild_ids()

        for guild_id in guild_ids:
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue

            config = await database.get_config(guild_id)
            loas = await database.get_all_active_loas(guild_id)

            for loa in loas:
                if not loa.get("end_date"):
                    continue
                end_date = datetime.fromisoformat(loa["end_date"])
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                if now < end_date:
                    continue

                # LOA expired — remove it
                await database.remove_loa(loa["user_id"], guild_id)
                bot_id = str(self.bot.user.id) if self.bot.user else "0"
                await database.log_action(guild_id, loa["user_id"], bot_id, "LOA Ended", "Auto-expired")

                member = guild.get_member(int(loa["user_id"]))
                if member:
                    try:
                        nick = member.display_name
                        if nick.startswith("[LOA] "):
                            clean = nick[6:] or None
                            await member.edit(nick=clean, reason="LOA expired")
                            await cross_server.update_linked_nickname(
                                self.bot, config, member.id, clean, "LOA expired (cross-server sync)"
                            )
                    except discord.Forbidden:
                        pass

                    try:
                        embed = discord.Embed(
                            title="🏖️ LOA Expired",
                            description=(
                                f"Your Leave of Absence at **{guild.name}** has expired and has been automatically removed.\n\n"
                                "Welcome back! 👋"
                            ),
                            color=0x2ECC71,
                            timestamp=now,
                        )
                        await member.send(embed=embed)
                    except discord.Forbidden:
                        pass

                log_channel_id = config.get("log_channel_id")
                if log_channel_id:
                    channel = guild.get_channel(int(log_channel_id))
                    if channel:
                        member_text = member.mention if member else f"`{loa['user_id']}`"
                        embed = discord.Embed(
                            title="⏰ LOA Auto-Expired",
                            description=f"{member_text}'s LOA has expired and been automatically removed.",
                            color=0x2ECC71,
                            timestamp=now,
                        )
                        embed.set_footer(text="Automatic LOA expiry check")
                        await channel.send(embed=embed)

    @loa_expiry_task.before_loop
    async def before_loa_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(MonthlyReset(bot))

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

import database
from utils.embeds import info_embed, error_embed
from utils.checks import require_staff


class Messages(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        await database.increment_message_count(str(message.author.id), str(message.guild.id))

    messages_group = app_commands.Group(name="messages", description="Message statistics")

    @messages_group.command(name="leaderboard", description="Top 10 staff members by messages")
    @require_staff()
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        entries = await database.get_leaderboard(str(interaction.guild_id))
        if not entries:
            await interaction.followup.send(embed=info_embed("Leaderboard", "No messages recorded yet."), ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Messages Leaderboard",
            color=0xF1C40F,
            timestamp=datetime.now(timezone.utc),
        )
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, entry in enumerate(entries):
            member = interaction.guild.get_member(int(entry["user_id"]))
            name = member.display_name if member else f"ID: {entry['user_id']}"
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{medal} **{name}** — {entry['count']:,} messages")

        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @messages_group.command(name="self", description="Show your own message count")
    @require_staff()
    async def messages_self(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        count = await database.get_message_count(str(interaction.user.id), str(interaction.guild_id))
        embed = discord.Embed(
            title="💬 Your Messages",
            description=f"You have sent **{count:,}** messages in this server.",
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @messages_group.command(name="user", description="Show the message count of a user")
    @app_commands.describe(user="The user")
    @require_staff()
    async def messages_user(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        count = await database.get_message_count(str(user.id), str(interaction.guild_id))
        embed = discord.Embed(
            title=f"💬 Messages by {user.display_name}",
            description=f"{user.mention} has sent **{count:,}** messages in this server.",
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Messages(bot))

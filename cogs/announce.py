import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

import database
from utils.embeds import success_embed, error_embed
from utils.checks import require_leader


TEMPLATES = {
    "general": {"color": 0x5865F2, "emoji": "📢"},
    "important": {"color": 0xE74C3C, "emoji": "🚨"},
    "update": {"color": 0x2ECC71, "emoji": "📋"},
    "event": {"color": 0xF39C12, "emoji": "🎉"},
    "reminder": {"color": 0x3498DB, "emoji": "🔔"},
    "meeting": {"color": 0x9B59B6, "emoji": "📅"},
}


class AnnounceModal(discord.ui.Modal, title="Create Announcement"):
    ann_title = discord.ui.TextInput(
        label="Title",
        placeholder="Announcement title",
        required=True,
        max_length=100,
    )
    content = discord.ui.TextInput(
        label="Message",
        placeholder="Write your announcement here...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000,
    )
    ping = discord.ui.TextInput(
        label="Ping (optional)",
        placeholder="e.g. @Staff, @everyone, @here — or leave empty",
        required=False,
        max_length=100,
    )

    def __init__(self, template: str, channel: discord.TextChannel):
        super().__init__()
        self.template = template
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tmpl = TEMPLATES.get(self.template, TEMPLATES["general"])

        embed = discord.Embed(
            title=f"{tmpl['emoji']} {self.ann_title.value}",
            description=self.content.value,
            color=tmpl["color"],
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(
            text=f"Announced by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        ping_text = self.ping.value.strip() if self.ping.value else ""
        await self.channel.send(content=ping_text or None, embed=embed)

        await interaction.followup.send(
            embed=success_embed("Announcement sent", f"Your announcement was posted in {self.channel.mention}."),
            ephemeral=True,
        )


class TemplateSelectView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=120)
        self.channel = channel
        options = [
            discord.SelectOption(label="General", value="general", emoji="📢", description="Standard announcement"),
            discord.SelectOption(label="Important", value="important", emoji="🚨", description="Urgent/critical notice"),
            discord.SelectOption(label="Update", value="update", emoji="📋", description="System or rule update"),
            discord.SelectOption(label="Event", value="event", emoji="🎉", description="Event announcement"),
            discord.SelectOption(label="Reminder", value="reminder", emoji="🔔", description="Reminder for staff"),
            discord.SelectOption(label="Meeting", value="meeting", emoji="📅", description="Meeting notice"),
        ]
        select = discord.ui.Select(placeholder="Choose announcement type...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        template = interaction.data["values"][0]
        await interaction.response.send_modal(AnnounceModal(template, self.channel))


class Announce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="announce", description="Send a staff announcement (Leaders & Admins only)")
    @app_commands.describe(channel="Channel to send the announcement to (defaults to configured announce channel)")
    @require_leader()
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        config = await database.get_config(str(interaction.guild_id))

        target_channel = channel
        if not target_channel:
            announce_channel_id = config.get("announce_channel_id")
            if announce_channel_id:
                target_channel = interaction.guild.get_channel(int(announce_channel_id))

        if not target_channel:
            await interaction.response.send_message(
                embed=error_embed(
                    "No channel set",
                    "Please specify a channel or set one with `/permissions set-announce-channel #channel`."
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📢 Create Announcement",
            description=f"Select the type of announcement for {target_channel.mention}:",
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, view=TemplateSelectView(target_channel), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Announce(bot))

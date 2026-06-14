import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone, timedelta

import database
from utils.embeds import success_embed, error_embed, info_embed, log_embed
from utils.checks import require_staff
from utils import cross_server


def parse_duration(duration_str: str) -> timedelta | None:
    """Parse duration string like 2d, 3h, 1w, 30m into timedelta."""
    try:
        unit = duration_str[-1].lower()
        value = int(duration_str[:-1])
        if unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
        elif unit == 'w':
            return timedelta(weeks=value)
    except (ValueError, IndexError):
        pass
    return None


class ResignModal(discord.ui.Modal, title="Resign"):
    reason = discord.ui.TextInput(
        label="Reason for resignation",
        placeholder="Why do you want to resign?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        guild = interaction.guild
        config = self.config

        staff_roles = json.loads(config.get("staff_roles_json", "[]"))
        leader_roles = json.loads(config.get("leader_roles_json", "[]"))
        admin_roles = json.loads(config.get("admin_roles_json", "[]"))
        all_staff_role_ids = set(staff_roles + leader_roles + admin_roles)

        roles_to_remove = [r for r in member.roles if str(r.id) in all_staff_role_ids]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=f"Resignation: {self.reason.value}")
            except discord.Forbidden:
                await interaction.followup.send(embed=error_embed("Error", "I do not have permission to remove roles."), ephemeral=True)
                return

        try:
            dm_embed = discord.Embed(
                title="📋 Resignation confirmed",
                description=f"Your resignation from **{guild.name}** has been processed.\n\n**Reason:** {self.reason.value}",
                color=0xE74C3C,
                timestamp=datetime.now(timezone.utc),
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await database.log_action(str(guild.id), str(member.id), str(member.id), "Resignation", self.reason.value)

        # Also remove roles on linked server (Work Server)
        linked_guild_name = await cross_server.remove_linked_staff_roles(
            interaction.client, config, member.id, f"Resignation: {self.reason.value}"
        )

        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = log_embed("Resignation (Resign)", member, member, self.reason.value, 0xE74C3C)
                if linked_guild_name:
                    embed.add_field(name="Cross-Server", value=f"Roles removed in **{linked_guild_name}**", inline=False)
                await channel.send(embed=embed)

        extra = f"\nRoles also removed from **{linked_guild_name}**." if linked_guild_name else ""
        await interaction.followup.send(
            embed=success_embed("Resignation submitted", f"Your resignation has been successfully processed. All staff roles have been removed.{extra}"),
            ephemeral=True,
        )


class LOARequestModal(discord.ui.Modal, title="Request Leave of Absence"):
    duration = discord.ui.TextInput(
        label="How long? (e.g. 2d, 3h, 1w)",
        placeholder="e.g. 2d (m/h/d/w)",
        required=True,
        max_length=10,
    )
    reason = discord.ui.TextInput(
        label="Reason for leave",
        placeholder="Visible to leaders only",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        guild = interaction.guild
        config = self.config

        delta = parse_duration(self.duration.value)
        if delta is None:
            await interaction.followup.send(
                embed=error_embed("Invalid format", "Please specify the duration in the format `2d`, `3h`, `1w`, `30m`."),
                ephemeral=True,
            )
            return

        end_date = (datetime.now(timezone.utc) + delta).isoformat()
        await database.set_loa(str(member.id), str(guild.id), self.duration.value, self.reason.value, end_date)
        await database.log_action(str(guild.id), str(member.id), str(member.id), "LOA Started", f"Duration: {self.duration.value}")

        try:
            current_nick = member.display_name
            if not current_nick.startswith("[LOA] "):
                new_nick = f"[LOA] {current_nick}"[:32]
                await member.edit(nick=new_nick, reason="LOA started")
                # Mirror nickname on linked server
                await cross_server.update_linked_nickname(
                    interaction.client, config, member.id, new_nick, "LOA started (cross-server sync)"
                )
        except discord.Forbidden:
            pass

        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = log_embed("LOA started", member, member, self.reason.value, 0xF39C12, Duration=self.duration.value)
                await channel.send(embed=embed)

        try:
            dm_embed = discord.Embed(
                title="🏖️ LOA confirmed",
                description=f"Your LOA at **{guild.name}** has been recorded.\n\n**Duration:** {self.duration.value}\n**Ends:** <t:{int((datetime.now(timezone.utc) + delta).timestamp())}:F>",
                color=0xF39C12,
                timestamp=datetime.now(timezone.utc),
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await interaction.followup.send(
            embed=success_embed("LOA recorded", f"Your LOA has been recorded for **{self.duration.value}**. Your nickname has been updated."),
            ephemeral=True,
        )


class LOAView(discord.ui.View):
    def __init__(self, config: dict, is_in_loa: bool):
        super().__init__(timeout=300)
        self.config = config
        self.is_in_loa = is_in_loa

    @discord.ui.button(label="Request LOA", style=discord.ButtonStyle.primary, emoji="🏖️")
    async def request_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LOARequestModal(self.config))

    @discord.ui.button(label="Remove LOA", style=discord.ButtonStyle.danger, emoji="🔴")
    async def remove_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        guild = interaction.guild

        loa = await database.get_active_loa(str(member.id), str(guild.id))
        if not loa:
            await interaction.followup.send(embed=error_embed("No LOA", "You do not currently have an active LOA."), ephemeral=True)
            return

        await database.remove_loa(str(member.id), str(guild.id))
        await database.log_action(str(guild.id), str(member.id), str(member.id), "LOA Ended")

        try:
            current_nick = member.display_name
            if current_nick.startswith("[LOA] "):
                clean_nick = current_nick[6:] or None
                await member.edit(nick=clean_nick, reason="LOA ended")
                await cross_server.update_linked_nickname(
                    interaction.client, config, member.id, clean_nick, "LOA ended (cross-server sync)"
                )
        except discord.Forbidden:
            pass

        config = self.config
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = log_embed("LOA ended", member, member, "Ended by self", 0x2ECC71)
                await channel.send(embed=embed)

        await interaction.followup.send(embed=success_embed("LOA ended", "Your LOA has been removed and your nickname updated."), ephemeral=True)


class ManageSelfView(discord.ui.View):
    def __init__(self, config: dict):
        super().__init__(timeout=300)
        self.config = config

    @discord.ui.button(label="Resign", style=discord.ButtonStyle.danger, emoji="🚪")
    async def resign(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ResignModal(self.config))

    @discord.ui.button(label="LeaveOfAbsence (LOA)", style=discord.ButtonStyle.primary, emoji="🏖️")
    async def loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        loa = await database.get_active_loa(str(interaction.user.id), str(interaction.guild_id))
        is_in_loa = loa is not None
        status_text = "You are currently **on LOA**." if is_in_loa else "You are currently **not on LOA**."
        embed = info_embed("Leave of Absence", status_text)
        view = LOAView(self.config, is_in_loa)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Infractions", style=discord.ButtonStyle.secondary, emoji="📋")
    async def infractions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        infractions = await database.get_infractions(str(interaction.user.id), str(interaction.guild_id))

        if not infractions:
            await interaction.followup.send(embed=success_embed("Infractions", "You have no active infractions."), ephemeral=True)
            return

        embed = discord.Embed(title="📋 Your Infractions", color=0xE67E22, timestamp=datetime.now(timezone.utc))
        for inf in infractions[:10]:
            moderator = interaction.guild.get_member(int(inf["moderator_id"]))
            mod_text = moderator.mention if moderator else f"ID: {inf['moderator_id']}"
            expires = f"\n*Expires: <t:{int(datetime.fromisoformat(inf['expires_at']).timestamp())}:R>*" if inf.get("expires_at") else ""
            embed.add_field(
                name=f"{inf['type']} - {inf['timestamp'][:10]}",
                value=f"**Reason:** {inf['reason']}\n**By:** {mod_text}{expires}",
                inline=False,
            )
        embed.set_footer(text=f"{len(infractions)} infractions total")
        await interaction.followup.send(embed=embed, ephemeral=True)


class ManageSelf(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="manage-self", description="Manage your own staff status")
    @require_staff()
    async def manage_self(self, interaction: discord.Interaction):
        config = await database.get_config(str(interaction.guild_id))
        embed = discord.Embed(
            title="👤 Staff Self-Management",
            description="Choose an action for your account:",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, view=ManageSelfView(config), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ManageSelf(bot))

import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone, timedelta

import database
from utils.embeds import success_embed, error_embed, info_embed, log_embed
from utils.checks import require_leader, is_leader_or_admin
from utils import cross_server


INFRACTION_TYPES = {
    "verbal_warning": ("Verbal Warning", "⚠️", 30),
    "warning": ("Warning", "🟡", None),
    "strike": ("Strike", "🔴", None),
}


async def send_to_channel(guild: discord.Guild, channel_id: str | None, embed: discord.Embed):
    if channel_id:
        channel = guild.get_channel(int(channel_id))
        if channel:
            await channel.send(embed=embed)


async def send_dm(member: discord.Member, embed: discord.Embed):
    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        pass


class PromoteModal(discord.ui.Modal, title="Promote staff member"):
    reason = discord.ui.TextInput(
        label="Reason for promotion",
        placeholder="Why is this staff member being promoted?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, target: discord.Member, config: dict):
        super().__init__()
        self.modal_title = f"Promote: {target.display_name}"
        self.target = target
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target = self.target
        guild = interaction.guild
        config = self.config

        staff_roles = json.loads(config.get("staff_roles_json", "[]"))
        member_role_ids = [str(r.id) for r in target.roles]

        current_idx = -1
        for i, role_id in enumerate(staff_roles):
            if role_id in member_role_ids:
                current_idx = i

        if current_idx == -1:
            await interaction.followup.send(embed=error_embed("Error", "The user does not have a known staff role."), ephemeral=True)
            return
        if current_idx >= len(staff_roles) - 1:
            await interaction.followup.send(embed=error_embed("Error", "The user is already at the highest level."), ephemeral=True)
            return

        old_role = guild.get_role(int(staff_roles[current_idx]))
        new_role = guild.get_role(int(staff_roles[current_idx + 1]))

        if not old_role or not new_role:
            await interaction.followup.send(embed=error_embed("Error", "Role not found. Please reconfigure the staff roles."), ephemeral=True)
            return

        try:
            await target.remove_roles(old_role, reason=f"Promotion by {interaction.user}")
            await target.add_roles(new_role, reason=f"Promotion by {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(embed=error_embed("Error", "No permission to change roles."), ephemeral=True)
            return

        log_embed_obj = log_embed(
            "Promotion", target, interaction.user, self.reason.value, 0x2ECC71,
            **{"Old Role": old_role.mention, "New Role": new_role.mention}
        )
        await send_to_channel(guild, config.get("promotion_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        dm_embed = discord.Embed(
            title="🎉 You have been promoted!",
            description=f"You have been promoted at **{guild.name}**!\n\n**New Role:** {new_role.name}\n**Reason:** {self.reason.value}",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        await interaction.followup.send(
            embed=success_embed("Promoted", f"{target.mention} has been promoted to **{new_role.name}**."),
            ephemeral=True,
        )


class DemoteModal(discord.ui.Modal, title="Demote staff member"):
    reason = discord.ui.TextInput(
        label="Reason for demotion",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, target: discord.Member, config: dict):
        super().__init__()
        self.target = target
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target = self.target
        guild = interaction.guild
        config = self.config

        staff_roles = json.loads(config.get("staff_roles_json", "[]"))
        member_role_ids = [str(r.id) for r in target.roles]

        current_idx = -1
        for i, role_id in enumerate(staff_roles):
            if role_id in member_role_ids:
                current_idx = i

        if current_idx <= 0:
            await interaction.followup.send(embed=error_embed("Error", "The user cannot be demoted further."), ephemeral=True)
            return

        old_role = guild.get_role(int(staff_roles[current_idx]))
        new_role = guild.get_role(int(staff_roles[current_idx - 1]))

        if not old_role or not new_role:
            await interaction.followup.send(embed=error_embed("Error", "Role not found."), ephemeral=True)
            return

        try:
            await target.remove_roles(old_role, reason=f"Demotion by {interaction.user}")
            await target.add_roles(new_role, reason=f"Demotion by {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(embed=error_embed("Error", "No permission to change roles."), ephemeral=True)
            return

        log_embed_obj = log_embed(
            "Demotion", target, interaction.user, self.reason.value, 0xF39C12,
            **{"Old Role": old_role.mention, "New Role": new_role.mention}
        )
        await send_to_channel(guild, config.get("demotion_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        dm_embed = discord.Embed(
            title="📉 You have been demoted",
            description=f"You have been demoted at **{guild.name}**.\n\n**New Role:** {new_role.name}\n**Reason:** {self.reason.value}",
            color=0xF39C12,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        await interaction.followup.send(
            embed=success_embed("Demoted", f"{target.mention} has been demoted to **{new_role.name}**."),
            ephemeral=True,
        )


class TerminateModal(discord.ui.Modal, title="Terminate staff member"):
    reason = discord.ui.TextInput(
        label="Reason for termination",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, target: discord.Member, config: dict):
        super().__init__()
        self.target = target
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target = self.target
        guild = interaction.guild
        config = self.config

        staff_roles = json.loads(config.get("staff_roles_json", "[]"))
        leader_roles = json.loads(config.get("leader_roles_json", "[]"))
        admin_roles = json.loads(config.get("admin_roles_json", "[]"))
        all_staff_role_ids = set(staff_roles + leader_roles + admin_roles)
        roles_to_remove = [r for r in target.roles if str(r.id) in all_staff_role_ids]

        try:
            if roles_to_remove:
                await target.remove_roles(*roles_to_remove, reason=f"Termination by {interaction.user}")
        except discord.Forbidden:
            pass

        # Cross-server: remove roles and kick from linked server too
        linked_guild_name = await cross_server.remove_linked_staff_roles(
            interaction.client, config, target.id, f"Terminated: {self.reason.value}"
        )
        linked_kicked = await cross_server.kick_from_linked(
            interaction.client, config, target.id, f"Terminated: {self.reason.value}"
        )

        linked_guild = None
        linked_guild_id = config.get("linked_guild_id")
        if linked_guild_id:
            linked_guild = interaction.client.get_guild(int(linked_guild_id))

        dm_embed = discord.Embed(
            title="🚫 You have been terminated",
            description=f"You have been terminated from **{guild.name}**.\n\n**Reason:** {self.reason.value}" +
                        (f"\n\nYou have also been removed from **{linked_guild.name if linked_guild else 'the linked server'}**." if linked_kicked else ""),
            color=0xE74C3C,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        log_embed_obj = log_embed("Termination (Terminate)", target, interaction.user, self.reason.value, 0xE74C3C)
        if linked_guild_name:
            log_embed_obj.add_field(name="Cross-Server", value=f"Roles removed & kicked from **{linked_guild_name}**", inline=False)
        await send_to_channel(guild, config.get("termination_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        try:
            await target.kick(reason=f"Terminated: {self.reason.value}")
        except discord.Forbidden:
            pass

        cross_note = f" Also removed from **{linked_guild_name}**." if linked_guild_name else ""
        await interaction.followup.send(
            embed=success_embed("Terminated", f"{target.mention} has been terminated and kicked from the server.{cross_note}"),
            ephemeral=True,
        )


class InfractModal(discord.ui.Modal):
    reason = discord.ui.TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, target: discord.Member, infraction_type: str, config: dict):
        self.infraction_type = infraction_type
        label, emoji, days = INFRACTION_TYPES[infraction_type]
        super().__init__(title=f"{emoji} Issue {label}")
        self.target = target
        self.config = config
        self.label_name = label
        self.days = days

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target = self.target
        guild = interaction.guild
        config = self.config

        expires_at = None
        if self.days:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=self.days)).isoformat()

        await database.add_infraction(
            str(target.id), str(guild.id), self.label_name,
            self.reason.value, str(interaction.user.id), expires_at
        )

        log_embed_obj = log_embed(
            f"Infraction: {self.label_name}", target, interaction.user, self.reason.value, 0xE67E22,
            **{"Type": self.label_name, "Expires": f"<t:{int(datetime.fromisoformat(expires_at).timestamp())}:R>" if expires_at else "Permanent"}
        )
        await send_to_channel(guild, config.get("infractions_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        dm_embed = discord.Embed(
            title=f"⚠️ You have received a {self.label_name}",
            description=f"You have received an infraction at **{guild.name}**.\n\n**Type:** {self.label_name}\n**Reason:** {self.reason.value}" +
                        (f"\n**Expires:** <t:{int(datetime.fromisoformat(expires_at).timestamp())}:R>" if expires_at else "\n**Valid:** Permanent"),
            color=0xE67E22,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        await interaction.followup.send(
            embed=success_embed("Infraction issued", f"{target.mention} has received a **{self.label_name}**."),
            ephemeral=True,
        )


class InfractView(discord.ui.View):
    def __init__(self, target: discord.Member, config: dict):
        super().__init__(timeout=300)
        self.target = target
        self.config = config

    @discord.ui.button(label="Verbal Warning", style=discord.ButtonStyle.secondary, emoji="⚠️")
    async def verbal_warning(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InfractModal(self.target, "verbal_warning", self.config))

    @discord.ui.button(label="Warning", style=discord.ButtonStyle.primary, emoji="🟡")
    async def warning(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InfractModal(self.target, "warning", self.config))

    @discord.ui.button(label="Strike", style=discord.ButtonStyle.danger, emoji="🔴")
    async def strike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InfractModal(self.target, "strike", self.config))


class NoteModal(discord.ui.Modal, title="Add note"):
    content = discord.ui.TextInput(
        label="Note",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await database.add_note(str(self.target.id), str(interaction.guild_id), self.content.value, str(interaction.user.id))
        await interaction.followup.send(embed=success_embed("Note saved", f"Note for {self.target.mention} has been saved."), ephemeral=True)


class NotesView(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=300)
        self.target = target

    @discord.ui.button(label="Add note", style=discord.ButtonStyle.primary, emoji="✏️")
    async def add_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoteModal(self.target))

    @discord.ui.button(label="View notes", style=discord.ButtonStyle.secondary, emoji="📋")
    async def view_notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        notes = await database.get_notes(str(self.target.id), str(interaction.guild_id))
        if not notes:
            await interaction.followup.send(embed=info_embed("Notes", f"No notes for {self.target.mention}."), ephemeral=True)
            return
        embed = discord.Embed(title=f"📋 Notes for {self.target.display_name}", color=0x3498DB, timestamp=datetime.now(timezone.utc))
        for note in notes[:10]:
            mod = interaction.guild.get_member(int(note["moderator_id"]))
            mod_text = mod.mention if mod else f"ID: {note['moderator_id']}"
            embed.add_field(name=f"{note['timestamp'][:10]} by {mod_text}", value=note["content"], inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


class ManageUserView(discord.ui.View):
    def __init__(self, target: discord.Member, config: dict):
        super().__init__(timeout=300)
        self.target = target
        self.config = config

    @discord.ui.button(label="Promote", style=discord.ButtonStyle.success, emoji="⬆️")
    async def promote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("No access", "You do not have permission."), ephemeral=True)
            return
        await interaction.response.send_modal(PromoteModal(self.target, self.config))

    @discord.ui.button(label="Demote", style=discord.ButtonStyle.primary, emoji="⬇️")
    async def demote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("No access", "You do not have permission."), ephemeral=True)
            return
        await interaction.response.send_modal(DemoteModal(self.target, self.config))

    @discord.ui.button(label="Terminate", style=discord.ButtonStyle.danger, emoji="🚫")
    async def terminate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("No access", "You do not have permission."), ephemeral=True)
            return
        await interaction.response.send_modal(TerminateModal(self.target, self.config))

    @discord.ui.button(label="Infract", style=discord.ButtonStyle.secondary, emoji="⚠️")
    async def infract(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("No access", "You do not have permission."), ephemeral=True)
            return
        embed = info_embed("Issue infraction", f"Choose the type of infraction for {self.target.mention}:")
        await interaction.response.send_message(embed=embed, view=InfractView(self.target, self.config), ephemeral=True)

    @discord.ui.button(label="Notes", style=discord.ButtonStyle.secondary, emoji="📝")
    async def notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("No access", "You do not have permission."), ephemeral=True)
            return
        embed = info_embed("Notes", f"Manage notes for {self.target.mention}:")
        await interaction.response.send_message(embed=embed, view=NotesView(self.target), ephemeral=True)

    @discord.ui.button(label="View Infractions", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def view_infractions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("No access", "You do not have permission."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        infractions = await database.get_infractions(str(self.target.id), str(interaction.guild_id))
        if not infractions:
            await interaction.followup.send(embed=success_embed("Infractions", f"{self.target.mention} has no active infractions."), ephemeral=True)
            return
        embed = discord.Embed(title=f"📋 Infractions of {self.target.display_name}", color=0xE67E22, timestamp=datetime.now(timezone.utc))
        for inf in infractions[:10]:
            mod = interaction.guild.get_member(int(inf["moderator_id"]))
            mod_text = mod.mention if mod else f"ID: {inf['moderator_id']}"
            expires = f"\n*Expires: <t:{int(datetime.fromisoformat(inf['expires_at']).timestamp())}:R>*" if inf.get("expires_at") else ""
            embed.add_field(
                name=f"{inf['type']} – {inf['timestamp'][:10]}",
                value=f"**Reason:** {inf['reason']}\n**By:** {mod_text}{expires}",
                inline=False,
            )
        embed.set_footer(text=f"{len(infractions)} infractions total")
        await interaction.followup.send(embed=embed, ephemeral=True)


class ManageUser(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="manage-user", description="Manage a staff member (leaders/admins only)")
    @app_commands.describe(user="The staff member you want to manage")
    @require_leader()
    async def manage_user(self, interaction: discord.Interaction, user: discord.Member):
        if user.bot:
            await interaction.response.send_message(embed=error_embed("Error", "You cannot manage a bot."), ephemeral=True)
            return

        config = await database.get_config(str(interaction.guild_id))
        embed = discord.Embed(
            title=f"👥 Manage Staff Member",
            description=f"Choose an action for {user.mention}:",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, view=ManageUserView(user, config), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ManageUser(bot))

import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone, timedelta

import database
from utils.embeds import success_embed, error_embed, info_embed, log_embed
from utils.checks import require_leader, is_leader_or_admin


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


class PromoteModal(discord.ui.Modal, title="Mitarbeiter befördern"):
    reason = discord.ui.TextInput(
        label="Grund für die Beförderung",
        placeholder="Warum wird dieser Mitarbeiter befördert?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, target: discord.Member, config: dict):
        super().__init__()
        self.modal_title = f"Befördern: {target.display_name}"
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
            await interaction.followup.send(embed=error_embed("Fehler", "Der Nutzer hat keine bekannte Staff-Rolle."), ephemeral=True)
            return
        if current_idx >= len(staff_roles) - 1:
            await interaction.followup.send(embed=error_embed("Fehler", "Der Nutzer ist bereits auf der höchsten Stufe."), ephemeral=True)
            return

        old_role = guild.get_role(int(staff_roles[current_idx]))
        new_role = guild.get_role(int(staff_roles[current_idx + 1]))

        if not old_role or not new_role:
            await interaction.followup.send(embed=error_embed("Fehler", "Rolle nicht gefunden. Bitte konfiguriere die Staff-Rollen neu."), ephemeral=True)
            return

        try:
            await target.remove_roles(old_role, reason=f"Beförderung durch {interaction.user}")
            await target.add_roles(new_role, reason=f"Beförderung durch {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(embed=error_embed("Fehler", "Keine Berechtigung zum Ändern von Rollen."), ephemeral=True)
            return

        log_embed_obj = log_embed(
            "Beförderung", target, interaction.user, self.reason.value, 0x2ECC71,
            **{"Alte Rolle": old_role.mention, "Neue Rolle": new_role.mention}
        )
        await send_to_channel(guild, config.get("promotion_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        dm_embed = discord.Embed(
            title="🎉 Du wurdest befördert!",
            description=f"Du wurdest bei **{guild.name}** befördert!\n\n**Neue Rolle:** {new_role.name}\n**Grund:** {self.reason.value}",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        await interaction.followup.send(
            embed=success_embed("Befördert", f"{target.mention} wurde zu **{new_role.name}** befördert."),
            ephemeral=True,
        )


class DemoteModal(discord.ui.Modal, title="Mitarbeiter degradieren"):
    reason = discord.ui.TextInput(
        label="Grund für die Degradierung",
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
            await interaction.followup.send(embed=error_embed("Fehler", "Der Nutzer kann nicht weiter degradiert werden."), ephemeral=True)
            return

        old_role = guild.get_role(int(staff_roles[current_idx]))
        new_role = guild.get_role(int(staff_roles[current_idx - 1]))

        if not old_role or not new_role:
            await interaction.followup.send(embed=error_embed("Fehler", "Rolle nicht gefunden."), ephemeral=True)
            return

        try:
            await target.remove_roles(old_role, reason=f"Degradierung durch {interaction.user}")
            await target.add_roles(new_role, reason=f"Degradierung durch {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(embed=error_embed("Fehler", "Keine Berechtigung zum Ändern von Rollen."), ephemeral=True)
            return

        log_embed_obj = log_embed(
            "Degradierung", target, interaction.user, self.reason.value, 0xF39C12,
            **{"Alte Rolle": old_role.mention, "Neue Rolle": new_role.mention}
        )
        await send_to_channel(guild, config.get("demotion_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        dm_embed = discord.Embed(
            title="📉 Du wurdest degradiert",
            description=f"Du wurdest bei **{guild.name}** degradiert.\n\n**Neue Rolle:** {new_role.name}\n**Grund:** {self.reason.value}",
            color=0xF39C12,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        await interaction.followup.send(
            embed=success_embed("Degradiert", f"{target.mention} wurde zu **{new_role.name}** degradiert."),
            ephemeral=True,
        )


class TerminateModal(discord.ui.Modal, title="Mitarbeiter entlassen"):
    reason = discord.ui.TextInput(
        label="Grund für die Entlassung",
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
                await target.remove_roles(*roles_to_remove, reason=f"Entlassung durch {interaction.user}")
        except discord.Forbidden:
            pass

        dm_embed = discord.Embed(
            title="🚫 Du wurdest entlassen",
            description=f"Du wurdest bei **{guild.name}** entlassen.\n\n**Grund:** {self.reason.value}",
            color=0xE74C3C,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        log_embed_obj = log_embed("Entlassung (Terminate)", target, interaction.user, self.reason.value, 0xE74C3C)
        await send_to_channel(guild, config.get("termination_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        try:
            await target.kick(reason=f"Entlassen: {self.reason.value}")
        except discord.Forbidden:
            pass

        await interaction.followup.send(
            embed=success_embed("Entlassen", f"{target.mention} wurde entlassen und aus dem Server gekickt."),
            ephemeral=True,
        )


class InfractModal(discord.ui.Modal):
    reason = discord.ui.TextInput(
        label="Grund",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(self, target: discord.Member, infraction_type: str, config: dict):
        self.infraction_type = infraction_type
        label, emoji, days = INFRACTION_TYPES[infraction_type]
        super().__init__(title=f"{emoji} {label} vergeben")
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
            **{"Typ": self.label_name, "Läuft ab": f"<t:{int(datetime.fromisoformat(expires_at).timestamp())}:R>" if expires_at else "Permanent"}
        )
        await send_to_channel(guild, config.get("infractions_channel_id"), log_embed_obj)
        await send_to_channel(guild, config.get("log_channel_id"), log_embed_obj)

        dm_embed = discord.Embed(
            title=f"⚠️ Du hast eine {self.label_name} erhalten",
            description=f"Du hast bei **{guild.name}** eine Infraction erhalten.\n\n**Typ:** {self.label_name}\n**Grund:** {self.reason.value}" +
                        (f"\n**Läuft ab:** <t:{int(datetime.fromisoformat(expires_at).timestamp())}:R>" if expires_at else "\n**Gültig:** Permanent"),
            color=0xE67E22,
            timestamp=datetime.now(timezone.utc),
        )
        await send_dm(target, dm_embed)

        await interaction.followup.send(
            embed=success_embed("Infraction vergeben", f"{target.mention} hat eine **{self.label_name}** erhalten."),
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


class NoteModal(discord.ui.Modal, title="Notiz hinzufügen"):
    content = discord.ui.TextInput(
        label="Notiz",
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
        await interaction.followup.send(embed=success_embed("Notiz gespeichert", f"Notiz für {self.target.mention} wurde gespeichert."), ephemeral=True)


class NotesView(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=300)
        self.target = target

    @discord.ui.button(label="Notiz hinzufügen", style=discord.ButtonStyle.primary, emoji="✏️")
    async def add_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoteModal(self.target))

    @discord.ui.button(label="Notizen anzeigen", style=discord.ButtonStyle.secondary, emoji="📋")
    async def view_notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        notes = await database.get_notes(str(self.target.id), str(interaction.guild_id))
        if not notes:
            await interaction.followup.send(embed=info_embed("Notizen", f"Keine Notizen für {self.target.mention} vorhanden."), ephemeral=True)
            return
        embed = discord.Embed(title=f"📋 Notizen für {self.target.display_name}", color=0x3498DB, timestamp=datetime.now(timezone.utc))
        for note in notes[:10]:
            mod = interaction.guild.get_member(int(note["moderator_id"]))
            mod_text = mod.mention if mod else f"ID: {note['moderator_id']}"
            embed.add_field(name=f"{note['timestamp'][:10]} von {mod_text}", value=note["content"], inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


class ManageUserView(discord.ui.View):
    def __init__(self, target: discord.Member, config: dict):
        super().__init__(timeout=300)
        self.target = target
        self.config = config

    @discord.ui.button(label="Promote", style=discord.ButtonStyle.success, emoji="⬆️")
    async def promote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        await interaction.response.send_modal(PromoteModal(self.target, self.config))

    @discord.ui.button(label="Demote", style=discord.ButtonStyle.primary, emoji="⬇️")
    async def demote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        await interaction.response.send_modal(DemoteModal(self.target, self.config))

    @discord.ui.button(label="Terminate", style=discord.ButtonStyle.danger, emoji="🚫")
    async def terminate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        await interaction.response.send_modal(TerminateModal(self.target, self.config))

    @discord.ui.button(label="Infract", style=discord.ButtonStyle.secondary, emoji="⚠️")
    async def infract(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        embed = info_embed("Infraction vergeben", f"Wähle den Typ der Infraction für {self.target.mention}:")
        await interaction.response.send_message(embed=embed, view=InfractView(self.target, self.config), ephemeral=True)

    @discord.ui.button(label="Notes", style=discord.ButtonStyle.secondary, emoji="📝")
    async def notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        embed = info_embed("Notizen", f"Notizen für {self.target.mention} verwalten:")
        await interaction.response.send_message(embed=embed, view=NotesView(self.target), ephemeral=True)

    @discord.ui.button(label="Infractions anzeigen", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def view_infractions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        infractions = await database.get_infractions(str(self.target.id), str(interaction.guild_id))
        if not infractions:
            await interaction.followup.send(embed=success_embed("Infractions", f"{self.target.mention} hat keine aktiven Infractions."), ephemeral=True)
            return
        embed = discord.Embed(title=f"📋 Infractions von {self.target.display_name}", color=0xE67E22, timestamp=datetime.now(timezone.utc))
        for inf in infractions[:10]:
            mod = interaction.guild.get_member(int(inf["moderator_id"]))
            mod_text = mod.mention if mod else f"ID: {inf['moderator_id']}"
            expires = f"\n*Läuft ab: <t:{int(datetime.fromisoformat(inf['expires_at']).timestamp())}:R>*" if inf.get("expires_at") else ""
            embed.add_field(
                name=f"{inf['type']} – {inf['timestamp'][:10]}",
                value=f"**Grund:** {inf['reason']}\n**Von:** {mod_text}{expires}",
                inline=False,
            )
        embed.set_footer(text=f"{len(infractions)} Infractions insgesamt")
        await interaction.followup.send(embed=embed, ephemeral=True)


class ManageUser(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="manage-user", description="Verwalte einen Mitarbeiter (nur Leader/Admins)")
    @app_commands.describe(user="Der Mitarbeiter, den du verwalten möchtest")
    @require_leader()
    async def manage_user(self, interaction: discord.Interaction, user: discord.Member):
        if user.bot:
            await interaction.response.send_message(embed=error_embed("Fehler", "Du kannst keinen Bot verwalten."), ephemeral=True)
            return

        config = await database.get_config(str(interaction.guild_id))
        embed = discord.Embed(
            title=f"👥 Mitarbeiter verwalten",
            description=f"Wähle eine Aktion für {user.mention}:",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Angefragt von {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, view=ManageUserView(user, config), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ManageUser(bot))

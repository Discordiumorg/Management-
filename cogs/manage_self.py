import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone, timedelta

import database
from utils.embeds import success_embed, error_embed, info_embed, log_embed
from utils.checks import require_staff


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
        label="Grund für die Kündigung",
        placeholder="Warum möchtest du kündigen?",
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
                await interaction.followup.send(embed=error_embed("Fehler", "Ich habe keine Berechtigung, Rollen zu entfernen."), ephemeral=True)
                return

        try:
            dm_embed = discord.Embed(
                title="📋 Kündigung bestätigt",
                description=f"Deine Kündigung bei **{guild.name}** wurde verarbeitet.\n\n**Grund:** {self.reason.value}",
                color=0xE74C3C,
                timestamp=datetime.now(timezone.utc),
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = log_embed("Kündigung (Resign)", member, member, self.reason.value, 0xE74C3C)
                await channel.send(embed=embed)

        await interaction.followup.send(
            embed=success_embed("Kündigung eingereicht", "Deine Kündigung wurde erfolgreich verarbeitet. Alle Staff-Rollen wurden entfernt."),
            ephemeral=True,
        )


class LOARequestModal(discord.ui.Modal, title="Leave of Absence anfragen"):
    duration = discord.ui.TextInput(
        label="Wie lange? (z.B. 2d, 3h, 1w)",
        placeholder="z.B. 2d (m/h/d/w)",
        required=True,
        max_length=10,
    )
    reason = discord.ui.TextInput(
        label="Grund für die Abwesenheit",
        placeholder="Nur für Leader sichtbar",
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
                embed=error_embed("Ungültiges Format", "Bitte gib die Dauer im Format `2d`, `3h`, `1w`, `30m` an."),
                ephemeral=True,
            )
            return

        end_date = (datetime.now(timezone.utc) + delta).isoformat()
        await database.set_loa(str(member.id), str(guild.id), self.duration.value, self.reason.value, end_date)

        try:
            current_nick = member.display_name
            if not current_nick.startswith("[LOA] "):
                await member.edit(nick=f"[LOA] {current_nick}"[:32], reason="LOA gestartet")
        except discord.Forbidden:
            pass

        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = log_embed("LOA gestartet", member, member, self.reason.value, 0xF39C12, Dauer=self.duration.value)
                await channel.send(embed=embed)

        try:
            dm_embed = discord.Embed(
                title="🏖️ LOA bestätigt",
                description=f"Dein LOA bei **{guild.name}** wurde eingetragen.\n\n**Dauer:** {self.duration.value}\n**Ende:** <t:{int((datetime.now(timezone.utc) + delta).timestamp())}:F>",
                color=0xF39C12,
                timestamp=datetime.now(timezone.utc),
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await interaction.followup.send(
            embed=success_embed("LOA eingetragen", f"Dein LOA wurde für **{self.duration.value}** eingetragen. Dein Nickname wurde aktualisiert."),
            ephemeral=True,
        )


class LOAView(discord.ui.View):
    def __init__(self, config: dict, is_in_loa: bool):
        super().__init__(timeout=300)
        self.config = config
        self.is_in_loa = is_in_loa

    @discord.ui.button(label="LOA anfragen", style=discord.ButtonStyle.primary, emoji="🏖️")
    async def request_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LOARequestModal(self.config))

    @discord.ui.button(label="LOA entfernen", style=discord.ButtonStyle.danger, emoji="🔴")
    async def remove_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        guild = interaction.guild

        loa = await database.get_active_loa(str(member.id), str(guild.id))
        if not loa:
            await interaction.followup.send(embed=error_embed("Kein LOA", "Du hast aktuell kein aktives LOA."), ephemeral=True)
            return

        await database.remove_loa(str(member.id), str(guild.id))

        try:
            current_nick = member.display_name
            if current_nick.startswith("[LOA] "):
                await member.edit(nick=current_nick[6:] or None, reason="LOA beendet")
        except discord.Forbidden:
            pass

        config = self.config
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = log_embed("LOA beendet", member, member, "Selbst beendet", 0x2ECC71)
                await channel.send(embed=embed)

        await interaction.followup.send(embed=success_embed("LOA beendet", "Dein LOA wurde entfernt und dein Nickname aktualisiert."), ephemeral=True)


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
        status_text = "Du bist aktuell **im LOA**." if is_in_loa else "Du bist aktuell **nicht im LOA**."
        embed = info_embed("Leave of Absence", status_text)
        view = LOAView(self.config, is_in_loa)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Infractions", style=discord.ButtonStyle.secondary, emoji="📋")
    async def infractions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        infractions = await database.get_infractions(str(interaction.user.id), str(interaction.guild_id))

        if not infractions:
            await interaction.followup.send(embed=success_embed("Infractions", "Du hast keine aktiven Infractions."), ephemeral=True)
            return

        embed = discord.Embed(title="📋 Deine Infractions", color=0xE67E22, timestamp=datetime.now(timezone.utc))
        for inf in infractions[:10]:
            moderator = interaction.guild.get_member(int(inf["moderator_id"]))
            mod_text = moderator.mention if moderator else f"ID: {inf['moderator_id']}"
            expires = f"\n*Läuft ab: <t:{int(datetime.fromisoformat(inf['expires_at']).timestamp())}:R>*" if inf.get("expires_at") else ""
            embed.add_field(
                name=f"{inf['type']} - {inf['timestamp'][:10]}",
                value=f"**Grund:** {inf['reason']}\n**Von:** {mod_text}{expires}",
                inline=False,
            )
        embed.set_footer(text=f"{len(infractions)} Infractions insgesamt")
        await interaction.followup.send(embed=embed, ephemeral=True)


class ManageSelf(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="manage-self", description="Verwalte deinen eigenen Staff-Status")
    @require_staff()
    async def manage_self(self, interaction: discord.Interaction):
        config = await database.get_config(str(interaction.guild_id))
        embed = discord.Embed(
            title="👤 Staff Selbstverwaltung",
            description="Wähle eine Aktion für deinen Account:",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Angefragt von {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, view=ManageSelfView(config), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ManageSelf(bot))

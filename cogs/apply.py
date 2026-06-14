import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone

import database
from utils.embeds import success_embed, error_embed, info_embed
from utils.checks import is_hr_or_above


class ApplicationModal(discord.ui.Modal, title="Bewerbung"):
    full_name = discord.ui.TextInput(
        label="Vollständiger Name / Ingame-Name",
        placeholder="Dein Name",
        required=True,
        max_length=100,
    )
    age = discord.ui.TextInput(
        label="Alter",
        placeholder="z.B. 18",
        required=True,
        max_length=3,
    )
    experience = discord.ui.TextInput(
        label="Erfahrung",
        placeholder="Beschreibe deine relevante Erfahrung",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )
    why = discord.ui.TextInput(
        label="Warum möchtest du diese Position?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )
    timezone_field = discord.ui.TextInput(
        label="Zeitzone",
        placeholder="z.B. Europe/Berlin, CET, UTC+1",
        required=True,
        max_length=50,
    )

    def __init__(self, position: str, config: dict):
        super().__init__(title=f"Bewerbung: {position[:40]}")
        self.position = position
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        config = self.config

        answers = {
            "name": self.full_name.value,
            "age": self.age.value,
            "experience": self.experience.value,
            "why": self.why.value,
            "timezone": self.timezone_field.value,
        }
        app_id = await database.add_application(str(interaction.user.id), str(guild.id), self.position, answers)

        channel_id = config.get("applications_channel_id")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                embed = _build_application_embed(interaction.user, self.position, app_id, answers)
                view = ApplicationReviewView(app_id, interaction.user.id)
                await channel.send(embed=embed, view=view)

        await interaction.followup.send(
            embed=success_embed(
                "Bewerbung eingereicht",
                f"Deine Bewerbung für **{self.position}** wurde erfolgreich eingereicht.\nDu wirst per DM benachrichtigt, sobald sie bearbeitet wurde.",
            ),
            ephemeral=True,
        )

        try:
            dm_embed = discord.Embed(
                title="📩 Bewerbung eingereicht",
                description=(
                    f"Deine Bewerbung für **{self.position}** bei **{guild.name}** wurde eingereicht!\n\n"
                    f"**Bewerbungs-ID:** #{app_id}\n\n"
                    "Wir werden uns bald bei dir melden."
                ),
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            await interaction.user.send(embed=dm_embed)
        except discord.Forbidden:
            pass


def _build_application_embed(user: discord.Member, position: str, app_id: int, answers: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"📩 Neue Bewerbung – {position}",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    embed.add_field(name="Bewerber", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="Position", value=position, inline=True)
    embed.add_field(name="Bewerbungs-ID", value=f"#{app_id}", inline=True)
    embed.add_field(name="Name", value=answers["name"], inline=True)
    embed.add_field(name="Alter", value=answers["age"], inline=True)
    embed.add_field(name="Zeitzone", value=answers["timezone"], inline=True)
    embed.add_field(name="Erfahrung", value=answers["experience"], inline=False)
    embed.add_field(name="Motivation", value=answers["why"], inline=False)
    embed.set_footer(text="Status: Ausstehend ⏳")
    return embed


class AcceptReasonModal(discord.ui.Modal, title="Bewerbung annehmen"):
    reason = discord.ui.TextInput(
        label="Grund für die Annahme",
        placeholder="Warum wird diese Bewerbung angenommen?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    def __init__(self, app_id: int, applicant_id: int, message: discord.Message, review_view: "ApplicationReviewView"):
        super().__init__()
        self.app_id = app_id
        self.applicant_id = applicant_id
        self.message = message
        self.review_view = review_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        app = await database.get_application(self.app_id)
        if not app or app["status"] != "pending":
            await interaction.followup.send(embed=error_embed("Fehler", "Diese Bewerbung wurde bereits bearbeitet."), ephemeral=True)
            return

        await database.update_application_status(self.app_id, "accepted")

        applicant = interaction.guild.get_member(self.applicant_id)
        if applicant:
            try:
                dm_embed = discord.Embed(
                    title="🎉 Bewerbung angenommen!",
                    description=(
                        f"Deine Bewerbung für **{app['position']}** bei **{interaction.guild.name}** wurde angenommen!\n\n"
                        f"**Begründung:** {self.reason.value}\n\n"
                        "Willkommen im Team! 🎊"
                    ),
                    color=0x2ECC71,
                    timestamp=datetime.now(timezone.utc),
                )
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        # Update embed in applications channel
        embed = self.message.embeds[0]
        embed.color = 0x2ECC71
        embed.set_footer(
            text=f"✅ Angenommen von {interaction.user.display_name} • {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC"
        )
        embed.add_field(name="✅ Annahme-Begründung", value=self.reason.value, inline=False)

        for child in self.review_view.children:
            child.disabled = True
        await self.message.edit(embed=embed, view=self.review_view)

        await interaction.followup.send(
            embed=success_embed("Angenommen", f"Bewerbung **#{self.app_id}** wurde angenommen." + (f" {applicant.mention} wurde per DM benachrichtigt." if applicant else "")),
            ephemeral=True,
        )


class DenyReasonModal(discord.ui.Modal, title="Bewerbung ablehnen"):
    reason = discord.ui.TextInput(
        label="Ablehnungsgrund",
        placeholder="Warum wird diese Bewerbung abgelehnt?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    def __init__(self, app_id: int, applicant_id: int, message: discord.Message, review_view: "ApplicationReviewView"):
        super().__init__()
        self.app_id = app_id
        self.applicant_id = applicant_id
        self.message = message
        self.review_view = review_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        app = await database.get_application(self.app_id)
        if not app or app["status"] != "pending":
            await interaction.followup.send(embed=error_embed("Fehler", "Diese Bewerbung wurde bereits bearbeitet."), ephemeral=True)
            return

        await database.update_application_status(self.app_id, "denied")

        applicant = interaction.guild.get_member(self.applicant_id)
        if applicant:
            try:
                dm_embed = discord.Embed(
                    title="❌ Bewerbung abgelehnt",
                    description=(
                        f"Deine Bewerbung für **{app['position']}** bei **{interaction.guild.name}** wurde leider abgelehnt.\n\n"
                        f"**Begründung:** {self.reason.value}"
                    ),
                    color=0xE74C3C,
                    timestamp=datetime.now(timezone.utc),
                )
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        embed = self.message.embeds[0]
        embed.color = 0xE74C3C
        embed.set_footer(
            text=f"❌ Abgelehnt von {interaction.user.display_name} • {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC"
        )
        embed.add_field(name="❌ Ablehnungs-Begründung", value=self.reason.value, inline=False)

        for child in self.review_view.children:
            child.disabled = True
        await self.message.edit(embed=embed, view=self.review_view)

        await interaction.followup.send(
            embed=success_embed("Abgelehnt", f"Bewerbung **#{self.app_id}** wurde abgelehnt." + (f" {applicant.mention} wurde per DM benachrichtigt." if applicant else "")),
            ephemeral=True,
        )


class ApplicationReviewView(discord.ui.View):
    def __init__(self, app_id: int, applicant_id: int):
        super().__init__(timeout=None)
        self.app_id = app_id
        self.applicant_id = applicant_id

    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        if not await is_hr_or_above(interaction):
            await interaction.response.send_message(
                embed=error_embed("Kein Zugriff", "Du benötigst eine HR-, Leader- oder Admin-Rolle um Bewerbungen zu bearbeiten."),
                ephemeral=True,
            )
            return False
        return True

    async def _check_still_pending(self, interaction: discord.Interaction) -> bool:
        app = await database.get_application(self.app_id)
        if not app or app["status"] != "pending":
            await interaction.response.send_message(
                embed=error_embed("Bereits bearbeitet", "Diese Bewerbung wurde bereits angenommen oder abgelehnt."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, emoji="✅", custom_id="app_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_permission(interaction):
            return
        if not await self._check_still_pending(interaction):
            return
        await interaction.response.send_modal(AcceptReasonModal(self.app_id, self.applicant_id, interaction.message, self))

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, emoji="❌", custom_id="app_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_permission(interaction):
            return
        if not await self._check_still_pending(interaction):
            return
        await interaction.response.send_modal(DenyReasonModal(self.app_id, self.applicant_id, interaction.message, self))


class PositionSelectView(discord.ui.View):
    def __init__(self, positions: list, config: dict):
        super().__init__(timeout=300)
        self.config = config
        options = [
            discord.SelectOption(label=p["name"][:100], description=p.get("description", "")[:100])
            for p in positions[:25]
        ]
        select = discord.ui.Select(placeholder="Wähle eine Position...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        position = interaction.data["values"][0]
        await interaction.response.send_modal(ApplicationModal(position, self.config))


class Apply(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="apply", description="Bewirb dich für eine Position im Staff-Team")
    async def apply(self, interaction: discord.Interaction):
        config = await database.get_config(str(interaction.guild_id))
        positions = json.loads(config.get("apply_positions_json", "[]"))

        if not positions:
            await interaction.response.send_message(
                embed=error_embed("Keine Positionen", "Aktuell sind keine Positionen zur Bewerbung verfügbar."),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📩 Jetzt bewerben",
            description="Wähle die Position, für die du dich bewerben möchtest:",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        for pos in positions:
            embed.add_field(name=f"🔹 {pos['name']}", value=pos.get("description", "Keine Beschreibung"), inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=PositionSelectView(positions, config),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Apply(bot))

import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone

import database
from utils.embeds import success_embed, error_embed, info_embed
from utils.checks import is_leader_or_admin


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
                embed = discord.Embed(
                    title=f"📩 Neue Bewerbung – {self.position}",
                    color=0x5865F2,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
                embed.add_field(name="Bewerber", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                embed.add_field(name="Position", value=self.position, inline=True)
                embed.add_field(name="Bewerbungs-ID", value=f"#{app_id}", inline=True)
                embed.add_field(name="Name", value=answers["name"], inline=True)
                embed.add_field(name="Alter", value=answers["age"], inline=True)
                embed.add_field(name="Zeitzone", value=answers["timezone"], inline=True)
                embed.add_field(name="Erfahrung", value=answers["experience"], inline=False)
                embed.add_field(name="Motivation", value=answers["why"], inline=False)
                view = ApplicationReviewView(app_id, interaction.user.id)
                await channel.send(embed=embed, view=view)

        await interaction.followup.send(
            embed=success_embed("Bewerbung eingereicht", f"Deine Bewerbung für **{self.position}** wurde erfolgreich eingereicht. Du wirst per DM benachrichtigt."),
            ephemeral=True,
        )

        try:
            dm_embed = discord.Embed(
                title="📩 Bewerbung eingereicht",
                description=f"Deine Bewerbung für **{self.position}** bei **{guild.name}** wurde eingereicht!\n\n**Bewerbungs-ID:** #{app_id}\n\nWir werden uns bald bei dir melden.",
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            await interaction.user.send(embed=dm_embed)
        except discord.Forbidden:
            pass


class ApplicationReviewView(discord.ui.View):
    def __init__(self, app_id: int, applicant_id: int):
        super().__init__(timeout=None)
        self.app_id = app_id
        self.applicant_id = applicant_id

    @discord.ui.button(label="Annehmen ✅", style=discord.ButtonStyle.success, custom_id="app_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        await interaction.response.defer()
        app = await database.get_application(self.app_id)
        if not app or app["status"] != "pending":
            await interaction.followup.send(embed=error_embed("Fehler", "Diese Bewerbung wurde bereits bearbeitet."), ephemeral=True)
            return
        await database.update_application_status(self.app_id, "accepted")

        applicant = interaction.guild.get_member(self.applicant_id)
        if applicant:
            try:
                answers = json.loads(app["answers_json"])
                dm_embed = discord.Embed(
                    title="🎉 Bewerbung angenommen!",
                    description=f"Deine Bewerbung für **{app['position']}** bei **{interaction.guild.name}** wurde angenommen!\n\nWillkommen im Team! 🎊",
                    color=0x2ECC71,
                    timestamp=datetime.now(timezone.utc),
                )
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        embed = interaction.message.embeds[0]
        embed.color = 0x2ECC71
        embed.set_footer(text=f"✅ Angenommen von {interaction.user.display_name}")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Ablehnen ❌", style=discord.ButtonStyle.danger, custom_id="app_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(embed=error_embed("Kein Zugriff", "Du hast keine Berechtigung."), ephemeral=True)
            return
        await interaction.response.send_modal(DenyReasonModal(self.app_id, self.applicant_id, interaction.message, self))


class DenyReasonModal(discord.ui.Modal, title="Bewerbung ablehnen"):
    reason = discord.ui.TextInput(
        label="Ablehnungsgrund (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, app_id: int, applicant_id: int, message: discord.Message, view: ApplicationReviewView):
        super().__init__()
        self.app_id = app_id
        self.applicant_id = applicant_id
        self.message = message
        self.review_view = view

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
                    description=f"Deine Bewerbung für **{app['position']}** bei **{interaction.guild.name}** wurde leider abgelehnt." +
                                (f"\n\n**Grund:** {self.reason.value}" if self.reason.value else ""),
                    color=0xE74C3C,
                    timestamp=datetime.now(timezone.utc),
                )
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        embed = self.message.embeds[0]
        embed.color = 0xE74C3C
        embed.set_footer(text=f"❌ Abgelehnt von {interaction.user.display_name}")
        for child in self.review_view.children:
            child.disabled = True
        await self.message.edit(embed=embed, view=self.review_view)


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
            title="📩 Bewerbung",
            description="Wähle die Position, für die du dich bewerben möchtest:",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        for pos in positions:
            embed.add_field(name=pos["name"], value=pos.get("description", "Keine Beschreibung"), inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=PositionSelectView(positions, config),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_ready(self):
        # Re-register persistent views so buttons still work after restart
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Apply(bot))

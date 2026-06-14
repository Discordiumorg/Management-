import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone

import database
from utils.embeds import success_embed, error_embed, info_embed


class Permissions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    perms_group = app_commands.Group(name="permissions", description="Berechtigungen verwalten")

    @perms_group.command(name="add-leader", description="Füge eine Leader-Rolle hinzu (nur Admins)")
    @app_commands.describe(role="Die Rolle, die Leader-Rechte erhalten soll")
    @app_commands.default_permissions(administrator=True)
    async def add_leader(self, interaction: discord.Interaction, role: discord.Role):
        config = await database.get_config(str(interaction.guild_id))
        roles = json.loads(config.get("leader_roles_json", "[]"))
        if str(role.id) not in roles:
            roles.append(str(role.id))
            await database.set_config(str(interaction.guild_id), leader_roles_json=json.dumps(roles))
        await interaction.response.send_message(
            embed=success_embed("Leader-Rolle hinzugefügt", f"{role.mention} hat jetzt Leader-Berechtigungen."),
            ephemeral=True,
        )

    @perms_group.command(name="add-staff", description="Füge eine Staff-Rolle hinzu (nur Admins)")
    @app_commands.describe(role="Die Rolle, die als Staff-Rolle gilt")
    @app_commands.default_permissions(administrator=True)
    async def add_staff(self, interaction: discord.Interaction, role: discord.Role):
        config = await database.get_config(str(interaction.guild_id))
        roles = json.loads(config.get("staff_roles_json", "[]"))
        if str(role.id) not in roles:
            roles.append(str(role.id))
            await database.set_config(str(interaction.guild_id), staff_roles_json=json.dumps(roles))
        await interaction.response.send_message(
            embed=success_embed("Staff-Rolle hinzugefügt", f"{role.mention} ist jetzt eine Staff-Rolle."),
            ephemeral=True,
        )

    @perms_group.command(name="set-log-channel", description="Setzt den Log-Kanal (nur Admins)")
    @app_commands.describe(channel="Der Kanal für Logs")
    @app_commands.default_permissions(administrator=True)
    async def set_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), log_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Log-Kanal gesetzt", f"Log-Kanal: {channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-promotion-channel", description="Setzt den Beförderungs-Kanal (nur Admins)")
    @app_commands.default_permissions(administrator=True)
    async def set_promotion(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), promotion_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Beförderungs-Kanal gesetzt", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-demotion-channel", description="Setzt den Degradierungs-Kanal (nur Admins)")
    @app_commands.default_permissions(administrator=True)
    async def set_demotion(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), demotion_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Degradierungs-Kanal gesetzt", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-termination-channel", description="Setzt den Entlassungs-Kanal (nur Admins)")
    @app_commands.default_permissions(administrator=True)
    async def set_termination(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), termination_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Entlassungs-Kanal gesetzt", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-infractions-channel", description="Setzt den Infractions-Kanal (nur Admins)")
    @app_commands.default_permissions(administrator=True)
    async def set_infractions(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), infractions_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Infractions-Kanal gesetzt", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-applications-channel", description="Setzt den Bewerbungs-Kanal (nur Admins)")
    @app_commands.default_permissions(administrator=True)
    async def set_applications(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), applications_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Bewerbungs-Kanal gesetzt", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="add-hr", description="Füge eine HR-Rolle hinzu (darf Bewerbungen bearbeiten)")
    @app_commands.describe(role="Die Rolle, die HR-Rechte für Bewerbungen erhalten soll")
    @app_commands.default_permissions(administrator=True)
    async def add_hr(self, interaction: discord.Interaction, role: discord.Role):
        config = await database.get_config(str(interaction.guild_id))
        roles = json.loads(config.get("hr_roles_json", "[]"))
        if str(role.id) not in roles:
            roles.append(str(role.id))
            await database.set_config(str(interaction.guild_id), hr_roles_json=json.dumps(roles))
        await interaction.response.send_message(
            embed=success_embed("HR-Rolle hinzugefügt", f"{role.mention} kann jetzt Bewerbungen annehmen und ablehnen."),
            ephemeral=True,
        )

    @perms_group.command(name="add-position", description="Füge eine bewerbbare Position hinzu (nur Admins)")
    @app_commands.describe(name="Name der Position", description="Beschreibung der Position")
    @app_commands.default_permissions(administrator=True)
    async def add_position(self, interaction: discord.Interaction, name: str, description: str):
        config = await database.get_config(str(interaction.guild_id))
        positions = json.loads(config.get("apply_positions_json", "[]"))
        positions.append({"name": name, "description": description})
        await database.set_config(str(interaction.guild_id), apply_positions_json=json.dumps(positions))
        await interaction.response.send_message(
            embed=success_embed("Position hinzugefügt", f"Position **{name}** wurde hinzugefügt."),
            ephemeral=True,
        )

    @perms_group.command(name="list", description="Zeigt alle Konfigurationen (nur Admins)")
    @app_commands.default_permissions(administrator=True)
    async def list_config(self, interaction: discord.Interaction):
        config = await database.get_config(str(interaction.guild_id))
        guild = interaction.guild

        def channel_mention(cid):
            if cid:
                ch = guild.get_channel(int(cid))
                return ch.mention if ch else f"ID: {cid}"
            return "*Nicht gesetzt*"

        def roles_list(json_str):
            ids = json.loads(json_str or "[]")
            if not ids:
                return "*Keine*"
            return ", ".join(r.mention if (r := guild.get_role(int(rid))) else f"ID: {rid}" for rid in ids)

        embed = discord.Embed(title="⚙️ Bot-Konfiguration", color=0x5865F2, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Log-Kanal", value=channel_mention(config.get("log_channel_id")), inline=True)
        embed.add_field(name="Beförderungs-Kanal", value=channel_mention(config.get("promotion_channel_id")), inline=True)
        embed.add_field(name="Degradierungs-Kanal", value=channel_mention(config.get("demotion_channel_id")), inline=True)
        embed.add_field(name="Entlassungs-Kanal", value=channel_mention(config.get("termination_channel_id")), inline=True)
        embed.add_field(name="Infractions-Kanal", value=channel_mention(config.get("infractions_channel_id")), inline=True)
        embed.add_field(name="Bewerbungs-Kanal", value=channel_mention(config.get("applications_channel_id")), inline=True)
        embed.add_field(name="Staff-Rollen", value=roles_list(config.get("staff_roles_json")), inline=False)
        embed.add_field(name="Leader-Rollen", value=roles_list(config.get("leader_roles_json")), inline=False)
        embed.add_field(name="HR-Rollen", value=roles_list(config.get("hr_roles_json")), inline=False)
        positions = json.loads(config.get("apply_positions_json", "[]"))
        pos_text = "\n".join(f"• **{p['name']}** – {p['description']}" for p in positions) or "*Keine*"
        embed.add_field(name="Bewerbbare Positionen", value=pos_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Permissions(bot))

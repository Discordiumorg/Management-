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

    perms_group = app_commands.Group(name="permissions", description="Manage permissions")

    @perms_group.command(name="add-leader", description="Add a leader role (admins only)")
    @app_commands.describe(role="The role that should receive leader permissions")
    @app_commands.default_permissions(administrator=True)
    async def add_leader(self, interaction: discord.Interaction, role: discord.Role):
        config = await database.get_config(str(interaction.guild_id))
        roles = json.loads(config.get("leader_roles_json", "[]"))
        if str(role.id) not in roles:
            roles.append(str(role.id))
            await database.set_config(str(interaction.guild_id), leader_roles_json=json.dumps(roles))
        await interaction.response.send_message(
            embed=success_embed("Leader role added", f"{role.mention} now has leader permissions."),
            ephemeral=True,
        )

    @perms_group.command(name="add-staff", description="Add a staff role (admins only)")
    @app_commands.describe(role="The role that counts as a staff role")
    @app_commands.default_permissions(administrator=True)
    async def add_staff(self, interaction: discord.Interaction, role: discord.Role):
        config = await database.get_config(str(interaction.guild_id))
        roles = json.loads(config.get("staff_roles_json", "[]"))
        if str(role.id) not in roles:
            roles.append(str(role.id))
            await database.set_config(str(interaction.guild_id), staff_roles_json=json.dumps(roles))
        await interaction.response.send_message(
            embed=success_embed("Staff role added", f"{role.mention} is now a staff role."),
            ephemeral=True,
        )

    @perms_group.command(name="set-log-channel", description="Set the log channel (admins only)")
    @app_commands.describe(channel="The channel for logs")
    @app_commands.default_permissions(administrator=True)
    async def set_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), log_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Log channel set", f"Log channel: {channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-promotion-channel", description="Set the promotion channel (admins only)")
    @app_commands.default_permissions(administrator=True)
    async def set_promotion(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), promotion_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Promotion channel set", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-demotion-channel", description="Set the demotion channel (admins only)")
    @app_commands.default_permissions(administrator=True)
    async def set_demotion(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), demotion_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Demotion channel set", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-termination-channel", description="Set the termination channel (admins only)")
    @app_commands.default_permissions(administrator=True)
    async def set_termination(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), termination_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Termination channel set", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-infractions-channel", description="Set the infractions channel (admins only)")
    @app_commands.default_permissions(administrator=True)
    async def set_infractions(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), infractions_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Infractions channel set", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="set-applications-channel", description="Set the applications channel (admins only)")
    @app_commands.default_permissions(administrator=True)
    async def set_applications(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await database.set_config(str(interaction.guild_id), applications_channel_id=str(channel.id))
        await interaction.response.send_message(embed=success_embed("Applications channel set", f"{channel.mention}"), ephemeral=True)

    @perms_group.command(name="add-hr", description="Add an HR role (can review applications)")
    @app_commands.describe(role="The role that should receive HR permissions for applications")
    @app_commands.default_permissions(administrator=True)
    async def add_hr(self, interaction: discord.Interaction, role: discord.Role):
        config = await database.get_config(str(interaction.guild_id))
        roles = json.loads(config.get("hr_roles_json", "[]"))
        if str(role.id) not in roles:
            roles.append(str(role.id))
            await database.set_config(str(interaction.guild_id), hr_roles_json=json.dumps(roles))
        await interaction.response.send_message(
            embed=success_embed("HR role added", f"{role.mention} can now accept and deny applications."),
            ephemeral=True,
        )

    @perms_group.command(name="add-position", description="Add an open position for applications (admins only)")
    @app_commands.describe(name="Name of the position", description="Description of the position")
    @app_commands.default_permissions(administrator=True)
    async def add_position(self, interaction: discord.Interaction, name: str, description: str):
        config = await database.get_config(str(interaction.guild_id))
        positions = json.loads(config.get("apply_positions_json", "[]"))
        positions.append({"name": name, "description": description})
        await database.set_config(str(interaction.guild_id), apply_positions_json=json.dumps(positions))
        await interaction.response.send_message(
            embed=success_embed("Position added", f"Position **{name}** has been added."),
            ephemeral=True,
        )

    @perms_group.command(name="list", description="Show all configurations (admins only)")
    @app_commands.default_permissions(administrator=True)
    async def list_config(self, interaction: discord.Interaction):
        config = await database.get_config(str(interaction.guild_id))
        guild = interaction.guild

        def channel_mention(cid):
            if cid:
                ch = guild.get_channel(int(cid))
                return ch.mention if ch else f"ID: {cid}"
            return "*Not set*"

        def roles_list(json_str):
            ids = json.loads(json_str or "[]")
            if not ids:
                return "*None*"
            return ", ".join(r.mention if (r := guild.get_role(int(rid))) else f"ID: {rid}" for rid in ids)

        embed = discord.Embed(title="⚙️ Bot Configuration", color=0x5865F2, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Log Channel", value=channel_mention(config.get("log_channel_id")), inline=True)
        embed.add_field(name="Promotion Channel", value=channel_mention(config.get("promotion_channel_id")), inline=True)
        embed.add_field(name="Demotion Channel", value=channel_mention(config.get("demotion_channel_id")), inline=True)
        embed.add_field(name="Termination Channel", value=channel_mention(config.get("termination_channel_id")), inline=True)
        embed.add_field(name="Infractions Channel", value=channel_mention(config.get("infractions_channel_id")), inline=True)
        embed.add_field(name="Applications Channel", value=channel_mention(config.get("applications_channel_id")), inline=True)
        embed.add_field(name="Staff Roles", value=roles_list(config.get("staff_roles_json")), inline=False)
        embed.add_field(name="Leader Roles", value=roles_list(config.get("leader_roles_json")), inline=False)
        embed.add_field(name="HR Roles", value=roles_list(config.get("hr_roles_json")), inline=False)
        positions = json.loads(config.get("apply_positions_json", "[]"))
        pos_text = "\n".join(f"• **{p['name']}** – {p['description']}" for p in positions) or "*None*"
        embed.add_field(name="Open Positions", value=pos_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Permissions(bot))

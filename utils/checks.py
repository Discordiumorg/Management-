import discord
import json
from discord import app_commands
import database


async def is_leader_or_admin(interaction: discord.Interaction) -> bool:
    config = await database.get_config(str(interaction.guild_id))
    leader_roles = json.loads(config.get("leader_roles_json", "[]"))
    admin_roles = json.loads(config.get("admin_roles_json", "[]"))
    allowed = set(leader_roles + admin_roles)
    user_role_ids = {str(r.id) for r in interaction.user.roles}
    if interaction.user.guild_permissions.administrator:
        return True
    return bool(user_role_ids & allowed)


async def is_staff(interaction: discord.Interaction) -> bool:
    config = await database.get_config(str(interaction.guild_id))
    staff_roles = json.loads(config.get("staff_roles_json", "[]"))
    leader_roles = json.loads(config.get("leader_roles_json", "[]"))
    admin_roles = json.loads(config.get("admin_roles_json", "[]"))
    allowed = set(staff_roles + leader_roles + admin_roles)
    user_role_ids = {str(r.id) for r in interaction.user.roles}
    if interaction.user.guild_permissions.administrator:
        return True
    return bool(user_role_ids & allowed)


def require_leader():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not await is_leader_or_admin(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Kein Zugriff", description="Du benötigst eine Leader- oder Admin-Rolle.", color=0xE74C3C),
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)


def require_staff():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not await is_staff(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Kein Zugriff", description="Du musst ein Mitarbeiter sein.", color=0xE74C3C),
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)

"""
Helpers for applying staff actions across a linked server (Staff Server <-> Work Server).
"""
import discord
import json
import database


async def get_linked_member(bot: discord.Client, config: dict, user_id: int) -> discord.Member | None:
    """Fetch the member from the linked guild, if configured."""
    linked_guild_id = config.get("linked_guild_id")
    if not linked_guild_id:
        return None
    linked_guild = bot.get_guild(int(linked_guild_id))
    if not linked_guild:
        return None
    try:
        return linked_guild.get_member(user_id) or await linked_guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def remove_linked_staff_roles(bot: discord.Client, config: dict, user_id: int, reason: str) -> str | None:
    """Remove all configured linked-server staff roles from the user. Returns guild name or None."""
    linked_member = await get_linked_member(bot, config, user_id)
    if not linked_member:
        return None

    linked_roles_ids = json.loads(config.get("linked_staff_roles_json", "[]"))
    roles_to_remove = [r for r in linked_member.roles if str(r.id) in linked_roles_ids]
    if roles_to_remove:
        try:
            await linked_member.remove_roles(*roles_to_remove, reason=reason)
        except discord.Forbidden:
            pass
    return linked_member.guild.name


async def update_linked_nickname(bot: discord.Client, config: dict, user_id: int, new_nick: str | None, reason: str) -> bool:
    """Update nickname on linked server. Returns True if successful."""
    linked_member = await get_linked_member(bot, config, user_id)
    if not linked_member:
        return False
    try:
        await linked_member.edit(nick=new_nick, reason=reason)
        return True
    except discord.Forbidden:
        return False


async def kick_from_linked(bot: discord.Client, config: dict, user_id: int, reason: str) -> bool:
    """Kick user from linked server. Returns True if successful."""
    linked_member = await get_linked_member(bot, config, user_id)
    if not linked_member:
        return False
    try:
        await linked_member.kick(reason=reason)
        return True
    except discord.Forbidden:
        return False

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

import database
from utils.embeds import success_embed, error_embed, info_embed
from utils.checks import require_staff


class Duty(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="duty", description="Toggle your on-duty / off-duty status")
    @require_staff()
    async def duty(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        guild = interaction.guild
        config = await database.get_config(str(guild.id))

        current = await database.get_duty_status(str(member.id), str(guild.id))
        is_on_duty = bool(current.get("on_duty"))
        new_status = not is_on_duty

        await database.set_duty_status(str(member.id), str(guild.id), new_status)
        await database.log_action(
            str(guild.id), str(member.id), str(member.id),
            "Duty On" if new_status else "Duty Off",
        )

        # Assign/remove duty role if configured
        duty_role_id = config.get("duty_role_id")
        if duty_role_id:
            role = guild.get_role(int(duty_role_id))
            if role:
                try:
                    if new_status:
                        await member.add_roles(role, reason="On duty")
                    else:
                        await member.remove_roles(role, reason="Off duty")
                except discord.Forbidden:
                    pass

        # Update nickname prefix [ON-DUTY]
        try:
            nick = member.display_name
            if new_status and not nick.startswith("[ON-DUTY] "):
                await member.edit(nick=f"[ON-DUTY] {nick}"[:32], reason="On duty")
            elif not new_status and nick.startswith("[ON-DUTY] "):
                await member.edit(nick=nick[10:] or None, reason="Off duty")
        except discord.Forbidden:
            pass

        if new_status:
            embed = success_embed(
                "🟢 You are now On Duty",
                "Your status has been set to **On Duty**.\nYou are now visible as active in the staff roster."
            )
        else:
            since = current.get("since")
            duration_text = ""
            if since:
                delta = datetime.now(timezone.utc) - datetime.fromisoformat(since)
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                minutes = rem // 60
                duration_text = f"\nDuty session duration: **{hours}h {minutes}m**"
            embed = info_embed(
                "🔴 You are now Off Duty",
                f"Your status has been set to **Off Duty**.{duration_text}"
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Duty(bot))

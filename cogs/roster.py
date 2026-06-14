import discord
from discord import app_commands
from discord.ext import commands
import json
from datetime import datetime, timezone

import database
from utils.checks import require_staff, require_leader


class Roster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    staff_group = app_commands.Group(name="staff", description="Staff roster and statistics")

    @staff_group.command(name="roster", description="Show all current staff members")
    @require_staff()
    async def roster(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = await database.get_config(str(interaction.guild_id))
        guild = interaction.guild

        staff_role_ids = json.loads(config.get("staff_roles_json", "[]"))
        leader_role_ids = json.loads(config.get("leader_roles_json", "[]"))

        if not staff_role_ids and not leader_role_ids:
            await interaction.followup.send(
                embed=discord.Embed(title="❌ Not configured", description="No staff roles configured. Use `/permissions add-staff`.", color=0xE74C3C),
                ephemeral=True,
            )
            return

        all_role_ids = leader_role_ids + [r for r in staff_role_ids if r not in leader_role_ids]

        embed = discord.Embed(
            title=f"👥 Staff Roster — {guild.name}",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

        total_staff = 0
        for role_id in all_role_ids:
            role = guild.get_role(int(role_id))
            if not role or not role.members:
                continue

            lines = []
            for member in sorted(role.members, key=lambda m: m.display_name):
                loa = await database.get_active_loa(str(member.id), str(guild.id))
                duty = await database.get_duty_status(str(member.id), str(guild.id))
                badges = ""
                if loa:
                    badges += " 🏖️"
                if duty.get("on_duty"):
                    badges += " 🟢"
                lines.append(f"• {member.mention}{badges}")
                total_staff += 1

            if lines:
                value = "\n".join(lines[:15])
                if len(lines) > 15:
                    value += f"\n*...and {len(lines) - 15} more*"
                embed.add_field(name=f"{role.name} ({len(lines)})", value=value, inline=False)

        embed.set_footer(text=f"Total: {total_staff} staff members • 🟢 On Duty • 🏖️ On LOA")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @staff_group.command(name="stats", description="Show staff statistics dashboard")
    @require_staff()
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        config = await database.get_config(str(interaction.guild_id))

        staff_role_ids = json.loads(config.get("staff_roles_json", "[]"))
        leader_role_ids = json.loads(config.get("leader_roles_json", "[]"))
        all_role_ids = set(staff_role_ids + leader_role_ids)

        total_staff = 0
        on_loa = 0
        on_duty = 0

        loas = await database.get_all_active_loas(str(guild.id))
        loa_user_ids = {l["user_id"] for l in loas}

        duty_members = await database.get_all_on_duty(str(guild.id))
        on_duty = len(duty_members)

        for role_id in all_role_ids:
            role = guild.get_role(int(role_id))
            if role:
                for member in role.members:
                    total_staff += 1
                    if str(member.id) in loa_user_ids:
                        on_loa += 1

        infraction_stats = await database.get_guild_infraction_stats(str(guild.id))
        pending_apps = await database.get_pending_applications_count(str(guild.id))

        embed = discord.Embed(
            title=f"📊 Staff Statistics — {guild.name}",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

        embed.add_field(name="👥 Total Staff", value=str(total_staff), inline=True)
        embed.add_field(name="🟢 On Duty", value=str(on_duty), inline=True)
        embed.add_field(name="🏖️ On LOA", value=str(on_loa), inline=True)
        embed.add_field(name="✅ Active", value=str(total_staff - on_loa), inline=True)
        embed.add_field(name="📩 Pending Applications", value=str(pending_apps), inline=True)
        embed.add_field(name="​", value="​", inline=True)

        inf_text = (
            f"⚠️ Verbal Warnings: **{infraction_stats.get('Verbal Warning', 0)}**\n"
            f"🟡 Warnings: **{infraction_stats.get('Warning', 0)}**\n"
            f"🔴 Strikes: **{infraction_stats.get('Strike', 0)}**"
        )
        embed.add_field(name="📋 Active Infractions", value=inf_text, inline=False)

        loa_list = []
        for loa in loas[:5]:
            member = guild.get_member(int(loa["user_id"]))
            name = member.mention if member else f"ID: {loa['user_id']}"
            end = f"<t:{int(datetime.fromisoformat(loa['end_date']).timestamp())}:R>" if loa.get("end_date") else "No end date"
            loa_list.append(f"• {name} — ends {end}")
        if loa_list:
            embed.add_field(name="🏖️ Current LOAs", value="\n".join(loa_list), inline=False)

        embed.set_footer(text="Monthly infractions reset automatically on the 1st of each month")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @staff_group.command(name="history", description="View the full action history of a staff member")
    @app_commands.describe(user="The staff member to look up")
    @require_leader()
    async def history(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        logs = await database.get_action_log(str(user.id), str(interaction.guild_id))

        embed = discord.Embed(
            title=f"📜 Action History — {user.display_name}",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        if not logs:
            embed.description = "No actions recorded for this user."
        else:
            action_icons = {
                "Promotion": "⬆️", "Demotion": "⬇️", "Termination": "🚫",
                "Resignation": "🚪", "LOA Started": "🏖️", "LOA Ended": "✅",
                "Verbal Warning": "⚠️", "Warning": "🟡", "Strike": "🔴",
                "Note": "📝",
            }
            lines = []
            for entry in logs:
                actor = interaction.guild.get_member(int(entry["actor_id"]))
                actor_name = actor.display_name if actor else f"ID:{entry['actor_id']}"
                icon = action_icons.get(entry["action"], "•")
                ts = int(datetime.fromisoformat(entry["timestamp"]).timestamp())
                line = f"{icon} **{entry['action']}** — <t:{ts}:d> by {actor_name}"
                if entry.get("detail"):
                    line += f"\n  *{entry['detail'][:80]}{'...' if len(entry['detail']) > 80 else ''}*"
                lines.append(line)
            embed.description = "\n\n".join(lines[:15])
            if len(logs) > 15:
                embed.set_footer(text=f"Showing 15 of {len(logs)} entries")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Roster(bot))

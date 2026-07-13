import discord

async def grant_role(member: discord.Member, role_id: int) -> tuple[bool, str]:
    if not role_id:
        return True, "No role configured."
    guild = member.guild
    role = guild.get_role(int(role_id))
    if not role:
        return False, "Role not found."
    try:
        await member.add_roles(role, reason="Community OS shop reward")
        return True, f"Role granted: {role.name}"
    except Exception as exc:
        return False, f"Failed to grant role: {exc}"

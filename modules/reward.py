from __future__ import annotations

import discord


async def grant_role(member: discord.Member, role_id: int | None) -> tuple[bool, str]:
    if not role_id:
        return True, "No role configured"

    role = member.guild.get_role(int(role_id))
    if role is None:
        return False, "Role not found"

    try:
        await member.add_roles(role, reason="Community OS shop redemption")
        return True, f"Role granted: {role.name}"
    except discord.Forbidden:
        return False, "Bot has no permission to grant this role"
    except Exception as exc:
        return False, f"Role grant failed: {exc}"

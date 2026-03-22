from __future__ import annotations

from typing import cast

import discord
from discord.ext import commands

from config import Settings


class PresenceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = cast(Settings, getattr(bot, "settings"))

    @commands.Cog.listener()
    async def on_ready(self):
        await self._apply_rpc_presence()

    def _resolve_rpc_status(self) -> discord.Status:
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        return status_map.get(self.settings.rpc_status, discord.Status.online)

    def _build_rpc_activity(self) -> discord.BaseActivity | None:
        activity_type = self.settings.rpc_activity_type
        name = self.settings.rpc_activity_name
        if activity_type == "none":
            return None
        if activity_type == "playing":
            return discord.Game(name=name)
        if activity_type == "streaming":
            return discord.Streaming(name=name, url=self.settings.rpc_activity_url or "")

        discord_activity_map = {
            "listening": discord.ActivityType.listening,
            "watching": discord.ActivityType.watching,
            "competing": discord.ActivityType.competing,
        }
        mapped = discord_activity_map.get(activity_type, discord.ActivityType.playing)
        return discord.Activity(type=mapped, name=name)

    async def _apply_rpc_presence(self) -> None:
        if not self.settings.rpc_enabled:
            print("Discord RPC presence: disabled")
            return
        status = self._resolve_rpc_status()
        activity = self._build_rpc_activity()
        await self.bot.change_presence(status=status, activity=activity)
        activity_type = self.settings.rpc_activity_type
        activity_name = self.settings.rpc_activity_name if activity else "(none)"
        print(
            "Discord RPC presence applied: "
            f"status={self.settings.rpc_status}, "
            f"type={activity_type}, "
            f"name={activity_name}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PresenceCog(bot))

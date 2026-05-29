from __future__ import annotations

import os
import sys
from typing import cast

from discord.ext import commands

from config import Settings


class BackgroundTasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = cast(Settings, getattr(bot, "settings"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BackgroundTasksCog(bot))


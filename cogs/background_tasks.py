from __future__ import annotations

import os
import sys
from typing import cast

from discord.ext import commands, tasks

from config import Settings
from utils import clear_pycache


class BackgroundTasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = cast(Settings, getattr(bot, "settings"))
        if self.settings.restart_interval_hours > 0:
            self.scheduled_restart.start()

    def cog_unload(self):
        self.scheduled_restart.cancel()

    @tasks.loop(hours=12)
    async def scheduled_restart(self):
        """Periodically restarts the bot and clears cache for stability."""
        print(f"Scheduled restart triggered after {self.settings.restart_interval_hours} hours...")
        if self.bot.owner_id:
            try:
                owner = await self.bot.fetch_user(self.bot.owner_id)
                await owner.send("Performing scheduled restart and clearing cache...")
            except Exception as e:
                print(f"Could not notify owner of scheduled restart: {e}")
        
        await self.bot.close()
        clear_pycache()
        
        print("Restarting bot process...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    @scheduled_restart.before_loop
    async def before_scheduled_restart(self):
        await self.bot.wait_until_ready()
        # Set the loop hours dynamically from settings
        self.scheduled_restart.change_interval(hours=self.settings.restart_interval_hours)
        print(f"Scheduled restart task started. Interval: {self.settings.restart_interval_hours} hours.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BackgroundTasksCog(bot))

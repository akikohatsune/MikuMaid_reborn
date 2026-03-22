from __future__ import annotations

import os
import sys
import subprocess
import asyncio
from typing import cast

import discord
from discord.ext import commands, tasks

from config import Settings


class AutoupdateCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings):
        self.bot = bot
        self.settings = settings
        self.auto_update_loop.start()

    def cog_unload(self) -> None:
        self.auto_update_loop.cancel()

    async def _is_owner(self, user: discord.abc.User | discord.User | discord.Member) -> bool:
        return await self.bot.is_owner(user)

    @tasks.loop(hours=24)
    async def auto_update_loop(self) -> None:
        """Background task that checks for updates every 24 hours."""
        try:
            # Check for updates from git
            print("Checking for updates in background task...")
            # We run 'git pull' directly. If it changes files, we restart.
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout or ""
            
            if "Already up to date." not in output:
                print(f"Updates found and pulled:\n{output}")
                
                # Notify owner if possible
                if self.bot.owner_id:
                    owner = self.bot.get_user(self.bot.owner_id)
                    if not owner:
                        owner = await self.bot.fetch_user(self.bot.owner_id)
                    
                    if owner:
                        try:
                            await owner.send(
                                f"**[Auto-Update]** New updates were found and pulled:\n"
                                f"```\n{output[:1800]}\n```\n"
                                f"Restarting bot to apply changes..."
                            )
                        except Exception as e:
                            print(f"Failed to notify owner: {e}")

                # Wait a bit for the message to send before restarting
                await asyncio.sleep(5)
                
                # Restart the bot
                print("Auto-restarting bot...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                print("No updates found in background check.")

        except Exception as exc:
            print(f"Auto-update background task failed: {exc}")

    @auto_update_loop.before_loop
    async def before_auto_update_loop(self) -> None:
        await self.bot.wait_until_ready()
        # Optional: wait a bit after startup before the first check
        await asyncio.sleep(10)

    @commands.command(name="update")
    async def update_bot(self, ctx: commands.Context[commands.Bot]) -> None:
        if not await self._is_owner(ctx.author):
            await ctx.reply("Only the bot owner can use this command.", mention_author=False)
            return

        await ctx.reply("Updating bot from git...", mention_author=False)
        try:
            # Use subprocess to run git pull
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout or result.stderr
            if "Already up to date." in output:
                await ctx.reply("The bot is already up to date.", mention_author=False)
            else:
                await ctx.reply(
                    f"Update successful:\n```\n{output[:1700]}\n```\n"
                    "Restarting bot to apply changes...",
                    mention_author=False
                )
                # Wait a bit for the message to send
                await asyncio.sleep(5)
                # Restart the bot
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except subprocess.CalledProcessError as exc:
            await ctx.reply(f"Update failed:\n```\n{exc.stderr[:1800]}\n```", mention_author=False)
        except Exception as exc:
            await ctx.reply(f"An error occurred: `{exc}`", mention_author=False)

    @commands.command(name="restart")
    async def restart_bot(self, ctx: commands.Context[commands.Bot]) -> None:
        if not await self._is_owner(ctx.author):
            await ctx.reply("Only the bot owner can use this command.", mention_author=False)
            return

        await ctx.reply("Restarting bot...", mention_author=False)
        
        # Close the bot and restart the process
        # os.execv will replace the current process with a new one
        try:
            # sys.executable is the path to the python interpreter
            # sys.argv is the list of command line arguments
            # This effectively runs "python main.py" (or whatever was used to start it)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            await ctx.reply(f"Restart failed: `{exc}`", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    settings = cast(Settings, getattr(bot, "settings"))
    await bot.add_cog(AutoupdateCog(bot, settings))

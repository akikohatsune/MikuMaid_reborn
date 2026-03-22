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

    async def _run_update_flow(self, output: str, ctx: commands.Context[commands.Bot] | None = None) -> None:
        """Shared logic for performing an update and restarting."""
        update_notice = f"Updates found and pulled:\n```\n{output[:1700]}\n```\n"

        # Check if requirements.txt was updated
        if "requirements.txt" in output:
            update_notice += "Dependencies have changed. Running `pip install --upgrade`...\n"
            if ctx:
                await ctx.reply(update_notice, mention_author=False)
            else:
                print(update_notice)
            
            try:
                # Install dependencies
                pip_result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"],
                    capture_output=True, text=True, check=True,
                )
                pip_output = pip_result.stdout or pip_result.stderr
                success_msg = f"Dependencies installed successfully.\n```\n{pip_output[:1000]}\n```Restarting bot..."
                if ctx:
                    await ctx.send(success_msg)
                else:
                    print(success_msg)
            except subprocess.CalledProcessError as exc:
                fail_msg = f"Failed to install dependencies:\n```\n{exc.stderr[:1800]}\n```Bot will restart anyway."
                if ctx:
                    await ctx.send(fail_msg)
                else:
                    print(fail_msg)
        else:
            update_notice += "Restarting bot to apply changes..."
            if ctx:
                await ctx.reply(update_notice, mention_author=False)
            else:
                print(update_notice)

        # Wait a bit for messages to send
        await asyncio.sleep(5)
        
        # Restart the bot
        print("Auto-restarting bot...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @tasks.loop(hours=24)
    async def auto_update_loop(self) -> None:
        """Background task that checks for updates every 24 hours."""
        try:
            # Check for updates from git
            print("Checking for updates in background task...")
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True, text=True, check=False,
            )
            output = result.stdout or ""
            
            if "Already up to date." not in output and result.returncode == 0:
                await self._run_update_flow(output)
            elif result.returncode != 0:
                 print(f"Auto-update git pull failed with exit code {result.returncode}:\n{result.stderr}")
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
                capture_output=True, text=True, check=True,
            )
            output = result.stdout or result.stderr
            if "Already up to date." in output:
                await ctx.reply("The bot is already up to date.", mention_author=False)
            else:
                await self._run_update_flow(output, ctx)

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
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            await ctx.reply(f"Restart failed: `{exc}`", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    settings = cast(Settings, getattr(bot, "settings"))
    await bot.add_cog(AutoupdateCog(bot, settings))

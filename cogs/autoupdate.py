from __future__ import annotations

import sys
import subprocess
from typing import cast

import discord
from discord.ext import commands

from config import Settings
from i18n import t, detect_language


class AutoupdateCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings):
        self.bot = bot
        self.settings = settings

    async def _is_owner(self, user: discord.abc.User | discord.User | discord.Member) -> bool:
        return await self.bot.is_owner(user)

    async def _run_update_flow(self, output: str, ctx: commands.Context[commands.Bot] | None = None) -> None:
        """Apply an update without replacing the running bot process."""
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
                success_msg = f"Dependencies installed successfully.\n```\n{pip_output[:1000]}\n```"
                if ctx:
                    await ctx.send(success_msg)
                else:
                    print(success_msg)
            except subprocess.CalledProcessError as exc:
                fail_msg = f"Failed to install dependencies:\n```\n{exc.stderr[:1800]}\n```"
                if ctx:
                    await ctx.send(fail_msg)
                else:
                    print(fail_msg)
        else:
            update_notice += "Update downloaded. Changes apply on the next process start."
            if ctx:
                await ctx.reply(update_notice, mention_author=False)
            else:
                print(update_notice)

    @commands.command(name="update")
    async def update_bot(self, ctx: commands.Context[commands.Bot]) -> None:
        locale = detect_language(ctx.message.content)
        if not await self._is_owner(ctx.author):
            await ctx.reply(t("permissions.owner_only", locale), mention_author=False)
            return

        await ctx.reply(t("update.updating", locale), mention_author=False)
        try:
            # Use subprocess to run git pull
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True, text=True, check=True,
            )
            output = result.stdout or result.stderr
            if "Already up to date." in output:
                await ctx.reply(t("update.already_up_to_date", locale), mention_author=False)
            else:
                await self._run_update_flow(output, ctx)

        except subprocess.CalledProcessError as exc:
            await ctx.reply(f"Update failed:\n```\n{exc.stderr[:1800]}\n```", mention_author=False)
        except Exception as exc:
            await ctx.reply(t("update.error_occurred", locale, error=exc), mention_author=False)

async def setup(bot: commands.Bot) -> None:
    settings = cast(Settings, getattr(bot, "settings"))
    await bot.add_cog(AutoupdateCog(bot, settings))

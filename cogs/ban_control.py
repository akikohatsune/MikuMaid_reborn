from __future__ import annotations

from typing import cast

import discord
from discord.ext import commands

from config import Settings
from memory_store import ShortTermMemoryStore


class BanControlCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings):
        self.bot = bot
        self.settings = settings
        self.store = ShortTermMemoryStore(
            db_path=settings.ban_db_path,
            max_history_turns=settings.max_history,
        )

    async def cog_load(self) -> None:
        await self.store.initialize()

    async def cog_unload(self) -> None:
        await self.store.close()

    async def _ensure_owner_permission(
        self,
        ctx: commands.Context[commands.Bot],
    ) -> bool:
        if ctx.guild is None:
            await ctx.reply("This command can only be used in a server.", mention_author=False)
            return False

        if await self.bot.is_owner(ctx.author):
            return True

        await ctx.reply("Only the bot owner can use this command.", mention_author=False)
        return False

    def _parse_user_id(self, target: str) -> int | None:
        target = target.strip()
        if target.startswith("<@") and target.endswith(">"):
            target = target[2:-1]
            if target.startswith("!"):
                target = target[1:]
        try:
            return int(target)
        except ValueError:
            return None

    @commands.command(
        name="ban",
        help="Ban a user from using the AI bot",
    )
    async def ban_user(
        self,
        ctx: commands.Context[commands.Bot],
        target: str,
        *,
        reason: str | None = None,
    ) -> None:
        user_id = self._parse_user_id(target)
        if user_id is None:
            await ctx.reply("Invalid user ID or mention.", mention_author=False)
            return

        if not await self._ensure_owner_permission(ctx):
            return

        user = self.bot.get_user(user_id)
        if user and user.bot:
            await ctx.reply("You cannot ban a bot account.", mention_author=False)
            return

        guild = cast(discord.Guild, ctx.guild)
        created = await self.store.ban_user(
            guild_id=guild.id,
            user_id=user_id,
            banned_by=ctx.author.id,
            reason=(reason or "").strip() or None,
        )

        if created:
            await ctx.reply(
                f"Banned <@{user_id}> from using the AI bot.",
                mention_author=False,
            )
            return

        await ctx.reply(
            f"Updated ban entry for <@{user_id}>.",
            mention_author=False,
        )

    @commands.command(
        name="removeban",
        help="Remove AI-bot ban from a user",
    )
    async def remove_ban(
        self,
        ctx: commands.Context[commands.Bot],
        target: str,
    ) -> None:
        user_id = self._parse_user_id(target)
        if user_id is None:
            await ctx.reply("Invalid user ID or mention.", mention_author=False)
            return

        if not await self._ensure_owner_permission(ctx):
            return

        guild = cast(discord.Guild, ctx.guild)
        removed = await self.store.unban_user(guild.id, user_id)
        if removed:
            await ctx.reply(
                f"Removed AI-bot ban for <@{user_id}>.",
                mention_author=False,
            )
            return

        await ctx.reply(
            f"<@{user_id}> is not currently in the ban list.",
            mention_author=False,
        )

    async def cog_command_error(
        self,
        ctx: commands.Context[commands.Bot],
        error: commands.CommandError,
    ) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Missing required argument: `{error.param.name}`. Please check your command.", mention_author=False)
        else:
            await ctx.reply(f"An error occurred: {error}", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    settings = cast(Settings, getattr(bot, "settings"))
    await bot.add_cog(BanControlCog(bot, settings))

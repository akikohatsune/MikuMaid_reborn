from __future__ import annotations

from typing import cast

import discord
from discord.ext import commands

from config import Settings
from i18n import t, detect_language
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

    async def _get_locale(self, ctx: commands.Context[commands.Bot]) -> str:
        """Resolve the locale for the current user."""
        # Try stored preference first
        stored = await self.store.get_user_language(ctx.author.id)
        if stored:
            return stored
        # Auto-detect from message content
        return detect_language(ctx.message.content)

    async def _ensure_owner_permission(
        self,
        ctx: commands.Context[commands.Bot],
    ) -> bool:
        locale = await self._get_locale(ctx)
        if ctx.guild is None:
            await ctx.reply(t("permissions.server_only", locale), mention_author=False)
            return False

        if await self.bot.is_owner(ctx.author):
            return True

        await ctx.reply(t("permissions.owner_only", locale), mention_author=False)
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
        name="blockchat",
        aliases=["block", "cấm"],
        help="Block a user from using the AI bot",
    )
    async def block_user(
        self,
        ctx: commands.Context[commands.Bot],
        target: str,
        *,
        reason: str | None = None,
    ) -> None:
        locale = await self._get_locale(ctx)
        user_id = self._parse_user_id(target)
        if user_id is None:
            await ctx.reply(t("permissions.invalid_user", locale), mention_author=False)
            return

        if not await self._ensure_owner_permission(ctx):
            return

        user = self.bot.get_user(user_id)
        if user and user.bot:
            await ctx.reply(t("ban.cannot_block_bot", locale), mention_author=False)
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
                t("ban.blocked", locale, user_id=user_id),
                mention_author=False,
            )
            return

        await ctx.reply(
            t("ban.updated_block", locale, user_id=user_id),
            mention_author=False,
        )

    @commands.command(
        name="unblockchat",
        aliases=["unban", "unblock", "bỏcấm", "removeban"],
        help="Unblock a user from chatting with the AI bot",
    )
    async def unblock_user(
        self,
        ctx: commands.Context[commands.Bot],
        target: str,
    ) -> None:
        locale = await self._get_locale(ctx)
        user_id = self._parse_user_id(target)
        if user_id is None:
            await ctx.reply(t("permissions.invalid_user", locale), mention_author=False)
            return

        if not await self._ensure_owner_permission(ctx):
            return

        guild = cast(discord.Guild, ctx.guild)
        removed = await self.store.unban_user(guild.id, user_id)
        if removed:
            await ctx.reply(
                t("ban.unblocked", locale, user_id=user_id),
                mention_author=False,
            )
            return

        await ctx.reply(
            t("ban.not_blocked", locale, user_id=user_id),
            mention_author=False,
        )

    async def cog_command_error(
        self,
        ctx: commands.Context[commands.Bot],
        error: commands.CommandError,
    ) -> None:
        locale = detect_language(str(ctx.message.content))
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(t("ban.missing_argument", locale, param=error.param.name), mention_author=False)
        else:
            await ctx.reply(t("ban.error_occurred", locale, error=error), mention_author=False)


async def setup(bot: commands.Bot) -> None:
    settings = cast(Settings, getattr(bot, "settings"))
    await bot.add_cog(BanControlCog(bot, settings))

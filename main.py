from __future__ import annotations

import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from config import Settings, get_settings
from utils import auto_merge_dotenv


class MikuAIBot(commands.Bot):
    def __init__(self, settings: Settings):
        if not hasattr(discord, "Intents"):
            module_path = getattr(discord, "__file__", "unknown location")
            raise RuntimeError(
                "The imported 'discord' module is not discord.py 2.x "
                f"(loaded from {module_path}). Remove conflicting Discord packages "
                "and reinstall requirements.txt with this Python interpreter."
            )
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=settings.command_prefix,
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
            allowed_mentions=discord.AllowedMentions.none(),
            owner_id=settings.owner_id,
        )
        self.settings = settings

    async def setup_hook(self) -> None:
        cogs_dir = Path(__file__).parent / "cogs"
        for file in sorted(cogs_dir.glob("*.py")):
            if file.name.startswith("_"):
                continue
            await self.load_extension(f"cogs.{file.stem}")
        
        print("Loaded cogs:", list(self.cogs.keys()))
        print("Commands:", [c.name for c in self.commands])

        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")

    async def on_ready(self) -> None:
        user = self.user
        user_id = user.id if user else "unknown"
        print(f"Logged in as {user} (ID: {user_id})")
        if self.owner_id:
            print(f"Owner ID: {self.owner_id}")
        elif self.owner_ids:
            print(f"Owner IDs: {list(self.owner_ids)}")
        
        print("Provider: NVIDIA NIM")
        print(f"Model: {self._active_chat_model()}")
        print("---")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            print(f"[CommandNotFound] User {ctx.author} tried to use unknown command '{ctx.invoked_with}'. Full message: {ctx.message.content}")
        else:
            print(f"[CommandError] {ctx.command}: {error}")
            try:
                from i18n import t, detect_language
                locale = detect_language(ctx.message.content)
                await ctx.reply(t("errors.generic", locale, error=error), mention_author=False)
            except discord.HTTPException:
                pass

    def _active_chat_model(self) -> str:
        return self.settings.nvidia_model


async def main() -> None:
    auto_merge_dotenv()
    settings = get_settings()
    bot = MikuAIBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

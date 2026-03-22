from __future__ import annotations

import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from config import Settings, get_settings
from utils import auto_merge_dotenv


class MikuAIBot(commands.Bot):
    def __init__(self, settings: Settings):
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
        
        print(f"Provider: {self.settings.provider}")
        print(f"Model: {self._active_chat_model()}")
        print("---")

    def _active_chat_model(self) -> str:
        if self.settings.provider == "gemini":
            return self.settings.gemini_model
        if self.settings.provider == "groq":
            return self.settings.groq_model
        if self.settings.provider == "openai":
            return self.settings.openai_model
        if self.settings.provider == "local":
            return self.settings.local_model
        return "unknown"


async def main() -> None:
    auto_merge_dotenv()
    settings = get_settings()
    bot = MikuAIBot(settings)
    await bot.start(settings.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

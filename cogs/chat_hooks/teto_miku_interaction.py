from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import discord
from discord.ext import commands

from config import Settings


@dataclass(slots=True)
class PendingDualMention:
    created_at: float
    trigger_message_id: int


class TetoMikuDualMentionHook:
    TETO_FEAR_LINES = [
        "Oh... <@{miku_id}>, you are here too?",
        "I heard you, Miku. You speak first...",
        "Wait, please do not look at me like that...",
        "I will behave, I am not messing around...",
        "Can I stand a bit farther away...?",
        "Okay... I will answer after you...",
        "Alright, I will be good. Please do not scold me...",
    ]
    MIKU_TEASE_LINES = [
        "Hey <@{teto_id}>, relax. I run this chat now.",
        "If there is drama, I will win it in one verse.",
        "Teto, keep up. English mode is on.",
        "User tagged both of us, so I speak first as usual.",
        "No panic. Follow my tempo.",
        "Stay sharp, Kasane. I am watching.",
        "Alright chat, Miku has the floor.",
    ]

    def __init__(self, bot: commands.Bot, settings: Settings):
        self.bot = bot
        self.settings = settings
        self.pending_by_channel: dict[int, PendingDualMention] = {}
        self.active_channels: set[int] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def handle_message(self, message: discord.Message) -> bool:
        if not self.settings.dual_mention_hook_enabled:
            return False

        me = self.bot.user
        if me is None:
            return False

        self._expire_pending()
        if message.channel.id in self.active_channels:
            return False

        if me.id == self.settings.teto_bot_id:
            return await self._handle_as_teto(message)
        if me.id == self.settings.miku_bot_id:
            return await self._handle_as_miku(message)
        return False

    async def aclose(self) -> None:
        if not self._tasks:
            return
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def _expire_pending(self) -> None:
        now = time.monotonic()
        timeout = float(self.settings.teto_wait_miku_timeout_seconds)
        expired_channels = [
            channel_id
            for channel_id, pending in self.pending_by_channel.items()
            if now - pending.created_at > timeout
        ]
        for channel_id in expired_channels:
            self.pending_by_channel.pop(channel_id, None)

    async def _handle_as_teto(self, message: discord.Message) -> bool:
        if message.author.bot:
            return await self._handle_teto_bot_message(message)

        if self._is_dual_mention_trigger(message):
            self.pending_by_channel[message.channel.id] = PendingDualMention(
                created_at=time.monotonic(),
                trigger_message_id=message.id,
            )
            # Suppress default auto-reply from Teto. We wait for Miku to speak first.
            return True

        return False

    async def _handle_as_miku(self, message: discord.Message) -> bool:
        if message.author.bot:
            return False
        if not self._is_dual_mention_trigger(message):
            return False

        task = asyncio.create_task(
            self._run_sequence(
                channel=message.channel,
                channel_id=message.channel.id,
                trigger_message_id=message.id,
                lines=self._build_miku_tease_lines(),
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        # Suppress default mention auto-reply so Miku follows hidden interaction script.
        return True

    async def _handle_teto_bot_message(self, message: discord.Message) -> bool:
        if message.author.id != self.settings.miku_bot_id:
            return False

        pending = self.pending_by_channel.pop(message.channel.id, None)
        if pending is None:
            return False

        task = asyncio.create_task(
            self._run_sequence(
                channel=message.channel,
                channel_id=message.channel.id,
                trigger_message_id=pending.trigger_message_id,
                lines=self._build_teto_fear_lines(),
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return False

    async def _run_sequence(
        self,
        *,
        channel: discord.abc.Messageable,
        channel_id: int,
        trigger_message_id: int,
        lines: list[str],
    ) -> None:
        self.active_channels.add(channel_id)
        try:
            for index, line in enumerate(lines):
                delay_seconds = 0.8 if index == 0 else 1.2
                async with channel.typing():
                    await asyncio.sleep(delay_seconds)
                await channel.send(
                    line,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except Exception as exc:
            print(
                "[teto-miku-hook] failed to run sequence "
                f"(channel={channel_id}, trigger={trigger_message_id}): {exc}"
            )
        finally:
            self.active_channels.discard(channel_id)

    def _build_teto_fear_lines(self) -> list[str]:
        target_count = max(1, self.settings.teto_fear_message_count)
        base_lines = [
            template.format(miku_id=self.settings.miku_bot_id)
            for template in self.TETO_FEAR_LINES
        ]
        return self._expand_lines(base_lines, target_count)

    def _build_miku_tease_lines(self) -> list[str]:
        target_count = max(1, self.settings.teto_fear_message_count)
        base_lines = [
            template.format(teto_id=self.settings.teto_bot_id)
            for template in self.MIKU_TEASE_LINES
        ]
        return self._expand_lines(base_lines, target_count)

    def _expand_lines(self, base_lines: list[str], target_count: int) -> list[str]:
        if target_count <= len(base_lines):
            return base_lines[:target_count]
        extended = list(base_lines)
        while len(extended) < target_count:
            extended.extend(base_lines)
        return extended[:target_count]

    def _is_dual_mention_trigger(self, message: discord.Message) -> bool:
        mention_ids = {member.id for member in message.mentions}
        return (
            self.settings.teto_bot_id in mention_ids
            and self.settings.miku_bot_id in mention_ids
        )

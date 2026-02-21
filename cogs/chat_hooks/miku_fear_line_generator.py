from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable

import discord
from discord.ext import commands

from client import LLMClient
from config import Settings


class MikuFearLineGenerator:
    HOOK_LINE_PREFIX_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")
    MATERIAL_WORD_PATTERN = re.compile(r"[A-Za-z0-9']{4,}")
    MATERIAL_STOPWORDS = {
        "this",
        "that",
        "with",
        "from",
        "your",
        "have",
        "will",
        "just",
        "what",
        "when",
        "where",
        "which",
        "about",
        "please",
    }

    def __init__(
        self,
        *,
        client: LLMClient,
        settings: Settings,
        normalize_model_reply: Callable[[str], str],
    ) -> None:
        self.client = client
        self.settings = settings
        self.normalize_model_reply = normalize_model_reply

    async def generate_miku_tease_lines(
        self,
        message: discord.Message,
        line_count: int,
    ) -> list[str]:
        content = message.clean_content.strip() or message.content.strip() or "(empty)"
        material_words = self._extract_material_words(content)
        prompt = self._build_miku_tease_prompt(
            content=content,
            line_count=line_count,
            material_words=material_words,
            trigger_user_id=message.author.id,
        )
        raw = await self.client.generate([{"role": "user", "content": prompt}])
        return self._parse_lines(
            raw_output=raw,
            line_count=line_count,
            required_mention_id=self.settings.teto_bot_id,
            material_words=material_words,
        )

    def _build_miku_tease_prompt(
        self,
        *,
        content: str,
        line_count: int,
        material_words: list[str],
        trigger_user_id: int,
    ) -> str:
        material_hint = ", ".join(material_words) if material_words else "none"
        return (
            "[hidden_hook:miku_fear]\n"
            "Context: user mentioned both Teto and Miku in the same message.\n"
            "Behavior: Miku speaks first and intimidates Teto with controlled threats.\n"
            f"Session turn: 1/{line_count}\n"
            f"Trigger user id: {trigger_user_id}\n"
            "KProfessional assertiveness.\n"
            "Teto message:\n"
            f"{content}\n"
            "Output requirements:\n"
            f"- Write exactly {line_count} short lines.\n"
            "- English only.\n"
            "- Tone: dominant, intimidating, sharp. No gore, no real-world violence.\n"
            "- No markdown, no numbering, no bullet points.\n"
            "- One line per sentence, max 120 characters per line.\n"
            f"- First line must include <@{self.settings.teto_bot_id}>.\n"
            "- At least 2 lines must reuse/remix words or ideas from Teto message.\n"
            f"- Preferred material words: {material_hint}.\n"
            "Return only the lines."
        )

    def _parse_lines(
        self,
        *,
        raw_output: str,
        line_count: int,
        required_mention_id: int,
        material_words: list[str],
    ) -> list[str]:
        normalized = self.normalize_model_reply(raw_output).strip()
        if not normalized:
            raise RuntimeError("Hook line generator returned empty output.")

        lines = self._extract_lines_from_text(normalized)
        if not lines:
            raise RuntimeError("Hook line generator returned unparseable output.")

        mention_token = f"<@{required_mention_id}>"
        if mention_token not in " ".join(lines):
            lines[0] = f"{mention_token} {lines[0]}"

        if material_words and not self._has_material_overlap(lines, material_words):
            raise RuntimeError("Hook line generator ignored user material words.")

        return self._expand_lines(lines, line_count)

    def _extract_lines_from_text(self, text: str) -> list[str]:
        candidate = text.strip()
        parsed_lines: list[str] = []

        if candidate.startswith("[") or candidate.startswith("{"):
            try:
                decoded = json.loads(candidate)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                parsed_lines.extend(str(item).strip() for item in decoded)
            elif isinstance(decoded, dict):
                lines_obj = decoded.get("lines")
                if isinstance(lines_obj, list):
                    parsed_lines.extend(str(item).strip() for item in lines_obj)
                else:
                    answer_obj = decoded.get("answer")
                    if isinstance(answer_obj, str):
                        candidate = answer_obj

        if not parsed_lines:
            candidate = candidate.replace("```", "").strip()
            for raw_line in candidate.splitlines():
                cleaned = self.HOOK_LINE_PREFIX_PATTERN.sub("", raw_line).strip()
                if cleaned:
                    parsed_lines.append(cleaned)

        return [line for line in parsed_lines if line]

    def _extract_material_words(self, text: str) -> list[str]:
        raw_words = self.MATERIAL_WORD_PATTERN.findall(text.lower())
        material: list[str] = []
        for word in raw_words:
            if word in self.MATERIAL_STOPWORDS:
                continue
            if word in material:
                continue
            material.append(word)
            if len(material) >= 8:
                break
        return material

    def _has_material_overlap(self, lines: list[str], material_words: list[str]) -> bool:
        haystack = " ".join(lines).lower()
        for word in material_words[:5]:
            if word in haystack:
                return True
        return False

    def _expand_lines(self, lines: list[str], target_count: int) -> list[str]:
        if target_count <= len(lines):
            return lines[:target_count]
        expanded = list(lines)
        while len(expanded) < target_count:
            expanded.extend(lines)
        return expanded[:target_count]

class TetoMikuDualMentionHook:
    def __init__(
        self,
        bot: commands.Bot,
        settings: Settings,
        build_miku_tease_lines: Callable[
            [discord.Message, int],
            Awaitable[list[str]],
        ]
        | None = None,
    ):
        self.bot = bot
        self.settings = settings
        self.build_miku_tease_lines = build_miku_tease_lines
        self.active_channels: set[int] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def handle_message(self, message: discord.Message) -> bool:
        if not self.settings.dual_mention_hook_enabled:
            return False

        me = self.bot.user
        if me is None:
            return False

        if me.id != self.settings.miku_bot_id:
            return False

        if message.channel.id in self.active_channels:
            return False

        return await self._handle_as_miku(message)

    async def aclose(self) -> None:
        if not self._tasks:
            return
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _handle_as_miku(self, message: discord.Message) -> bool:
        if message.author.bot:
            return False
        if not self._is_dual_mention_trigger(message):
            return False

        task = asyncio.create_task(self._run_miku_sequence(message))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        # Suppress default mention auto-reply so Miku follows hidden interaction script.
        return True

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

    async def _run_miku_sequence(self, message: discord.Message) -> None:
        lines = await self._build_miku_tease_lines(message)
        if not lines:
            return
        await self._run_sequence(
            channel=message.channel,
            channel_id=message.channel.id,
            trigger_message_id=message.id,
            lines=lines,
        )

    async def _build_miku_tease_lines(self, message: discord.Message) -> list[str]:
        target_count = max(1, self.settings.teto_fear_message_count)
        if self.build_miku_tease_lines is None:
            print("[teto-miku-hook] API-only tease mode: missing generator callback.")
            return []
        try:
            dynamic_lines = await self.build_miku_tease_lines(message, target_count)
            normalized = [line.strip() for line in dynamic_lines if line.strip()]
            if not normalized:
                return []
            return self._expand_lines(normalized, target_count)
        except Exception as exc:
            print(f"[teto-miku-hook] tease generation failed: {exc}")
            return []

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

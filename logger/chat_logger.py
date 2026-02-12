from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class ChatReplayLogger:
    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self._lock = asyncio.Lock()
        self._next_id = 1

    async def initialize(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    async def log_chat(
        self,
        *,
        guild_id: int | None,
        guild_name: str | None,
        channel_id: int,
        channel_name: str | None,
        user_id: int,
        user_name: str,
        user_display: str,
        trigger: str,
        prompt: str,
        reply_length: int,
    ) -> None:
        async with self._lock:
            record_id = self._next_id
            self._next_id += 1

            record = {
                "id": record_id,
                "type": "chat",
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "guild_id": guild_id,
                "guild_name": guild_name,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "user_id": user_id,
                "user_name": user_name,
                "user_display": user_display,
                "trigger": trigger,
                "prompt": prompt[:600],
                "reply_length": reply_length,
            }
            line = json.dumps(record, ensure_ascii=False)
            await asyncio.to_thread(self._append_line_sync, line)

    async def read_recent(
        self,
        *,
        limit: int,
        guild_id: int | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, limit)
        async with self._lock:
            return await asyncio.to_thread(
                self._read_recent_sync,
                safe_limit,
                guild_id,
            )

    async def read_recent_indexed(
        self,
        *,
        limit: int,
        guild_id: int | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        safe_limit = max(1, limit)
        async with self._lock:
            return await asyncio.to_thread(
                self._read_recent_indexed_sync,
                safe_limit,
                guild_id,
            )

    async def get_by_index(
        self,
        *,
        record_id: int,
        guild_id: int | None = None,
    ) -> dict[str, Any] | None:
        if record_id <= 0:
            return None
        async with self._lock:
            return await asyncio.to_thread(
                self._get_by_index_sync,
                record_id,
                guild_id,
            )

    def _initialize_sync(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()
            self._next_id = 1
            return

        max_id = 0
        for idx, _ in self._iter_chat_records_sync():
            if idx > max_id:
                max_id = idx
        self._next_id = max_id + 1

    def _append_line_sync(self, line: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fp:
            fp.write(line)
            fp.write("\n")

    def _read_recent_sync(
        self,
        limit: int,
        guild_id: int | None,
    ) -> list[dict[str, Any]]:
        indexed = self._read_recent_indexed_sync(limit=limit, guild_id=guild_id)
        return [item[1] for item in indexed]

    def _read_recent_indexed_sync(
        self,
        limit: int,
        guild_id: int | None,
    ) -> list[tuple[int, dict[str, Any]]]:
        # Keep only the most recent `limit` records in memory.
        latest: deque[tuple[int, dict[str, Any]]] = deque(maxlen=limit)
        for idx, item in self._iter_chat_records_sync(guild_id=guild_id):
            latest.append((idx, item))

        records = list(latest)
        records.reverse()
        return records

    def _get_by_index_sync(
        self,
        record_id: int,
        guild_id: int | None,
    ) -> dict[str, Any] | None:
        for idx, item in self._iter_chat_records_sync(guild_id=guild_id):
            if idx == record_id:
                return item
            if idx > record_id:
                break
        return None

    def _iter_chat_records_sync(
        self,
        guild_id: int | None = None,
    ) -> Iterable[tuple[int, dict[str, Any]]]:
        if not self.log_path.exists():
            return

        fallback_id = 0
        with self.log_path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                line = raw.strip()
                if not line:
                    continue

                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not isinstance(item, dict):
                    continue
                if item.get("type") != "chat":
                    continue

                raw_id = item.get("id")
                if isinstance(raw_id, int) and raw_id > 0:
                    record_id = raw_id
                    if record_id > fallback_id:
                        fallback_id = record_id
                else:
                    fallback_id += 1
                    record_id = fallback_id

                if guild_id is not None and item.get("guild_id") != guild_id:
                    continue

                yield record_id, item

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite


class ShortTermMemoryStore:
    def __init__(self, db_path: str, max_history_turns: int):
        self.db_path = db_path
        self.max_messages = max(2, max_history_turns * 2)
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_banned_users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                banned_by INTEGER,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_call_preferences (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_calls_miku TEXT,
                miku_calls_user TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_memory_channel_id_id ON chat_memory (channel_id, id)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bot_banned_users_guild_user ON bot_banned_users (guild_id, user_id)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_call_preferences_guild_user ON user_call_preferences (guild_id, user_id)"
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def append_message(self, channel_id: int, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError(f"Invalid role: {role}")

        async with self._lock:
            conn = self._require_conn()
            await conn.execute(
                "INSERT INTO chat_memory (channel_id, role, content) VALUES (?, ?, ?)",
                (channel_id, role, content),
            )
            await self._trim_channel(channel_id)
            await conn.commit()

    async def get_history(self, channel_id: int) -> list[dict[str, str]]:
        async with self._lock:
            conn = self._require_conn()
            cursor = await conn.execute(
                """
                SELECT role, content
                FROM chat_memory
                WHERE channel_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (channel_id, self.max_messages),
            )
            rows = await cursor.fetchall()
            await cursor.close()

        rows.reverse()
        return [{"role": row[0], "content": row[1]} for row in rows]

    async def clear_channel(self, channel_id: int) -> None:
        async with self._lock:
            conn = self._require_conn()
            await conn.execute("DELETE FROM chat_memory WHERE channel_id = ?", (channel_id,))
            await conn.commit()

    async def ban_user(
        self,
        guild_id: int,
        user_id: int,
        banned_by: int | None = None,
        reason: str | None = None,
    ) -> bool:
        async with self._lock:
            conn = self._require_conn()
            cursor = await conn.execute(
                """
                SELECT 1
                FROM bot_banned_users
                WHERE guild_id = ? AND user_id = ?
                LIMIT 1
                """,
                (guild_id, user_id),
            )
            existed = await cursor.fetchone() is not None
            await cursor.close()

            await conn.execute(
                """
                INSERT INTO bot_banned_users (guild_id, user_id, banned_by, reason)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    banned_by = excluded.banned_by,
                    reason = excluded.reason,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (guild_id, user_id, banned_by, reason),
            )
            await conn.commit()
            return not existed

    async def unban_user(self, guild_id: int, user_id: int) -> bool:
        async with self._lock:
            conn = self._require_conn()
            cursor = await conn.execute(
                "DELETE FROM bot_banned_users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            affected = cursor.rowcount
            await cursor.close()
            await conn.commit()
            return affected > 0

    async def is_user_banned(self, guild_id: int, user_id: int) -> bool:
        async with self._lock:
            conn = self._require_conn()
            cursor = await conn.execute(
                """
                SELECT 1
                FROM bot_banned_users
                WHERE guild_id = ? AND user_id = ?
                LIMIT 1
                """,
                (guild_id, user_id),
            )
            banned = await cursor.fetchone() is not None
            await cursor.close()
            return banned

    async def set_user_calls_miku(
        self,
        guild_id: int,
        user_id: int,
        call_name: str,
    ) -> None:
        async with self._lock:
            conn = self._require_conn()
            await conn.execute(
                """
                INSERT INTO user_call_preferences (guild_id, user_id, user_calls_miku)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    user_calls_miku = excluded.user_calls_miku,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (guild_id, user_id, call_name),
            )
            await conn.commit()

    async def set_miku_calls_user(
        self,
        guild_id: int,
        user_id: int,
        call_name: str,
    ) -> None:
        async with self._lock:
            conn = self._require_conn()
            await conn.execute(
                """
                INSERT INTO user_call_preferences (guild_id, user_id, miku_calls_user)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    miku_calls_user = excluded.miku_calls_user,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (guild_id, user_id, call_name),
            )
            await conn.commit()

    async def get_user_call_preferences(
        self,
        guild_id: int,
        user_id: int,
    ) -> tuple[str | None, str | None]:
        async with self._lock:
            conn = self._require_conn()
            cursor = await conn.execute(
                """
                SELECT user_calls_miku, miku_calls_user
                FROM user_call_preferences
                WHERE guild_id = ? AND user_id = ?
                LIMIT 1
                """,
                (guild_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                return None, None
            return row[0], row[1]

    async def prune_inactive_channels(self, idle_seconds: int) -> None:
        if idle_seconds <= 0:
            return

        async with self._lock:
            conn = self._require_conn()
            await conn.execute(
                """
                DELETE FROM chat_memory
                WHERE channel_id IN (
                    SELECT channel_id
                    FROM chat_memory
                    GROUP BY channel_id
                    HAVING MAX(created_at) < datetime('now', ?)
                )
                """,
                (f"-{idle_seconds} seconds",),
            )
            await conn.commit()

    async def _trim_channel(self, channel_id: int) -> None:
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT id
            FROM chat_memory
            WHERE channel_id = ?
            ORDER BY id DESC
            LIMIT 1 OFFSET ?
            """,
            (channel_id, self.max_messages - 1),
        )
        row = await cursor.fetchone()
        await cursor.close()

        if row is None:
            return

        cutoff_id = row[0]
        await conn.execute(
            "DELETE FROM chat_memory WHERE channel_id = ? AND id < ?",
            (channel_id, cutoff_id),
        )

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Memory store is not initialized")
        return self._conn

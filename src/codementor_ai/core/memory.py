"""SQLite-backed conversation memory for CodeMentor sessions."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class MemoryMessage:
    role: str
    content: str
    created_at: str


class SQLiteMemory:
    """Persist small, auditable session transcripts without an external service."""

    def __init__(self, database_path: str = "codementor.db") -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)"
            )
            # What the chat box shows, per project: the prompts as typed and the final answers.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_project ON chat_messages(project, id)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def add(self, session_id: str, role: str, content: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, datetime.now(timezone.utc).isoformat()),
            )

    def recent(self, session_id: str, limit: int = 12) -> List[MemoryMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at FROM messages
                WHERE session_id = ? ORDER BY id DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [MemoryMessage(*row) for row in reversed(rows)]

    def clear(self, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

    def add_chat(self, project: str, role: str, content: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO chat_messages(project, role, content, created_at) VALUES (?, ?, ?, ?)",
                (project, role, content, datetime.now(timezone.utc).isoformat()),
            )

    def chat_history(self, project: str, limit: int = 200) -> List[MemoryMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at FROM chat_messages
                WHERE project = ? ORDER BY id DESC LIMIT ?
                """,
                (project, limit),
            ).fetchall()
        return [MemoryMessage(*row) for row in reversed(rows)]

    def rename_project(self, old: str, new: str) -> None:
        """Keep a project's chat history and agent session when its folder is renamed."""
        with self._connect() as connection:
            connection.execute("UPDATE chat_messages SET project = ? WHERE project = ?", (new, old))
            connection.execute(
                "UPDATE messages SET session_id = ? WHERE session_id = ?",
                (f"project:{new}", f"project:{old}"),
            )

    def clear_chat(self, project: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM chat_messages WHERE project = ?", (project,))
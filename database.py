"""Database management for the Telegram Summary Bot."""
import aiosqlite
from datetime import datetime
from typing import List, Optional, Tuple
from config import DATABASE_PATH


class Database:
    """Async database manager for storing user data, channels, and settings."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    summary_period INTEGER DEFAULT 1,
                    last_summary TIMESTAMP
                )
            ''')

            # Channels table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_username TEXT NOT NULL,
                    channel_id INTEGER,
                    channel_title TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_message_date TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    UNIQUE(user_id, channel_username)
                )
            ''')

            await db.commit()

    async def add_user(self, user_id: int, username: Optional[str], first_name: Optional[str]):
        """Add or update a user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
            ''', (user_id, username, first_name))
            await db.commit()

    async def add_channel(self, user_id: int, channel_username: str,
                         channel_id: Optional[int] = None,
                         channel_title: Optional[str] = None) -> bool:
        """Add a channel to user's tracking list. Returns True if added, False if already exists."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO channels (user_id, channel_username, channel_id, channel_title)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, channel_username, channel_id, channel_title))
                await db.commit()
                return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_channel(self, user_id: int, channel_username: str) -> bool:
        """Remove a channel from user's tracking list. Returns True if removed."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                DELETE FROM channels
                WHERE user_id = ? AND channel_username = ?
            ''', (user_id, channel_username))
            await db.commit()
            return cursor.rowcount > 0

    async def get_user_channels(self, user_id: int) -> List[Tuple[str, str, datetime]]:
        """Get all channels tracked by a user. Returns list of (username, title, added_at)."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT channel_username, channel_title, added_at
                FROM channels
                WHERE user_id = ?
                ORDER BY added_at DESC
            ''', (user_id,)) as cursor:
                return await cursor.fetchall()

    async def set_summary_period(self, user_id: int, period_days: int):
        """Set the summary period for a user (in days)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users
                SET summary_period = ?
                WHERE user_id = ?
            ''', (period_days, user_id))
            await db.commit()

    async def get_summary_period(self, user_id: int) -> int:
        """Get the summary period for a user (in days). Default is 1."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT summary_period FROM users WHERE user_id = ?
            ''', (user_id,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 1

    async def update_last_summary(self, user_id: int):
        """Update the last summary timestamp for a user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users
                SET last_summary = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            await db.commit()

    async def get_users_for_summary(self) -> List[Tuple[int, str, int, datetime]]:
        """Get users who need a summary. Returns list of (user_id, username, period_days, last_summary)."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT user_id, username, summary_period, last_summary
                FROM users
                WHERE (
                    last_summary IS NULL
                    OR date(last_summary, '+' || summary_period || ' days') <= date('now')
                )
            ''') as cursor:
                return await cursor.fetchall()

    async def update_channel_info(self, user_id: int, channel_username: str,
                                  channel_id: int, channel_title: str):
        """Update channel information."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE channels
                SET channel_id = ?, channel_title = ?
                WHERE user_id = ? AND channel_username = ?
            ''', (channel_id, channel_title, user_id, channel_username))
            await db.commit()

    async def update_channel_last_message(self, user_id: int, channel_username: str,
                                         last_message_date: datetime):
        """Update the last message date for a channel."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE channels
                SET last_message_date = ?
                WHERE user_id = ? AND channel_username = ?
            ''', (last_message_date, user_id, channel_username))
            await db.commit()

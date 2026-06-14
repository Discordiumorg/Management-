import aiosqlite
import json
from datetime import datetime, timezone

DB_PATH = "staff_management.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS infractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                type TEXT NOT NULL,
                reason TEXT NOT NULL,
                moderator_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                expires_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                content TEXT NOT NULL,
                moderator_id TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                duration TEXT NOT NULL,
                reason TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_counts (
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                last_updated TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                position TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                timestamp TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS staff_config (
                guild_id TEXT PRIMARY KEY,
                log_channel_id TEXT,
                promotion_channel_id TEXT,
                demotion_channel_id TEXT,
                termination_channel_id TEXT,
                infractions_channel_id TEXT,
                applications_channel_id TEXT,
                staff_roles_json TEXT DEFAULT '[]',
                leader_roles_json TEXT DEFAULT '[]',
                admin_roles_json TEXT DEFAULT '[]',
                apply_positions_json TEXT DEFAULT '[]'
            )
        """)
        await db.commit()


async def get_config(guild_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM staff_config WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {
                    "guild_id": guild_id,
                    "log_channel_id": None,
                    "promotion_channel_id": None,
                    "demotion_channel_id": None,
                    "termination_channel_id": None,
                    "infractions_channel_id": None,
                    "applications_channel_id": None,
                    "staff_roles_json": "[]",
                    "leader_roles_json": "[]",
                    "admin_roles_json": "[]",
                    "apply_positions_json": "[]",
                }
            return dict(row)


async def set_config(guild_id: str, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        existing = await get_config(guild_id)
        existing.update(kwargs)
        await db.execute("""
            INSERT OR REPLACE INTO staff_config
            (guild_id, log_channel_id, promotion_channel_id, demotion_channel_id,
             termination_channel_id, infractions_channel_id, applications_channel_id,
             staff_roles_json, leader_roles_json, admin_roles_json, apply_positions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            guild_id,
            existing.get("log_channel_id"),
            existing.get("promotion_channel_id"),
            existing.get("demotion_channel_id"),
            existing.get("termination_channel_id"),
            existing.get("infractions_channel_id"),
            existing.get("applications_channel_id"),
            existing.get("staff_roles_json", "[]"),
            existing.get("leader_roles_json", "[]"),
            existing.get("admin_roles_json", "[]"),
            existing.get("apply_positions_json", "[]"),
        ))
        await db.commit()


async def add_infraction(user_id: str, guild_id: str, infraction_type: str, reason: str, moderator_id: str, expires_at: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO infractions (user_id, guild_id, type, reason, moderator_id, timestamp, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, guild_id, infraction_type, reason, moderator_id, datetime.now(timezone.utc).isoformat(), expires_at)
        )
        await db.commit()


async def get_infractions(user_id: str, guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.now(timezone.utc).isoformat()
        async with db.execute(
            "SELECT * FROM infractions WHERE user_id = ? AND guild_id = ? AND (expires_at IS NULL OR expires_at > ?) ORDER BY timestamp DESC",
            (user_id, guild_id, now)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def add_note(user_id: str, guild_id: str, content: str, moderator_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notes (user_id, guild_id, content, moderator_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, guild_id, content, moderator_id, datetime.now(timezone.utc).isoformat())
        )
        await db.commit()


async def get_notes(user_id: str, guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM notes WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC",
            (user_id, guild_id)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def set_loa(user_id: str, guild_id: str, duration: str, reason: str, end_date: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE loa SET active = 0 WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        await db.execute(
            "INSERT INTO loa (user_id, guild_id, duration, reason, start_date, end_date, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
            (user_id, guild_id, duration, reason, datetime.now(timezone.utc).isoformat(), end_date)
        )
        await db.commit()


async def remove_loa(user_id: str, guild_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE loa SET active = 0 WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        await db.commit()


async def get_active_loa(user_id: str, guild_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM loa WHERE user_id = ? AND guild_id = ? AND active = 1",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def increment_message_count(user_id: str, guild_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO message_counts (user_id, guild_id, count, last_updated)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET count = count + 1, last_updated = ?
        """, (user_id, guild_id, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
        await db.commit()


async def get_message_count(user_id: str, guild_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM message_counts WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_leaderboard(guild_id: str, limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, count FROM message_counts WHERE guild_id = ? ORDER BY count DESC LIMIT ?",
            (guild_id, limit)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def add_application(user_id: str, guild_id: str, position: str, answers: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO applications (user_id, guild_id, position, answers_json, status, timestamp) VALUES (?, ?, ?, ?, 'pending', ?)",
            (user_id, guild_id, position, json.dumps(answers), datetime.now(timezone.utc).isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def update_application_status(app_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE applications SET status = ? WHERE id = ?", (status, app_id))
        await db.commit()


async def get_application(app_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

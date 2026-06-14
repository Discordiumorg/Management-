import asyncpg
import json
import os
from datetime import datetime, timezone
from typing import Optional

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


async def init_db():
    global _pool
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    # Railway sometimes provides postgres:// — asyncpg needs postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    _pool = await asyncpg.create_pool(url, min_size=1, max_size=10)

    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS infractions (
                id          SERIAL PRIMARY KEY,
                user_id     TEXT NOT NULL,
                guild_id    TEXT NOT NULL,
                type        TEXT NOT NULL,
                reason      TEXT NOT NULL,
                moderator_id TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                expires_at  TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id           SERIAL PRIMARY KEY,
                user_id      TEXT NOT NULL,
                guild_id     TEXT NOT NULL,
                content      TEXT NOT NULL,
                moderator_id TEXT NOT NULL,
                timestamp    TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS loa (
                id         SERIAL PRIMARY KEY,
                user_id    TEXT NOT NULL,
                guild_id   TEXT NOT NULL,
                duration   TEXT NOT NULL,
                reason     TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date   TEXT,
                active     INTEGER DEFAULT 1
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS message_counts (
                user_id      TEXT NOT NULL,
                guild_id     TEXT NOT NULL,
                count        BIGINT DEFAULT 0,
                last_updated TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id           SERIAL PRIMARY KEY,
                user_id      TEXT NOT NULL,
                guild_id     TEXT NOT NULL,
                position     TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                status       TEXT DEFAULT 'pending',
                timestamp    TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_config (
                guild_id                TEXT PRIMARY KEY,
                log_channel_id          TEXT,
                promotion_channel_id    TEXT,
                demotion_channel_id     TEXT,
                termination_channel_id  TEXT,
                infractions_channel_id  TEXT,
                applications_channel_id TEXT,
                announce_channel_id     TEXT,
                staff_roles_json        TEXT DEFAULT '[]',
                leader_roles_json       TEXT DEFAULT '[]',
                admin_roles_json        TEXT DEFAULT '[]',
                hr_roles_json           TEXT DEFAULT '[]',
                apply_positions_json    TEXT DEFAULT '[]',
                linked_guild_id         TEXT,
                linked_staff_roles_json TEXT DEFAULT '[]',
                duty_role_id            TEXT,
                strike_threshold        INTEGER DEFAULT 3,
                strike_action           TEXT DEFAULT 'terminate'
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id        SERIAL PRIMARY KEY,
                guild_id  TEXT NOT NULL,
                user_id   TEXT NOT NULL,
                actor_id  TEXT NOT NULL,
                action    TEXT NOT NULL,
                detail    TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS duty (
                user_id  TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                on_duty  INTEGER DEFAULT 0,
                since    TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        """)

        # Add missing columns to existing tables (safe migrations)
        migrations = [
            ("staff_config", "hr_roles_json",           "TEXT DEFAULT '[]'"),
            ("staff_config", "linked_guild_id",          "TEXT"),
            ("staff_config", "linked_staff_roles_json",  "TEXT DEFAULT '[]'"),
            ("staff_config", "duty_role_id",             "TEXT"),
            ("staff_config", "strike_threshold",         "INTEGER DEFAULT 3"),
            ("staff_config", "strike_action",            "TEXT DEFAULT 'terminate'"),
            ("staff_config", "announce_channel_id",      "TEXT"),
        ]
        for table, col, coltype in migrations:
            try:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}")
            except Exception:
                pass


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ── Config ────────────────────────────────────────────────────────────────────

def _default_config(guild_id: str) -> dict:
    return {
        "guild_id": guild_id,
        "log_channel_id": None,
        "promotion_channel_id": None,
        "demotion_channel_id": None,
        "termination_channel_id": None,
        "infractions_channel_id": None,
        "applications_channel_id": None,
        "announce_channel_id": None,
        "staff_roles_json": "[]",
        "leader_roles_json": "[]",
        "admin_roles_json": "[]",
        "hr_roles_json": "[]",
        "apply_positions_json": "[]",
        "linked_guild_id": None,
        "linked_staff_roles_json": "[]",
        "duty_role_id": None,
        "strike_threshold": 3,
        "strike_action": "terminate",
    }


async def get_config(guild_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM staff_config WHERE guild_id = $1", guild_id)
        return dict(row) if row else _default_config(guild_id)


async def set_config(guild_id: str, **kwargs):
    pool = await get_pool()
    existing = await get_config(guild_id)
    existing.update(kwargs)
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO staff_config
                (guild_id, log_channel_id, promotion_channel_id, demotion_channel_id,
                 termination_channel_id, infractions_channel_id, applications_channel_id,
                 announce_channel_id, staff_roles_json, leader_roles_json, admin_roles_json,
                 hr_roles_json, apply_positions_json, linked_guild_id, linked_staff_roles_json,
                 duty_role_id, strike_threshold, strike_action)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
            ON CONFLICT (guild_id) DO UPDATE SET
                log_channel_id          = EXCLUDED.log_channel_id,
                promotion_channel_id    = EXCLUDED.promotion_channel_id,
                demotion_channel_id     = EXCLUDED.demotion_channel_id,
                termination_channel_id  = EXCLUDED.termination_channel_id,
                infractions_channel_id  = EXCLUDED.infractions_channel_id,
                applications_channel_id = EXCLUDED.applications_channel_id,
                announce_channel_id     = EXCLUDED.announce_channel_id,
                staff_roles_json        = EXCLUDED.staff_roles_json,
                leader_roles_json       = EXCLUDED.leader_roles_json,
                admin_roles_json        = EXCLUDED.admin_roles_json,
                hr_roles_json           = EXCLUDED.hr_roles_json,
                apply_positions_json    = EXCLUDED.apply_positions_json,
                linked_guild_id         = EXCLUDED.linked_guild_id,
                linked_staff_roles_json = EXCLUDED.linked_staff_roles_json,
                duty_role_id            = EXCLUDED.duty_role_id,
                strike_threshold        = EXCLUDED.strike_threshold,
                strike_action           = EXCLUDED.strike_action
        """,
            guild_id,
            existing.get("log_channel_id"),
            existing.get("promotion_channel_id"),
            existing.get("demotion_channel_id"),
            existing.get("termination_channel_id"),
            existing.get("infractions_channel_id"),
            existing.get("applications_channel_id"),
            existing.get("announce_channel_id"),
            existing.get("staff_roles_json", "[]"),
            existing.get("leader_roles_json", "[]"),
            existing.get("admin_roles_json", "[]"),
            existing.get("hr_roles_json", "[]"),
            existing.get("apply_positions_json", "[]"),
            existing.get("linked_guild_id"),
            existing.get("linked_staff_roles_json", "[]"),
            existing.get("duty_role_id"),
            int(existing.get("strike_threshold") or 3),
            existing.get("strike_action", "terminate"),
        )


# ── Action log ────────────────────────────────────────────────────────────────

async def log_action(guild_id: str, user_id: str, actor_id: str, action: str, detail: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO action_log (guild_id, user_id, actor_id, action, detail, timestamp) VALUES ($1,$2,$3,$4,$5,$6)",
            guild_id, user_id, str(actor_id), action, detail, datetime.now(timezone.utc).isoformat()
        )


async def get_action_log(user_id: str, guild_id: str, limit: int = 20) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM action_log WHERE user_id = $1 AND guild_id = $2 ORDER BY timestamp DESC LIMIT $3",
            user_id, guild_id, limit
        )
        return [dict(r) for r in rows]


# ── Duty ─────────────────────────────────────────────────────────────────────

async def get_duty_status(user_id: str, guild_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM duty WHERE user_id = $1 AND guild_id = $2", user_id, guild_id)
        return dict(row) if row else {"user_id": user_id, "guild_id": guild_id, "on_duty": 0, "since": None}


async def set_duty_status(user_id: str, guild_id: str, on_duty: bool):
    pool = await get_pool()
    since = datetime.now(timezone.utc).isoformat() if on_duty else None
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO duty (user_id, guild_id, on_duty, since) VALUES ($1,$2,$3,$4)
            ON CONFLICT (user_id, guild_id) DO UPDATE SET on_duty = $3, since = $4
        """, user_id, guild_id, int(on_duty), since)


async def get_all_on_duty(guild_id: str) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM duty WHERE guild_id = $1 AND on_duty = 1", guild_id)
        return [dict(r) for r in rows]


# ── Infractions ───────────────────────────────────────────────────────────────

async def add_infraction(user_id: str, guild_id: str, infraction_type: str, reason: str, moderator_id: str, expires_at: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO infractions (user_id, guild_id, type, reason, moderator_id, timestamp, expires_at) VALUES ($1,$2,$3,$4,$5,$6,$7)",
            user_id, guild_id, infraction_type, reason, moderator_id, datetime.now(timezone.utc).isoformat(), expires_at
        )


async def get_infractions(user_id: str, guild_id: str) -> list:
    pool = await get_pool()
    now = datetime.now(timezone.utc).isoformat()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM infractions WHERE user_id=$1 AND guild_id=$2 AND (expires_at IS NULL OR expires_at > $3) ORDER BY timestamp DESC",
            user_id, guild_id, now
        )
        return [dict(r) for r in rows]


async def count_infractions_by_type(user_id: str, guild_id: str, infraction_type: str) -> int:
    pool = await get_pool()
    now = datetime.now(timezone.utc).isoformat()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT COUNT(*) FROM infractions WHERE user_id=$1 AND guild_id=$2 AND type=$3 AND (expires_at IS NULL OR expires_at > $4)",
            user_id, guild_id, infraction_type, now
        )
        return val or 0


async def get_guild_infraction_stats(guild_id: str) -> dict:
    pool = await get_pool()
    now = datetime.now(timezone.utc).isoformat()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT type, COUNT(*) AS cnt FROM infractions WHERE guild_id=$1 AND (expires_at IS NULL OR expires_at > $2) GROUP BY type",
            guild_id, now
        )
        return {r["type"]: r["cnt"] for r in rows}


async def reset_all_infractions(guild_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM infractions WHERE guild_id = $1", guild_id)
        # result is like "DELETE 5"
        return int(result.split()[-1])


# ── Notes ─────────────────────────────────────────────────────────────────────

async def add_note(user_id: str, guild_id: str, content: str, moderator_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO notes (user_id, guild_id, content, moderator_id, timestamp) VALUES ($1,$2,$3,$4,$5)",
            user_id, guild_id, content, moderator_id, datetime.now(timezone.utc).isoformat()
        )


async def get_notes(user_id: str, guild_id: str) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM notes WHERE user_id=$1 AND guild_id=$2 ORDER BY timestamp DESC",
            user_id, guild_id
        )
        return [dict(r) for r in rows]


# ── LOA ───────────────────────────────────────────────────────────────────────

async def set_loa(user_id: str, guild_id: str, duration: str, reason: str, end_date: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE loa SET active = 0 WHERE user_id=$1 AND guild_id=$2", user_id, guild_id)
        await conn.execute(
            "INSERT INTO loa (user_id, guild_id, duration, reason, start_date, end_date, active) VALUES ($1,$2,$3,$4,$5,$6,1)",
            user_id, guild_id, duration, reason, datetime.now(timezone.utc).isoformat(), end_date
        )


async def remove_loa(user_id: str, guild_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE loa SET active = 0 WHERE user_id=$1 AND guild_id=$2", user_id, guild_id)


async def get_active_loa(user_id: str, guild_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM loa WHERE user_id=$1 AND guild_id=$2 AND active=1",
            user_id, guild_id
        )
        return dict(row) if row else None


async def get_all_active_loas(guild_id: str) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM loa WHERE guild_id=$1 AND active=1", guild_id)
        return [dict(r) for r in rows]


# ── Messages ──────────────────────────────────────────────────────────────────

async def increment_message_count(user_id: str, guild_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO message_counts (user_id, guild_id, count, last_updated) VALUES ($1,$2,1,$3)
            ON CONFLICT (user_id, guild_id) DO UPDATE SET count = message_counts.count + 1, last_updated = $3
        """, user_id, guild_id, datetime.now(timezone.utc).isoformat())


async def get_message_count(user_id: str, guild_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT count FROM message_counts WHERE user_id=$1 AND guild_id=$2", user_id, guild_id)
        return val or 0


async def get_leaderboard(guild_id: str, limit: int = 10) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, count FROM message_counts WHERE guild_id=$1 ORDER BY count DESC LIMIT $2",
            guild_id, limit
        )
        return [dict(r) for r in rows]


# ── Applications ──────────────────────────────────────────────────────────────

async def add_application(user_id: str, guild_id: str, position: str, answers: dict) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        app_id = await conn.fetchval(
            "INSERT INTO applications (user_id, guild_id, position, answers_json, status, timestamp) VALUES ($1,$2,$3,$4,'pending',$5) RETURNING id",
            user_id, guild_id, position, json.dumps(answers), datetime.now(timezone.utc).isoformat()
        )
        return app_id


async def update_application_status(app_id: int, status: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE applications SET status=$1 WHERE id=$2", status, app_id)


async def get_application(app_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM applications WHERE id=$1", app_id)
        return dict(row) if row else None


async def get_pending_applications_count(guild_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT COUNT(*) FROM applications WHERE guild_id=$1 AND status='pending'", guild_id
        )
        return val or 0


# ── Misc ──────────────────────────────────────────────────────────────────────

async def get_all_guild_ids() -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT guild_id FROM staff_config")
        return [r["guild_id"] for r in rows]

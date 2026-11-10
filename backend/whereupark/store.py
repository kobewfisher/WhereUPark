"""SQLite storage for observed occupancy (camera feeds, East End sensors, manual counts)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import CAMPUS_TZ, REPO_ROOT

DATA_DIR = Path(os.environ.get("WHEREUPARK_DATA", REPO_ROOT / "backend" / "data"))
DB_PATH = DATA_DIR / "whereupark.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    ts         TEXT NOT NULL,      -- ISO-8601 with UTC offset
    site_id    TEXT NOT NULL,
    spot_type  TEXT NOT NULL,
    occupied   INTEGER NOT NULL,
    capacity   INTEGER,            -- NULL = use the configured count
    source     TEXT NOT NULL,      -- parklio | east_end_sensors | manual_count | import
    PRIMARY KEY (ts, site_id, spot_type, source)
);
CREATE INDEX IF NOT EXISTS idx_obs_site_ts ON observations(site_id, ts);
"""


@contextmanager
def connect(db_path: Path | None = None):
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _utc_iso(ts: datetime | str) -> str:
    """Store every timestamp as UTC so SQLite's string comparisons order correctly."""
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=CAMPUS_TZ)
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def add_observations(rows: list[dict], db_path: Path | None = None) -> int:
    with connect(db_path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)",
            [
                (
                    _utc_iso(r["ts"]),
                    r["site_id"], r["spot_type"], int(r["occupied"]),
                    None if r.get("capacity") is None else int(r["capacity"]),
                    r.get("source", "import"),
                )
                for r in rows
            ],
        )
    return len(rows)


def load_observations(db_path: Path | None = None, since: datetime | None = None) -> pd.DataFrame:
    with connect(db_path) as conn:
        q, params = "SELECT * FROM observations", ()
        if since is not None:
            q, params = q + " WHERE ts >= ?", (_utc_iso(since),)
        df = pd.read_sql_query(q, conn, params=params)
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    return df


def latest_observations(site_id: str, since: datetime, db_path: Path | None = None) -> pd.DataFrame:
    """Most recent reading per spot type for a site, no older than `since`."""
    df = load_observations(db_path, since=since)
    if df.empty:
        return df
    df = df[df.site_id == site_id].sort_values("ts")
    return df.groupby("spot_type").tail(1)

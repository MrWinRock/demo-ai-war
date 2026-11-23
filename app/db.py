"""SQLite แบบเรียบง่าย: การเชื่อมต่อเดียว + lock เพียงพอสำหรับเดโม"""
import os
import sqlite3
import threading

DB_PATH = os.environ.get("DB_PATH", "/data/app.db")

# เพิ่มเลขนี้เมื่อแก้ SCHEMA หรือข้อมูลตัวอย่าง ระบบจะล้างฐานข้อมูลเดิมแล้วสร้างใหม่ตอนเริ่มทำงาน
SCHEMA_VERSION = "2"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL,
    lat REAL NOT NULL, lng REAL NOT NULL, points INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, capacity_units INTEGER NOT NULL,  -- พื้นที่บรรทุก เทียบเป็นถุงหิ้ว
    color TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, member_id INTEGER NOT NULL,
    lat REAL NOT NULL, lng REAL NOT NULL,
    slot TEXT NOT NULL, window_start INTEGER NOT NULL, window_end INTEGER NOT NULL,
    items TEXT NOT NULL,       -- JSON: รายการที่ AI เห็นในรูป
    materials TEXT NOT NULL,   -- JSON: [{material, share}]
    size TEXT NOT NULL, volume INTEGER NOT NULL,  -- พื้นที่บนรถที่ใช้ ตามขนาดกอง
    est_kg REAL NOT NULL, est_value REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | collected
    photo TEXT NOT NULL DEFAULT '',  -- รูปย่อ (data URL) เก็บเป็นหลักฐาน
    actual_kg REAL, note TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _c() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init() -> None:
    with _lock:
        _c().executescript(SCHEMA)
        _c().commit()


def query(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in _c().execute(sql, params).fetchall()]


def execute(sql: str, params: tuple = ()) -> int:
    with _lock:
        cur = _c().execute(sql, params)
        _c().commit()
        return cur.lastrowid


def get_kv(key: str) -> str | None:
    rows = query("SELECT value FROM kv WHERE key=?", (key,))
    return rows[0]["value"] if rows else None


def set_kv(key: str, value: str) -> None:
    execute("INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def reset() -> None:
    with _lock:
        _c().executescript("DROP TABLE IF EXISTS members; DROP TABLE IF EXISTS vehicles; DROP TABLE IF EXISTS requests; DROP TABLE IF EXISTS kv;")
        _c().executescript(SCHEMA)
        _c().commit()

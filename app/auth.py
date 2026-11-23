"""การเข้าสู่ระบบ 4 บทบาท: user (สมาชิก), driver (คนขับ), admin (ผู้ดูแลระบบ), partner (คู่ค้า)

ใช้ session cookie แบบ HttpOnly เพื่อให้รูปและไฟล์ดาวน์โหลดใช้สิทธิ์เดียวกับ API ได้
เดโมนี้มี quick login สำหรับบัญชีตัวอย่าง ปิดได้ด้วยตัวแปร DEMO_QUICK_LOGIN=0
"""
import hashlib
import hmac
import os
import secrets
import time

from fastapi import Cookie, Depends, HTTPException

from . import db

COOKIE = "yt_session"
ROLES = ("user", "driver", "admin", "partner")
QUICK_LOGIN = os.environ.get("DEMO_QUICK_LOGIN", "1") != "0"
SESSION_SECONDS = 12 * 3600


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()
    return digest, salt


def check_password(user: dict, password: str) -> bool:
    digest, _ = hash_password(password, user["pw_salt"])
    return hmac.compare_digest(digest, user["pw_hash"])


def start_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)", (token, user_id, time.time()))
    return token


def end_session(token: str | None) -> None:
    if token:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def current(yt_session: str | None = Cookie(None)) -> dict:
    """ผู้ใช้ของคำขอนี้ ถ้ายังไม่เข้าสู่ระบบหรือ session หมดอายุ ตอบ 401"""
    if yt_session:
        rows = db.query(
            "SELECT u.id, u.username, u.name, u.role, u.ref_id, s.created_at FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (yt_session,),
        )
        if rows and time.time() - rows[0]["created_at"] < SESSION_SECONDS:
            return rows[0]
    raise HTTPException(401, "กรุณาเข้าสู่ระบบ")


def need(*roles: str):
    """ใช้กับ Depends: ผ่านได้เฉพาะบทบาทที่ระบุ"""
    def dep(user: dict = Depends(current)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "บทบาทของคุณไม่มีสิทธิ์ทำรายการนี้")
        return user
    return dep

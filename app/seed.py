"""ข้อมูลตัวอย่าง: สมาชิก รถ และคำขอรับ ในย่านจตุจักร–ลาดพร้าว (สุ่มแบบกำหนด seed ให้ได้ผลเดิมทุกครั้ง)"""
import json
import random
import time

from . import db
from .config import SIZES, SLOTS, VEHICLE_COLORS
from .estimate import estimate

NAMES = [
    "คุณสมชาย", "คุณวิภา", "คุณอนันต์", "คุณมาลี", "คุณประเสริฐ", "คุณสุดา", "คุณธนา", "คุณนภา",
    "คุณกิตติ", "คุณอรทัย", "คุณชัยวัฒน์", "คุณพิมพ์ใจ", "คุณวีระ", "คุณจันทร์เพ็ญ", "คุณสุรชัย", "คุณรัตนา",
    "คุณณัฐ", "คุณศิริพร", "คุณพงศ์", "คุณกมล", "คุณอารีย์", "คุณบุญส่ง", "คุณลัดดา", "คุณเอกชัย",
]

# ชุดวัสดุตัวอย่างสำหรับกองขนาดเล็ก: (ชื่อ, ชนิดวัสดุ, จำนวนชิ้น) กองใหญ่ขึ้นจะคูณจำนวนตามขนาด
BUNDLES = [
    [("ขวดน้ำดื่ม", "pet", 15), ("กระป๋องน้ำอัดลม", "aluminum", 8)],
    [("ลังกระดาษ", "cardboard", 6)],
    [("ขวดแก้ว", "glass", 10), ("กระป๋องอาหาร", "steel", 5)],
    [("นิตยสารเก่า", "paper", 8), ("ลังกระดาษ", "cardboard", 3)],
    [("ขวดนม", "hdpe", 9), ("ขวดน้ำดื่ม", "pet", 20)],
    [("กระป๋องเบียร์", "aluminum", 24)],
    [("ขวดน้ำดื่ม", "pet", 30), ("ลังกระดาษ", "cardboard", 4), ("ขวดแก้ว", "glass", 6)],
]

CENTER = (13.8150, 100.5850)
N_REQUESTS = 20  # สมาชิก 4 คนแรกไม่มีคำขอ เก็บไว้ใช้เดโมสด


def run() -> None:
    rnd = random.Random(7)
    for i, name in enumerate(NAMES, start=1):
        lat = CENTER[0] + rnd.uniform(-0.030, 0.030)
        lng = CENTER[1] + rnd.uniform(-0.035, 0.035)
        db.execute(
            "INSERT INTO members(id, name, address, lat, lng, points) VALUES(?,?,?,?,?,?)",
            (i, name, f"ซอยตัวอย่าง {i}", round(lat, 6), round(lng, 6), rnd.choice([0, 40, 120, 250])),
        )

    for i, (name, cap) in enumerate([("รถกระบะ 1", 30), ("รถกระบะ 2", 30)], start=1):
        db.execute(
            "INSERT INTO vehicles(id, name, capacity_units, color, active) VALUES(?,?,?,?,1)",
            (i, name, cap, VEHICLE_COLORS[(i - 1) % len(VEHICLE_COLORS)]),
        )

    members = db.query("SELECT * FROM members WHERE id > ? ORDER BY id", (len(NAMES) - N_REQUESTS,))
    now = time.time()
    for n, m in enumerate(members):
        slot = rnd.choice(SLOTS)
        size = rnd.choices(["S", "M", "L"], weights=[4, 4, 1])[0]
        units = SIZES[size]["units"]
        items = [{"name_th": a, "material": b, "count": c * units, "prep_tip_th": ""} for a, b, c in rnd.choice(BUNDLES)]
        est = estimate(items)
        db.execute(
            "INSERT INTO requests(member_id, lat, lng, slot, window_start, window_end, items, materials, size, volume, est_kg, est_value, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m["id"], m["lat"], m["lng"], slot["id"], slot["start"], slot["end"], json.dumps(items, ensure_ascii=False),
             json.dumps(est["materials"]), size, units, est["est_kg"], est["est_value"], now + n),
        )

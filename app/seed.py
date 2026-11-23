"""ข้อมูลตัวอย่าง: สมาชิก บริษัท รถ คำขอรับ คู่ค้า ประวัติราคา และบัญชีผู้ใช้ของทั้ง 4 บทบาท

ทุกอย่างเป็นข้อมูลสมมติ ชื่อ เบอร์โทร และอีเมลไม่ใช่ของจริง สุ่มแบบกำหนด seed ให้ได้ผลเดิมทุกครั้ง
"""
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

from . import auth, db
from .config import BAG_TAGS, CODE_ALPHABET, MATERIALS, PRICE_FRAME, SIZES, SLOTS, VEHICLE_COLORS
from .estimate import aggregate_items, estimate

BKK = timezone(timedelta(hours=7))
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")  # รหัสผ่านของบัญชีตัวอย่างทุกบัญชี
PRICE_DAYS = 60

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

COMPANIES = [
    (25, "บริษัท ค้าปลีกตัวอย่าง จำกัด", "อาคารสำนักงาน ถนนพหลโยธิน (ตัวอย่าง)", 13.8262, 100.5688),
    (26, "อาคารสำนักงานตัวอย่าง ทาวเวอร์", "ถนนรัชดาภิเษก (ตัวอย่าง)", 13.8030, 100.5745),
]

# (id, ชื่อ, ชนิด, ประเภทวัสดุที่รับ, lat, lng, ผู้ติดต่อ, เบอร์, LINE, อีเมล, เวลาทำการ)
PARTNERS = [
    (1, "โรงงานรีไซเคิลพลาสติก (ตัวอย่าง)", "factory", ["plastic"], 13.8600, 100.6400, "คุณวิทยา ฝ่ายจัดซื้อ", "02-000-0101", "@plastic-demo", "buy@plastic-factory.example", "จ.–ส. 08:00–17:00"),
    (2, "โรงงานกระดาษ (ตัวอย่าง)", "factory", ["paper"], 13.7700, 100.6200, "คุณสมศรี ฝ่ายรับวัตถุดิบ", "02-000-0102", "@paper-demo", "inbound@paper-mill.example", "ทุกวัน 07:00–18:00"),
    (3, "โรงหลอมโลหะและแก้ว (ตัวอย่าง)", "factory", ["metal", "glass"], 13.8500, 100.5200, "คุณธีระ ผู้จัดการลานรับ", "02-000-0103", "@metal-demo", "yard@smelter.example", "จ.–ศ. 08:00–16:30"),
    (4, "ร้านรับซื้อของเก่า ลาดพร้าว (ตัวอย่าง)", "shop", ["plastic", "paper", "metal", "glass"], 13.8190, 100.6050, "เฮียชัย เจ้าของร้าน", "08-0000-0104", "@shop-ladprao-demo", "shop.ladprao@scrap.example", "ทุกวัน 08:00–19:00"),
    (5, "ร้านรับซื้อของเก่า จตุจักร (ตัวอย่าง)", "shop", ["plastic", "paper", "metal", "glass"], 13.8285, 100.5600, "เจ๊นิด เจ้าของร้าน", "08-0000-0105", "@shop-chatuchak-demo", "shop.chatuchak@scrap.example", "จ.–ส. 08:30–18:00"),
]

# (username, ชื่อที่แสดง, บทบาท, ref_id, แสดงในปุ่ม quick login)
USERS = [
    ("somchai", "คุณสมชาย", "user", 1, 1),
    ("wipa", "คุณวิภา", "user", 2, 0),
    ("prasert", "คุณประเสริฐ", "user", 5, 1),
    ("company1", "บริษัท ค้าปลีกตัวอย่าง จำกัด", "user", 25, 1),
    ("company2", "อาคารสำนักงานตัวอย่าง ทาวเวอร์", "user", 26, 0),
    ("driver1", "คนขับ รถกระบะ 1", "driver", 1, 1),
    ("driver2", "คนขับ รถกระบะ 2", "driver", 2, 1),
    ("admin", "ผู้ดูแลระบบ", "admin", None, 1),
    ("factory1", "โรงงานรีไซเคิลพลาสติก (ตัวอย่าง)", "partner", 1, 1),
    ("factory2", "โรงงานกระดาษ (ตัวอย่าง)", "partner", 2, 0),
    ("factory3", "โรงหลอมโลหะและแก้ว (ตัวอย่าง)", "partner", 3, 0),
    ("shop1", "ร้านรับซื้อของเก่า ลาดพร้าว (ตัวอย่าง)", "partner", 4, 1),
    ("shop2", "ร้านรับซื้อของเก่า จตุจักร (ตัวอย่าง)", "partner", 5, 0),
]


def _bag(k: int, name: str, material: str, count: int, size: str) -> dict:
    items = [{"name_th": name, "material": material, "count": count, "prep_tip_th": ""}]
    est = estimate(items)
    return {
        "tag": BAG_TAGS[k], "name_th": f"ถุง{name}", "position_th": "", "kind": "bag", "mixed": False,
        "size": size, "count_method": "exact", "partial_view": False, "photo": None, "items": items,
        "est_kg": est["est_kg"], "est_value": est["est_value"], "found": None, "actual_kg": None, "mismatch": False,
    }


def run() -> None:
    rnd = random.Random(7)
    code_rnd = random.Random(11)  # แยกตัวสุ่มของรหัส เพื่อไม่ให้กระทบลำดับการสุ่มข้อมูลตัวอย่าง
    for i, name in enumerate(NAMES, start=1):
        lat = CENTER[0] + rnd.uniform(-0.030, 0.030)
        lng = CENTER[1] + rnd.uniform(-0.035, 0.035)
        db.execute(
            "INSERT INTO members(id, name, address, lat, lng, points, phone) VALUES(?,?,?,?,?,?,?)",
            (i, name, f"ซอยตัวอย่าง {i}", round(lat, 6), round(lng, 6), rnd.choice([0, 40, 120, 250]), f"08-0000-{1000 + i}"),
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
        # วัสดุแต่ละชนิดในชุดเป็นถุงของตัวเอง เหมือนบ้านที่แยกไว้แล้ว
        bags = [_bag(k, name, material, count * units, size) for k, (name, material, count) in enumerate(rnd.choice(BUNDLES))]
        items = aggregate_items(bags)
        est = estimate(items)
        db.execute(
            "INSERT INTO requests(member_id, lat, lng, slot, window_start, window_end, bags, items, materials, volume, est_kg, est_value, code, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m["id"], m["lat"], m["lng"], slot["id"], slot["start"], slot["end"], json.dumps(bags, ensure_ascii=False),
             json.dumps(items, ensure_ascii=False), json.dumps(est["materials"]), units, est["est_kg"], est["est_value"],
             "".join(code_rnd.choice(CODE_ALPHABET) for _ in range(6)), now + n),
        )

    _companies(now)
    _partners_and_prices()
    _users()


def _companies(now: float) -> None:
    """บริษัทสองแห่ง พร้อมประวัติการรับที่ส่งถึงศูนย์แล้วย้อนหลังราว 2 เดือน ใช้แสดงรายงานคาร์บอน"""
    rnd = random.Random(31)
    for mid, name, address, lat, lng in COMPANIES:
        db.execute(
            "INSERT INTO members(id, name, address, lat, lng, points, kind, phone) VALUES(?,?,?,?,?,?,?,?)",
            (mid, name, address, lat, lng, 0, "company", f"02-000-{2000 + mid}"),
        )
        points = 0
        for week in range(8 if mid == 25 else 5):
            created = now - (week * 7 + 2) * 86400 - rnd.uniform(0, 6) * 3600
            spec = [("ลังกระดาษ", "cardboard", rnd.randint(60, 140), "L"), ("กระดาษสำนักงาน", "paper", rnd.randint(80, 200), "M"),
                    ("ขวดน้ำดื่ม", "pet", rnd.randint(150, 400), "M")]
            if week % 2 == 0:
                spec.append(("กระป๋องเครื่องดื่ม", "aluminum", rnd.randint(80, 220), "S"))
            bags = [_bag(k, n, m, c, size) for k, (n, m, c, size) in enumerate(spec)]
            for b in bags:  # น้ำหนักจริงที่คนขับชั่ง ใกล้เคียงกับที่ประเมิน
                b.update(found=True, actual_kg=round(b["est_kg"] * rnd.uniform(0.85, 1.15), 1))
            items = aggregate_items(bags)
            est = estimate(items)
            actual = round(sum(b["actual_kg"] for b in bags), 2)
            points += round(actual * 10)
            slot = SLOTS[week % len(SLOTS)]
            db.execute(
                "INSERT INTO requests(member_id, lat, lng, slot, window_start, window_end, bags, items, materials, volume, est_kg,"
                " est_value, code, created_at, status, vehicle_id, verified_at, collected_at, delivered_at, actual_kg, actual_items)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (mid, lat, lng, slot["id"], slot["start"], slot["end"], json.dumps(bags, ensure_ascii=False),
                 json.dumps(items, ensure_ascii=False), json.dumps(est["materials"]), sum(SIZES[b["size"]]["units"] for b in bags),
                 est["est_kg"], est["est_value"], "".join(rnd.choice(CODE_ALPHABET) for _ in range(6)), created, "delivered",
                 1 + week % 2, created + 3600, created + 4200, created + 9000, actual, json.dumps(items, ensure_ascii=False)),
            )
        db.execute("UPDATE members SET points = ? WHERE id = ?", (points, mid))


def _partners_and_prices() -> None:
    """คู่ค้าและราคารับซื้อย้อนหลัง เป็นข้อมูลจำลอง ไม่ใช่ราคาตลาดจริง

    ราคาเดินแบบสุ่มภายในกรอบของราคาอ้างอิง (PRICE_FRAME): โรงงานเริ่มใกล้ขอบบน ร้านรับซื้อเริ่มใกล้ขอบล่าง
    """
    rnd = random.Random(23)
    today = datetime.now(BKK).date()
    days = [(today - timedelta(days=d)).isoformat() for d in range(PRICE_DAYS - 1, -1, -1)]
    for pid, name, kind, accepts, lat, lng, contact, phone, line_id, email, hours in PARTNERS:
        db.execute(
            "INSERT INTO partners(id, name, kind, accepts, lat, lng, contact_name, phone, line_id, email, hours) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (pid, name, kind, json.dumps(accepts), lat, lng, contact, phone, line_id, email, hours),
        )
        for key, m in MATERIALS.items():
            if m["factory"] not in accepts:
                continue
            low, high = PRICE_FRAME.get(key, (m["price"] * 0.9, m["price"] * 1.3))
            span = max(high - low, low * 0.08)
            price = (high - span * 0.15 if kind == "factory" else low + span * 0.2) * rnd.uniform(0.98, 1.02)
            drift = rnd.uniform(-0.0012, 0.0018)
            for day in days:
                price = min(high * 1.06, max(low * 0.94, price * (1 + drift + rnd.gauss(0, 0.011))))
                db.execute("INSERT INTO prices(partner_id, material, day, price) VALUES(?,?,?,?)", (pid, key, day, round(price, 2)))


def _users() -> None:
    for uid, (username, name, role, ref_id, quick) in enumerate(USERS, start=1):
        digest, salt = auth.hash_password(DEMO_PASSWORD)
        db.execute(
            "INSERT INTO users(id, username, name, role, ref_id, pw_hash, pw_salt, quick) VALUES(?,?,?,?,?,?,?,?)",
            (uid, username, name, role, ref_id, digest, salt, quick),
        )

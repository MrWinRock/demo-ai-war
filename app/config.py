"""ค่าตั้งต้นของระบบ: ชนิดวัสดุ ขนาดถุง ช่วงเวลานัด ศูนย์คัดแยก และค่าตั้งต้นของเกณฑ์ที่ผู้ดูแลแก้ได้

ราคา น้ำหนักต่อชิ้น และตำแหน่งต่าง ๆ เป็น "ค่าตัวอย่าง" สำหรับเดโม
ค่าที่ผู้ดูแลระบบแก้ผ่านหน้าหลังบ้านจะเก็บในฐานข้อมูล และทับค่าตั้งต้นในไฟล์นี้ (ดู settings.py)
"""

# price = บาทต่อกิโลกรัมที่ใช้ประเมินมูลค่าให้สมาชิก, unit_kg = น้ำหนักเฉลี่ยต่อชิ้น (กก.), factory = ประเภทโรงงานปลายทาง
MATERIALS = {
    "pet": {"label": "ขวดพลาสติกใส (PET)", "price": 8, "unit_kg": 0.025, "factory": "plastic"},
    "hdpe": {"label": "พลาสติกขุ่น (HDPE)", "price": 10, "unit_kg": 0.05, "factory": "plastic"},
    "other_plastic": {"label": "พลาสติกอื่น ๆ", "price": 2, "unit_kg": 0.02, "factory": "plastic"},
    "cardboard": {"label": "กระดาษลัง", "price": 3, "unit_kg": 0.35, "factory": "paper"},
    "paper": {"label": "กระดาษ", "price": 4, "unit_kg": 0.15, "factory": "paper"},
    "aluminum": {"label": "กระป๋องอะลูมิเนียม", "price": 40, "unit_kg": 0.015, "factory": "metal"},
    "steel": {"label": "กระป๋องเหล็ก/โลหะ", "price": 6, "unit_kg": 0.05, "factory": "metal"},
    "glass": {"label": "ขวดแก้ว", "price": 1, "unit_kg": 0.3, "factory": "glass"},
    "non_recyclable": {"label": "ไม่รับ", "price": 0, "unit_kg": 0, "factory": None},
}

# ขนาดถุงใช้จองพื้นที่บนรถ (ของรีไซเคิลเบาแต่กินที่ รถจึงเต็มด้วยปริมาตรก่อนน้ำหนัก)
# units = พื้นที่ที่ใช้ เทียบเป็นจำนวนถุงหิ้ว
SIZES = {
    "S": {"label": "เล็ก (ถุงหิ้ว 1 ใบ)", "units": 1},
    "M": {"label": "กลาง (ถุงดำ 1 ใบ)", "units": 3},
    "L": {"label": "ใหญ่ (หลายถุง/ลัง)", "units": 8},
}

# นาทีนับจากเที่ยงคืน
SLOTS = [
    {"id": "09-11", "label": "09:00–11:00", "start": 540, "end": 660},
    {"id": "11-13", "label": "11:00–13:00", "start": 660, "end": 780},
    {"id": "13-15", "label": "13:00–15:00", "start": 780, "end": 900},
    {"id": "15-17", "label": "15:00–17:00", "start": 900, "end": 1020},
]
SLOT_BY_ID = {s["id"]: s for s in SLOTS}

DEPOT = {"name": "ศูนย์คัดแยก (ตัวอย่าง)", "lat": 13.8050, "lng": 100.5530}

VEHICLE_COLORS = ["#2563eb", "#ea580c", "#7c3aed", "#0891b2"]

# ตัวอักษรของรหัสรับของ ตัดตัวที่อ่านสับสนออก (0/O, 1/I)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
QR_PREFIX = "YAEKTOOK"

# ป้ายของถุงในหนึ่งคำขอ ถุงใบแรกคือ A (ข้ามตัว I ที่อ่านสับสนกับเลข 1) จึงรับได้สูงสุด 12 ถุงต่อคำขอ
BAG_TAGS = "ABCDEFGHJKLM"

# ---------- เกณฑ์การรับของและการผ่อนปรน (ค่าตั้งต้น ผู้ดูแลแก้ได้ที่หน้าหลังบ้าน) ----------
DEFAULT_SETTINGS = {
    # วัสดุที่รับ ราคา และน้ำหนักต่อชิ้น เติมจาก MATERIALS ตอนโหลด
    "materials": {},
    "min_request_kg": 0.3,            # น้ำหนักรวมขั้นต่ำต่อคำขอ (กก. โดยประมาณ)
    "below_min_policy": "allow_flag",  # block = ไม่รับ, allow_flag = ผ่อนปรนให้รับแต่ติดธง
    "mixed_policy": "warn",            # ถุงที่ของปนกัน: accept รับตามปกติ, warn รับแต่ติดธง, reject ไม่รับ
    "scan_max_distance_m": 200,        # ระยะห่างสูงสุดจากหมุดตอนคนขับสแกน QR
    "scan_far_policy": "allow_flag",   # block = ไม่ให้ยืนยันจุด, allow_flag = ผ่อนปรนแต่ติดธง
    "allow_partial_pickup": True,      # รับได้แม้ไม่พบบางถุง
    "weight_tolerance_pct": 50,        # น้ำหนักจริงต่างจากที่ประเมินเกินกี่เปอร์เซ็นต์จึงติดธง
    "points_per_kg": 10,
    "carbon_price_thb": 100,           # ราคาคาร์บอนที่ใช้ตีมูลค่า (บาทต่อ tCO2e) เป็นค่าสมมติ
    "road_routing": True,              # ใช้บริการเส้นทางตามถนนภายนอก (OSRM สาธารณะ) ในโหมดนำทางของคนขับ
}

POLICIES = {
    "below_min_policy": ("block", "allow_flag"),
    "mixed_policy": ("accept", "warn", "reject"),
    "scan_far_policy": ("block", "allow_flag"),
}

# รหัสธงของคำขอ: กรณีที่ผ่อนปรนให้ หรือควรให้ผู้ดูแลตรวจ
FLAGS = {
    "below_min": "ต่ำกว่าน้ำหนักขั้นต่ำ (ผ่อนปรนให้)",
    "mixed_bag": "มีถุงที่ของปนกัน",
    "scan_far": "สแกนไกลจากหมุดเกินเกณฑ์ (ผ่อนปรนให้)",
    "missing_bag": "ไม่พบบางถุง",
    "mismatch": "ของในถุงไม่ตรงกับที่แจ้ง",
    "weight_diff": "น้ำหนักจริงต่างจากที่ประเมินเกินเกณฑ์",
}

# ---------- คาร์บอน ----------
# ปัจจัยการปล่อยสุทธิของการรีไซเคิล จาก US EPA WARM รุ่น 16 หน่วย MTCO2E ต่อ short ton (ค่าลบ = หลีกเลี่ยงการปล่อย)
# ที่มา: Documentation for Greenhouse Gas Emission and Energy Factors Used in WARM, Management Practices Chapters (ธ.ค. 2566)
# เป็นค่าของสหรัฐฯ ใช้ประมาณการเบื้องต้นเท่านั้น งานที่ต้องยื่นขอคาร์บอนเครดิตต้องใช้ค่าและระเบียบวิธีที่ อบก. รับรอง
WARM_RECYCLING_MTCO2E_PER_SHORT_TON = {
    "pet": -1.04, "hdpe": -0.76, "other_plastic": -0.93,   # other_plastic ใช้ค่า Mixed Plastics
    "cardboard": -3.14, "paper": -3.55,                     # paper ใช้ค่า Mixed Paper (general)
    "aluminum": -9.13, "steel": -1.83, "glass": -0.28,
}
SHORT_TON_KG = 907.185

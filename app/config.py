"""ค่าคงที่ของระบบ: ชนิดวัสดุ ราคา ขนาดกอง ช่วงเวลานัด

ราคารับซื้อและตำแหน่งโรงงานเป็น "ค่าตัวอย่าง" สำหรับเดโม แก้ได้ที่ไฟล์นี้ที่เดียว
"""

# price = บาทต่อกิโลกรัม, unit_kg = น้ำหนักเฉลี่ยต่อชิ้น (กก.), factory = ประเภทโรงงานปลายทาง
# ทั้งราคาและน้ำหนักต่อชิ้นเป็นค่าตัวอย่าง ควรปรับตามข้อมูลจริงของทีม
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

# ขนาดกองใช้จองพื้นที่บนรถ (ของรีไซเคิลเบาแต่กินที่ รถจึงเต็มด้วยปริมาตรก่อนน้ำหนัก)
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

FACTORIES = [
    {"id": 1, "name": "โรงงานรีไซเคิลพลาสติก (ตัวอย่าง)", "lat": 13.8600, "lng": 100.6400, "accepts": ["plastic"]},
    {"id": 2, "name": "โรงงานกระดาษ (ตัวอย่าง)", "lat": 13.7700, "lng": 100.6200, "accepts": ["paper"]},
    {"id": 3, "name": "โรงหลอมโลหะและแก้ว (ตัวอย่าง)", "lat": 13.8500, "lng": 100.5200, "accepts": ["metal", "glass"]},
]

VEHICLE_COLORS = ["#2563eb", "#ea580c", "#7c3aed", "#0891b2"]

POINTS_PER_KG = 10

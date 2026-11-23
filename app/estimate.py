"""แปลงจำนวนชิ้นที่นับได้ เป็นน้ำหนักและมูลค่าโดยประมาณ

น้ำหนัก = จำนวนชิ้น x น้ำหนักเฉลี่ยต่อชิ้นของวัสดุนั้น คำนวณที่เซิร์ฟเวอร์จากตารางใน config
ไม่ให้ LLM คิดเลขเอง และคนขับยืนยันน้ำหนักจริงอีกครั้งตอนรับ
"""
from . import settings


def estimate(items: list[dict], mats: dict | None = None) -> dict:
    """mats = ตารางวัสดุตามเกณฑ์ล่าสุด (ส่งมาเองได้เมื่อเรียกหลายครั้งติดกัน) วัสดุที่ไม่รับถูกนับเป็นศูนย์"""
    mats = mats or settings.materials()
    kg_by_material: dict[str, float] = {}
    for i in items:
        m = mats.get(i.get("material"))
        count = max(0, int(i.get("count") or 0))
        if m and m["accepted"] and m["unit_kg"] > 0 and count > 0:
            kg_by_material[i["material"]] = kg_by_material.get(i["material"], 0.0) + count * m["unit_kg"]
    total = sum(kg_by_material.values())
    # share = สัดส่วนตามน้ำหนัก ใช้แบ่งน้ำหนักจริงไปยังโรงงานปลายทาง
    materials = [{"material": k, "share": round(v / total, 3)} for k, v in kg_by_material.items()]
    value = sum(v * mats[k]["price"] for k, v in kg_by_material.items())
    return {"materials": materials, "est_kg": round(total, 2), "est_value": round(value, 1)}


def aggregate_items(bags: list[dict]) -> list[dict]:
    """รวมรายการของทุกถุงเป็นรายการเดียวต่อชื่อและวัสดุ ใช้แสดงยอดรวมของคำขอ"""
    merged: dict[tuple[str, str], dict] = {}
    for b in bags:
        for i in b["items"]:
            key = (i["name_th"], i["material"])
            if key not in merged:
                merged[key] = {"name_th": i["name_th"], "material": i["material"], "count": 0, "prep_tip_th": i.get("prep_tip_th", "")}
            merged[key]["count"] += max(0, int(i.get("count") or 0))
    return list(merged.values())

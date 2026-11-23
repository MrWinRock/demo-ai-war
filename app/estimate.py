"""แปลงจำนวนชิ้นที่นับได้ เป็นน้ำหนักและมูลค่าโดยประมาณ

น้ำหนัก = จำนวนชิ้น x น้ำหนักเฉลี่ยต่อชิ้นของวัสดุนั้น คำนวณที่เซิร์ฟเวอร์จากตารางใน config
ไม่ให้ LLM คิดเลขเอง และคนขับยืนยันน้ำหนักจริงอีกครั้งตอนรับ
"""
from .config import MATERIALS


def estimate(items: list[dict]) -> dict:
    kg_by_material: dict[str, float] = {}
    for i in items:
        m = MATERIALS.get(i.get("material"))
        count = max(0, int(i.get("count") or 0))
        if m and m["unit_kg"] > 0 and count > 0:
            kg_by_material[i["material"]] = kg_by_material.get(i["material"], 0.0) + count * m["unit_kg"]
    total = sum(kg_by_material.values())
    # share = สัดส่วนตามน้ำหนัก ใช้แบ่งน้ำหนักจริงไปยังโรงงานปลายทาง
    materials = [{"material": k, "share": round(v / total, 3)} for k, v in kg_by_material.items()]
    value = sum(v * MATERIALS[k]["price"] for k, v in kg_by_material.items())
    return {"materials": materials, "est_kg": round(total, 2), "est_value": round(value, 1)}

"""แปลงผลที่ AI เห็นในรูป เป็นน้ำหนักและมูลค่าโดยประมาณ

ตัวเลขคำนวณที่ฝั่งเซิร์ฟเวอร์จากตารางราคา ไม่ให้ LLM คิดเลขเอง
สัดส่วนวัสดุคิดจากจำนวนชิ้น ซึ่งหยาบ จึงให้คนขับยืนยันน้ำหนักจริงตอนรับ
"""
from .config import MATERIALS, SIZES


def estimate(items: list[dict], size: str) -> dict:
    ok = [i for i in items if i.get("material") in MATERIALS and i["material"] != "non_recyclable"]
    counts: dict[str, int] = {}
    for i in ok:
        counts[i["material"]] = counts.get(i["material"], 0) + max(1, int(i.get("count") or 1))
    total = sum(counts.values())
    kg = float(SIZES[size]["kg"]) if total else 0.0
    materials = [{"material": m, "share": round(c / total, 3)} for m, c in counts.items()]
    value = sum(x["share"] * kg * MATERIALS[x["material"]]["price"] for x in materials)
    return {"materials": materials, "est_kg": kg, "est_value": round(value, 1)}

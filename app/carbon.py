"""ประมาณการก๊าซเรือนกระจกที่หลีกเลี่ยงได้จากการรีไซเคิล

เป็นการประมาณเบื้องต้นสำหรับรายงานภายในและงาน ESG ไม่ใช่คาร์บอนเครดิตที่ซื้อขายได้
การขอคาร์บอนเครดิต (เช่น T-VER ของ อบก.) ต้องขึ้นทะเบียนโครงการ ใช้ระเบียบวิธีที่รับรอง และผ่านการทวนสอบ
"""
from .config import SHORT_TON_KG, WARM_RECYCLING_MTCO2E_PER_SHORT_TON

# kgCO2e ที่หลีกเลี่ยงได้ต่อวัสดุ 1 กก. (แปลงจาก MTCO2E ต่อ short ton และกลับเครื่องหมายให้เป็นค่าบวก)
KG_CO2E_PER_KG = {k: round(-v * 1000 / SHORT_TON_KG, 3) for k, v in WARM_RECYCLING_MTCO2E_PER_SHORT_TON.items()}


def avoided_kg(kg_by_material: dict[str, float]) -> float:
    return sum(kg * KG_CO2E_PER_KG.get(m, 0) for m, kg in kg_by_material.items())

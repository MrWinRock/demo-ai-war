"""จุดที่ใช้ AI สองจุด: (1) แยกชนิดและนับขยะจากรูป (2) แปลคำสั่งภาษาพูดของผู้จัดรถเป็น action

ถ้าไม่มี ANTHROPIC_API_KEY หรือเรียก API ไม่สำเร็จ จะคืนผลแบบจำลองพร้อมธง source="mock"
เพื่อให้เดโมเดินต่อได้ หน้าเว็บแสดงธงนี้ให้เห็นชัดเจนเสมอ
"""
import hashlib
import json
import os
import re

import anthropic

from .config import MATERIALS

MODEL = "claude-opus-5-5"
ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_client: anthropic.Anthropic | None = None


class AIError(Exception):
    pass


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _ask(system: str, content: list | str, schema: dict) -> dict:
    """เรียก Claude แบบบังคับรูปแบบคำตอบเป็น JSON ตาม schema"""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    try:
        resp = _client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            # ถ้าโมเดลหลักปฏิเสธคำขอ ให้ API ลองโมเดลสำรองให้ในการเรียกครั้งเดียวกัน
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            # งานจำแนกภาพไม่ต้องคิดลึก ใช้ effort ต่ำเพื่อให้ตอบเร็วตอนเดโม
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.AuthenticationError as e:
        raise AIError("API key ไม่ถูกต้อง") from e
    except anthropic.RateLimitError as e:
        raise AIError("เรียก AI ถี่เกินไป ลองใหม่อีกครั้ง") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"AI ตอบผิดพลาด ({e.status_code})") from e
    except anthropic.APIConnectionError as e:
        raise AIError("เชื่อมต่อ AI ไม่ได้") from e

    if resp.stop_reason == "refusal":
        raise AIError("AI ปฏิเสธคำขอนี้")
    if resp.stop_reason == "max_tokens":
        raise AIError("คำตอบของ AI ยาวเกินกำหนด")
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        raise AIError("AI ไม่ได้ส่งคำตอบกลับมา")
    return json.loads(text)


# ---------- 1) แยกและนับขยะจากรูป ----------

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name_th": {"type": "string"},
                    "material": {"type": "string", "enum": list(MATERIALS.keys())},
                    "count": {"type": "integer"},
                    "prep_tip_th": {"type": "string"},
                },
                "required": ["name_th", "material", "count", "prep_tip_th"],
                "additionalProperties": False,
            },
        },
        "size": {"type": "string", "enum": ["S", "M", "L"]},
        "summary_th": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["items", "size", "summary_th", "confidence"],
    "additionalProperties": False,
}

CLASSIFY_SYSTEM = """คุณช่วยสมาชิกบริการรับขยะรีไซเคิลถึงบ้านในกรุงเทพฯ ผู้ใช้แนบรูปกองของที่อยากให้มารับ \
ผลของคุณจะถูกใช้กรอกคำขอรับอัตโนมัติ และใช้จัดรถกับเลือกโรงงานปลายทาง จึงต้องตรงกับสิ่งที่เห็นในรูปจริง

สิ่งที่ต้องทำ:
- แจกแจงของในรูปเป็นรายการ โดยรวมของชนิดเดียวกันไว้ในรายการเดียว แล้วนับจำนวนชิ้นที่มองเห็นใส่ใน count \
ถ้าของซ้อนหรือบังกันจนนับไม่ครบ ให้นับเท่าที่ประเมินได้อย่างสมเหตุสมผล และตั้ง confidence เป็น low หรือ medium
- เลือก material ให้ตรงชนิดวัสดุ: pet = ขวดพลาสติกใส, hdpe = พลาสติกขุ่นเช่นขวดนมหรือแกลลอน, \
other_plastic = พลาสติกชนิดอื่น, cardboard = กระดาษลัง, paper = กระดาษทั่วไป, aluminum = กระป๋องอะลูมิเนียม, \
steel = กระป๋องเหล็กหรือโลหะอื่น, glass = ขวดหรือโหลแก้ว, non_recyclable = ของที่บริการนี้ไม่รับ \
เช่น เศษอาหาร ของเปื้อนมาก โฟม ของอันตราย
- prep_tip_th คือคำแนะนำสั้น ๆ ก่อนส่ง เช่น เทน้ำออก ล้างคราบ บีบให้แบน แกะฉลาก ถ้าไม่มีอะไรต้องทำให้เว้นว่าง
- size คือปริมาตรของกองโดยรวม ใช้จองพื้นที่บนรถ: S ประมาณถุงหิ้วหนึ่งใบ, M ประมาณถุงดำหนึ่งใบ, L หลายถุงหรือหลายลัง
- summary_th คือสรุปหนึ่งประโยคให้สมาชิกอ่าน
- ถ้าในรูปไม่มีของที่เป็นขยะหรือของรีไซเคิลเลย ให้ items เป็นรายการว่าง และบอกเหตุผลใน summary_th

ตอบข้อความทุกช่องเป็นภาษาไทย"""

_MOCKS = [
    {
        "items": [
            {"name_th": "ขวดน้ำดื่มพลาสติก", "material": "pet", "count": 12, "prep_tip_th": "เทน้ำออกและบีบให้แบน"},
            {"name_th": "กระป๋องน้ำอัดลม", "material": "aluminum", "count": 6, "prep_tip_th": "ล้างคราบหวานออก"},
        ],
        "size": "S", "confidence": "medium",
        "summary_th": "พบขวดพลาสติกใสและกระป๋องอะลูมิเนียม รับได้ทั้งหมด",
    },
    {
        "items": [
            {"name_th": "ลังกระดาษ", "material": "cardboard", "count": 5, "prep_tip_th": "พับให้แบนและมัดรวมกัน"},
            {"name_th": "ขวดแก้ว", "material": "glass", "count": 4, "prep_tip_th": "ล้างและแยกฝาออก"},
            {"name_th": "กล่องโฟม", "material": "non_recyclable", "count": 2, "prep_tip_th": ""},
        ],
        "size": "M", "confidence": "medium",
        "summary_th": "พบลังกระดาษและขวดแก้วที่รับได้ ส่วนกล่องโฟมไม่อยู่ในรายการรับ",
    },
]


def classify(image_b64: str, media_type: str) -> dict:
    def mock(warning: str) -> dict:
        pick = int(hashlib.sha256(image_b64[:4096].encode()).hexdigest(), 16) % len(_MOCKS)
        return {**_MOCKS[pick], "source": "mock", "warning": warning}

    if not has_key():
        return mock("ยังไม่ได้ตั้งค่า API key จึงแสดงผลแบบจำลอง ไม่ได้มาจากรูปที่แนบ")
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
        {"type": "text", "text": "ช่วยแยกชนิดและนับจำนวนของในรูปนี้"},
    ]
    try:
        return {**_ask(CLASSIFY_SYSTEM, content, CLASSIFY_SCHEMA), "source": "claude", "warning": ""}
    except AIError as e:
        return mock(f"{e} จึงแสดงผลแบบจำลอง ไม่ได้มาจากรูปที่แนบ")


# ---------- 2) คำสั่งภาษาพูดของผู้จัดรถ ----------

COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["disable_vehicle", "enable_vehicle", "replan", "unknown"]},
        "vehicle_id": {"type": "integer"},
    },
    "required": ["action", "vehicle_id"],
    "additionalProperties": False,
}

COMMAND_SYSTEM = """คุณแปลคำสั่งภาษาพูดของผู้จัดรถเก็บขยะรีไซเคิลให้เป็นคำสั่งของระบบ \
ระบบจะนำคำสั่งไปจัดเส้นทางใหม่ด้วยตัวคำนวณเอง คุณไม่ต้องคิดเส้นทาง

คำสั่งที่ระบบรองรับ:
- disable_vehicle: รถคันหนึ่งใช้งานไม่ได้ เช่น เสีย คนขับลา ติดธุระ
- enable_vehicle: รถคันหนึ่งกลับมาใช้งานได้
- replan: ขอให้จัดเส้นทางใหม่โดยไม่เปลี่ยนสถานะรถ
- unknown: คำสั่งอยู่นอกเหนือจากสามแบบข้างต้น หรือระบุรถไม่ได้ว่าคันไหน

vehicle_id ให้ใส่ id ของรถที่ผู้ใช้หมายถึง จากรายการรถที่ให้ไว้ ถ้าคำสั่งไม่เกี่ยวกับรถคันใดให้ใส่ 0"""


def _parse_command_rule(text: str) -> dict:
    m = re.search(r"(?:รถ|คัน)\D{0,12}?(\d+)", text)
    vid = int(m.group(1)) if m else 0
    if vid and re.search(r"เสีย|พัง|หยุด|ปิด|ไม่ว่าง|ลา|ใช้ไม่ได้", text):
        return {"action": "disable_vehicle", "vehicle_id": vid}
    if vid and re.search(r"กลับมา|เปิด|พร้อม|ซ่อมเสร็จ|ใช้ได้", text):
        return {"action": "enable_vehicle", "vehicle_id": vid}
    if re.search(r"จัด|วางแผน|ใหม่|replan", text, re.I):
        return {"action": "replan", "vehicle_id": 0}
    return {"action": "unknown", "vehicle_id": 0}


def parse_command(text: str, vehicles: list[dict]) -> dict:
    if not has_key():
        return {**_parse_command_rule(text), "source": "rule"}
    fleet = ", ".join(f'id {v["id"]} = {v["name"]} ({"ใช้งานอยู่" if v["active"] else "หยุดใช้งาน"})' for v in vehicles)
    try:
        out = _ask(COMMAND_SYSTEM, f"รายการรถ: {fleet}\nคำสั่งของผู้จัดรถ: {text}", COMMAND_SCHEMA)
        return {**out, "source": "claude"}
    except AIError:
        return {**_parse_command_rule(text), "source": "rule"}

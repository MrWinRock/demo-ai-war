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


# ---------- 1) นับถุง แยกชนิด และนับชิ้นจากรูป ----------
# หนึ่งรูปอาจมีหลายภาชนะ (เช่น ถังแยก 4 ใบ) AI จึงตอบเป็นรายการ "ภาชนะ" แต่ละใบมีรายการของข้างใน
# แต่ละภาชนะจะกลายเป็นถุงหนึ่งใบในคำขอ มีป้ายของตัวเอง และคนขับตรวจรับทีละใบ

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "containers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name_th": {"type": "string"},
                    "position_th": {"type": "string"},
                    "kind": {"type": "string", "enum": ["bag", "bin", "box", "pile"]},
                    "mixed": {"type": "boolean"},
                    "size": {"type": "string", "enum": ["S", "M", "L"]},
                    "count_method": {"type": "string", "enum": ["exact", "estimate"]},
                    "partial_view": {"type": "boolean"},
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
                },
                "required": ["name_th", "position_th", "kind", "mixed", "size", "count_method", "partial_view", "items"],
                "additionalProperties": False,
            },
        },
        "summary_th": {"type": "string"},
        "photo_tip_th": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["containers", "summary_th", "photo_tip_th", "confidence"],
    "additionalProperties": False,
}

CLASSIFY_SYSTEM = """คุณช่วยสมาชิกบริการรับขยะรีไซเคิลถึงบ้านในกรุงเทพฯ สมาชิกถ่ายรูปของที่อยากให้มารับด้วยมือถือ \
ผลของคุณจะถูกใช้กรอกคำขอรับอัตโนมัติ ใช้จัดรถ ใช้เลือกโรงงานปลายทาง และคนขับจะใช้ตรวจรับทีละถุง จึงต้องตรงกับสิ่งที่เห็นในรูปจริง

คนทั่วไปถ่ายรูปแบบนี้ ซึ่งคุณต้องรับมือได้ทั้งหมด:
- ถุงใบเดียวที่อัดของชนิดเดียวไว้แน่น เช่น ขวดน้ำซ้อนทับกันเต็มถุง
- ถังหรือถุงหลายใบในรูปเดียว แต่ละใบแยกชนิดไว้แล้ว เช่น พลาสติก แก้ว กระดาษ โลหะ
- รูปถ่ายใกล้ที่เห็นกองของเพียงบางส่วน เช่น กระป๋องเต็มเฟรม
- ของหลายชนิดปนกันในถุงเดียว

วิธีทำ:
- แบ่งสิ่งที่เห็นเป็นภาชนะทีละใบใน containers ถ้าทั้งรูปเป็นถุงหรือกองเดียวให้มีรายการเดียว \
ถ้ามีหลายถุงหรือหลายถังให้แยกเป็นรายการละใบ อย่ารวมถังที่แยกกันอยู่ให้เป็นใบเดียว
- name_th คือชื่อสั้น ๆ ที่สมาชิกและคนขับใช้เรียกถุงนั้น เช่น "ถุงขวดพลาสติก" "ถังแก้ว" \
position_th คือตำแหน่งในรูป เช่น "บนซ้าย" "ล่างขวา" ถ้ามีใบเดียวให้ใส่ "ทั้งรูป"
- kind คือชนิดภาชนะ: bag ถุง, bin ถังหรือตะกร้า, box กล่องหรือลัง, pile กองที่ไม่มีภาชนะ
- items คือของในภาชนะนั้น รวมของชนิดเดียวกันไว้ในรายการเดียว และนับจำนวนชิ้นใส่ใน count
- ถ้านับได้ครบทุกชิ้นให้ count_method เป็น exact ถ้าของซ้อนหรือบังกันจนต้องประมาณ ให้เป็น estimate \
โดยประมาณจากชิ้นที่เห็นบวกกับส่วนที่น่าจะถูกบังอยู่อย่างสมเหตุสมผล อย่าใส่ตัวเลขที่สูงเกินกว่าปริมาตรของภาชนะจะจุได้
- ถ้ารูปตัดขอบจนเห็นกองหรือถุงเพียงบางส่วน ให้ partial_view เป็น true และนับเฉพาะส่วนที่อยู่ในรูป
- mixed เป็น true เมื่อภาชนะนั้นมีวัสดุต่างชนิดปนกันจนควรแยกก่อนส่ง
- size คือปริมาตรของภาชนะนั้น ใช้จองพื้นที่บนรถ: S ประมาณถุงหิ้วหนึ่งใบ, M ประมาณถุงดำหนึ่งใบ, L ใหญ่กว่านั้น
- เลือก material ให้ตรงชนิดวัสดุ: pet = ขวดพลาสติกใส, hdpe = พลาสติกขุ่นเช่นขวดนมหรือแกลลอน, \
other_plastic = พลาสติกชนิดอื่นเช่นถาด แก้ว ฝา, cardboard = กระดาษลังและกล่องกระดาษแข็ง, paper = กระดาษทั่วไป, \
aluminum = กระป๋องเครื่องดื่มอะลูมิเนียม, steel = กระป๋องอาหารหรือโลหะอื่น, glass = ขวดหรือโหลแก้ว, \
non_recyclable = ของที่บริการนี้ไม่รับ เช่น ซองขนม ถุงพลาสติกเปื้อน เศษอาหาร โฟม ของอันตราย
- prep_tip_th คือคำแนะนำสั้น ๆ ก่อนส่ง เช่น เทน้ำออก ล้างคราบ บีบให้แบน ถ้าไม่มีอะไรต้องทำให้เว้นว่าง
- summary_th คือสรุปหนึ่งประโยคให้สมาชิกอ่าน บอกจำนวนถุงและของหลัก
- photo_tip_th ใช้เมื่อถ่ายใหม่แล้วจะนับได้แม่นขึ้น เช่น ให้ถ่ายจากด้านบนให้เห็นทั้งถุง หรือเกลี่ยของออก ถ้ารูปดีพอแล้วให้เว้นว่าง
- confidence คือความมั่นใจโดยรวมของการนับ
- ถ้าในรูปไม่มีขยะหรือของรีไซเคิลเลย ให้ containers เป็นรายการว่าง และบอกเหตุผลใน summary_th

ตอบข้อความทุกช่องเป็นภาษาไทย"""

_MOCKS = [
    {
        "containers": [
            {"name_th": "ถุงขวดพลาสติก", "position_th": "ทั้งรูป", "kind": "bag", "mixed": False, "size": "M",
             "count_method": "estimate", "partial_view": False,
             "items": [{"name_th": "ขวดน้ำดื่มพลาสติก", "material": "pet", "count": 24, "prep_tip_th": "เทน้ำออกและบีบให้แบน"}]},
        ],
        "summary_th": "พบถุงขวดพลาสติกใส 1 ถุง ประมาณ 24 ขวด", "photo_tip_th": "", "confidence": "medium",
    },
    {
        "containers": [
            {"name_th": "ถังพลาสติก", "position_th": "บนซ้าย", "kind": "bin", "mixed": False, "size": "S",
             "count_method": "exact", "partial_view": False,
             "items": [{"name_th": "ขวดและภาชนะพลาสติก", "material": "pet", "count": 6, "prep_tip_th": "ล้างคราบออก"}]},
            {"name_th": "ถังแก้ว", "position_th": "บนขวา", "kind": "bin", "mixed": False, "size": "S",
             "count_method": "exact", "partial_view": False,
             "items": [{"name_th": "ขวดและโหลแก้ว", "material": "glass", "count": 5, "prep_tip_th": "แยกฝาออก"}]},
            {"name_th": "ถังโลหะ", "position_th": "ล่างขวา", "kind": "bin", "mixed": False, "size": "S",
             "count_method": "exact", "partial_view": False,
             "items": [{"name_th": "กระป๋องอาหาร", "material": "steel", "count": 7, "prep_tip_th": "ล้างเศษอาหารออก"}]},
        ],
        "summary_th": "พบถังแยกชนิด 3 ใบ คือพลาสติก แก้ว และโลหะ", "photo_tip_th": "", "confidence": "medium",
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
        {"type": "text", "text": "ช่วยแบ่งเป็นถุงหรือถังทีละใบ แยกชนิด และนับจำนวนของในรูปนี้"},
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

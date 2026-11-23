"""แยกถูก รับถึงบ้าน: API + เสิร์ฟหน้าเว็บ PWA"""
import base64
import csv
import hmac
import io
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import segno

from . import ai, db, routing, seed
from .config import CODE_ALPHABET, DEPOT, FACTORIES, MATERIALS, POINTS_PER_KG, QR_PREFIX, SIZES, SLOT_BY_ID, SLOTS
from .estimate import estimate

BASE = Path(__file__).resolve().parent.parent
BKK = timezone(timedelta(hours=7))


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    # ฐานข้อมูลว่าง หรือสร้างจากโครงสร้างรุ่นเก่า: ล้างแล้วใส่ข้อมูลตัวอย่างใหม่
    if db.get_kv("schema_version") != db.SCHEMA_VERSION:
        reseed()
    yield


app = FastAPI(title="แยกถูก รับถึงบ้าน", lifespan=lifespan)


# ---------- ตัวช่วย ----------

def reseed() -> None:
    db.reset()
    seed.run()
    db.set_kv("schema_version", db.SCHEMA_VERSION)
    compute_plan()


def load_requests(where: str = "", params: tuple = ()) -> list[dict]:
    rows = db.query(
        "SELECT r.id, r.member_id, r.lat, r.lng, r.slot, r.window_start, r.window_end, r.items, r.materials, r.size,"
        " r.volume, r.est_kg, r.est_value, r.status, r.actual_kg, r.note, r.created_at, (r.photo != '') AS has_photo,"
        " r.vehicle_id, r.verified_at, r.verify_distance_m, r.collected_at, r.delivered_at, r.actual_items,"
        f" m.name AS member_name, m.address FROM requests r JOIN members m ON m.id = r.member_id {where} ORDER BY r.id",
        params,
    )
    for r in rows:
        r["items"] = json.loads(r["items"])
        r["materials"] = json.loads(r["materials"])
        r["actual_items"] = json.loads(r["actual_items"]) if r["actual_items"] else None
        r["total_count"] = sum(int(i.get("count") or 0) for i in r["items"] if i.get("material") != "non_recyclable")
    return rows


def compute_plan() -> dict:
    """จัดเส้นทางจากคำขอที่ยังไม่ได้รับ แล้วเก็บแผนล่าสุดไว้"""
    vehicles = db.query("SELECT * FROM vehicles WHERE active = 1 ORDER BY id")
    reqs = load_requests("WHERE r.status IN ('pending', 'verified')")  # จุดที่คนขับยังรับไม่เสร็จ
    result = routing.solve(DEPOT, vehicles, reqs)
    by_id = {r["id"]: r for r in reqs}
    veh_by_id = {v["id"]: v for v in vehicles}

    served = [by_id[s["request_id"]] for route in result["routes"] for s in route["stops"]]
    served.sort(key=lambda r: r["id"])
    total_km = round(sum(route["km"] for route in result["routes"]), 1)
    base_km = round(routing.baseline_km(DEPOT, len(vehicles), served), 1)
    saving = round((1 - total_km / base_km) * 100) if base_km > 0 else 0

    # รวมน้ำหนักตามโรงงานปลายทาง จากสัดส่วนวัสดุของแต่ละคำขอ
    kg_by_type: dict[str, float] = {}
    for r in served:
        for m in r["materials"]:
            ftype = MATERIALS[m["material"]]["factory"]
            if ftype:
                kg_by_type[ftype] = kg_by_type.get(ftype, 0) + m["share"] * r["est_kg"]
    factory_kg = [
        {"factory_id": f["id"], "name": f["name"], "kg": round(sum(kg_by_type.get(t, 0) for t in f["accepts"]), 1)}
        for f in FACTORIES
    ]

    for route in result["routes"]:
        v = veh_by_id[route["vehicle_id"]]
        route.update(name=v["name"], color=v["color"], capacity_units=v["capacity_units"])

    n_stops = len(served)
    summary = f"ใช้รถ {sum(1 for r in result['routes'] if r['stops'])} คัน รับ {n_stops} จุด ระยะทางรวม {total_km} กม."
    if base_km > 0 and n_stops > 1:
        summary += f" สั้นกว่าวิ่งตามลำดับที่แจ้ง ({base_km} กม.) {saving}%"
    if result["unassigned"]:
        summary += f" มี {len(result['unassigned'])} จุดที่จัดไม่ลงในวันนี้"
    if not vehicles:
        summary = "ไม่มีรถที่ใช้งานได้ จึงยังจัดเส้นทางไม่ได้"

    plan = {
        "created_at": time.time(), "routes": result["routes"], "unassigned": result["unassigned"],
        "total_km": total_km, "baseline_km": base_km, "saving_pct": saving,
        "factory_kg": factory_kg, "summary": summary,
    }
    db.set_kv("plan", json.dumps(plan, ensure_ascii=False))
    return plan


def get_plan() -> dict | None:
    raw = db.get_kv("plan")
    return json.loads(raw) if raw else None


# ---------- API ----------

class ClassifyIn(BaseModel):
    image_b64: str
    media_type: str = "image/jpeg"


class ItemIn(BaseModel):
    name_th: str
    material: str
    count: int = 1
    ai_count: int | None = None   # จำนวนที่ AI นับได้ ก่อนสมาชิกแก้ไข
    prep_tip_th: str = ""


class RequestIn(BaseModel):
    member_id: int
    lat: float
    lng: float
    slot: str
    size: str
    items: list[ItemIn]
    photo: str = ""
    note: str = ""


class VerifyIn(BaseModel):
    scan: str                    # ข้อความจาก QR หรือรหัส 6 ตัวที่พิมพ์เอง
    vehicle_id: int
    lat: float | None = None     # ตำแหน่งคนขับตอนสแกน (ถ้าอุปกรณ์ให้ได้)
    lng: float | None = None


class CollectIn(BaseModel):
    actual_kg: float
    items: list[ItemIn] | None = None   # จำนวนที่คนขับนับได้จริง


class CommandIn(BaseModel):
    text: str


@app.get("/api/state")
def state():
    return {
        "ai_mode": "claude" if ai.has_key() else "mock",
        "config": {"materials": MATERIALS, "sizes": SIZES, "slots": SLOTS, "depot": DEPOT,
                   "factories": FACTORIES, "points_per_kg": POINTS_PER_KG},
        "members": db.query("SELECT * FROM members ORDER BY id"),
        "vehicles": db.query("SELECT * FROM vehicles ORDER BY id"),
        "requests": load_requests(),
        "plan": get_plan(),
        "dropoffs": json.loads(db.get_kv("dropoffs") or "[]")[-10:],
    }


@app.post("/api/classify")
def classify(body: ClassifyIn):
    if body.media_type not in ai.ALLOWED_MEDIA:
        raise HTTPException(400, "รองรับเฉพาะไฟล์ภาพ JPEG, PNG, WebP หรือ GIF")
    if len(body.image_b64) > 7_000_000:
        raise HTTPException(413, "รูปใหญ่เกินไป")
    try:
        base64.b64decode(body.image_b64, validate=True)
    except Exception:
        raise HTTPException(400, "ข้อมูลรูปไม่ถูกต้อง")
    result = ai.classify(body.image_b64, body.media_type)
    result["estimate"] = estimate(result["items"])
    return result


@app.post("/api/requests")
def create_request(body: RequestIn):
    if body.slot not in SLOT_BY_ID or body.size not in SIZES:
        raise HTTPException(400, "ช่วงเวลาหรือขนาดกองไม่ถูกต้อง")
    if not db.query("SELECT 1 FROM members WHERE id = ?", (body.member_id,)):
        raise HTTPException(404, "ไม่พบสมาชิก")
    if not (-90 <= body.lat <= 90 and -180 <= body.lng <= 180):
        raise HTTPException(400, "พิกัดไม่ถูกต้อง")
    photo = body.photo if body.photo.startswith("data:image/jpeg;base64,") and len(body.photo) < 300_000 else ""
    items = [i.model_dump() for i in body.items if i.material in MATERIALS]
    est = estimate(items)
    if est["est_kg"] <= 0:
        raise HTTPException(400, "ไม่มีรายการที่รับได้ในคำขอนี้")
    slot = SLOT_BY_ID[body.slot]
    rid = db.execute(
        "INSERT INTO requests(member_id, lat, lng, slot, window_start, window_end, items, materials, size, volume,"
        " est_kg, est_value, photo, note, code, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (body.member_id, round(body.lat, 6), round(body.lng, 6), slot["id"], slot["start"], slot["end"],
         json.dumps(items, ensure_ascii=False), json.dumps(est["materials"]), body.size, SIZES[body.size]["units"],
         est["est_kg"],
         est["est_value"], photo, body.note[:200], "".join(secrets.choice(CODE_ALPHABET) for _ in range(6)), time.time()),
    )
    plan = compute_plan()  # มีงานใหม่เข้ามา จัดเส้นทางใหม่ทันที
    stop = next(
        ({"vehicle": r["name"], "eta": s["eta"], "seq": n + 1}
         for r in plan["routes"] for n, s in enumerate(r["stops"]) if s["request_id"] == rid),
        None,
    )
    return {"request": load_requests("WHERE r.id = ?", (rid,))[0], "stop": stop}


@app.get("/api/requests/{rid}/photo")
def request_photo(rid: int):
    rows = db.query("SELECT photo FROM requests WHERE id = ?", (rid,))
    if not rows or not rows[0]["photo"]:
        raise HTTPException(404, "ไม่มีรูป")
    return Response(base64.b64decode(rows[0]["photo"].split(",", 1)[1]), media_type="image/jpeg")


@app.get("/api/requests/{rid}/ticket")
def ticket(rid: int):
    """QR และรหัสที่สมาชิกแสดงให้คนขับ เดโมนี้ไม่มีระบบล็อกอิน จึงยังไม่ได้จำกัดว่าใครเรียกได้"""
    rows = db.query("SELECT code FROM requests WHERE id = ?", (rid,))
    if not rows:
        raise HTTPException(404, "ไม่พบคำขอ")
    payload = f"{QR_PREFIX}:{rid}:{rows[0]['code']}"
    buf = io.BytesIO()
    # make_qr บังคับเป็น QR ปกติ (ค่าเริ่มต้นอาจได้ Micro QR ซึ่งกล้องมือถือส่วนใหญ่อ่านไม่ได้)
    # omitsize ให้ SVG มี viewBox จึงย่อขยายตามขนาดที่หน้าเว็บกำหนด
    segno.make_qr(payload, error="m").save(buf, kind="svg", border=3, xmldecl=False, light="#ffffff", omitsize=True)
    return {"request_id": rid, "code": rows[0]["code"], "payload": payload, "svg": buf.getvalue().decode("utf-8")}


@app.post("/api/requests/{rid}/verify")
def verify(rid: int, body: VerifyIn):
    """คนขับสแกน QR ของสมาชิกเมื่อถึงจุด: ยืนยันว่ามาถูกคำขอ ก่อนจะรับของได้"""
    rows = db.query("SELECT * FROM requests WHERE id = ?", (rid,))
    if not rows:
        raise HTTPException(404, "ไม่พบคำขอ")
    req = rows[0]
    if req["status"] in ("collected", "delivered"):
        raise HTTPException(409, "คำขอนี้รับไปแล้ว")
    if not db.query("SELECT 1 FROM vehicles WHERE id = ?", (body.vehicle_id,)):
        raise HTTPException(404, "ไม่พบรถ")

    scan = body.scan.strip().upper()
    code = scan
    if scan.startswith(QR_PREFIX + ":"):
        parts = scan.split(":")
        if len(parts) != 3 or not parts[1].isdigit():
            raise HTTPException(400, "QR นี้ไม่ใช่ของระบบ")
        if int(parts[1]) != rid:
            raise HTTPException(409, f"QR นี้เป็นของคำขอ #{int(parts[1])} ไม่ใช่จุดนี้")
        code = parts[2]
    if not hmac.compare_digest(code, req["code"]):
        raise HTTPException(400, "รหัสไม่ตรงกับคำขอนี้")

    distance = None
    if body.lat is not None and body.lng is not None:
        distance = round(routing.haversine_km((body.lat, body.lng), (req["lat"], req["lng"])) * 1000)
    now = time.time()
    if req["status"] == "pending":
        db.execute(
            "UPDATE requests SET status = 'verified', verified_at = ?, verify_distance_m = ?, vehicle_id = ? WHERE id = ?",
            (now, distance, body.vehicle_id, rid),
        )
    return {"ok": True, "verified_at": req["verified_at"] or now, "distance_m": distance}


@app.post("/api/requests/{rid}/collect")
def collect(rid: int, body: CollectIn):
    """คนขับตรวจของและบันทึกน้ำหนักจริง ทำได้หลังยืนยันจุดด้วย QR แล้วเท่านั้น"""
    rows = db.query("SELECT * FROM requests WHERE id = ?", (rid,))
    if not rows:
        raise HTTPException(404, "ไม่พบคำขอ")
    req = rows[0]
    if req["status"] in ("collected", "delivered"):
        raise HTTPException(409, "คำขอนี้รับไปแล้ว")
    if req["status"] != "verified":
        raise HTTPException(409, "ต้องสแกน QR ของลูกค้าเพื่อยืนยันจุดก่อน")
    if not 0 < body.actual_kg <= 500:
        raise HTTPException(400, "น้ำหนักต้องมากกว่า 0 และไม่เกิน 500 กก.")
    actual = [i.model_dump() for i in body.items if i.material in MATERIALS] if body.items is not None else None
    points = round(body.actual_kg * POINTS_PER_KG)
    db.execute(
        "UPDATE requests SET status = 'collected', actual_kg = ?, actual_items = ?, collected_at = ? WHERE id = ?",
        (body.actual_kg, json.dumps(actual, ensure_ascii=False) if actual is not None else None, time.time(), rid),
    )
    db.execute("UPDATE members SET points = points + ? WHERE id = ?", (points, req["member_id"]))
    return {"ok": True, "points": points}


@app.post("/api/vehicles/{vid}/dropoff")
def dropoff(vid: int):
    """ปิดรอบ: รถส่งของที่รับมาทั้งหมดให้ศูนย์คัดแยก และสรุปน้ำหนักที่ต้องส่งต่อแต่ละโรงงาน"""
    veh = db.query("SELECT * FROM vehicles WHERE id = ?", (vid,))
    if not veh:
        raise HTTPException(404, "ไม่พบรถ")
    loads = load_requests("WHERE r.status = 'collected' AND r.vehicle_id = ?", (vid,))
    if not loads:
        raise HTTPException(409, "ไม่มีของบนรถที่ต้องส่ง")
    kg_by_type: dict[str, float] = {}
    for r in loads:
        for m in r["materials"]:
            ftype = MATERIALS[m["material"]]["factory"]
            if ftype:
                kg_by_type[ftype] = kg_by_type.get(ftype, 0) + m["share"] * r["actual_kg"]
    now = time.time()
    db.execute("UPDATE requests SET status = 'delivered', delivered_at = ? WHERE status = 'collected' AND vehicle_id = ?", (now, vid))
    summary = {
        "vehicle_id": vid, "vehicle": veh[0]["name"], "at": now, "stops": len(loads),
        "kg": round(sum(r["actual_kg"] for r in loads), 1),
        "pieces": sum(sum(int(i.get("count") or 0) for i in (r["actual_items"] or r["items"]) if i.get("material") != "non_recyclable") for r in loads),
        "factories": [
            {"name": f["name"], "kg": round(sum(kg_by_type.get(t, 0) for t in f["accepts"]), 1)} for f in FACTORIES
        ],
    }
    history = json.loads(db.get_kv("dropoffs") or "[]")
    history.append(summary)
    db.set_kv("dropoffs", json.dumps(history[-50:], ensure_ascii=False))
    return summary


@app.post("/api/plan")
def plan():
    return compute_plan()


@app.post("/api/command")
def command(body: CommandIn):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "กรุณาพิมพ์คำสั่ง")
    vehicles = db.query("SELECT * FROM vehicles ORDER BY id")
    parsed = ai.parse_command(text[:500], vehicles)
    action, vid = parsed["action"], parsed["vehicle_id"]
    veh = next((v for v in vehicles if v["id"] == vid), None)

    if action in ("disable_vehicle", "enable_vehicle") and veh:
        db.execute("UPDATE vehicles SET active = ? WHERE id = ?", (0 if action == "disable_vehicle" else 1, vid))
        did = f"{'หยุดใช้' if action == 'disable_vehicle' else 'เปิดใช้'}{veh['name']} แล้ว"
    elif action == "replan":
        did = "จัดเส้นทางใหม่แล้ว"
    else:
        return {"ok": False, "source": parsed["source"],
                "reply": "ยังไม่เข้าใจคำสั่งนี้ ลองพิมพ์เช่น “รถคัน 2 เสีย” “รถคัน 2 กลับมาแล้ว” หรือ “จัดเส้นทางใหม่”"}
    new_plan = compute_plan()
    return {"ok": True, "source": parsed["source"], "reply": f"{did} {new_plan['summary']}"}


@app.post("/api/reset")
def reset():
    reseed()
    return {"ok": True}


STATUS_LABEL = {"pending": "รอรับ", "verified": "ยืนยันจุดแล้ว", "collected": "รับแล้ว", "delivered": "ส่งถึงศูนย์แล้ว"}


def fmt_time(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, BKK).strftime("%Y-%m-%d %H:%M") if ts else ""


@app.get("/api/records.csv")
def records_csv():
    vehicles = {v["id"]: v["name"] for v in db.query("SELECT id, name FROM vehicles")}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["เลขที่", "เวลาแจ้ง", "สมาชิก", "ละติจูด", "ลองจิจูด", "ช่วงเวลานัด", "รายการ (ชิ้น)", "จำนวนรวม (ชิ้น)",
                "ขนาดกอง", "พื้นที่บนรถ (ถุง)", "น้ำหนักประมาณ (กก.)", "มูลค่าประมาณ (บาท)", "สถานะ", "รถที่รับ",
                "เวลายืนยันจุด", "ระยะจากหมุดตอนสแกน (ม.)", "เวลารับของ", "จำนวนที่รับจริง (ชิ้น)", "น้ำหนักจริง (กก.)", "เวลาส่งถึงศูนย์"])
    for r in load_requests():
        items = "; ".join(f'{i["name_th"]} x{i.get("count", 0)}' for i in r["items"])
        actual = sum(int(i.get("count") or 0) for i in r["actual_items"]) if r["actual_items"] else ""
        w.writerow([r["id"], fmt_time(r["created_at"]), r["member_name"], r["lat"], r["lng"], SLOT_BY_ID[r["slot"]]["label"], items,
                    r["total_count"], r["size"], r["volume"], r["est_kg"], r["est_value"], STATUS_LABEL[r["status"]],
                    vehicles.get(r["vehicle_id"], ""), fmt_time(r["verified_at"]),
                    r["verify_distance_m"] if r["verify_distance_m"] is not None else "", fmt_time(r["collected_at"]),
                    actual, r["actual_kg"] or "", fmt_time(r["delivered_at"])])
    # ใส่ BOM ให้ Excel อ่านภาษาไทยได้ถูกต้อง
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="pickup-records.csv"'})


@app.get("/api/health")
def health():
    return {"ok": True}


app.mount("/icons", StaticFiles(directory=os.environ.get("ICON_DIR", str(BASE / "icons")), check_dir=False), name="icons")
app.mount("/", StaticFiles(directory=str(BASE / "web"), html=True), name="web")

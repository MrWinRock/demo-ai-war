"""แยกถูก รับถึงบ้าน: API + เสิร์ฟหน้าเว็บ PWA"""
import base64
import csv
import io
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, db, routing, seed
from .config import DEPOT, FACTORIES, MATERIALS, POINTS_PER_KG, SIZES, SLOT_BY_ID, SLOTS
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
        f" m.name AS member_name, m.address FROM requests r JOIN members m ON m.id = r.member_id {where} ORDER BY r.id",
        params,
    )
    for r in rows:
        r["items"] = json.loads(r["items"])
        r["materials"] = json.loads(r["materials"])
        r["total_count"] = sum(int(i.get("count") or 0) for i in r["items"] if i.get("material") != "non_recyclable")
    return rows


def compute_plan() -> dict:
    """จัดเส้นทางจากคำขอที่ยังไม่ได้รับ แล้วเก็บแผนล่าสุดไว้"""
    vehicles = db.query("SELECT * FROM vehicles WHERE active = 1 ORDER BY id")
    reqs = load_requests("WHERE r.status = 'pending'")
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


class CollectIn(BaseModel):
    actual_kg: float


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
        " est_kg, est_value, photo, note, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (body.member_id, round(body.lat, 6), round(body.lng, 6), slot["id"], slot["start"], slot["end"],
         json.dumps(items, ensure_ascii=False), json.dumps(est["materials"]), body.size, SIZES[body.size]["units"],
         est["est_kg"],
         est["est_value"], photo, body.note[:200], time.time()),
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


@app.post("/api/requests/{rid}/collect")
def collect(rid: int, body: CollectIn):
    rows = db.query("SELECT * FROM requests WHERE id = ?", (rid,))
    if not rows:
        raise HTTPException(404, "ไม่พบคำขอ")
    if rows[0]["status"] == "collected":
        raise HTTPException(409, "คำขอนี้รับไปแล้ว")
    if not 0 < body.actual_kg <= 500:
        raise HTTPException(400, "น้ำหนักต้องมากกว่า 0 และไม่เกิน 500 กก.")
    points = round(body.actual_kg * POINTS_PER_KG)
    db.execute("UPDATE requests SET status = 'collected', actual_kg = ? WHERE id = ?", (body.actual_kg, rid))
    db.execute("UPDATE members SET points = points + ? WHERE id = ?", (points, rows[0]["member_id"]))
    return {"ok": True, "points": points}


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


@app.get("/api/records.csv")
def records_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["เลขที่", "เวลาแจ้ง", "สมาชิก", "ละติจูด", "ลองจิจูด", "ช่วงเวลานัด", "รายการ (ชิ้น)", "จำนวนรวม (ชิ้น)",
                "ขนาดกอง", "พื้นที่บนรถ (ถุง)", "น้ำหนักประมาณ (กก.)", "มูลค่าประมาณ (บาท)", "สถานะ", "น้ำหนักจริง (กก.)"])
    for r in load_requests():
        items = "; ".join(f'{i["name_th"]} x{i.get("count", 0)}' for i in r["items"])
        when = datetime.fromtimestamp(r["created_at"], BKK).strftime("%Y-%m-%d %H:%M")
        w.writerow([r["id"], when, r["member_name"], r["lat"], r["lng"], SLOT_BY_ID[r["slot"]]["label"], items,
                    r["total_count"], r["size"], r["volume"], r["est_kg"], r["est_value"],
                    "รับแล้ว" if r["status"] == "collected" else "รอรับ", r["actual_kg"] or ""])
    # ใส่ BOM ให้ Excel อ่านภาษาไทยได้ถูกต้อง
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="pickup-records.csv"'})


@app.get("/api/health")
def health():
    return {"ok": True}


app.mount("/icons", StaticFiles(directory=os.environ.get("ICON_DIR", str(BASE / "icons")), check_dir=False), name="icons")
app.mount("/", StaticFiles(directory=str(BASE / "web"), html=True), name="web")

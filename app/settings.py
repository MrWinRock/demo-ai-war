"""เกณฑ์การรับของและการผ่อนปรนที่ผู้ดูแลระบบแก้ได้ เก็บเป็น JSON ในตาราง kv"""
import copy
import json

from . import db
from .config import DEFAULT_SETTINGS, MATERIALS, POLICIES


def get() -> dict:
    stored = json.loads(db.get_kv("settings") or "{}")
    out = copy.deepcopy(DEFAULT_SETTINGS)
    out.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS and k != "materials"})
    saved = stored.get("materials", {})
    for key, m in MATERIALS.items():
        if key == "non_recyclable":
            continue
        s = saved.get(key, {})
        out["materials"][key] = {
            "accepted": bool(s.get("accepted", True)),
            "price": float(s.get("price", m["price"])),
            "unit_kg": float(s.get("unit_kg", m["unit_kg"])),
        }
    return out


def materials() -> dict:
    """ตารางวัสดุที่ใช้คำนวณจริง: ป้ายและโรงงานจาก config รวมกับราคา น้ำหนักต่อชิ้น และการรับ/ไม่รับ จากเกณฑ์ล่าสุด"""
    s = get()["materials"]
    out = {}
    for key, m in MATERIALS.items():
        cur = s.get(key, {"accepted": False, "price": 0, "unit_kg": 0})
        out[key] = {"label": m["label"], "factory": m["factory"], **cur}
    return out


def save(patch: dict) -> dict:
    """ตรวจค่าที่ผู้ดูแลส่งมา แล้วบันทึกเฉพาะช่องที่รู้จัก คืนเกณฑ์ล่าสุด"""
    cur = get()
    for key, value in patch.items():
        if key == "materials":
            for mk, mv in (value or {}).items():
                if mk not in cur["materials"]:
                    raise ValueError(f"ไม่รู้จักวัสดุ {mk}")
                price, unit = float(mv.get("price", cur["materials"][mk]["price"])), float(mv.get("unit_kg", cur["materials"][mk]["unit_kg"]))
                if not (0 <= price <= 1000 and 0 < unit <= 50):
                    raise ValueError("ราคาต้องอยู่ระหว่าง 0–1,000 บาท และน้ำหนักต่อชิ้นต้องมากกว่า 0")
                cur["materials"][mk] = {"accepted": bool(mv.get("accepted", cur["materials"][mk]["accepted"])), "price": price, "unit_kg": unit}
        elif key in POLICIES:
            if value not in POLICIES[key]:
                raise ValueError(f"ค่าของ {key} ไม่ถูกต้อง")
            cur[key] = value
        elif key in ("allow_partial_pickup", "road_routing"):
            cur[key] = bool(value)
        elif key in ("min_request_kg", "scan_max_distance_m", "weight_tolerance_pct", "points_per_kg", "carbon_price_thb"):
            v = float(value)
            if not 0 <= v <= 100000:
                raise ValueError("ตัวเลขต้องไม่ติดลบ")
            cur[key] = v
        else:
            raise ValueError(f"ไม่รู้จักการตั้งค่า {key}")
    db.set_kv("settings", json.dumps(cur, ensure_ascii=False))
    return cur

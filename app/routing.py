"""จัดเส้นทางรถเก็บขยะรีไซเคิล: VRP แบบมีเวลานัดและความจุรถ ด้วย OR-Tools

ความจุรถคิดจากพื้นที่ (volume ของคำขอ เทียบ capacity_units ของรถ) เพราะของรีไซเคิลเบาแต่กินที่

ข้อจำกัดของเดโม: ระยะทางใช้เส้นตรงคูณค่าคงที่ (ไม่ใช่ระยะถนนจริง) และความเร็วเฉลี่ยคงที่
"""
import math

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

ROAD_FACTOR = 1.35   # เส้นตรง -> ระยะถนนโดยประมาณ
SPEED_KMH = 22       # ความเร็วเฉลี่ยในเมือง
SERVICE_MIN = 6      # เวลาจอดรับต่อจุด
DAY_START = 510      # 08:30 รถออกจากศูนย์
DAY_END = 1080       # 18:00 รถต้องกลับถึงศูนย์
DROP_PENALTY = 200_000  # เมตร: ยอมทิ้งจุดก็ต่อเมื่อจัดไม่ลงจริง ๆ


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def road_km(a, b) -> float:
    return haversine_km(a, b) * ROAD_FACTOR


def path_km(points: list[tuple[float, float]]) -> float:
    return sum(road_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def baseline_km(depot: dict, n_vehicles: int, requests: list[dict]) -> float:
    """วิ่งตามลำดับที่แจ้งเข้ามา แบ่งงานสลับคันไปเรื่อย ๆ ใช้เป็นตัวเทียบ"""
    if not n_vehicles or not requests:
        return 0.0
    d = (depot["lat"], depot["lng"])
    total = 0.0
    for v in range(n_vehicles):
        stops = [(r["lat"], r["lng"]) for i, r in enumerate(requests) if i % n_vehicles == v]
        if stops:
            total += path_km([d] + stops + [d])
    return total


def solve(depot: dict, vehicles: list[dict], requests: list[dict], time_limit_s: int = 2) -> dict:
    """คืน {"routes": [{vehicle_id, km, load_units, load_kg, stops: [{request_id, eta}]}], "unassigned": [request_id]}"""
    empty = [{"vehicle_id": v["id"], "km": 0.0, "load_units": 0, "load_kg": 0.0, "stops": [], "back_at": None} for v in vehicles]
    if not vehicles or not requests:
        return {"routes": empty, "unassigned": [r["id"] for r in requests]}

    pts = [(depot["lat"], depot["lng"])] + [(r["lat"], r["lng"]) for r in requests]
    n = len(pts)
    km = [[road_km(pts[i], pts[j]) if i != j else 0.0 for j in range(n)] for i in range(n)]
    dist_m = [[int(round(km[i][j] * 1000)) for j in range(n)] for i in range(n)]
    # เวลาเดินทาง + เวลาจอดรับที่จุดต้นทาง (ศูนย์ไม่มีเวลาจอด)
    minutes = [
        [0 if i == j else math.ceil(km[i][j] / SPEED_KMH * 60) + (SERVICE_MIN if i > 0 else 0) for j in range(n)]
        for i in range(n)
    ]

    manager = pywrapcp.RoutingIndexManager(n, len(vehicles), 0)
    model = pywrapcp.RoutingModel(manager)

    dist_cb = model.RegisterTransitCallback(lambda i, j: dist_m[manager.IndexToNode(i)][manager.IndexToNode(j)])
    model.SetArcCostEvaluatorOfAllVehicles(dist_cb)

    time_cb = model.RegisterTransitCallback(lambda i, j: minutes[manager.IndexToNode(i)][manager.IndexToNode(j)])
    model.AddDimension(time_cb, 240, DAY_END, False, "Time")  # รอหน้าบ้านได้สูงสุด 240 นาที
    time_dim = model.GetDimensionOrDie("Time")
    for node, r in enumerate(requests, start=1):
        time_dim.CumulVar(manager.NodeToIndex(node)).SetRange(int(r["window_start"]), int(r["window_end"]))
    for v in range(len(vehicles)):
        time_dim.CumulVar(model.Start(v)).SetRange(DAY_START, DAY_END)
        time_dim.CumulVar(model.End(v)).SetRange(DAY_START, DAY_END)
        model.AddVariableMinimizedByFinalizer(time_dim.CumulVar(model.End(v)))

    def demand(i: int) -> int:
        node = manager.IndexToNode(i)
        return 0 if node == 0 else int(requests[node - 1]["volume"])

    demand_cb = model.RegisterUnaryTransitCallback(demand)
    model.AddDimensionWithVehicleCapacity(demand_cb, 0, [int(v["capacity_units"]) for v in vehicles], True, "Load")

    for node in range(1, n):
        model.AddDisjunction([manager.NodeToIndex(node)], DROP_PENALTY)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromSeconds(time_limit_s)
    sol = model.SolveWithParameters(params)
    if sol is None:
        return {"routes": empty, "unassigned": [r["id"] for r in requests]}

    routes, served = [], set()
    for v, veh in enumerate(vehicles):
        idx, stops, route_km, load, units, prev = model.Start(v), [], 0.0, 0.0, 0, 0
        while not model.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node > 0:
                r = requests[node - 1]
                served.add(r["id"])
                load += r["est_kg"]
                units += int(r["volume"])
                stops.append({"request_id": r["id"], "eta": sol.Min(time_dim.CumulVar(idx))})
            route_km += km[prev][node]
            prev = node
            idx = sol.Value(model.NextVar(idx))
        route_km += km[prev][0]
        routes.append({
            "vehicle_id": veh["id"], "km": round(route_km, 1) if stops else 0.0, "load_units": units, "load_kg": round(load, 1),
            "stops": stops, "back_at": sol.Min(time_dim.CumulVar(idx)) if stops else None,
        })
    return {"routes": routes, "unassigned": [r["id"] for r in requests if r["id"] not in served]}

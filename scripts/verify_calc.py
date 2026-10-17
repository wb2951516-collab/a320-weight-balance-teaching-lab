"""快速校验装载计算是否落在合理 %MAC"""
import math

MAC = 4.195
LEMAC = 13.0
OEW, OEW_ST = 42500.0, 13.0 + 0.25 * MAC
PAX_W, BAG_W = 84.0, 12.0
ZONES = {"FWD": 13.15, "MID": 14.50, "AFT": 16.10}
CARGO = {"FWD": 12.55, "AFT": 16.55, "BULK": 17.35}
FUEL = {"WING": 14.00, "CTR": 14.80}
INIT_PAX = {"FWD": 40, "MID": 60, "AFT": 35}
INIT_CARGO = {"FWD": 1800, "AFT": 2200, "BULK": 400}
INIT_FUEL = {"WING": 8500, "CTR": 3500}


def calc(pax, cargo, fuel):
    items = [(OEW, OEW_ST)]
    for z, n in pax.items():
        items.append((n * PAX_W, ZONES[z]))
        bag_st = CARGO["FWD"] if z == "FWD" else CARGO["AFT"]
        items.append((n * BAG_W, bag_st))
    for c, kg in cargo.items():
        items.append((kg, CARGO[c]))
    for f, kg in fuel.items():
        items.append((kg, FUEL[f]))
    tw = sum(w for w, _ in items)
    tm = sum(w * a for w, a in items)
    cg = tm / tw
    mac = (cg - LEMAC) / MAC * 100
    return tw, tm, cg, mac


print("=== 正常 ===", calc(INIT_PAX, INIT_CARGO, INIT_FUEL))
print("=== 前重 ===", calc({"FWD": 60, "MID": 15, "AFT": 0}, {"FWD": 3500, "AFT": 0, "BULK": 0}, {"WING": 12000, "CTR": 0}))
print("=== 后重 ===", calc({"FWD": 0, "MID": 10, "AFT": 50}, {"FWD": 0, "AFT": 4500, "BULK": 1500}, {"WING": 2000, "CTR": 8000}))
print("OEW only", calc({}, {}, {}))
print("教学包线 20-34%")

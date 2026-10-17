"""
A320-200 教学数表 v2
来源：Airbus ACAP 公开几何 + 简化 WBM + A320 通用 3+3 LOPA 示意排
DATUM = 机头 FS=0，站位向机尾递增（m）
"""
# —— 几何 ACAP ——
LENGTH = 37.57
WINGSPAN = 34.10
HEIGHT = 11.76
FUS_DIA = 3.95
CABIN_WIDTH = 3.70
WING_AREA = 122.6
WING_SWEEP_DEG = 25.0
WING_DIHEDRAL_DEG = 5.1
WHEELBASE = 12.64
MAIN_TRACK = 7.59
MAC = 4.1935
LEMAC_ST = 16.92
TEMAC_ST = LEMAC_ST + MAC
WING_ROOT_LE_ST = 14.80
WING_SPAR_ST = 18.20
CTR_TANK_ST = 18.50
NOSE_X = LENGTH / 2.0  # 18.785

# —— 起落架站位（必须与配载重心自洽，否则会出现物理上不可能的姿态）——
# 三轮车式起落架：**重心必须在主轮接地点之前**，且前轮通常承担 8~10% 全重。
# 由"前轮载荷"反推主轮站位：Xmg = 包线中部 + NOSE_LOAD × 轮距。
# 这样 ① 正常配载前轮载荷约 7~9%；② 尾坐阈值（cg = Xmg）落在 ≈54% MAC，
# 远在包线后限 36% 之后 —— 只有严重后重这类失衡工况才触发，教学因果自洽。
# （历史教训：曾按 LEMAC+0.365×MAC 取值，前轮载荷只有 1.4%，且尾坐阈值贴住后限。）
NOSE_LOAD = 0.09
MG_STATION = LEMAC_ST + 0.27 * MAC + NOSE_LOAD * WHEELBASE   # 主轮接地点站位 ≈ 19.19 m
NG_STATION = MG_STATION - WHEELBASE                          # 前轮接地点站位 ≈ 6.55 m
NOSE_LOAD_MAX = 0.15    # 前轮过载极限：超过即"前轮折断、机头砸在机坪上"

# —— 重量 ——
OEW = 42500.0
OEW_MAC_PCT = 25.0
OEW_ST = LEMAC_ST + (OEW_MAC_PCT / 100.0) * MAC
MTOW = 78000.0
MZFW = 62500.0
MLW = 66000.0
MAX_FUEL = 19090.0
PAX_STD_W = 84.0
BAG_STD_W = 12.0
# 真实构型为 186Y = 31 排 × 6（见 docs/机型与参考资源.md 与真实舱单）。
# 原为 180（30 排），现按真实构型改为 186。
PAX_MAX = 186

# —— 货舱 ACAP 量级 ——
CARGO_FWD_MAX = 3175.0
CARGO_AFT_MAX = 4480.0
CARGO_BULK_MAX = 1495.0
CARGO_FWD_ST = 12.80
CARGO_AFT_ST = 24.60
CARGO_BULK_ST = 28.80
CARGO_Y = {"FWD": 0.10, "AFT": -0.08, "BULK": 0.05}

# —— LOPA：3+3，排距 ~0.78 m，31 排 = 186 座（真实 186Y 构型）——
# 分区排号：前舱 0A 排 1-12 ｜ 中舱 0B 排 13-20 ｜ 后舱 0C 排 21-31  → 72 / 48 / 66 = 186
# ⚠️ 舱区边界为「按原教学比例外推」的取值，不是注册号 LOPA 的原值：
#    手册只给出 0A/0B/0C 的命名规则，本地资料不含 186Y 的逐排分区表。
#    原 30 排按 12/8/10 分配，补到 31 排时为 12/8/11，0A/0B 边界保持不变。
#    若日后拿到该构型 LOPA，只改这里的 rows 即可（几何与计算都读此处）。
SEAT_PITCH = 0.78
SEAT_COLS = [-1.25, -0.75, -0.25, 0.25, 0.75, 1.25]  # 3+3 相对中线
ZONES = {
    "FWD": {"label": "前舱", "station": 11.20, "max": 60, "rows": (1, 12),
            "row0_st": 8.6, "color": (0.95, 0.55, 0.18), "y": 0.02},
    "MID": {"label": "中舱", "station": 18.50, "max": 70, "rows": (13, 20),
            "row0_st": 17.0, "color": (0.35, 0.78, 0.95), "y": -0.01},
    "AFT": {"label": "后舱", "station": 25.80, "max": 50, "rows": (21, 31),
            "row0_st": 23.2, "color": (0.92, 0.45, 0.75), "y": 0.03},
}
# 每区排数与理论座位数（满员）
for z in ZONES.values():
    r0, r1 = z["rows"]
    z["n_rows"] = r1 - r0 + 1
    z["seats_full"] = z["n_rows"] * 6

CARGO = {
    "FWD": {"label": "前货舱", "station": CARGO_FWD_ST, "max": CARGO_FWD_MAX,
            "y": CARGO_Y["FWD"], "color": (0.95, 0.78, 0.25), "z": -1.35},
    "AFT": {"label": "后货舱", "station": CARGO_AFT_ST, "max": CARGO_AFT_MAX,
            "y": CARGO_Y["AFT"], "color": (0.95, 0.5, 0.2), "z": -1.35},
    "BULK": {"label": "散装舱", "station": CARGO_BULK_ST, "max": CARGO_BULK_MAX,
             "y": CARGO_Y["BULK"], "color": (0.78, 0.48, 0.28), "z": -1.5},
}
FUEL = {
    "WING_L": {"label": "左翼油", "station": WING_SPAR_ST, "max": 7500.0, "y": -5.5,
               "color": (0.25, 0.8, 0.5)},
    "WING_R": {"label": "右翼油", "station": WING_SPAR_ST, "max": 7500.0, "y": 5.5,
               "color": (0.25, 0.8, 0.5)},
    "CTR": {"label": "中央油箱", "station": CTR_TANK_ST, "max": 6145.0, "y": 0.0,
            "color": (0.2, 0.6, 0.9)},
}

FWD_LIM_PCT = 18.0
AFT_LIM_PCT = 36.0
Y_LIM = 0.35
FUEL_IMB_LIM = 800.0

INIT_PAX = {"FWD": 40, "MID": 60, "AFT": 35}
INIT_CARGO = {"FWD": 1800, "AFT": 2200, "BULK": 400}
INIT_FUEL = {"WING_L": 4200, "WING_R": 4300, "CTR": 3500}

# 姿态教学增益（装载驱动的示意俯仰/横滚角，弧度）
PITCH_GAIN_FWD = 0.035   # %MAC 低于前限时额外低头
PITCH_GAIN_AFT = 0.040
ROLL_GAIN = 0.12         # 每米横向 CG 的侧倾示意


def sx(st: float) -> float:
    return NOSE_X - st


def pct_mac(st: float) -> float:
    return (st - LEMAC_ST) / MAC * 100.0


def compute(pax=None, cargo=None, fuel=None) -> dict:
    pax = pax or INIT_PAX
    cargo = cargo or INIT_CARGO
    fuel = fuel or INIT_FUEL
    items = [("OEW", OEW, OEW_ST, 0.0)]
    for z, n in pax.items():
        zc = ZONES[z]
        items.append((f"PAX_{z}", n * PAX_STD_W, zc["station"], zc["y"]))
        bag_st = CARGO["FWD"]["station"] if z == "FWD" else CARGO["AFT"]["station"]
        bag_y = CARGO["FWD"]["y"] if z == "FWD" else CARGO["AFT"]["y"]
        items.append((f"BAG_{z}", n * BAG_STD_W, bag_st, bag_y))
    for c, kg in cargo.items():
        items.append((f"C_{c}", float(kg), CARGO[c]["station"], CARGO[c]["y"]))
    for f, kg in fuel.items():
        items.append((f"F_{f}", float(kg), FUEL[f]["station"], FUEL[f]["y"]))

    tw = sum(w for _, w, _, _ in items)
    tm = sum(w * a for _, w, a, _ in items)
    my = sum(w * y for _, w, _, y in items)
    cg = tm / tw if tw else 0.0
    cy = my / tw if tw else 0.0
    mac = pct_mac(cg)
    fuel_w = sum(float(fuel.get(k, 0)) for k in FUEL)
    fuel_L = float(fuel.get("WING_L", 0))
    fuel_R = float(fuel.get("WING_R", 0))
    fuel_imb = abs(fuel_L - fuel_R)
    ok_mac = FWD_LIM_PCT <= mac <= AFT_LIM_PCT
    ok_y = abs(cy) <= Y_LIM
    ok_fuel = fuel_imb <= FUEL_IMB_LIM
    ok_tow = tw <= MTOW

    # 姿态示意（教学幅度封顶，避免夸张）
    pitch_deg = 0.0
    if mac < FWD_LIM_PCT:
        pitch = "前重·低头趋势"
        pitch_deg = -math_deg(PITCH_GAIN_FWD * (FWD_LIM_PCT - mac))
    elif mac > AFT_LIM_PCT:
        pitch = "后重·抬头趋势"
        pitch_deg = math_deg(PITCH_GAIN_AFT * (mac - AFT_LIM_PCT))
    else:
        pitch = "俯仰可配平"
    pitch_deg = max(-12.0, min(12.0, pitch_deg))
    roll_deg = -math_deg(ROLL_GAIN * cy)
    roll_deg = max(-12.0, min(12.0, roll_deg))
    if abs(cy) < 0.05:
        roll = "横向居中"
    elif cy > 0:
        roll = "右偏·左倾趋势"
    else:
        roll = "左偏·右倾趋势"

    # 配平提示
    trim_pitch = "升降舵中立"
    if pitch_deg < -0.5:
        trim_pitch = "需带杆/升降舵上偏配平"
    elif pitch_deg > 0.5:
        trim_pitch = "需推杆/升降舵下偏配平"
    trim_roll = "副翼中立"
    if roll_deg > 0.5:
        trim_roll = "需右压杆/右副翼上偏"
    elif roll_deg < -0.5:
        trim_roll = "需左压杆/左副翼上偏"

    return {
        "tow": tw, "moment": tm, "cg": cg, "cg_station": cg, "cg_mac": mac, "mac": mac,
        "cg_y": cy, "zfw": tw - fuel_w, "fuel": fuel_w, "fuel_imb": fuel_imb,
        "payload": sum(n * (PAX_STD_W + BAG_STD_W) for n in pax.values()) + sum(float(v) for v in cargo.values()),
        "pax": sum(int(n) for n in pax.values()),
        "ok_mac": ok_mac, "ok_y": ok_y, "ok_fuel": ok_fuel, "ok_tow": ok_tow,
        "pitch": pitch, "roll": roll,
        "pitch_deg": pitch_deg, "roll_deg": roll_deg,
        "trim_pitch": trim_pitch, "trim_roll": trim_roll,
    }


def math_deg(rad):
    return rad * 180.0 / 3.141592653589793

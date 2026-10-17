# -*- coding: utf-8 -*-
"""
把 a320_data.py 的口径导成前端可用的 groups.json
=================================================

为什么需要它：
  "点击查看"要显示每个拆解组的**静态属性**（中文名/类别/站位/限重/分区/说明），
  而"参数联动"要实时算 TOW / CG / %MAC / 横向 y。
  两者必须用**同一份口径**，否则 3D 与面板会各说各话 —— 所以从唯一数据源
  `scripts/a320_data.py` 导出，而不是在 JS 里另抄一遍。

a320_data 是纯 Python（不依赖 bpy），可直接用普通 Python 运行。

用法：python scripts/export_groups.py
产出：output/stage1/groups.json
"""
import io, json, os, sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import a320_data as D

OUT = os.path.join(os.path.dirname(SP), "output", "stage1", "groups.json")

# 每个拆解组的中文名、类别与教学说明（考点）
GROUP_META = {
    # —— 客舱载荷 ——
    "PAX_0A": ("前舱座椅 0A", "payload",
               "0A 区（排 1-12）。旅客是**站位靠前**的业载，加满会把 CG 往前拉。"),
    "PAX_0B": ("中舱座椅 0B", "payload",
               "0B 区（排 13-20）。位于重心附近，对 CG 影响最小 —— 所以调载常拿它做微调。"),
    "PAX_0C": ("后舱座椅 0C", "payload",
               "0C 区（排 21-31）。后舱加满会把 CG 明显往后拉，是「后重」工况的主因。"),
    "BAG_1": ("行李（1 舱）", "payload",
              "前舱旅客的托运行李，随前货舱装载。行李重量按 12 kg/人计。"),
    "BAG_3": ("行李（3 舱）", "payload",
              "后舱旅客的托运行李，随后货舱装载。"),
    # —— 货舱 ——
    "CARGO_1": ("1 舱 前货舱", "payload", "位于主翼前，限重最紧，装重货会把 CG 前拉。"),
    "CARGO_3": ("3 舱 后货舱", "payload", "后货舱前半段，容积大，是压舱调载的首选位。"),
    "CARGO_5": ("5 舱 散货舱", "payload",
                "散货舱（LDM 记 5H），位置最靠后，装载对 CG 影响最敏感。"),
    # —— 燃油 ——
    "FUEL_WING_L": ("左翼油箱", "system", "左/右翼油差直接造成**横向不平衡**，是横滚配平的主因。"),
    "FUEL_WING_R": ("右翼油箱", "system", "左右翼油差超过限值需按燃油不平衡程序处理。"),
    "FUEL_CTR": ("中央油箱", "system",
                 "位置贴近重心，加注几乎不改变 %MAC，但计入 TOW —— 是「先加中央油」的依据。"),
    # —— 结构 / 系统 ——
    "HULL_UPPER": ("机身壳体", "structure", "机身结构本体，属 OEW，不随装载变化。"),
    "FLOOR_CABIN": ("客舱地板", "structure", "客舱与货舱的分界，也是客舱载荷的承力面。"),
    "FLOOR_CARGO": ("货舱地板", "structure", "货舱承力面。"),
    "BELLY_FAIRING": ("翼身整流罩", "structure", "主翼与机身交接处的整流结构，属 OEW。"),
    "WING_L": ("左机翼", "structure", "含翼尖小翼。翼内为油箱，属结构 + 系统。"),
    "WING_R": ("右机翼", "structure", "含翼尖小翼。"),
    "ENG_L": ("左发动机与吊挂", "system", "计入 OEW。吊挂位置对 CG 有小幅影响。"),
    "ENG_R": ("右发动机与吊挂", "system", "计入 OEW。"),
    "TAIL_HS": ("水平尾翼", "structure", "提供俯仰配平力矩，配平值以 STAB TRIM 给出。"),
    "TAIL_VS": ("垂直尾翼", "structure", "提供偏航稳定性，属 OEW。"),
    "DOORS": ("舱门", "structure", "客/货舱门，属 OEW。装卸作业的通道。"),
    "WINDOWS": ("舷窗", "structure", "属 OEW。"),
    "MARKINGS": ("机身标识", "structure", "属 OEW。"),
    "GEAR_N": ("前起落架", "system", "属 OEW。地面停放由三点式起落架支撑。"),
    "GEAR_ML": ("左主起落架", "system", "属 OEW。"),
    "GEAR_MR": ("右主起落架", "system", "属 OEW。"),
    "GEAR_WHEEL": ("机轮", "system", "属 OEW。"),
    "ANNO_CG": ("CG 标记", "annotation", "重心标记，非实体。"),
    "ANNO_SCALE": ("标尺", "annotation", "MAC / 站位标尺，非实体。"),
    "ANNO_UI": ("界面标注", "annotation", "界面元素，非实体。"),
    "ANNO_TEXT": ("文字标注", "annotation", "文字层，非实体。"),
    "ANNO_LABEL": ("部件名称", "annotation", "部件名称标签。"),
    "ENV_GROUND": ("地面", "env", "环境地面，非实体。"),
}


def main():
    zones = {}
    for k, z in D.ZONES.items():
        zones[k] = {"label": z["label"], "station": z["station"], "rows": list(z["rows"]),
                    "row0_st": z["row0_st"], "seats_full": z["seats_full"],
                    "max": z["max"], "y": z["y"]}
    # 注意 y（横向偏置）必须一并导出：它参与横向重心 CGy 的计算，
    # 若前端另填一套值就会与 a320_data 的口径漂移。
    cargo = {k: {"label": v["label"], "station": v["station"], "max": v["max"], "y": v["y"]}
             for k, v in D.CARGO.items()}
    fuel = {k: {"label": v["label"], "station": v["station"], "max": v["max"], "y": v["y"]}
            for k, v in D.FUEL.items()}

    groups = {}
    for g, (label, kind, note) in GROUP_META.items():
        it = {"label": label, "kind": kind, "note": note}
        if g in ("PAX_0A", "PAX_0B", "PAX_0C"):
            zk = {"PAX_0A": "FWD", "PAX_0B": "MID", "PAX_0C": "AFT"}[g]
            z = D.ZONES[zk]
            it.update({"station": z["station"], "zone": zk,
                       "rows": "%d-%d" % tuple(z["rows"]), "capacity": z["seats_full"],
                       "unit_kg": D.PAX_STD_W})
        elif g in ("BAG_1", "BAG_3"):
            zk = "FWD" if g == "BAG_1" else "AFT"
            it.update({"station": D.CARGO[zk]["station"], "zone": zk,
                       "unit_kg": D.BAG_STD_W, "capacity": D.ZONES[zk]["seats_full"]})
        elif g in ("CARGO_1", "CARGO_3", "CARGO_5"):
            ck = {"CARGO_1": "FWD", "CARGO_3": "AFT", "CARGO_5": "BULK"}[g]
            it.update({"station": D.CARGO[ck]["station"], "hold": ck,
                       "limit_kg": D.CARGO[ck]["max"]})
        elif g in ("FUEL_WING_L", "FUEL_WING_R", "FUEL_CTR"):
            fk = {"FUEL_WING_L": "WING_L", "FUEL_WING_R": "WING_R", "FUEL_CTR": "CTR"}[g]
            it.update({"station": D.FUEL[fk]["station"], "limit_kg": D.FUEL[fk]["max"],
                       "y": D.FUEL[fk]["y"]})
        groups[g] = it

    payload = {
        "aircraft": {
            "type": "A320-200（ACAP 量级，教学简化）",
            "length": D.LENGTH, "wingspan": D.WINGSPAN, "mac": D.MAC, "lemac": D.LEMAC_ST,
            "oew": D.OEW, "oew_station": D.OEW_ST, "oew_mac_pct": D.OEW_MAC_PCT,
            "mtow": D.MTOW, "mzfw": D.MZFW, "mlw": D.MLW, "pax_max": D.PAX_MAX,
            "envelope": [D.FWD_LIM_PCT, D.AFT_LIM_PCT],
            "y_limit": D.Y_LIM, "fuel_imb_limit": D.FUEL_IMB_LIM,
            "pax_std_w": D.PAX_STD_W, "bag_std_w": D.BAG_STD_W,
            "nose_x": D.NOSE_X,
            # 起落架站位与轮距：视图侧算前轮载荷、尾坐/机头砸地判定都要用，
            # 必须来自 a320_data（唯一真源），不能让几何与配载各写一套。
            "wheelbase": D.WHEELBASE, "main_track": D.MAIN_TRACK,
            "mg_station": D.MG_STATION, "ng_station": D.NG_STATION,
            "nose_load_max": D.NOSE_LOAD_MAX,
        },
        "zones": zones, "cargo": cargo, "fuel": fuel,
        "init": {"pax": D.INIT_PAX, "cargo": D.INIT_CARGO, "fuel": D.INIT_FUEL},
        "groups": groups,
        "note": ("由 scripts/a320_data.py 自动导出，请勿手工编辑；"
                 "站位 Arm 自机头 DATUM 向后量（m），%MAC = (CG − LEMAC)/MAC × 100。"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("WROTE", OUT)
    print("groups:", len(groups), "zones:", len(zones), "cargo:", len(cargo), "fuel:", len(fuel))
    # 顺带打印初始工况，便于与 docs/算法核实.md 对照
    # 注意：Python 的 % 格式化里 "%%" 才是字面量 "%"，"%MAC" 会被当成格式符 %M 而报错
    r = D.compute()
    print("初始工况: TOW=%.0f ZFW=%.0f CG=%.3f %%MAC=%.2f y=%+.4f"
          % (r["tow"], r["zfw"], r["cg_station"], r["cg_mac"], r["cg_y"]))


if __name__ == "__main__":
    main()

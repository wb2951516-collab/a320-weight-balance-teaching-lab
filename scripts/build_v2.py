"""
配载平衡 3D 教学模型 — 重建脚本（教学示意风格，几何清晰、文字可读）
约定：+X 机头, +Y 右翼, +Z 上
DATUM 在 x=18.0（机头前参考面），站位 station = 18 - x
"""
import bpy
import math
import os
import importlib.util

OUT = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
PANEL_PATH = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts\loadbalance_panel.py"

# ---- 教学参数 ----
MAC = 4.195
LEMAC_ST = 13.0
TEMAC_ST = LEMAC_ST + MAC
OEW = 42500.0
OEW_ST = LEMAC_ST + 0.25 * MAC
PAX_W, BAG_W = 84.0, 12.0
DATUM_X = 18.0

ZONES = {
    "FWD": {"label": "前舱", "st": 13.15, "max": 60, "color": (0.95, 0.55, 0.18)},
    "MID": {"label": "中舱", "st": 14.50, "max": 70, "color": (0.35, 0.75, 0.95)},
    "AFT": {"label": "后舱", "st": 16.10, "max": 50, "color": (0.9, 0.45, 0.75)},
}
CARGO = {
    "FWD": {"label": "前货舱", "st": 12.55, "max": 3500, "color": (0.95, 0.75, 0.25)},
    "AFT": {"label": "后货舱", "st": 16.55, "max": 4500, "color": (0.95, 0.5, 0.2)},
    "BULK": {"label": "散装舱", "st": 17.35, "max": 1500, "color": (0.75, 0.45, 0.25)},
}
FUEL = {
    "WING": {"label": "机翼油箱", "st": 14.00, "max": 18000, "color": (0.25, 0.8, 0.5)},
    "CTR": {"label": "中央油箱", "st": 14.80, "max": 8000, "color": (0.2, 0.6, 0.9)},
}
INIT_PAX = {"FWD": 40, "MID": 60, "AFT": 35}
INIT_CARGO = {"FWD": 1800, "AFT": 2200, "BULK": 400}
INIT_FUEL = {"WING": 8500, "CTR": 3500}

EXPLODE = {
    "PAX_FWD": (4.0, 0, 3.2),
    "PAX_MID": (0, 0, 4.2),
    "PAX_AFT": (-4.0, 0, 3.2),
    "BAG_FWD": (2.5, 0, 5.5),
    "BAG_AFT": (-2.5, 0, 5.5),
    "CARGO_FWD": (2.0, 0, 6.8),
    "CARGO_AFT": (-2.0, 0, 6.8),
    "CARGO_BULK": (-4.5, 0, 6.8),
    "FUEL_WING": (0, 6.5, 1.8),
    "FUEL_CTR": (0, 0, 8.0),
}


def sx(st):
    return DATUM_X - st


def pct_mac(st):
    return (st - LEMAC_ST) / MAC * 100.0


def compute(pax=None, cargo=None, fuel=None):
    pax = pax or INIT_PAX
    cargo = cargo or INIT_CARGO
    fuel = fuel or INIT_FUEL
    items = [("OEW", OEW, OEW_ST)]
    for z, n in pax.items():
        items.append((f"PAX_{z}", n * PAX_W, ZONES[z]["st"]))
        bag_st = CARGO["FWD"]["st"] if z == "FWD" else CARGO["AFT"]["st"]
        items.append((f"BAG_{z}", n * BAG_W, bag_st))
    for c, kg in cargo.items():
        items.append((f"CARGO_{c}", float(kg), CARGO[c]["st"]))
    for f, kg in fuel.items():
        items.append((f"FUEL_{f}", float(kg), FUEL[f]["st"]))
    tw = sum(w for _, w, _ in items)
    tm = sum(w * a for _, w, a in items)
    cg = tm / tw if tw else 0.0
    return {
        "items": items,
        "tow": tw,
        "moment": tm,
        "cg": cg,
        "mac": pct_mac(cg),
        "fuel": sum(fuel.values()),
        "zfw": tw - sum(fuel.values()),
        "payload": sum(n * PAX_W for n in pax.values()) + sum(n * BAG_W for n in pax.values()) + sum(cargo.values()),
        "pax": sum(pax.values()),
    }


# ---- 基础 ----

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, color, metal=0.0, rough=0.4, alpha=1.0, emis=None, estr=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if "Alpha" in b.inputs:
        b.inputs["Alpha"].default_value = alpha
    if emis:
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (*emis, 1)
        elif "Emission" in b.inputs:
            b.inputs["Emission"].default_value = (*emis, 1)
        if "Emission Strength" in b.inputs:
            b.inputs["Emission Strength"].default_value = estr
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    if alpha < 1:
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
        try:
            m.blend_method = "BLEND"
        except Exception:
            pass
    return m


def parent(child, root):
    child.parent = root
    child.matrix_parent_inverse = root.matrix_world.inverted()


def cube(name, dims, loc, material, root=None, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    if bevel > 0:
        md = o.modifiers.new("Bevel", "BEVEL")
        md.width = bevel
        md.segments = 2
    if root:
        parent(o, root)
    return o


def cyl(name, radius, depth, loc, rot, material, root=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    if material:
        o.data.materials.append(material)
    if root:
        parent(o, root)
    return o


def sphere(name, radius, loc, material, root=None, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    if root:
        parent(o, root)
    return o


def text(name, body, loc, size, material, root=None, rot=(math.radians(90), 0, 0), align="LEFT"):
    """默认绕 X 转 90°，文字竖立、面向 -Y（观众侧），不镜像。"""
    cu = bpy.data.curves.new(name, type="FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.extrude = 0.008
    o = bpy.data.objects.new(name, cu)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.collection.objects.link(o)
    cu.materials.append(material)
    if root:
        parent(o, root)
    return o


def build():
    reset()
    # materials
    M = {
        "hull": mat("M_Hull", (0.75, 0.78, 0.84), metal=0.1, rough=0.4, alpha=0.18),
        "solid": mat("M_Solid", (0.55, 0.6, 0.68), metal=0.25, rough=0.4),
        "wing": mat("M_Wing", (0.6, 0.68, 0.78), metal=0.2, rough=0.4, alpha=0.5),
        "floor": mat("M_Floor", (0.25, 0.28, 0.32), rough=0.7),
        "eng": mat("M_Eng", (0.3, 0.32, 0.36), metal=0.55, rough=0.35),
        "gear": mat("M_Gear", (0.15, 0.15, 0.18), metal=0.6, rough=0.35),
        "paxF": mat("M_PaxF", ZONES["FWD"]["color"], rough=0.55),
        "paxM": mat("M_PaxM", ZONES["MID"]["color"], rough=0.55),
        "paxA": mat("M_PaxA", ZONES["AFT"]["color"], rough=0.55),
        "cF": mat("M_CF", CARGO["FWD"]["color"], rough=0.5),
        "cA": mat("M_CA", CARGO["AFT"]["color"], rough=0.5),
        "cB": mat("M_CB", CARGO["BULK"]["color"], rough=0.5),
        "bag": mat("M_Bag", (0.55, 0.4, 0.28), rough=0.7),
        "fW": mat("M_FW", FUEL["WING"]["color"], alpha=0.55, rough=0.3),
        "fC": mat("M_FC", FUEL["CTR"]["color"], alpha=0.55, rough=0.3),
        "mac": mat("M_MAC", (0.2, 0.95, 1.0), emis=(0.15, 0.85, 1.0), estr=2.0, rough=0.3),
        "cg": mat("M_CG", (1.0, 0.3, 0.25), emis=(1.0, 0.25, 0.2), estr=2.5, rough=0.3),
        "datum": mat("M_Datum", (1.0, 0.9, 0.2), emis=(1.0, 0.85, 0.1), estr=1.2, rough=0.3),
        "limit": mat("M_Limit", (1.0, 0.55, 0.15), emis=(1.0, 0.45, 0.1), estr=1.0, rough=0.3),
        "green": mat("M_Green", (0.2, 0.9, 0.45), emis=(0.15, 0.85, 0.4), estr=1.2, rough=0.3),
        "red": mat("M_Red", (1.0, 0.25, 0.2), emis=(1.0, 0.2, 0.15), estr=1.5, rough=0.3),
        "white": mat("M_White", (1, 1, 1), emis=(1, 1, 1), estr=1.0, rough=0.4),
        "yellow": mat("M_Yellow", (1, 0.85, 0.2), emis=(1, 0.8, 0.15), estr=1.0, rough=0.3),
        "panel": mat("M_Panel", (0.07, 0.09, 0.12), rough=0.5),
        "ground": mat("M_Ground", (0.1, 0.12, 0.16), rough=0.85),
        "band": mat("M_Band", (0.2, 0.85, 0.45), emis=(0.15, 0.7, 0.35), estr=0.8, rough=0.3),
    }

    root = bpy.data.objects.new("AIRCRAFT_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 1.5
    bpy.context.collection.objects.link(root)

    # ---- 机身（胶囊：圆柱+前后半球）----
    # 机身长 36m，中心在 x=0.5，机头 x≈18，机尾 x≈-17
    fuse_len = 30.0
    fuse_r = 2.0
    fuse_cx = 1.0
    body = cyl("Fuselage", fuse_r, fuse_len, (fuse_cx, 0, 0), (0, math.radians(90), 0), M["hull"], root)
    nose = sphere("Nose", fuse_r, (fuse_cx + fuse_len / 2, 0, 0), M["hull"], root, scale=(2.2, 1, 1))
    # 尾段收缩
    tail = cyl("TailCone", fuse_r * 0.7, 8.0, (fuse_cx - fuse_len / 2 - 3.0, 0, 0.4), (0, math.radians(90), 0), M["hull"], root)
    tail.scale = (1, 0.85, 0.9)
    # 地板
    floor = cube("Floor", (28, 3.2, 0.1), (2, 0, 0), M["floor"], root)
    cargo_floor = cube("CargoFloor", (26, 3.0, 0.08), (2, 0, -1.2), M["solid"], root)

    # ---- 机翼（扁盒+后掠）----
    wing_x = sx(15.0)  # ≈ 3
    for side, nm in ((-1, "Wing_L"), (1, "Wing_R")):
        w = cube(nm, (5.5, 14.0, 0.28), (wing_x, side * 9.0, -0.15), M["wing"], root, bevel=0.05)
        w.rotation_euler = (math.radians(side * 4), math.radians(-2), math.radians(side * -22))
        # 翼尖小翼
        tip = cube(nm + "_Tip", (0.35, 0.15, 1.2), (wing_x - 3.2, side * 16.8, 0.45), M["wing"], root)

    # ---- 平尾/垂尾 ----
    for side, nm in ((-1, "HS_L"), (1, "HS_R")):
        h = cube(nm, (2.2, 5.0, 0.18), (-14.5, side * 3.5, 1.0), M["solid"], root, bevel=0.04)
        h.rotation_euler = (0, 0, math.radians(side * -18))
    v = cube("VStab", (3.0, 0.18, 3.8), (-15.0, 0, 2.8), M["solid"], root, bevel=0.04)
    v.rotation_euler = (0, math.radians(-28), 0)

    # ---- 发动机 ----
    for side, nm in ((-1, "Eng_L"), (1, "Eng_R")):
        cyl(nm, 0.9, 3.0, (1.5, side * 6.2, -1.3), (0, math.radians(90), 0), M["eng"], root, 24)
        cyl(nm + "_N", 1.0, 0.3, (3.1, side * 6.2, -1.3), (0, math.radians(90), 0), M["eng"], root, 24)

    # ---- 起落架 ----
    cyl("GearN", 0.32, 1.5, (11.5, 0, -2.3), (0, 0, 0), M["gear"], root, 16)
    for side, nm in ((-1, "GearML"), (1, "GearMR")):
        cyl(nm, 0.4, 1.8, (0.5, side * 1.5, -2.4), (0, 0, 0), M["gear"], root, 16)

    # 地面
    cube("Ground", (60, 40, 0.1), (0, 0, -3.3), M["ground"], root)

    # ---- 装载物 ----
    payload = {}
    zone_mat = {"FWD": M["paxF"], "MID": M["paxM"], "AFT": M["paxA"]}
    # 座椅沿机身（视觉）：FWD 前部，MID 中部，AFT 后部
    zone_geo = {"FWD": (8.0, 12.5), "MID": (2.5, 7.5), "AFT": (-3.5, 1.8)}
    for zid, (x0, x1) in zone_geo.items():
        objs = []
        n = 5
        for i in range(n):
            x = x0 + (x1 - x0) * (i + 0.5) / n
            s = cube(f"Seat_{zid}_{i}", ((x1 - x0) / n * 0.85, 2.4, 0.5), (x, 0, 0.4), zone_mat[zid], root, 0.03)
            objs.append(s)
        payload[f"PAX_{zid}"] = objs

    bag_geo = [("FWD", 9.0, 12.0), ("AFT", 2.0, 5.0)]
    for zid, x0, x1 in bag_geo:
        objs = []
        for i in range(3):
            x = x0 + (x1 - x0) * (i + 0.5) / 3
            for y in (-0.6, 0.6):
                b = cube(f"Bag_{zid}_{i}_{int(y*10)}", (0.55, 0.45, 0.35), (x, y, -0.95), M["bag"], root, 0.02)
                objs.append(b)
        payload[f"BAG_{zid}"] = objs

    cargo_geo = [
        ("FWD", 9.5, 12.5, M["cF"], 0.65),
        ("AFT", 3.0, 6.0, M["cA"], 0.7),
        ("BULK", -0.5, 2.0, M["cB"], 0.4),
    ]
    for cid, x0, x1, mm, h in cargo_geo:
        objs = []
        for i in range(3):
            x = x0 + (x1 - x0) * (i + 0.5) / 3
            c = cube(f"Cargo_{cid}_{i}", (0.85, 1.5, h), (x, 0, -0.8), mm, root, 0.04)
            objs.append(c)
        payload[f"CARGO_{cid}"] = objs

    fuel_objs_w = []
    for side, nm in ((-1, "L"), (1, "R")):
        t = cube(f"Fuel_W_{nm}", (3.8, 7.0, 0.3), (wing_x - 0.3, side * 5.5, -0.05), M["fW"], root, 0.04)
        fuel_objs_w.append(t)
    payload["FUEL_WING"] = fuel_objs_w
    ctr = cube("Fuel_C", (3.2, 2.0, 0.35), (1.8, 0, -0.05), M["fC"], root, 0.04)
    payload["FUEL_CTR"] = [ctr]

    # explode props
    for g, objs in payload.items():
        off = EXPLODE.get(g, (0, 0, 3))
        for o in objs:
            o["gx"] = off[0]
            o["gy"] = off[1]
            o["gz"] = off[2]
            o["ax"] = o.location.x
            o["ay"] = o.location.y
            o["az"] = o.location.z
            o["group"] = g

    # ---- DATUM 细线（不要大平面）----
    dx = DATUM_X
    cyl("DatumLine", 0.06, 10, (dx, 0, 0), (math.radians(90), 0, 0), M["datum"], root, 8)
    text("Lab_Datum", "DATUM 基准面", (dx + 0.2, 0, 3.8), 0.45, M["datum"], root)

    # ---- MAC 条 ----
    le, te = sx(LEMAC_ST), sx(TEMAC_ST)
    mac_y = 3.8
    cube("MAC_Bar", (abs(le - te), 1.2, 0.08), ((le + te) / 2, mac_y, 0.7), M["mac"], root, 0.01)
    text("Lab_LE", "LEMAC", (le, mac_y + 0.8, 1.0), 0.32, M["mac"], root)
    text("Lab_TE", "TEMAC", (te - 0.8, mac_y + 0.8, 1.0), 0.32, M["mac"], root)
    text("Lab_MACv", f"MAC={MAC:.2f}m", ((le + te) / 2 - 0.7, mac_y + 0.8, 1.5), 0.3, M["mac"], root)

    for p in (20, 25, 30, 35):
        x = sx(LEMAC_ST + MAC * p / 100)
        cube(f"T{p}", (0.04, 0.3, 0.22), (x, mac_y + 1.0, 0.7), M["limit"], root)
        text(f"TL{p}", f"{p}%", (x - 0.12, mac_y + 1.0, 1.1), 0.25, M["limit"], root)

    # 安全带 20-34%
    lo, hi = sx(LEMAC_ST + MAC * 0.34), sx(LEMAC_ST + MAC * 0.20)  # x 较小=靠后
    cube("CGBand", (abs(lo - hi), 0.2, 0.1), ((lo + hi) / 2, mac_y + 0.55, 0.7), M["band"], root)

    # ---- CG 标记 ----
    res0 = compute()
    cgx = sx(res0["cg"])
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.5, depth=0.9, location=(cgx, 0, 2.6), rotation=(math.radians(180), 0, 0))
    cone = bpy.context.active_object
    cone.name = "CG_Cone"
    cone.data.materials.append(M["cg"])
    parent(cone, root)
    cyl("CG_Line", 0.04, 5.2, (cgx, 0, 0.2), (0, 0, 0), M["cg"], root, 8)
    empty = bpy.data.objects.new("CG_Empty", None)
    empty.empty_display_type = "ARROWS"
    empty.empty_display_size = 1.0
    empty.location = (cgx, 0, 0)
    bpy.context.collection.objects.link(empty)
    parent(empty, root)

    # 力矩条
    bar = cube("MomentBar", (abs(cgx - dx), 0.08, 0.08), ((cgx + dx) / 2, -3.2, 0.3), M["yellow"], root)
    text("Lab_Mom", "力矩 = 重量 × 力臂", ((cgx + dx) / 2 - 1.5, -3.2, 0.8), 0.32, M["yellow"], root)

    # ---- 信息面板（面向 -Y，文字不镜像）----
    # 面板放在 y=-8，面向 -Y
    panel = cube("InfoPanel", (9.5, 0.15, 8.5), (8, -8.5, 2.5), M["panel"], root, 0.06)
    lines = [
        ("Title", "配载平衡计算", (3.8, -8.35, 6.0), 0.48, M["white"]),
        ("Eq1", "力矩 M = 重量 W × 力臂 Arm", (3.8, -8.35, 5.2), 0.3, M["yellow"]),
        ("Eq2", "重心 CG = ΣM / ΣW", (3.8, -8.35, 4.6), 0.3, M["yellow"]),
        ("Eq3", "%MAC = (CG-LEMAC)/MAC ×100", (3.8, -8.35, 4.0), 0.28, M["mac"]),
        ("W", f"总重 TOW: {res0['tow']:.0f} kg", (3.8, -8.35, 3.2), 0.32, M["white"]),
        ("M", f"总力矩: {res0['moment']:.0f} kg·m", (3.8, -8.35, 2.6), 0.3, M["white"]),
        ("CG", f"重心站位: {res0['cg']:.2f} m", (3.8, -8.35, 2.0), 0.3, M["green"]),
        ("MAC", f"%MAC: {res0['mac']:.1f}%", (3.8, -8.35, 1.4), 0.36, M["cg"]),
        ("ZFW", f"ZFW: {res0['zfw']:.0f} kg", (3.8, -8.35, 0.8), 0.28, M["white"]),
        ("PL", f"业载: {res0['payload']:.0f} kg", (3.8, -8.35, 0.25), 0.28, M["white"]),
        ("PAX", f"旅客: {res0['pax']} 人", (3.8, -8.35, -0.3), 0.28, M["white"]),
        ("Note", "教学示意 · 非正式性能数据", (3.8, -8.35, -1.0), 0.22, M["white"]),
    ]
    ui = {}
    for key, body, loc, size, mm in lines:
        # 位置：面板中心 x=8, 文字从 x=3.8 开始左对齐；rot (90,0,0) 面向 -Y
        t = text(f"UI_{key}", body, loc, size, mm, root, rot=(math.radians(90), 0, 0), align="LEFT")
        ui[key] = t

    # 公式说明牌（MAC 旁）
    text("Lab_Formula", "CG = Σ(W×Arm) / ΣW", (0, 5.5, 2.5), 0.35, M["yellow"], root)
    text("Lab_Formula2", "%MAC 落在绿带内=安全", (0, 5.5, 1.9), 0.3, M["green"], root)

    # ---- 场景属性 ----
    sc = bpy.context.scene
    for z, n in INIT_PAX.items():
        sc[f"pax_{z}"] = n
    for c, kg in INIT_CARGO.items():
        sc[f"cargo_{c}"] = kg
    for f, kg in INIT_FUEL.items():
        sc[f"fuel_{f}"] = kg

    # 相机灯光
    bpy.ops.object.camera_add(location=(28, -36, 18), rotation=(math.radians(65), 0, math.radians(38)))
    cam = bpy.context.active_object
    cam.name = "TeachCam"
    sc.camera = cam
    cam.data.lens = 35

    bpy.ops.object.light_add(type="SUN", location=(10, -5, 30))
    bpy.context.active_object.data.energy = 4.0
    bpy.context.active_object.rotation_euler = (math.radians(40), math.radians(10), math.radians(-25))
    bpy.ops.object.light_add(type="AREA", location=(8, -20, 14))
    bpy.context.active_object.data.energy = 1200
    bpy.context.active_object.data.size = 25

    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.04, 0.055, 0.09, 1)
        bg.inputs[1].default_value = 0.7

    # 注册面板
    try:
        spec = importlib.util.spec_from_file_location("lb_panel", PANEL_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.register()
        print("[build] panel registered")
    except Exception as e:
        print("[build] panel register fail", e)

    # 内嵌文本
    try:
        src = open(PANEL_PATH, encoding="utf-8").read()
        txt = bpy.data.texts.new("loadbalance_panel.py")
        txt.write(src)
    except Exception as e:
        print("embed fail", e)

    # 启动时自动注册（打开 blend 即可用）
    boot = bpy.data.texts.new("00_boot_panel.py")
    boot.write(
        "import bpy\n"
        "try:\n"
        "    t = bpy.data.texts.get('loadbalance_panel.py')\n"
        "    if t:\n"
        "        mod = t.as_module()\n"
        "        if hasattr(mod, 'register'):\n"
        "            try:\n"
        "                mod.register()\n"
        "            except Exception:\n"
        "                pass\n"
        "except Exception:\n"
        "    pass\n"
    )
    # 用 load_post 在文本中无法自动；改用 handler 注册到当前会话
    def _boot(*_a):
        try:
            t = bpy.data.texts.get("loadbalance_panel.py")
            if t and "lb_panel_mod" not in bpy.context.scene:
                mod = t.as_module()
                if hasattr(mod, "register"):
                    mod.register()
                    bpy.context.scene["lb_panel_mod"] = 1
        except Exception as e:
            print("auto boot panel", e)

    if _boot not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_boot)
    _boot()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print(f"[build] saved {OUT}")
    print(f"[build] CG%MAC={res0['mac']:.2f} TOW={res0['tow']:.0f}")
    return res0


if __name__ == "__main__":
    build()

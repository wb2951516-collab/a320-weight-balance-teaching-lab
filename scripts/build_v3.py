"""
配载平衡教学模型 v3 — 侧影机身 + 清晰分区 + 可读文字 + 爆炸拆解
"""
import bpy, math, os, importlib.util

OUT = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
PANEL = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts\loadbalance_panel.py"
PREVIEW = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"

MAC = 4.195
LEMAC_ST = 13.0
DATUM_X = 18.0
OEW, OEW_ST = 42500.0, 13.0 + 0.25 * MAC
PAX_W, BAG_W = 84.0, 12.0

ZONES = {
    "FWD": {"label": "前舱", "st": 13.15, "color": (0.95, 0.55, 0.18)},
    "MID": {"label": "中舱", "st": 14.50, "color": (0.35, 0.78, 0.95)},
    "AFT": {"label": "后舱", "st": 16.10, "color": (0.92, 0.45, 0.75)},
}
CARGO = {
    "FWD": {"label": "前货舱", "st": 12.55, "color": (0.95, 0.78, 0.25)},
    "AFT": {"label": "后货舱", "st": 16.55, "color": (0.95, 0.5, 0.2)},
    "BULK": {"label": "散装舱", "st": 17.35, "color": (0.78, 0.48, 0.28)},
}
FUEL = {
    "WING": {"label": "机翼油箱", "st": 14.00, "color": (0.25, 0.8, 0.5)},
    "CTR": {"label": "中央油箱", "st": 14.80, "color": (0.2, 0.6, 0.9)},
}
INIT_PAX = {"FWD": 40, "MID": 60, "AFT": 35}
INIT_CARGO = {"FWD": 1800, "AFT": 2200, "BULK": 400}
INIT_FUEL = {"WING": 8500, "CTR": 3500}
EXPLODE = {
    "PAX_FWD": (3.5, 0, 2.8), "PAX_MID": (0, 0, 3.6), "PAX_AFT": (-3.5, 0, 2.8),
    "BAG_FWD": (2.0, 0, 4.5), "BAG_AFT": (-2.0, 0, 4.5),
    "CARGO_FWD": (1.5, 0, 5.5), "CARGO_AFT": (-1.5, 0, 5.5), "CARGO_BULK": (-4.0, 0, 5.5),
    "FUEL_WING": (0, 5.5, 1.5), "FUEL_CTR": (0, 0, 6.5),
}


def sx(st):
    return DATUM_X - st


def pct_mac(st):
    return (st - LEMAC_ST) / MAC * 100.0


def compute(pax=None, cargo=None, fuel=None):
    pax, cargo, fuel = pax or INIT_PAX, cargo or INIT_CARGO, fuel or INIT_FUEL
    items = [("OEW", OEW, OEW_ST)]
    for z, n in pax.items():
        items.append((f"PAX_{z}", n * PAX_W, ZONES[z]["st"]))
        items.append((f"BAG_{z}", n * BAG_W, CARGO["FWD" if z == "FWD" else "AFT"]["st"]))
    for c, kg in cargo.items():
        items.append((f"C_{c}", float(kg), CARGO[c]["st"]))
    for f, kg in fuel.items():
        items.append((f"F_{f}", float(kg), FUEL[f]["st"]))
    tw = sum(w for _, w, _ in items)
    tm = sum(w * a for _, w, a in items)
    cg = tm / tw if tw else 0
    return {
        "tow": tw, "moment": tm, "cg": cg, "mac": pct_mac(cg),
        "fuel": sum(fuel.values()), "zfw": tw - sum(fuel.values()),
        "payload": sum(n * (PAX_W + BAG_W) for n in pax.values()) + sum(cargo.values()),
        "pax": sum(pax.values()),
    }


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mkmat(name, color, metal=0, rough=0.4, alpha=1, emis=None, estr=0):
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
        key = "Emission Color" if "Emission Color" in b.inputs else "Emission"
        b.inputs[key].default_value = (*emis, 1)
        if "Emission Strength" in b.inputs:
            b.inputs["Emission Strength"].default_value = estr
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    if alpha < 1:
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    return m


def par(o, root):
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()


def box(name, dx, dy, dz, loc, material, root, bevel=0.02, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.dimensions = (dx, dy, dz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    if bevel:
        md = o.modifiers.new("B", "BEVEL")
        md.width = bevel
        md.segments = 2
    par(o, root)
    return o


def text(name, body, loc, size, material, root, align="LEFT"):
    """rot(90,0,0) 已验证：面向 -Y，中文可读。"""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.extrude = 0.006
    o = bpy.data.objects.new(name, cu)
    o.location = loc
    o.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.collection.objects.link(o)
    cu.materials.append(material)
    par(o, root)
    return o


def build_aircraft_silhouette(material, root):
    """用侧影点生成机身（挤出），教学示意。+X机头。"""
    # 半高侧影 (x, z_top, z_bot) — 简化窄体
    # x 从 17.5(机头) 到 -16(机尾)
    profile = [
        (17.5, 0.0, 0.0),      # 机头尖
        (16.8, 1.1, -1.1),
        (15.5, 1.7, -1.7),
        (13.0, 1.95, -1.95),
        (8.0, 2.0, -2.0),
        (2.0, 2.0, -2.0),
        (-4.0, 2.0, -2.0),
        (-9.0, 1.9, -1.8),
        (-13.0, 1.4, -1.3),
        (-16.0, 0.5, -0.5),
        (-17.0, 0.0, 0.0),
    ]
    # 构建左右侧壁 + 上下 — 用多个立方体拼更稳，或 mesh
    verts = []
    faces = []
    # 简化：用一串缩放的圆柱/立方
    for i in range(len(profile) - 1):
        x0, t0, b0 = profile[i]
        x1, t1, b1 = profile[i + 1]
        xc = (x0 + x1) / 2
        h = max((t0 + t1) / 2 - (b0 + b1) / 2, 0.2)
        w = max(h * 1.85, 0.3)  # 机身宽略小于高*2
        # 用 box 更干净
        box(f"Fus_{i}", abs(x1 - x0) * 1.05, w, h, (xc, 0, (t0 + t1 + b0 + b1) / 4), material, root, bevel=0.08)

    # 地板 / 货舱地板
    floor_m = mkmat("M_Floor2", (0.22, 0.25, 0.3), rough=0.7)
    box("Floor", 26, 3.0, 0.1, (2, 0, 0.0), floor_m, root, 0.02)
    box("CargoFloor", 24, 2.8, 0.08, (2, 0, -1.15), material, root, 0.02)


def build_wings(M, root):
    # 左右机翼：扁盒 + 明确后掠
    wing_x = sx(15.0)
    for side, nm in ((-1, "Wing_L"), (1, "Wing_R")):
        # 主翼盒 — 收窄，避免挡面板
        w = box(nm, 3.8, 9.0, 0.28, (wing_x - 0.5, side * 6.2, -0.8), M["wing"], root, 0.04)
        w.rotation_euler = (0, math.radians(side * 2), math.radians(side * -12))
        # 后缘小段
        box(nm + "_TE", 1.0, 8.0, 0.18, (wing_x - 2.8, side * 6.0, -0.85), M["wing"], root, 0.03)
        # 小翼
        box(nm + "_WL", 0.22, 0.12, 0.7, (wing_x - 2.2, side * 10.8, -0.4), M["wing"], root, 0.02)

    # 平尾 — 更小、贴尾
    for side, nm in ((-1, "HS_L"), (1, "HS_R")):
        box(nm, 1.5, 3.2, 0.12, (-14.5, side * 2.2, 0.9), M["solid"], root, 0.03, rot=(0, 0, math.radians(side * -15)))
    # 垂尾
    box("VS", 2.2, 0.14, 2.8, (-14.8, 0, 2.0), M["solid"], root, 0.03, rot=(0, math.radians(-28), 0))

    # 发动机
    for side, nm in ((-1, "E_L"), (1, "E_R")):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.85, depth=2.8, location=(2.2, side * 6.0, -1.4), rotation=(0, math.radians(90), 0))
        o = bpy.context.active_object
        o.name = nm
        o.data.materials.append(M["eng"])
        par(o, root)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.95, depth=0.25, location=(3.7, side * 6.0, -1.4), rotation=(0, math.radians(90), 0))
        o = bpy.context.active_object
        o.name = nm + "N"
        o.data.materials.append(M["eng"])
        par(o, root)

    # 起落架
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.28, depth=1.3, location=(10.5, 0, -2.5))
    o = bpy.context.active_object; o.name = "GN"; o.data.materials.append(M["gear"]); par(o, root)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.35, depth=1.5, location=(0.5, side * 1.4, -2.6))
        o = bpy.context.active_object; o.name = f"GM{side}"; o.data.materials.append(M["gear"]); par(o, root)


def build():
    reset()
    os.makedirs(PREVIEW, exist_ok=True)
    M = {
        "hull": mkmat("M_Hull", (0.72, 0.76, 0.82), rough=0.4, alpha=0.72),
        "solid": mkmat("M_Solid", (0.5, 0.55, 0.62), metal=0.2, rough=0.4),
        "wing": mkmat("M_Wing", (0.48, 0.55, 0.65), metal=0.2, rough=0.4, alpha=0.9),
        "eng": mkmat("M_Eng", (0.28, 0.3, 0.34), metal=0.5, rough=0.35),
        "gear": mkmat("M_Gear", (0.12, 0.12, 0.15), rough=0.4),
        "paxF": mkmat("M_pF", ZONES["FWD"]["color"], rough=0.5),
        "paxM": mkmat("M_pM", ZONES["MID"]["color"], rough=0.5),
        "paxA": mkmat("M_pA", ZONES["AFT"]["color"], rough=0.5),
        "cF": mkmat("M_cF", CARGO["FWD"]["color"], rough=0.45),
        "cA": mkmat("M_cA", CARGO["AFT"]["color"], rough=0.45),
        "cB": mkmat("M_cB", CARGO["BULK"]["color"], rough=0.45),
        "bag": mkmat("M_Bag", (0.55, 0.4, 0.28), rough=0.7),
        "fW": mkmat("M_fW", FUEL["WING"]["color"], alpha=0.5, rough=0.3),
        "fC": mkmat("M_fC", FUEL["CTR"]["color"], alpha=0.5, rough=0.3),
        "mac": mkmat("M_MAC", (0.25, 0.95, 1), emis=(0.2, 0.85, 1), estr=2, rough=0.3),
        "cg": mkmat("M_CG", (1, 0.3, 0.25), emis=(1, 0.25, 0.2), estr=2.5, rough=0.3),
        "datum": mkmat("M_Dat", (1, 0.88, 0.2), emis=(1, 0.8, 0.15), estr=1.2, rough=0.3),
        "limit": mkmat("M_Lim", (1, 0.55, 0.15), emis=(1, 0.45, 0.1), estr=1, rough=0.3),
        "green": mkmat("M_Gr", (0.2, 0.9, 0.45), emis=(0.15, 0.8, 0.4), estr=1.2, rough=0.3),
        "red": mkmat("M_Rd", (1, 0.25, 0.2), emis=(1, 0.2, 0.15), estr=1.5, rough=0.3),
        "white": mkmat("M_Wh", (0.95, 0.97, 1), emis=(1, 1, 1), estr=0.8, rough=0.4),
        "yellow": mkmat("M_Ye", (1, 0.85, 0.2), emis=(1, 0.8, 0.15), estr=1, rough=0.3),
        "panel": mkmat("M_Pn", (0.06, 0.08, 0.12), rough=0.45),
        "ground": mkmat("M_Gnd", (0.1, 0.11, 0.14), rough=0.9),
        "band": mkmat("M_Bd", (0.2, 0.85, 0.45), emis=(0.15, 0.7, 0.35), estr=0.8, rough=0.3),
    }

    root = bpy.data.objects.new("ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 1.2
    bpy.context.collection.objects.link(root)

    build_aircraft_silhouette(M["hull"], root)
    build_wings(M, root)
    box("Ground", 70, 50, 0.1, (0, 0, -3.35), M["ground"], root, 0)

    # 装载
    payload = {}
    zm = {"FWD": M["paxF"], "MID": M["paxM"], "AFT": M["paxA"]}
    zg = {"FWD": (9.0, 12.5), "MID": (3.0, 8.0), "AFT": (-3.0, 2.0)}
    for z, (x0, x1) in zg.items():
        objs = []
        n = 5
        for i in range(n):
            x = x0 + (x1 - x0) * (i + 0.5) / n
            objs.append(box(f"S_{z}_{i}", (x1 - x0) / n * 0.8, 2.2, 0.45, (x, 0, 0.35), zm[z], root, 0.03))
        payload[f"PAX_{z}"] = objs

    for z, x0, x1 in (("FWD", 9.5, 12.0), ("AFT", 2.5, 5.0)):
        objs = []
        for i in range(3):
            x = x0 + (x1 - x0) * (i + 0.5) / 3
            for y in (-0.55, 0.55):
                objs.append(box(f"B_{z}_{i}_{y}", 0.5, 0.4, 0.3, (x, y, -0.9), M["bag"], root, 0.02))
        payload[f"BAG_{z}"] = objs

    for cid, x0, x1, mm, h in (
        ("FWD", 10.0, 12.5, M["cF"], 0.6),
        ("AFT", 3.0, 5.8, M["cA"], 0.65),
        ("BULK", 0.0, 2.2, M["cB"], 0.4),
    ):
        objs = []
        for i in range(3):
            x = x0 + (x1 - x0) * (i + 0.5) / 3
            objs.append(box(f"C_{cid}_{i}", 0.8, 1.4, h, (x, 0, -0.75), mm, root, 0.04))
        payload[f"CARGO_{cid}"] = objs

    wing_x = sx(15.0)
    fw = []
    for side in (-1, 1):
        fw.append(box(f"FW_{side}", 3.5, 6.5, 0.25, (wing_x - 0.5, side * 5.2, -0.2), M["fW"], root, 0.03))
    payload["FUEL_WING"] = fw
    payload["FUEL_CTR"] = [box("FC", 2.8, 1.8, 0.3, (2.2, 0, -0.2), M["fC"], root, 0.03)]

    for g, objs in payload.items():
        off = EXPLODE[g]
        for o in objs:
            o["gx"], o["gy"], o["gz"] = off
            o["ax"], o["ay"], o["az"] = o.location.x, o.location.y, o.location.z
            o["group"] = g

    # DATUM — 细条 + 文字（不要大块）
    dx = DATUM_X
    box("DatumBar", 0.08, 0.08, 7, (dx, 0, 0.5), M["datum"], root, 0)
    text("T_Dat", "DATUM 基准面", (dx + 0.15, 0, 3.6), 0.4, M["datum"], root)

    # MAC
    le, te = sx(LEMAC_ST), sx(LEMAC_ST + MAC)
    my = 3.5
    box("MACBar", abs(le - te), 1.0, 0.08, ((le + te) / 2, my, 0.55), M["mac"], root, 0.01)
    text("T_LE", "LEMAC", (le - 0.1, my + 0.6, 0.9), 0.3, M["mac"], root)
    text("T_TE", "TEMAC", (te - 0.5, my + 0.6, 0.9), 0.3, M["mac"], root)
    text("T_MAC", f"MAC={MAC:.2f} m", ((le + te) / 2 - 0.5, my + 0.6, 1.4), 0.28, M["mac"], root)

    for p in (20, 25, 30, 35):
        x = sx(LEMAC_ST + MAC * p / 100)
        box(f"Tk{p}", 0.04, 0.25, 0.18, (x, my + 0.9, 0.55), M["limit"], root, 0)
        text(f"T{p}", f"{p}%", (x - 0.1, my + 0.9, 0.95), 0.22, M["limit"], root)

    lo, hi = sx(LEMAC_ST + MAC * 0.34), sx(LEMAC_ST + MAC * 0.20)
    box("Band", abs(lo - hi), 0.18, 0.1, ((lo + hi) / 2, my + 0.5, 0.55), M["band"], root, 0)

    # CG
    res = compute()
    cgx = sx(res["cg"])
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.45, depth=0.8, location=(cgx, 0, 2.4), rotation=(math.radians(180), 0, 0))
    cone = bpy.context.active_object
    cone.name = "CGCone"
    cone.data.materials.append(M["cg"])
    par(cone, root)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.035, depth=4.8, location=(cgx, 0, 0.1))
    line = bpy.context.active_object
    line.name = "CGLine"
    line.data.materials.append(M["cg"])
    par(line, root)
    empty = bpy.data.objects.new("CG_Empty", None)
    empty.location = (cgx, 0, 0)
    empty.empty_display_type = "ARROWS"
    empty.empty_display_size = 0.9
    bpy.context.collection.objects.link(empty)
    par(empty, root)

    box("MomBar", abs(cgx - dx), 0.07, 0.07, ((cgx + dx) / 2, -3.0, 0.25), M["yellow"], root, 0)
    text("T_Mom", "力矩 = 重量 × 力臂", ((cgx + dx) / 2 - 1.4, -3.0, 0.7), 0.3, M["yellow"], root)

    # 信息面板 — 朝相机(-Y)；文字必须放在板的近侧面
    # 面板中心 y=-7.2，厚 0.12 → 近面 y≈-7.26；文字放 y=-7.32
    box("Panel", 10.5, 0.12, 7.5, (6, -10.5, 0.5), M["panel"], root, 0.05)
    lines = [
        ("Title", "配载平衡计算 Load Control", (1.5, -10.62, 3.5), 0.42, M["white"]),
        ("Eq1", "力矩 Moment = 重量 × 力臂", (1.5, -10.62, 2.8), 0.28, M["yellow"]),
        ("Eq2", "重心 CG = Σ力矩 / Σ重量", (1.5, -10.62, 2.3), 0.28, M["yellow"]),
        ("Eq3", "%MAC = (CG-LEMAC)/MAC × 100", (1.5, -10.62, 1.8), 0.26, M["mac"]),
        ("W", f"总重 TOW: {res['tow']:.0f} kg", (1.5, -10.62, 1.1), 0.3, M["white"]),
        ("M", f"总力矩: {res['moment']:.0f} kg·m", (1.5, -10.62, 0.6), 0.28, M["white"]),
        ("CG", f"重心站位: {res['cg']:.2f} m", (1.5, -10.62, 0.1), 0.28, M["green"]),
        ("MAC", f"%MAC: {res['mac']:.1f}%  (安全带 20~34%)", (1.5, -10.62, -0.4), 0.32, M["cg"]),
        ("ZFW", f"ZFW {res['zfw']:.0f} kg   业载 {res['payload']:.0f} kg   旅客 {res['pax']}", (1.5, -10.62, -0.95), 0.26, M["white"]),
        ("Note", "教学示意 · 非正式性能数据", (1.5, -10.62, -1.55), 0.22, M["white"]),
    ]
    ui = {}
    for k, body, loc, size, mm in lines:
        ui[k] = text(f"UI_{k}", body, loc, size, mm, root)

    text("T_F1", "CG = Σ(W×Arm) / ΣW", (-1, 5.2, 2.2), 0.32, M["yellow"], root)
    text("T_F2", "绿带内 = 重心安全", (-1, 5.2, 1.6), 0.28, M["green"], root)

    # 场景属性
    sc = bpy.context.scene
    for z, n in INIT_PAX.items():
        sc[f"pax_{z}"] = n
    for c, kg in INIT_CARGO.items():
        sc[f"cargo_{c}"] = kg
    for f, kg in INIT_FUEL.items():
        sc[f"fuel_{f}"] = kg

    # 相机：高侧前方，能同时看到飞机+面板+MAC
    bpy.ops.object.camera_add(location=(32, -30, 14), rotation=(math.radians(68), 0, math.radians(48)))
    cam = bpy.context.active_object
    cam.name = "TeachCam"
    cam.data.lens = 32
    sc.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(8, -4, 28))
    sun = bpy.context.active_object
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(42), math.radians(8), math.radians(-30))
    bpy.ops.object.light_add(type="AREA", location=(6, -16, 12))
    bpy.context.active_object.data.energy = 1000
    bpy.context.active_object.data.size = 20

    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.04, 0.055, 0.09, 1)
        bg.inputs[1].default_value = 0.65

    # 面板插件
    try:
        spec = importlib.util.spec_from_file_location("lbp", PANEL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.register()
        print("panel ok")
    except Exception as e:
        print("panel", e)
    try:
        t = bpy.data.texts.new("loadbalance_panel.py")
        t.write(open(PANEL, encoding="utf-8").read())
    except Exception as e:
        print("embed", e)

    def _boot(*a):
        try:
            t = bpy.data.texts.get("loadbalance_panel.py")
            if t:
                mod = t.as_module()
                if hasattr(mod, "register"):
                    mod.register()
        except Exception:
            pass

    if _boot not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_boot)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT, "MAC%", round(res["mac"], 2))

    # 预览渲染
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 900
    sc.render.image_settings.file_format = "PNG"

    def shot(name, cam_loc, cam_rot):
        cam.location = cam_loc
        cam.rotation_euler = cam_rot
        sc.render.filepath = os.path.join(PREVIEW, name)
        bpy.ops.render.render(write_still=True)
        print("shot", name)

    shot("v3_overview.png", (34, -34, 18), (math.radians(62), 0, math.radians(48)))
    shot("v3_side.png", (10, -48, 6), (math.radians(84), 0, math.radians(8)))
    # explode
    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"] + o["gx"], o["ay"] + o["gy"], o["az"] + o["gz"])
    shot("v3_explode.png", (30, -32, 20), (math.radians(58), 0, math.radians(45)))
    # 面板
    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"], o["ay"], o["az"])
    shot("v3_panel.png", (8, -28, 2.5), (math.radians(82), 0, math.radians(10)))

    # 保存爆炸后恢复组装再存一次？保存组装态
    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"], o["ay"], o["az"])
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("DONE")


if __name__ == "__main__":
    build()

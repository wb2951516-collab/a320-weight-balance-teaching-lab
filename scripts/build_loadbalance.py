"""
配载平衡 3D 教学模型 — Blender 构建脚本
目标：可操作、爆炸拆解、实时展示重量/力矩/%MAC
机型：简化窄体（A320量级，教学数值，非正式性能数据）
"""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# 0. 基础工具
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def log(msg):
    print(f"[build] {msg}")


def make_mat(name, color, metallic=0.0, rough=0.45, alpha=1.0, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha
    if emission is not None:
        # Blender 4+/5 Principled
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (*emission, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if alpha < 1.0:
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
        try:
            mat.surface_render_method = "BLENDED"
        except Exception:
            pass
    return mat


def link(obj):
    bpy.context.collection.objects.link(obj)
    return obj


def add_cube(name, size=(1, 1, 1), loc=(0, 0, 0), mat=None, bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0], size[1], size[2])
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        m = o.modifiers.new("Bevel", "BEVEL")
        m.width = bevel
        m.segments = 2
    if mat:
        o.data.materials.append(mat)
    return o


def add_cyl(name, radius=0.5, depth=2, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    if mat:
        o.data.materials.append(mat)
    return o


def add_sphere(name, radius=0.5, loc=(0, 0, 0), mat=None, seg=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=radius, location=loc)
    o = bpy.context.active_object
    o.name = name
    if mat:
        o.data.materials.append(mat)
    return o


def set_parent_keep(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def text_obj(name, body, loc, size=0.45, mat=None, align="CENTER", extrude=0.01):
    cu = bpy.data.curves.new(name, type="FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.extrude = extrude
    o = bpy.data.objects.new(name, cu)
    o.location = loc
    bpy.context.collection.objects.link(o)
    if mat:
        cu.materials.append(mat)
    return o


# ---------------------------------------------------------------------------
# 1. 教学参数（简化窄体，便于课堂）
# ---------------------------------------------------------------------------

# 坐标系：X=机身纵轴（机头在+X方向更直观？航空常用机头为正，但Blender Y轴更常用）
# 本模型约定：
#   +X = 机头方向
#   +Y = 右翼
#   +Z = 上
#   参考基准面 DATUM 在机头前 0.0 m（简化，实际常取机头后某固定站位）
# 教学用：DATUM 在 x=0（机头前0.5m），机体沿 +X 延伸到约 37m 不方便。
# 改为：机身中段在原点附近，DATUM 在 x=-18.5（机头），便于画图。

class Config:
    # 机头在 +X，DATUM 在机头前 0.5m → datum_x = 18.5 时，机头 x=18.0，机尾 x≈-18
    # 更清晰：机头 x=18.5，datum 在 x=18.5+0.5=19.0? 标准是 datum 为 0 量起。
    # 教学：datum = 0 在机头前 0.0；物体位置用 station（从 datum 往后的距离）。
    # 3D 中：x_world = datum_x - station，datum_x = 18.0，station 0→机头。
    DATUM_X = 18.0
    FUSE_LEN = 37.2
    FUSE_R = 1.95
    WING_SPAN = 34.1
    WING_ROOT_CHORD = 6.6
    WING_TIP_CHORD = 1.8
    WING_SWEEP_DEG = 25.0
    MAC = 4.195
    LEMAC_STATION = 13.0  # 从 datum 向后到 MAC 前缘
    TEMAC_STATION = 13.0 + MAC
    OEW = 42500.0
    OEW_STATION = 13.0 + 0.25 * MAC  # 25% MAC
    PAX_STD_W = 84.0
    BAG_STD_W = 12.0
    MAX_TOW = 78000.0
    MAX_PAX = 180

    # 站位：加大前后跨度，使危险配载能明显挪动 %MAC
    ZONES = {
        "FWD": {"label": "前舱", "station": 13.15, "max_seats": 60, "color": (0.95, 0.55, 0.15)},
        "MID": {"label": "中舱", "station": 14.50, "max_seats": 70, "color": (0.25, 0.75, 0.95)},
        "AFT": {"label": "后舱", "station": 16.10, "max_seats": 50, "color": (0.85, 0.35, 0.75)},
    }
    CARGO = {
        "FWD": {"label": "前货舱", "station": 12.55, "max_kg": 3500, "color": (0.9, 0.7, 0.2)},
        "AFT": {"label": "后货舱", "station": 16.55, "max_kg": 4500, "color": (0.9, 0.45, 0.2)},
        "BULK": {"label": "散装舱", "station": 17.35, "max_kg": 1500, "color": (0.7, 0.4, 0.2)},
    }
    FUEL = {
        "WING": {"label": "机翼燃油", "station": 14.00, "max_kg": 18000, "color": (0.2, 0.75, 0.45)},
        "CTR": {"label": "中央油箱", "station": 14.80, "max_kg": 8000, "color": (0.15, 0.55, 0.85)},
    }
    INIT_PAX = {"FWD": 40, "MID": 60, "AFT": 35}
    INIT_CARGO = {"FWD": 1800, "AFT": 2200, "BULK": 400}
    INIT_FUEL = {"WING": 8500, "CTR": 3500}
    INIT_BAG_PER_PAX = 1  # 行李按旅客数 * 标准重量

    @staticmethod
    def station_to_x(station):
        return Config.DATUM_X - station

    @staticmethod
    def x_to_station(x):
        return Config.DATUM_X - x

    @staticmethod
    def pct_mac(station):
        return (station - Config.LEMAC_STATION) / Config.MAC * 100.0


# ---------------------------------------------------------------------------
# 2. 装载计算
# ---------------------------------------------------------------------------

def compute_load(pax=None, cargo=None, fuel=None, bag_per_pax=None):
    pax = pax or Config.INIT_PAX
    cargo = cargo or Config.INIT_CARGO
    fuel = fuel or Config.INIT_FUEL
    bag_factor = Config.INIT_BAG_PER_PAX if bag_per_pax is None else bag_per_pax

    items = []
    # OEW
    items.append({
        "key": "OEW",
        "label": "使用空机重量",
        "weight": Config.OEW,
        "station": Config.OEW_STATION,
        "group": "OEW",
    })
    for zid, n in pax.items():
        z = Config.ZONES[zid]
        w = n * Config.PAX_STD_W
        items.append({
            "key": f"PAX_{zid}",
            "label": f"旅客-{z['label']}",
            "weight": w,
            "station": z["station"],
            "group": "PAX",
        })
        bw = n * Config.BAG_STD_W * bag_factor
        # 行李货舱按分区就近：前舱旅客→前货，后舱→后货
        bag_cargo = "FWD" if zid == "FWD" else ("BULK" if zid == "AFT" else "AFT")
        if zid == "MID":
            bag_cargo = "AFT"
        cs = Config.CARGO[bag_cargo]["station"]
        items.append({
            "key": f"BAG_{zid}",
            "label": f"行李-{z['label']}",
            "weight": bw,
            "station": cs,
            "group": "BAG",
        })
    for cid, kg in cargo.items():
        c = Config.CARGO[cid]
        items.append({
            "key": f"CARGO_{cid}",
            "label": f"货物-{c['label']}",
            "weight": float(kg),
            "station": c["station"],
            "group": "CARGO",
        })
    for fid, kg in fuel.items():
        f = Config.FUEL[fid]
        items.append({
            "key": f"FUEL_{fid}",
            "label": f"燃油-{f['label']}",
            "weight": float(kg),
            "station": f["station"],
            "group": "FUEL",
        })

    total_w = 0.0
    total_m = 0.0
    for it in items:
        it["arm"] = it["station"]  # station from datum = arm
        it["moment"] = it["weight"] * it["station"]
        total_w += it["weight"]
        total_m += it["moment"]

    cg_station = total_m / total_w if total_w else 0.0
    cg_mac = Config.pct_mac(cg_station)
    fuel_w = sum(fuel.values())
    zfw = total_w - fuel_w
    payload = sum(pax.values()) * Config.PAX_STD_W + sum(cargo.values()) + sum(
        n * Config.BAG_STD_W * bag_factor for n in pax.values()
    )
    return {
        "items": items,
        "total_weight": total_w,
        "total_moment": total_m,
        "cg_station": cg_station,
        "cg_mac": cg_mac,
        "zfw": zfw,
        "tow": total_w,
        "fuel": fuel_w,
        "payload": payload,
        "pax_total": sum(pax.values()),
    }


# ---------------------------------------------------------------------------
# 3. 材质
# ---------------------------------------------------------------------------

def build_materials():
    M = {}
    M["body"] = make_mat("M_Body", (0.82, 0.85, 0.9), metallic=0.15, rough=0.35, alpha=0.22)
    M["frame"] = make_mat("M_Frame", (0.75, 0.78, 0.82), metallic=0.4, rough=0.4)
    M["wing"] = make_mat("M_Wing", (0.7, 0.75, 0.82), metallic=0.2, rough=0.4, alpha=0.55)
    M["stab"] = make_mat("M_Stab", (0.65, 0.7, 0.78), metallic=0.2, rough=0.45)
    M["engine"] = make_mat("M_Engine", (0.35, 0.38, 0.42), metallic=0.6, rough=0.35)
    M["gear"] = make_mat("M_Gear", (0.2, 0.22, 0.25), metallic=0.7, rough=0.3)
    M["pax_fwd"] = make_mat("M_PaxFWD", Config.ZONES["FWD"]["color"], rough=0.6)
    M["pax_mid"] = make_mat("M_PaxMID", Config.ZONES["MID"]["color"], rough=0.6)
    M["pax_aft"] = make_mat("M_PaxAFT", Config.ZONES["AFT"]["color"], rough=0.6)
    M["cargo_fwd"] = make_mat("M_CargoFWD", Config.CARGO["FWD"]["color"], rough=0.55)
    M["cargo_aft"] = make_mat("M_CargoAFT", Config.CARGO["AFT"]["color"], rough=0.55)
    M["cargo_bulk"] = make_mat("M_CargoBULK", Config.CARGO["BULK"]["color"], rough=0.55)
    M["bag"] = make_mat("M_Bag", (0.55, 0.4, 0.25), rough=0.7)
    M["fuel_wing"] = make_mat("M_FuelWing", Config.FUEL["WING"]["color"], alpha=0.65, rough=0.3)
    M["fuel_ctr"] = make_mat("M_FuelCTR", Config.FUEL["CTR"]["color"], alpha=0.65, rough=0.3)
    M["mac"] = make_mat("M_MAC", (0.15, 0.95, 1.0), emission=(0.1, 0.8, 1.0), emission_strength=2.0, rough=0.3)
    M["cg"] = make_mat("M_CG", (1.0, 0.25, 0.2), emission=(1.0, 0.2, 0.15), emission_strength=3.0, rough=0.3)
    M["datum"] = make_mat("M_Datum", (1.0, 0.9, 0.2), emission=(1.0, 0.85, 0.1), emission_strength=1.5, rough=0.3)
    M["limit"] = make_mat("M_Limit", (1.0, 0.4, 0.1), emission=(1.0, 0.35, 0.05), emission_strength=1.0)
    M["text"] = make_mat("M_Text", (1.0, 1.0, 1.0), emission=(1, 1, 1), emission_strength=1.2)
    M["text_dark"] = make_mat("M_TextDark", (0.05, 0.08, 0.12), rough=0.4)
    M["panel"] = make_mat("M_Panel", (0.08, 0.1, 0.14), rough=0.5)
    M["green"] = make_mat("M_Green", (0.2, 0.95, 0.45), emission=(0.15, 0.9, 0.4), emission_strength=1.2)
    M["yellow"] = make_mat("M_Yellow", (1.0, 0.85, 0.15), emission=(1.0, 0.8, 0.1), emission_strength=1.0)
    M["red"] = make_mat("M_Red", (1.0, 0.25, 0.2), emission=(1.0, 0.2, 0.15), emission_strength=1.2)
    M["floor"] = make_mat("M_Floor", (0.18, 0.2, 0.24), rough=0.7)
    M["ground"] = make_mat("M_Ground", (0.12, 0.14, 0.18), rough=0.9)
    M["stripe"] = make_mat("M_Stripe", (0.95, 0.55, 0.1), rough=0.4)
    return M


# ---------------------------------------------------------------------------
# 4. 飞机几何
# ---------------------------------------------------------------------------

def build_aircraft(M, root):
    """简化窄体，机头 +X，机身沿 X 轴，原点在机身中心附近。"""
    parts = {}

    # 机身 — 分段圆柱 + 机头锥
    fuselage = []
    # 主身
    body = add_cyl(
        "Fuselage_Main",
        radius=Config.FUSE_R,
        depth=Config.FUSE_LEN * 0.78,
        loc=(0, 0, 0),
        rot=(0, math.radians(90), 0),
        mat=M["body"],
        verts=32,
    )
    set_parent_keep(body, root)
    fuselage.append(body)
    parts["body"] = body

    # 机头
    nose = add_sphere("Fuselage_Nose", radius=Config.FUSE_R, loc=(Config.FUSE_LEN * 0.39 + 1.2, 0, 0), mat=M["body"], seg=32)
    nose.scale = (1.8, 1.0, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    set_parent_keep(nose, root)
    fuselage.append(nose)

    # 机尾收缩
    tail = add_cyl("Fuselage_Tail", radius=Config.FUSE_R * 0.85, depth=8.0, loc=(-Config.FUSE_LEN * 0.39 - 2.5, 0, 0.3), rot=(0, math.radians(90), 0), mat=M["body"], verts=32)
    tail.scale = (1.0, 0.7, 0.9)
    bpy.ops.object.transform_apply(scale=True)
    set_parent_keep(tail, root)
    fuselage.append(tail)

    # 地板
    floor = add_cube("Cabin_Floor", size=(Config.FUSE_LEN * 0.72, Config.FUSE_R * 1.5, 0.12), loc=(1.5, 0, -0.15), mat=M["floor"])
    set_parent_keep(floor, root)
    parts["floor"] = floor

    # 下货舱地板
    cargo_floor = add_cube("Cargo_Floor", size=(Config.FUSE_LEN * 0.65, Config.FUSE_R * 1.3, 0.1), loc=(1.5, 0, -1.25), mat=M["frame"])
    set_parent_keep(cargo_floor, root)
    parts["cargo_floor"] = cargo_floor

    # 机翼 — 左右
    def wing(side_sign, name):
        # 简化梯形翼盒
        span_half = Config.WING_SPAN / 2
        root_c = Config.WING_ROOT_CHORD
        tip_c = Config.WING_TIP_CHORD
        # 翼根位置 station ~ 15 → x
        wing_x = Config.station_to_x(15.0)
        # 用自定义网格更可控
        mesh = bpy.data.meshes.new(name)
        # 8 vertices: root LE/TE, tip LE/TE (top and bottom simplified as thin extrude)
        sweep_tan = math.tan(math.radians(Config.WING_SWEEP_DEG))
        y_root = Config.FUSE_R * 0.7 * side_sign
        y_tip = span_half * side_sign
        # LE root
        x_le_r = wing_x + root_c * 0.3
        x_te_r = wing_x - root_c * 0.7
        x_le_t = x_le_r - abs(y_tip - y_root) * sweep_tan * 0.55
        x_te_t = x_le_t + tip_c
        z_r = -0.2
        z_t = 0.6
        t = 0.12
        verts = [
            (x_le_r, y_root, z_r + t),
            (x_te_r, y_root, z_r + t),
            (x_te_t, y_tip, z_t + t),
            (x_le_t, y_tip, z_t + t),
            (x_le_r, y_root, z_r - t),
            (x_te_r, y_root, z_r - t),
            (x_te_t, y_tip, z_t - t),
            (x_le_t, y_tip, z_t - t),
        ]
        faces = [
            (0, 1, 2, 3),
            (7, 6, 5, 4),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (3, 7, 4, 0),
        ]
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        o = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(o)
        o.data.materials.append(M["wing"])
        set_parent_keep(o, root)
        return o

    wl = wing(-1, "Wing_L")
    wr = wing(1, "Wing_R")
    parts["wings"] = [wl, wr]

    # 平尾
    for side_sign, nm in ((-1, "HStab_L"), (1, "HStab_R")):
        sh = add_cube(nm, size=(2.4, 5.5, 0.15), loc=(-14.5, 4.0 * side_sign, 1.2), mat=M["stab"])
        sh.rotation_euler = (0, 0, math.radians(-20 * side_sign))
        set_parent_keep(sh, root)
    # 垂尾
    vstab = add_cube("VStab", size=(3.2, 0.18, 4.5), loc=(-15.5, 0, 3.2), mat=M["stab"])
    vstab.rotation_euler = (0, math.radians(-30), 0)
    set_parent_keep(vstab, root)

    # 发动机
    for side_sign, nm in ((-1, "Engine_L"), (1, "Engine_R")):
        eng = add_cyl(nm, radius=0.85, depth=3.2, loc=(1.2, 4.8 * side_sign, -1.1), rot=(0, math.radians(90), 0), mat=M["engine"], verts=24)
        set_parent_keep(eng, root)
        inlet = add_cyl(nm + "_Inlet", radius=0.95, depth=0.35, loc=(2.85, 4.8 * side_sign, -1.1), rot=(0, math.radians(90), 0), mat=M["engine"], verts=24)
        set_parent_keep(inlet, root)

    # 起落架
    ng = add_cyl("Gear_Nose", radius=0.35, depth=1.6, loc=(12.5, 0, -2.4), mat=M["gear"])
    set_parent_keep(ng, root)
    for side_sign, nm in ((-1, "Gear_ML"), (1, "Gear_MR")):
        mg = add_cyl(nm, radius=0.42, depth=1.9, loc=(-1.0, 1.4 * side_sign, -2.5), mat=M["gear"])
        set_parent_keep(mg, root)

    parts["fuselage"] = fuselage
    return parts


# ---------------------------------------------------------------------------
# 5. 装载舱（旅客/行李/货/油）— 可爆炸
# ---------------------------------------------------------------------------

def build_payload(M, root):
    payload = {
        "groups": {},
        "all": [],
    }

    # 旅客座椅块（几何位置沿机身；计算用 arm 站位）
    # 机头 x≈18.6, 机尾 x≈-19；MAC 前缘 x = station_to_x(13) = 5.0
    zone_mesh_x = {
        "FWD": (7.5, 12.0),
        "MID": (2.0, 7.2),
        "AFT": (-3.5, 1.7),
    }
    mat_map = {"FWD": M["pax_fwd"], "MID": M["pax_mid"], "AFT": M["pax_aft"]}

    for zid, (x0, x1) in zone_mesh_x.items():
        objs = []
        n_rows = {"FWD": 5, "MID": 6, "AFT": 5}[zid]
        for i in range(n_rows):
            x = x0 + (x1 - x0) * (i + 0.5) / n_rows
            seat = add_cube(
                f"Seats_{zid}_{i}",
                size=((x1 - x0) / n_rows * 0.8, 2.2, 0.5),
                loc=(x, 0, 0.4),
                mat=mat_map[zid],
                bevel=0.03,
            )
            set_parent_keep(seat, root)
            objs.append(seat)
        payload["groups"][f"PAX_{zid}"] = objs
        payload["all"].extend(objs)

    # 行李（货舱内小箱）
    bag_zones = [
        ("FWD", 9.0, 12.5, M["bag"]),
        ("AFT", 1.5, 5.0, M["bag"]),
    ]
    for zid, x0, x1, mat in bag_zones:
        objs = []
        for i in range(4):
            x = x0 + (x1 - x0) * (i + 0.5) / 4
            for y in (-0.55, 0.55):
                b = add_cube(f"Bag_{zid}_{i}_{y}", size=(0.5, 0.42, 0.35), loc=(x, y, -1.05), mat=mat, bevel=0.02)
                set_parent_keep(b, root)
                objs.append(b)
        payload["groups"][f"BAG_{zid}"] = objs
        payload["all"].extend(objs)

    # 货物集装箱
    cargo_defs = [
        ("FWD", 10.0, 13.5, M["cargo_fwd"], 0.7),
        ("AFT", 2.5, 6.0, M["cargo_aft"], 0.75),
        ("BULK", -1.0, 2.0, M["cargo_bulk"], 0.45),
    ]
    for cid, x0, x1, mat, h in cargo_defs:
        objs = []
        for i in range(3):
            x = x0 + (x1 - x0) * (i + 0.5) / 3
            c = add_cube(f"Cargo_{cid}_{i}", size=(0.9, 1.5, h), loc=(x, 0, -0.85), mat=mat, bevel=0.04)
            set_parent_keep(c, root)
            objs.append(c)
        payload["groups"][f"CARGO_{cid}"] = objs
        payload["all"].extend(objs)

    # 燃油 — 机翼内
    fuel_objs = []
    for side_sign, nm in ((-1, "L"), (1, "R")):
        tank = add_cube(
            f"Fuel_Wing_{nm}",
            size=(4.0, 7.5, 0.35),
            loc=(1.0, 5.5 * side_sign, -0.1),
            mat=M["fuel_wing"],
            bevel=0.05,
        )
        set_parent_keep(tank, root)
        fuel_objs.append(tank)
    ctr = add_cube("Fuel_CTR", size=(3.5, 2.0, 0.4), loc=(1.5, 0, -0.1), mat=M["fuel_ctr"], bevel=0.05)
    set_parent_keep(ctr, root)
    fuel_objs.append(ctr)
    payload["groups"]["FUEL_WING"] = [o for o in fuel_objs if "Wing" in o.name]
    payload["groups"]["FUEL_CTR"] = [ctr]
    payload["all"].extend(fuel_objs)

    return payload


# ---------------------------------------------------------------------------
# 6. MAC / CG / DATUM 可视化
# ---------------------------------------------------------------------------

def build_wb_viz(M, root):
    viz = {}
    # DATUM 平面
    datum_x = Config.DATUM_X
    plane = add_cube("Viz_DatumPlane", size=(0.06, 12, 8), loc=(datum_x, 0, 0), mat=M["datum"], bevel=0)
    set_parent_keep(plane, root)
    viz["datum"] = plane
    lab = text_obj("Lab_Datum", "DATUM\n基准面", (datum_x + 0.3, 0, 4.5), size=0.55, mat=M["datum"])
    set_parent_keep(lab, root)

    # MAC 剖面（机翼中部一个矩形弦）
    le = Config.station_to_x(Config.LEMAC_STATION)
    te = Config.station_to_x(Config.TEMAC_STATION)
    mac_y = 4.2
    mac = add_cube("Viz_MAC", size=(abs(le - te), 1.6, 0.08), loc=((le + te) / 2, mac_y, 0.9), mat=M["mac"], bevel=0.02)
    set_parent_keep(mac, root)
    viz["mac"] = mac
    lab_le = text_obj("Lab_LEMAC", "LEMAC", (le, mac_y, 1.5), size=0.4, mat=M["mac"])
    set_parent_keep(lab_le, root)
    lab_te = text_obj("Lab_TEMAC", "TEMAC", (te, mac_y, 1.5), size=0.4, mat=M["mac"])
    set_parent_keep(lab_te, root)

    # %MAC 刻度条（在 MAC 上方）
    # 常用范围 5%~45%
    for pct in (5, 15, 25, 35, 45):
        x = Config.station_to_x(Config.LEMAC_STATION + Config.MAC * pct / 100)
        tick = add_cube(f"Tick_{pct}", size=(0.05, 0.35, 0.25), loc=(x, mac_y + 1.2, 0.9), mat=M["limit"], bevel=0)
        set_parent_keep(tick, root)
        t = text_obj(f"TickLab_{pct}", f"{pct}%", (x, mac_y + 1.2, 1.35), size=0.28, mat=M["limit"])
        set_parent_keep(t, root)

    # 安全包线色带（20%~34% 教学示例）
    lim_lo = Config.LEMAC_STATION + Config.MAC * 0.20
    lim_hi = Config.LEMAC_STATION + Config.MAC * 0.34
    x_lo = Config.station_to_x(lim_lo)
    x_hi = Config.station_to_x(lim_hi)
    band = add_cube("Viz_CGBand", size=(abs(x_lo - x_hi), 0.25, 0.12), loc=((x_lo + x_hi) / 2, mac_y + 0.8, 0.9), mat=M["green"], bevel=0)
    set_parent_keep(band, root)

    # CG 标记（空物体，便于驱动）
    cg_st = Config.OEW_STATION
    cg_x = Config.station_to_x(cg_st)
    empty = bpy.data.objects.new("CG_Empty", None)
    empty.empty_display_type = "ARROWS"
    empty.empty_display_size = 1.4
    empty.location = (cg_x, 0, 0)
    bpy.context.collection.objects.link(empty)
    set_parent_keep(empty, root)
    viz["cg_empty"] = empty

    # CG 锥体
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.55, depth=1.0, location=(cg_x, 0, 2.8), rotation=(math.radians(180), 0, 0))
    cone = bpy.context.active_object
    cone.name = "Viz_CGCone"
    cone.data.materials.append(M["cg"])
    set_parent_keep(cone, root)
    viz["cg_cone"] = cone

    # 垂线到机身
    rod = add_cyl("Viz_CGLine", radius=0.035, depth=5.5, loc=(cg_x, 0, 0.2), mat=M["cg"], verts=8)
    set_parent_keep(rod, root)
    viz["cg_line"] = rod

    # 力矩示意（从 datum 到 CG 的箭头条）
    moment_bar = add_cube("Viz_MomentBar", size=(abs(cg_x - datum_x), 0.08, 0.08), loc=((cg_x + datum_x) / 2, -3.5, 0.5), mat=M["yellow"], bevel=0)
    set_parent_keep(moment_bar, root)
    viz["moment_bar"] = moment_bar
    lab_m = text_obj("Lab_Moment", "力矩 = 重量 × 力臂", ((cg_x + datum_x) / 2, -3.5, 1.1), size=0.4, mat=M["yellow"])
    set_parent_keep(lab_m, root)

    # 地面
    ground = add_cube("Ground", size=(50, 40, 0.1), loc=(0, 0, -3.55), mat=M["ground"], bevel=0)
    set_parent_keep(ground, root)

    return viz


# ---------------------------------------------------------------------------
# 7. 计算面板（右侧立牌）
# ---------------------------------------------------------------------------

def build_info_panel(M, root, result):
    panel = add_cube("InfoPanel", size=(0.15, 7.5, 9.0), loc=(16.5, -9.5, 2.5), mat=M["panel"], bevel=0.08)
    set_parent_keep(panel, root)

    lines = [
        ("Title", "配载平衡计算 Load Control", (16.35, -9.5, 6.2), 0.42, M["text"]),
        ("Sep1", "──────────────", (16.35, -9.5, 5.6), 0.3, M["mac"]),
        ("Eq1", "力矩 Moment = 重量 W × 力臂 Arm", (16.35, -9.5, 5.0), 0.32, M["yellow"]),
        ("Eq2", "重心 CG = Σ力矩 / Σ重量", (16.35, -9.5, 4.4), 0.32, M["yellow"]),
        ("Eq3", "%MAC = (CG-LEMAC)/MAC × 100", (16.35, -9.5, 3.8), 0.32, M["mac"]),
        ("Sep2", "──────────────", (16.35, -9.5, 3.25), 0.3, M["mac"]),
        ("W", f"总重 TOW: {result['total_weight']:.0f} kg", (16.35, -9.5, 2.6), 0.35, M["text"]),
        ("M", f"总力矩: {result['total_moment']:.0f} kg·m", (16.35, -9.5, 2.0), 0.32, M["text"]),
        ("CG", f"重心站位: {result['cg_station']:.2f} m", (16.35, -9.5, 1.4), 0.32, M["green"]),
        ("MAC", f"重心 %MAC: {result['cg_mac']:.1f}%", (16.35, -9.5, 0.8), 0.38, M["cg"]),
        ("ZFW", f"零油重 ZFW: {result['zfw']:.0f} kg", (16.35, -9.5, 0.2), 0.3, M["text"]),
        ("PL", f"业载 Payload: {result['payload']:.0f} kg", (16.35, -9.5, -0.4), 0.3, M["text"]),
        ("PAX", f"旅客人数: {result['pax_total']} 人", (16.35, -9.5, -1.0), 0.28, M["text"]),
        ("Note", "教学模型·数值示意", (16.35, -9.5, -1.6), 0.25, M["text"]),
    ]
    objs = {}
    for key, body, loc, size, mat in lines:
        t = text_obj(f"UI_{key}", body, loc, size=size, mat=mat, align="CENTER")
        # 面向 -Y 方向（观众）
        t.rotation_euler = (math.radians(90), 0, math.radians(180))
        set_parent_keep(t, root)
        objs[key] = t
    return objs


# ---------------------------------------------------------------------------
# 8. 爆炸拆解布局
# ---------------------------------------------------------------------------

def build_explode_setup(groups_root, payload):
    """为每个可拆件写入 explode_offset 自定义属性，供后续驱动。"""
    # 各组爆炸方向（相对组装位）
    offsets = {
        "PAX_FWD": (5.0, 0, 4.0),
        "PAX_MID": (0, 0, 5.5),
        "PAX_AFT": (-5.0, 0, 4.0),
        "BAG_FWD": (3.0, 0, 7.0),
        "BAG_AFT": (-3.0, 0, 7.0),
        "CARGO_FWD": (2.5, 0, 8.5),
        "CARGO_AFT": (-2.5, 0, 8.5),
        "CARGO_BULK": (-5.5, 0, 8.5),
        "FUEL_WING": (0, 8.0, 2.5),
        "FUEL_CTR": (0, 0, 10.0),
    }
    for gname, objs in payload["groups"].items():
        off = offsets.get(gname, (0, 0, 5))
        for o in objs:
            o["explode_x"] = off[0]
            o["explode_y"] = off[1]
            o["explode_z"] = off[2]
            o["group"] = gname
            o["assembled_x"] = o.location.x
            o["assembled_y"] = o.location.y
            o["assembled_z"] = o.location.z


# ---------------------------------------------------------------------------
# 9. 主构建
# ---------------------------------------------------------------------------

def apply_load_to_viz(viz, ui, result, M):
    # 更新 CG 位置
    cg_x = Config.station_to_x(result["cg_station"])
    if "cg_empty" in viz:
        viz["cg_empty"].location.x = cg_x
    if "cg_cone" in viz:
        viz["cg_cone"].location.x = cg_x
    if "cg_line" in viz:
        viz["cg_line"].location.x = cg_x
    if "moment_bar" in viz:
        datum_x = Config.DATUM_X
        viz["moment_bar"].location.x = (cg_x + datum_x) / 2
        # 长度重缩放：以 mesh 1m 为基准 — 用 scale
        length = abs(cg_x - datum_x)
        # 原 cube size 已 apply，改 scale.x
        viz["moment_bar"].scale.x = length / max(viz["moment_bar"].dimensions.x / max(viz["moment_bar"].scale.x, 1e-6), 1e-6)

    # 更稳妥：直接重建长度
    if "moment_bar" in viz:
        bar = viz["moment_bar"]
        datum_x = Config.DATUM_X
        length = abs(cg_x - datum_x)
        # dimensions 基于当前 scale；重置 scale 后设置
        bar.scale = (1, 1, 1)
        # 原始 mesh 宽度已按初始 CG 固定，改用 scale 近似
        # 换成：用 empty 驱动的尺寸 — 直接改 scale.x 使 dims≈length
        current = bar.dimensions.x
        if current > 1e-6:
            bar.scale.x = length / current
        bar.location.x = (cg_x + datum_x) / 2

    # 包线颜色
    ok = 20.0 <= result["cg_mac"] <= 34.0
    color_mat = M["green"] if ok else M["red"]
    if "cg_cone" in viz:
        # 切换材质
        o = viz["cg_cone"]
        o.data.materials.clear()
        o.data.materials.append(color_mat)

    # 文本
    def setui(key, body):
        o = ui.get(key)
        if o and o.data and hasattr(o.data, "body"):
            o.data.body = body

    setui("W", f"总重 TOW: {result['total_weight']:.0f} kg")
    setui("M", f"总力矩: {result['total_moment']:.0f} kg·m")
    setui("CG", f"重心站位: {result['cg_station']:.2f} m")
    setui("MAC", f"重心 %MAC: {result['cg_mac']:.1f}%  {'✓ 安全' if ok else '✗ 超限'}")
    setui("ZFW", f"零油重 ZFW: {result['zfw']:.0f} kg")
    setui("PL", f"业载 Payload: {result['payload']:.0f} kg")
    setui("PAX", f"旅客人数: {result.get('pax_total', 0)} 人")


def main():
    clear_scene()
    log("scene cleared")
    M = build_materials()
    log("materials ready")

    # 根空物体
    root = bpy.data.objects.new("AIRCRAFT_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 2
    bpy.context.collection.objects.link(root)

    aircraft = build_aircraft(M, root)
    log("aircraft geometry")
    payload = build_payload(M, root)
    log("payload objects")
    build_explode_setup(None, payload)
    viz = build_wb_viz(M, root)
    log("wb visualization")

    result = compute_load()
    ui = build_info_panel(M, root, result)
    apply_load_to_viz(viz, ui, result, M)
    log(f"initial CG%MAC={result['cg_mac']:.2f} TOW={result['total_weight']:.0f}")

    # 场景自定义属性（供 UI 脚本）
    scene = bpy.context.scene
    scene["teaching"] = True
    for zid, n in Config.INIT_PAX.items():
        scene[f"pax_{zid}"] = n
    for cid, kg in Config.INIT_CARGO.items():
        scene[f"cargo_{cid}"] = kg
    for fid, kg in Config.INIT_FUEL.items():
        scene[f"fuel_{fid}"] = kg
    scene["cg_mac"] = result["cg_mac"]
    scene["tow"] = result["total_weight"]
    scene["explode"] = 0.0

    # 相机与灯光
    bpy.ops.object.camera_add(location=(38, -42, 22), rotation=(math.radians(62), 0, math.radians(42)))
    cam = bpy.context.active_object
    cam.name = "TeachCam"
    scene.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(20, -10, 40))
    sun = bpy.context.active_object
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(35), math.radians(15), math.radians(-30))

    bpy.ops.object.light_add(type="AREA", location=(5, -15, 12))
    area = bpy.context.active_object
    area.data.energy = 800
    area.data.size = 20

    # 世界背景
    world = bpy.data.worlds.new("TeachWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.07, 0.1, 1)
        bg.inputs[1].default_value = 0.6

    # 保存引用到场景
    scene["has_load_model"] = 1

    out = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # 内嵌交互面板脚本到 Text，便于在 Blender 中一键运行
    panel_src = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts\loadbalance_panel.py"
    try:
        with open(panel_src, "r", encoding="utf-8") as f:
            txt = bpy.data.texts.get("loadbalance_panel.py") or bpy.data.texts.new("loadbalance_panel.py")
            txt.clear()
            txt.write(f.read())
        # 注册 addon（同一会话可用）
        import importlib.util
        spec = importlib.util.spec_from_file_location("loadbalance_panel", panel_src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        try:
            mod.register()
            log("panel addon registered")
        except Exception as e:
            log(f"panel register warn: {e}")
    except Exception as e:
        log(f"embed panel failed: {e}")

    bpy.ops.wm.save_as_mainfile(filepath=out)
    log(f"saved {out}")
    return result


if __name__ == "__main__":
    main()

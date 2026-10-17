"""
配载平衡教学模型 v4 — A320-200 外形 + ACAP/WBM 数表 + 可操控 N 面板
通过 Blender MCP 或 blender --python 本脚本均可重建。
"""
import bpy, math, os, sys, importlib.util

ROOT_DIR = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模"
OUT = os.path.join(ROOT_DIR, "output", "配载平衡教学模型.blend")
PANEL = os.path.join(ROOT_DIR, "scripts", "loadbalance_panel.py")
DATA = os.path.join(ROOT_DIR, "scripts", "a320_data.py")
PREVIEW = os.path.join(ROOT_DIR, "output", "preview")

sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
import a320_data as D


def reset():
    """清空场景但保留 MCP 插件连接（不要 factory reset）。"""
    try:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
    except Exception:
        pass
    for block_list in (
        bpy.data.meshes, bpy.data.curves, bpy.data.materials,
        bpy.data.cameras, bpy.data.lights, bpy.data.worlds,
    ):
        for block in list(block_list):
            try:
                block_list.remove(block)
            except Exception:
                pass
    # 卸载旧面板
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("lbp_old", PANEL)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.unregister()
    except Exception:
        pass
    for h in list(bpy.app.handlers.load_post):
        try:
            bpy.app.handlers.load_post.remove(h)
        except Exception:
            pass


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


def build_fuselage(mat, root):
    """A320-200 机身：圆截面 + 钝机头 + 等直段 + 尾段上翘。机头 +X。"""
    r0 = D.FUS_DIA / 2.0  # 1.975
    # (station, radius, z_center) — 机头更钝，尾段下表面明显上翘
    sections = [
        (0.00, 0.12, 0.05),
        (0.35, 0.55, 0.02),
        (0.90, 1.05, 0.00),
        (1.60, 1.45, 0.00),
        (2.40, 1.72, 0.00),
        (3.30, 1.88, 0.00),
        (4.40, 1.96, 0.00),
        (5.60, r0, 0.00),
        (8.00, r0, 0.00),
        (12.0, r0, 0.00),
        (16.0, r0, 0.00),
        (20.0, r0, 0.00),
        (24.0, r0, 0.00),
        (27.0, r0, 0.00),
        (29.0, r0, 0.05),
        (30.5, r0, 0.15),
        (32.0, 1.92, 0.30),
        (33.3, 1.78, 0.45),
        (34.4, 1.55, 0.62),
        (35.3, 1.25, 0.78),
        (36.1, 0.90, 0.92),
        (36.8, 0.55, 1.05),
        (37.3, 0.28, 1.12),
        (37.57, 0.08, 1.15),
    ]
    segs = 28
    verts, faces = [], []
    for st, r, zc in sections:
        x = D.sx(st)
        for i in range(segs):
            a = 2 * math.pi * i / segs
            # 底部略扁（客机截面）
            y = r * math.sin(a)
            z = zc + r * math.cos(a)
            verts.append((x, y, z))
    n = len(sections)
    for s in range(n - 1):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append((s * segs + i, s * segs + j, (s + 1) * segs + j, (s + 1) * segs + i))
    faces.append(tuple(range(segs - 1, -1, -1)))
    faces.append(tuple((n - 1) * segs + i for i in range(segs)))

    me = bpy.data.meshes.new("Fuselage")
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new("Fuselage", me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    par(o, root)

    # 座舱风挡（斜窗带）
    glass = mkmat("M_Glass", (0.12, 0.22, 0.32), metal=0.25, rough=0.12, alpha=0.9)
    box("CockpitGlass", 1.4, 1.7, 0.5, (D.sx(2.9), 0, 0.95), glass, root, 0.12)
    # 地板 / 货舱地板 / 机腹
    floor_m = mkmat("M_Floor2", (0.22, 0.25, 0.3), rough=0.7)
    box("CabinFloor", 22.0, 3.3, 0.08, (D.sx(18.0), 0, 0.40), floor_m, root, 0.02)
    box("CargoFloor", 18.0, 3.1, 0.06, (D.sx(20.0), 0, -1.40), mat, root, 0.02)
    box("BellyFairing", 11.0, 3.0, 0.85, (D.sx(18.5), 0, -1.95), mat, root, 0.2)


def _wing_mesh(name, le_root_st, root_chord, tip_chord, y0, y1, z_root, sweep_tan, dihedral_tan, mat, root):
    """单侧梯形机翼。y0/y1 带符号（左负右正）；后掠/上反按 |y| 计算。"""
    ay1 = abs(y1)
    le_y0 = le_root_st
    te_y0 = le_root_st + root_chord
    le_y1 = le_root_st + sweep_tan * ay1
    te_y1 = le_y1 + tip_chord
    z1 = z_root + dihedral_tan * ay1
    t0, t1 = 0.38, 0.12

    def pt(st, y, z):
        return (D.sx(st), y, z)

    verts = [
        pt(le_y0, y0, z_root + t0 / 2), pt(te_y0, y0, z_root + t0 / 2),
        pt(te_y1, y1, z1 + t1 / 2), pt(le_y1, y1, z1 + t1 / 2),
        pt(le_y0, y0, z_root - t0 / 2), pt(te_y0, y0, z_root - t0 / 2),
        pt(te_y1, y1, z1 - t1 / 2), pt(le_y1, y1, z1 - t1 / 2),
    ]
    # 左右翼都保证外法线朝上/外
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 3, 7, 4),
        (2, 1, 5, 6),
        (1, 0, 4, 5),
        (3, 2, 6, 7),
    ]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    try:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.update()
    except Exception:
        pass
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
    par(o, root)
    return o


def build_wings(M, root):
    """低单翼 + 25° 后掠 + 5.1° 上反 + 翼尖小翼；翼展 34.1 m。"""
    span_half = D.WINGSPAN / 2.0
    root_chord = 7.0
    tip_chord = 1.6
    sweep_tan = math.tan(math.radians(D.WING_SWEEP_DEG))
    dihedral_tan = math.tan(math.radians(D.WING_DIHEDRAL_DEG))
    le_root_st = 16.45
    z_root = -1.70
    y_break = span_half * 0.52

    for side, nm in ((1.0, "Wing_R"), (-1.0, "Wing_L")):
        y0 = abs(0.0) + 1.2 if side > 0 else -(1.2)
        # 内段：从机身侧向折点
        _wing_mesh(nm + "_inner", le_root_st, root_chord,
                   root_chord + (tip_chord - root_chord) * (y_break / span_half),
                   side * 1.2, side * y_break, z_root, sweep_tan, dihedral_tan, M["wing"], root)
        # 外段
        _wing_mesh(nm + "_outer",
                   le_root_st + sweep_tan * y_break,
                   root_chord + (tip_chord - root_chord) * (y_break / span_half),
                   tip_chord,
                   side * y_break, side * span_half, z_root + dihedral_tan * y_break,
                   sweep_tan, dihedral_tan, M["wing"], root)

        le_t = le_root_st + sweep_tan * span_half
        z_t = z_root + dihedral_tan * span_half
        # A320ceo 翼尖围栏
        fence = box(f"{nm}_fence", 0.85, 0.12, 1.15,
                    (D.sx(le_t + 0.45), side * (span_half + 0.05), z_t + 0.50),
                    M["solid"], root, 0.02)
        fence.rotation_euler = (0, math.radians(-8), math.radians(side * 12))

    # 平尾：半展约 5.5 m → 全展约 11 m（接近 A320 12.45 m）
    for side, nm in ((-1, "HS_L"), (1, "HS_R")):
        box(nm, 2.2, 5.2, 0.14, (D.sx(32.4), side * 3.2, 1.20), M["solid"], root, 0.03,
            rot=(0, 0, math.radians(side * -18)))
    # 垂尾
    box("VS", 3.5, 0.16, 3.5, (D.sx(32.8), 0, 3.0), M["solid"], root, 0.04,
        rot=(0, math.radians(-30), 0))
    box("VS_Dorsal", 4.8, 0.12, 0.55, (D.sx(28.8), 0, 1.70), M["solid"], root, 0.03,
        rot=(0, math.radians(-5), 0))

    # 发动机：CFM56 量级，挂在翼下
    eng_r = 0.88
    eng_y = 5.8
    eng_st = 15.2
    eng_z = -2.55
    for side, nm in ((-1, "E_L"), (1, "E_R")):
        loc = (D.sx(eng_st), side * eng_y, eng_z)
        bpy.ops.mesh.primitive_cylinder_add(vertices=36, radius=eng_r, depth=3.8,
                                            location=loc, rotation=(0, math.radians(90), 0))
        o = bpy.context.active_object
        o.name = nm
        o.data.materials.append(M["eng"])
        par(o, root)
        bpy.ops.mesh.primitive_cylinder_add(vertices=36, radius=eng_r * 1.08, depth=0.4,
                                            location=(loc[0] + 1.75, loc[1], loc[2]),
                                            rotation=(0, math.radians(90), 0))
        o = bpy.context.active_object
        o.name = nm + "N"
        o.data.materials.append(M["eng"])
        par(o, root)
        # 尾喷
        bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=eng_r * 0.55, radius2=eng_r * 0.35,
                                        depth=0.9, location=(loc[0] - 2.1, loc[1], loc[2]),
                                        rotation=(0, math.radians(-90), 0))
        o = bpy.context.active_object
        o.name = nm + "X"
        o.data.materials.append(M["eng"])
        par(o, root)
        # 吊挂
        box(nm + "P", 1.8, 0.28, 1.0, (loc[0] + 0.3, loc[1] * 0.88, loc[2] + 1.0),
            M["solid"], root, 0.03)

    # 起落架
    nose_x = D.sx(3.5)
    main_x = D.sx(3.5 + D.WHEELBASE)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.32, depth=1.4,
                                        location=(nose_x, 0, -2.55))
    o = bpy.context.active_object; o.name = "GN"; o.data.materials.append(M["gear"]); par(o, root)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.42, depth=1.55,
                                            location=(main_x, side * D.MAIN_TRACK / 2, -2.7))
        o = bpy.context.active_object; o.name = f"GM{side}"; o.data.materials.append(M["gear"]); par(o, root)
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.45, depth=0.28,
                                            location=(main_x, side * (D.MAIN_TRACK / 2 + 0.2), -2.95),
                                            rotation=(math.radians(90), 0, 0))
        o = bpy.context.active_object; o.name = f"GW{side}"; o.data.materials.append(M["gear"]); par(o, root)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.35, depth=0.22,
                                        location=(nose_x, 0, -2.85), rotation=(math.radians(90), 0, 0))
    o = bpy.context.active_object; o.name = "GWN"; o.data.materials.append(M["gear"]); par(o, root)


def build():
    reset()
    os.makedirs(PREVIEW, exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    M = {
        "hull": mkmat("M_Hull", (0.80, 0.83, 0.88), metal=0.12, rough=0.32, alpha=0.42),
        "solid": mkmat("M_Solid", (0.48, 0.54, 0.62), metal=0.25, rough=0.35),
        "wing": mkmat("M_Wing", (0.62, 0.68, 0.78), metal=0.2, rough=0.38, alpha=1.0),
        "eng": mkmat("M_Eng", (0.28, 0.3, 0.34), metal=0.55, rough=0.3),
        "gear": mkmat("M_Gear", (0.12, 0.12, 0.15), rough=0.4),
        "paxF": mkmat("M_pF", D.ZONES["FWD"]["color"], rough=0.5),
        "paxM": mkmat("M_pM", D.ZONES["MID"]["color"], rough=0.5),
        "paxA": mkmat("M_pA", D.ZONES["AFT"]["color"], rough=0.5),
        "cF": mkmat("M_cF", D.CARGO["FWD"]["color"], rough=0.45),
        "cA": mkmat("M_cA", D.CARGO["AFT"]["color"], rough=0.45),
        "cB": mkmat("M_cB", D.CARGO["BULK"]["color"], rough=0.45),
        "bag": mkmat("M_Bag", (0.55, 0.4, 0.28), rough=0.7),
        "fW": mkmat("M_fW", (0.25, 0.8, 0.5), alpha=0.5, rough=0.3),
        "fC": mkmat("M_fC", (0.2, 0.6, 0.9), alpha=0.5, rough=0.3),
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

    build_fuselage(M["hull"], root)
    build_wings(M, root)
    # 地面
    ground_z = -3.25
    box("Ground", 90, 60, 0.1, (0, 0, ground_z), M["ground"], root, 0)

    # —— 装载可视化分组 ——
    payload = {}
    # 旅客区：舱地板附近色块
    zg = {
        "FWD": (7.0, 15.0),
        "MID": (15.0, 21.5),
        "AFT": (21.5, 29.0),
    }
    zm = {"FWD": M["paxF"], "MID": M["paxM"], "AFT": M["paxA"]}
    for z, (st0, st1) in zg.items():
        objs = []
        n = 5
        for i in range(n):
            st = st0 + (st1 - st0) * (i + 0.5) / n
            x = D.sx(st)
            objs.append(box(f"S_{z}_{i}", (st1 - st0) / n * 0.85, 2.4, 0.4,
                            (x, 0, 0.7), zm[z], root, 0.03))
        payload[f"PAX_{z}"] = objs

    # 行李
    for z, st0, st1 in (("FWD", 11.2, 14.5), ("AFT", 22.5, 26.5)):
        objs = []
        for i in range(3):
            st = st0 + (st1 - st0) * (i + 0.5) / 3
            x = D.sx(st)
            for y in (-0.6, 0.6):
                objs.append(box(f"B_{z}_{i}_{int(y*100)}", 0.55, 0.4, 0.3,
                                (x, y, -0.85), M["bag"], root, 0.02))
        payload[f"BAG_{z}"] = objs

    # 货舱
    for cid, st0, st1, mm, h in (
        ("FWD", 11.2, 14.4, M["cF"], 0.65),
        ("AFT", 22.8, 26.4, M["cA"], 0.7),
        ("BULK", 27.6, 30.0, M["cB"], 0.45),
    ):
        objs = []
        for i in range(3):
            st = st0 + (st1 - st0) * (i + 0.5) / 3
            x = D.sx(st)
            objs.append(box(f"C_{cid}_{i}", 0.85, 1.5, h, (x, 0, -0.9), mm, root, 0.04))
        payload[f"CARGO_{cid}"] = objs

    # 燃油
    fw = []
    wing_x = D.sx(D.WING_SPAR_ST)
    for side in (-1, 1):
        fw.append(box(f"FW_{side}", 4.2, 5.5, 0.22, (wing_x, side * 4.8, -1.45),
                      M["fW"], root, 0.03))
    payload["FUEL_WING"] = fw
    payload["FUEL_CTR"] = [box("FC", 2.6, 1.6, 0.25, (D.sx(D.CTR_TANK_ST), 0, -1.0),
                               M["fC"], root, 0.03)]

    explode = {
        "PAX_FWD": (4.0, 0, 3.2), "PAX_MID": (0, 0, 4.0), "PAX_AFT": (-4.0, 0, 3.2),
        "BAG_FWD": (2.5, 0, 5.0), "BAG_AFT": (-2.5, 0, 5.0),
        "CARGO_FWD": (2.0, 0, 6.0), "CARGO_AFT": (-2.0, 0, 6.0), "CARGO_BULK": (-5.0, 0, 6.0),
        "FUEL_WING": (0, 7.0, 1.8), "FUEL_CTR": (0, 0, 7.0),
    }
    for g, objs in payload.items():
        off = explode.get(g, (0, 0, 3))
        for o in objs:
            o["gx"], o["gy"], o["gz"] = off
            o["ax"], o["ay"], o["az"] = o.location.x, o.location.y, o.location.z
            o["group"] = g

    # —— DATUM / MAC / 包线 ——
    dx = D.sx(0.0)  # 机头 = DATUM
    box("DatumBar", 0.08, 0.08, 8.5, (dx, 0, 1.2), M["datum"], root, 0)
    text("T_Dat", "DATUM 机头 FS=0", (dx + 0.2, 0, 5.2), 0.38, M["datum"], root)

    le, te = D.sx(D.LEMAC_ST), D.sx(D.TEMAC_ST)
    my = 4.2
    box("MACBar", abs(te - le), 1.0, 0.08, ((le + te) / 2, my, 0.55), M["mac"], root, 0.01)
    text("T_LE", "LEMAC", (le - 0.1, my + 0.6, 0.95), 0.3, M["mac"], root)
    text("T_TE", "TEMAC", (te - 0.5, my + 0.6, 0.95), 0.3, M["mac"], root)
    text("T_MAC", f"MAC={D.MAC:.4f} m", ((le + te) / 2 - 0.7, my + 0.6, 1.45), 0.28, M["mac"], root)

    for p in (D.FWD_LIM_PCT, 20, 25, 30, D.AFT_LIM_PCT):
        x = D.sx(D.LEMAC_ST + D.MAC * p / 100)
        box(f"Tk{p}", 0.04, 0.28, 0.2, (x, my + 1.0, 0.55), M["limit"], root, 0)
        text(f"T{p}", f"{p:.0f}%", (x - 0.12, my + 1.0, 1.0), 0.22, M["limit"], root)

    lo = D.sx(D.LEMAC_ST + D.MAC * D.AFT_LIM_PCT / 100)
    hi = D.sx(D.LEMAC_ST + D.MAC * D.FWD_LIM_PCT / 100)
    box("Band", abs(hi - lo), 0.2, 0.1, ((lo + hi) / 2, my + 0.55, 0.55), M["band"], root, 0)
    text("T_Band", f"包线 {D.FWD_LIM_PCT:.0f}–{D.AFT_LIM_PCT:.0f}% MAC (ACAP简化)",
         ((lo + hi) / 2 - 2.2, my + 0.55, 1.15), 0.26, M["band"], root)

    # CG
    res = D.compute()
    cgx = D.sx(res["cg"])
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.5, depth=0.9,
                                    location=(cgx, 0, 2.6), rotation=(math.radians(180), 0, 0))
    cone = bpy.context.active_object
    cone.name = "CGCone"
    cone.data.materials.append(M["cg"])
    par(cone, root)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=5.2,
                                        location=(cgx, 0, 0.2))
    line = bpy.context.active_object
    line.name = "CGLine"
    line.data.materials.append(M["cg"])
    par(line, root)
    empty = bpy.data.objects.new("CG_Empty", None)
    empty.location = (cgx, 0, 0)
    empty.empty_display_type = "ARROWS"
    empty.empty_display_size = 1.0
    bpy.context.collection.objects.link(empty)
    par(empty, root)

    box("MomBar", abs(cgx - dx), 0.07, 0.07, ((cgx + dx) / 2, -3.6, 0.3), M["yellow"], root, 0)
    text("T_Mom", "力矩 = 重量 × 力臂", ((cgx + dx) / 2 - 1.5, -3.6, 0.75), 0.3, M["yellow"], root)

    # 信息面板 — 放到机腹侧后方，避免挡住外形
    box("Panel", 12.0, 0.12, 8.6, (10.5, -16.5, 1.0), M["panel"], root, 0.05)
    py = -16.62
    lines = [
        ("Title", "A320 配载平衡 Load Control", (1.8, py, 4.2), 0.42, M["white"]),
        ("Src", "数据：ACAP 几何 + 简化 WBM", (1.8, py, 3.6), 0.26, M["mac"]),
        ("Geo", f"L={D.LENGTH} m  B={D.WINGSPAN} m  MAC={D.MAC:.4f} m", (1.8, py, 3.1), 0.24, M["white"]),
        ("Wts", f"OEW={D.OEW:.0f}  MTOW={D.MTOW:.0f}  MZFW={D.MZFW:.0f} kg", (1.8, py, 2.6), 0.24, M["white"]),
        ("Eq2", "重心 CG = Σ力矩 / Σ重量", (1.8, py, 2.0), 0.28, M["yellow"]),
        ("Eq3", "%MAC = (CG-LEMAC)/MAC × 100", (1.8, py, 1.5), 0.26, M["mac"]),
        ("W", f"总重 TOW: {res['tow']:.0f} kg", (1.8, py, 0.9), 0.3, M["white"]),
        ("M", f"总力矩: {res['moment']:.0f} kg·m", (1.8, py, 0.4), 0.28, M["white"]),
        ("CG", f"纵向CG站位: {res['cg']:.2f} m", (1.8, py, -0.1), 0.28, M["green"]),
        ("MAC", f"%MAC: {res['mac']:.1f}%  {res['pitch']}", (1.8, py, -0.6), 0.3, M["cg"]),
        ("ZFW", f"ZFW {res['zfw']:.0f}  业载 {res['payload']:.0f}  旅客 {res['pax']}", (1.8, py, -1.15), 0.26, M["white"]),
        ("Y", f"横向 y={res['cg_y']:+.2f} m  {res['roll']}", (1.8, py, -1.65), 0.26, M["white"]),
        ("Note", "教学示意 · 实机以 AFM/WBM 为准", (1.8, py, -2.25), 0.22, M["white"]),
    ]
    for k, body, loc, size, mm in lines:
        text(f"UI_{k}", body, loc, size, mm, root)

    text("T_F1", "CG = Σ(W×Arm) / ΣW", (-2, 6.0, 2.5), 0.32, M["yellow"], root)
    text("T_F2", "绿带内 = 重心安全", (-2, 6.0, 1.9), 0.28, M["green"], root)

    # 场景属性（兼容 panel）
    sc = bpy.context.scene
    sc["lb_mac"] = D.MAC
    sc["lb_lemac"] = D.LEMAC_ST
    sc["lb_nose_x"] = D.NOSE_X
    sc["lb_fwd_lim"] = D.FWD_LIM_PCT
    sc["lb_aft_lim"] = D.AFT_LIM_PCT
    sc["lb_mtow"] = D.MTOW
    for z, n in D.INIT_PAX.items():
        sc[f"pax_{z}"] = n
    for c, kg in D.INIT_CARGO.items():
        sc[f"cargo_{c}"] = kg
    for f, kg in D.INIT_FUEL.items():
        sc[f"fuel_{f}"] = kg

    # 相机
    bpy.ops.object.camera_add(location=(42, -48, 22),
                              rotation=(math.radians(62), 0, math.radians(42)))
    cam = bpy.context.active_object
    cam.name = "TeachCam"
    cam.data.lens = 35
    sc.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(10, -6, 36))
    sun = bpy.context.active_object
    sun.data.energy = 3.8
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(-25))
    bpy.ops.object.light_add(type="AREA", location=(8, -20, 16))
    bpy.context.active_object.data.energy = 1200
    bpy.context.active_object.data.size = 24

    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.035, 0.05, 0.085, 1)
        bg.inputs[1].default_value = 0.7

    # 注册面板
    try:
        if os.path.isfile(PANEL):
            spec = importlib.util.spec_from_file_location("lbp", PANEL)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # 先卸载旧的
            try:
                mod.unregister()
            except Exception:
                pass
            mod.register()
            print("panel ok")
    except Exception as e:
        print("panel", e)
    try:
        t = bpy.data.texts.new("loadbalance_panel.py")
        t.write(open(PANEL, encoding="utf-8").read())
    except Exception as e:
        print("embed", e)
    try:
        t = bpy.data.texts.new("a320_data.py")
        t.write(open(DATA, encoding="utf-8").read())
    except Exception as e:
        print("embed data", e)

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

    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT, "MAC%", round(res["mac"], 2), "CG", round(res["cg"], 3))

    # 预览
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
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

    shot("v4_overview.png", (55, -42, 24), (math.radians(62), 0, math.radians(52)))
    shot("v4_side.png", (8, -58, 6), (math.radians(88), 0, math.radians(2)))
    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"] + o["gx"], o["ay"] + o["gy"], o["az"] + o["gz"])
    shot("v4_explode.png", (48, -40, 30), (math.radians(55), 0, math.radians(50)))
    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"], o["ay"], o["az"])
    shot("v4_panel.png", (14, -38, 3.5), (math.radians(82), 0, math.radians(6)))
    shot("v4_mac.png", (28, -30, 12), (math.radians(68), 0, math.radians(40)))
    shot("v4_top.png", (5, -2, 55), (0, 0, math.radians(2)))

    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"], o["ay"], o["az"])
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("DONE v4")


if __name__ == "__main__":
    build()

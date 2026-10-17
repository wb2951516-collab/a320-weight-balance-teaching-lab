"""
配载平衡教学模型 v6 — A320 外形 + LOPA 座椅阵列 + 货舱 + 零件 + 可操控面板
"""
import bpy, math, os, sys, importlib.util, bmesh

ROOT_DIR = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模"
OUT = os.path.join(ROOT_DIR, "output", "配载平衡教学模型.blend")
PANEL = os.path.join(ROOT_DIR, "scripts", "loadbalance_panel.py")
DATA = os.path.join(ROOT_DIR, "scripts", "a320_data.py")
PREVIEW = os.path.join(ROOT_DIR, "output", "preview")
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
import a320_data as D


def reset():
    try:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
    except Exception:
        pass
    for bl in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
               bpy.data.cameras, bpy.data.lights, bpy.data.worlds, bpy.data.actions):
        for b in list(bl):
            try:
                bl.remove(b)
            except Exception:
                pass
    for h in list(bpy.app.handlers.load_post):
        try:
            bpy.app.handlers.load_post.remove(h)
        except Exception:
            pass


def mkmat(name, color, metal=0.0, rough=0.4, alpha=1.0, emis=None, estr=0):
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


def cyl(name, r, depth, loc, material, root, rot=(0, 0, 0), verts=20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(material)
    par(o, root)
    return o


def text(name, body, loc, size, material, root, align="LEFT"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.extrude = 0.005
    o = bpy.data.objects.new(name, cu)
    o.location = loc
    o.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.collection.objects.link(o)
    cu.materials.append(material)
    par(o, root)
    return o


def wing_slab(name, le_root_st, root_chord, tip_chord, y0, y1, z_root,
              sweep_tan, dihedral_tan, t0, t1, mat, root):
    ay = abs(y1)
    le_r, te_r = le_root_st, le_root_st + root_chord
    le_t = le_root_st + sweep_tan * ay
    te_t = le_t + tip_chord
    z1 = z_root + dihedral_tan * ay

    def pt(st, y, z):
        return (D.sx(st), y, z)

    verts = [
        pt(le_r, y0, z_root + t0 / 2), pt(te_r, y0, z_root + t0 / 2),
        pt(te_t, y1, z1 + t1 / 2), pt(le_t, y1, z1 + t1 / 2),
        pt(le_r, y0, z_root - t0 / 2), pt(te_r, y0, z_root - t0 / 2),
        pt(te_t, y1, z1 - t1 / 2), pt(le_t, y1, z1 - t1 / 2),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 3, 7, 4), (2, 1, 5, 6), (1, 0, 4, 5), (3, 2, 6, 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free(); me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
    par(o, root)
    return o


def build_fuselage(mat, root):
    r0 = D.FUS_DIA / 2.0
    sections = [
        (0.00, 0.12, 0.05), (0.35, 0.55, 0.02), (0.90, 1.05, 0.00),
        (1.60, 1.45, 0.00), (2.40, 1.72, 0.00), (3.30, 1.88, 0.00),
        (4.40, 1.96, 0.00), (5.60, r0, 0.00), (8.00, r0, 0.00),
        (12.0, r0, 0.00), (16.0, r0, 0.00), (20.0, r0, 0.00),
        (24.0, r0, 0.00), (27.0, r0, 0.00), (29.0, r0, 0.05),
        (30.5, r0, 0.15), (32.0, 1.92, 0.30), (33.3, 1.78, 0.45),
        (34.4, 1.55, 0.62), (35.3, 1.25, 0.78), (36.1, 0.90, 0.92),
        (36.8, 0.55, 1.05), (37.3, 0.28, 1.12), (37.57, 0.08, 1.15),
    ]
    segs = 28

    def loft(name, ang0, ang1, n_ang):
        """按角度范围 loft（0=顶，π=底）。"""
        verts, faces = [], []
        for st, r, zc in sections:
            x = D.sx(st)
            for i in range(n_ang + 1):
                a = ang0 + (ang1 - ang0) * i / n_ang
                verts.append((x, r * math.sin(a), zc + r * math.cos(a)))
        cols = n_ang + 1
        n = len(sections)
        for s in range(n - 1):
            for i in range(n_ang):
                faces.append((
                    s * cols + i, s * cols + i + 1,
                    (s + 1) * cols + i + 1, (s + 1) * cols + i,
                ))
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update()
        o = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(o)
        o.data.materials.append(mat)
        for p in me.polygons:
            p.use_smooth = True
        try:
            md = o.modifiers.new("Subsurf", "SUBSURF")
            md.levels = 1
            md.render_levels = 1
        except Exception:
            pass
        par(o, root)
        return o

    # 下/侧壳常显；上盖可剖切隐藏
    loft("Fuselage", 0.15 * math.pi, 1.85 * math.pi, 20)
    upper = loft("Shell_Upper", -0.15 * math.pi, 0.15 * math.pi, 8)
    upper["role"] = "cutaway_shell"


def build_exterior(M, root):
    span_half = D.WINGSPAN / 2.0
    sweep_tan = math.tan(math.radians(D.WING_SWEEP_DEG))
    dih_tan = math.tan(math.radians(D.WING_DIHEDRAL_DEG))
    le_root = 16.45
    z_root = -1.70
    y_break = span_half * 0.52

    for side, nm in ((1, "Wing_R"), (-1, "Wing_L")):
        c_b = 7.0 + (1.6 - 7.0) * (y_break / span_half)
        wing_slab(nm + "_inner", le_root, 7.0, c_b, side * 1.1, side * y_break, z_root,
                  sweep_tan, dih_tan, 0.38, 0.22, M["wing"], root)
        le_b = le_root + sweep_tan * y_break
        wing_slab(nm + "_outer", le_b, c_b, 1.6, side * y_break, side * span_half,
                  z_root + dih_tan * y_break, sweep_tan, dih_tan, 0.22, 0.10, M["wing"], root)
        le_t = le_root + sweep_tan * span_half
        z_t = z_root + dih_tan * span_half
        f = box(f"Fence_{nm}", 0.85, 0.10, 1.2,
                (D.sx(le_t + 0.45), side * (span_half + 0.05), z_t + 0.55),
                M["blue"], root, 0.02)
        f.rotation_euler = (0, math.radians(-10), math.radians(side * 15))

    # 平尾后掠 32°
    for side, nm in ((1, "HS_R"), (-1, "HS_L")):
        wing_slab(nm, 30.2, 2.8, 1.3, side * 0.3, side * 6.2, 1.35,
                  math.tan(math.radians(32)), math.tan(math.radians(4)),
                  0.18, 0.10, M["solid"], root)
    # 垂尾
    le_st, root_c, tip_c, z0, z1 = 29.0, 4.2, 1.8, 1.2, 5.0
    st_sweep = math.tan(math.radians(35))
    h = z1 - z0
    le_t = le_st + st_sweep * h
    te_t = le_t + tip_c
    t = 0.16

    def pt(st, z):
        return (D.sx(st), 0.0, z)

    verts = [
        pt(le_st, z0 + t / 2), pt(le_st + root_c, z0 + t / 2),
        pt(te_t, z1 + t / 2), pt(le_t, z1 + t / 2),
        pt(le_st, z0 - t / 2), pt(le_st + root_c, z0 - t / 2),
        pt(te_t, z1 - t / 2), pt(le_t, z1 - t / 2),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 3, 7, 4), (2, 1, 5, 6), (1, 0, 4, 5), (3, 2, 6, 7)]
    me = bpy.data.meshes.new("VS")
    me.from_pydata(verts, [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free(); me.update()
    vs = bpy.data.objects.new("VS", me)
    bpy.context.collection.objects.link(vs)
    vs.data.materials.append(M["solid"])
    par(vs, root)
    box("VS_Dorsal", 4.0, 0.12, 0.55, (D.sx(26.5), 0, 1.75), M["solid"], root, 0.03,
        rot=(0, math.radians(8), 0))
    box("Logo_Tail", 2.0, 0.18, 1.5, (D.sx(32.6), 0, 3.3), M["blue"], root, 0.03,
        rot=(0, math.radians(-35), 0))

    # 发动机
    eng_r, eng_y, eng_st, eng_z = 0.88, 5.55, 14.8, -1.90
    for side, nm in ((-1, "E_L"), (1, "E_R")):
        loc = (D.sx(eng_st), side * eng_y, eng_z)
        cyl(nm, eng_r, 3.8, loc, M["eng"], root, rot=(0, math.radians(90), 0), verts=32)
        cyl(nm + "N", eng_r * 1.08, 0.4, (loc[0] + 1.75, loc[1], loc[2]), M["white"],
            root, rot=(0, math.radians(90), 0), verts=32)
        bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=eng_r * 0.55, radius2=eng_r * 0.32,
                                        depth=0.9, location=(loc[0] - 2.1, loc[1], loc[2]),
                                        rotation=(0, math.radians(-90), 0))
        o = bpy.context.active_object; o.name = nm + "X"
        o.data.materials.append(M["eng"]); par(o, root)
        box(nm + "P", 1.8, 0.28, 1.0, (loc[0] + 0.3, loc[1] * 0.88, loc[2] + 1.0),
            M["solid"], root, 0.03)

    # 起落架
    nose_x = D.sx(3.5)
    main_x = D.sx(3.5 + D.WHEELBASE)
    cyl("GN", 0.30, 1.4, (nose_x, 0, -2.55), M["gear"], root)
    cyl("GWN", 0.36, 0.24, (nose_x, 0, -2.9), M["gear"], root, rot=(math.radians(90), 0, 0))
    for side in (-1, 1):
        cyl(f"GM{side}", 0.40, 1.5, (main_x, side * D.MAIN_TRACK / 2, -2.65), M["gear"], root)
        for k in (-1, 1):
            cyl(f"GW{side}{k}", 0.45, 0.22,
                (main_x, side * D.MAIN_TRACK / 2 + k * 0.28, -2.95),
                M["gear"], root, rot=(math.radians(90), 0, 0))

    # 舱门 / 风挡 / 腰线
    glass = M["glass"]
    box("CockpitGlass", 1.5, 1.75, 0.55, (D.sx(2.85), 0, 1.0), glass, root, 0.1)
    for st, side, tag in ((7.8, -1, "L1"), (7.8, 1, "R1"), (27.2, -1, "L2"), (27.2, 1, "R2"),
                          (33.0, -1, "L3"), (33.0, 1, "R3")):
        box(f"Door_{tag}", 0.95, 0.06, 1.75, (D.sx(st), side * 1.97, 0.35), M["white"], root, 0.04)
        box(f"Door_{tag}F", 0.78, 0.04, 1.55, (D.sx(st), side * 2.0, 0.35), M["blue"], root, 0.03)
    for st, tag in ((11.5, "C1"), (24.5, "C3")):
        # A320 货舱门在右侧（+Y）
        box(f"Door_{tag}", 1.7, 0.05, 1.15, (D.sx(st), 1.90, -0.95), M["dark"], root, 0.03)
    for side in (-1, 1):
        box(f"Stripe_{side}", 24.0, 0.06, 0.20, (D.sx(18.0), side * 1.96, 0.55), M["blue"], root, 0.01)
    # 舷窗点
    for side in (-1, 1):
        for i in range(24):
            st = 8.5 + i * 0.9
            if st > 31:
                break
            cyl(f"Win_{side}_{i}", 0.08, 0.05, (D.sx(st), side * 1.99, 0.88), glass,
                root, rot=(math.radians(90), 0, 0), verts=10)

    # 地板
    box("CabinFloor", 22.0, 3.3, 0.08, (D.sx(18.0), 0, 0.40), M["floor"], root, 0.02)
    box("CargoFloor", 18.0, 3.1, 0.06, (D.sx(20.0), 0, -1.45), M["hull"], root, 0.02)
    box("BellyFairing", 11.0, 3.0, 0.85, (D.sx(18.5), 0, -1.95), M["hull"], root, 0.2)


def build_seats_cargo(M, root):
    """LOPA 3+3 座椅 + 货舱货块，带爆炸偏移。"""
    payload = {}
    seat_mats = {"FWD": M["paxF"], "MID": M["paxM"], "AFT": M["paxA"]}

    for zid, z in D.ZONES.items():
        r0, r1 = z["rows"]
        mat = seat_mats[zid]
        objs = []
        for r in range(r0, r1 + 1):
            st = z["row0_st"] + (r - r0) * D.SEAT_PITCH
            x = D.sx(st)
            for c, y in enumerate(D.SEAT_COLS):
                # 座椅：座垫+靠背
                # 机头 +X：旅客朝前，靠背在机尾侧（x 更小）
                o = box(f"Seat_{zid}_{r}_{c}", 0.48, 0.42, 0.28, (x + 0.08, y, 0.62), mat, root, 0.03)
                o["zone"] = zid
                o["row"] = r
                objs.append(o)
                b = box(f"SeatB_{zid}_{r}_{c}", 0.10, 0.42, 0.62, (x - 0.18, y, 0.98), mat, root, 0.03)
                # 头枕
                h = box(f"SeatH_{zid}_{r}_{c}", 0.08, 0.28, 0.18, (x - 0.20, y, 1.35), mat, root, 0.02)
                for child in (b, h):
                    child.parent = o
                    child.matrix_parent_inverse = o.matrix_world.inverted()
        # 区标签
        lab = text(f"T_Zone_{zid}", f"{z['label']} 排{r0}-{r1}",
                   (D.sx(z["row0_st"]) - 0.5, 0, 2.0), 0.28, mat, root)
        objs.append(lab)
        off = {"FWD": (0, 0, 4.8), "MID": (0, 0, 5.4), "AFT": (0, 0, 4.8)}[zid]
        for o in objs:
            o["gx"], o["gy"], o["gz"] = off
            o["ax"], o["ay"], o["az"] = o.location.x, o.location.y, o.location.z
            o["group"] = f"PAX_{zid}"
        payload[f"PAX_{zid}"] = objs

    # 行李（随前/后货舱）
    for zid, st0, st1, g in (("FWD", 11.0, 14.5, "BAG_FWD"), ("AFT", 22.5, 26.5, "BAG_AFT")):
        objs = []
        for i in range(4):
            st = st0 + (st1 - st0) * (i + 0.5) / 4
            for y in (-0.55, 0.55):
                o = box(f"Bag_{zid}_{i}_{int(y*100)}", 0.5, 0.35, 0.28,
                        (D.sx(st), y, -0.75), M["bag"], root, 0.02)
                objs.append(o)
        off = (0, 2.5, -4.2) if zid == "FWD" else (0, 2.5, -4.2)
        for o in objs:
            o["gx"], o["gy"], o["gz"] = off
            o["ax"], o["ay"], o["az"] = o.location
            o["group"] = g

    # 货舱货块（4 块/舱，按重量显示）
    for cid, st0, st1, mm in (
        ("FWD", 11.2, 14.6, M["cF"]),
        ("AFT", 22.8, 26.4, M["cA"]),
        ("BULK", 27.6, 30.0, M["cB"]),
    ):
        objs = []
        z = D.CARGO[cid]["z"]
        for i in range(4):
            st = st0 + (st1 - st0) * (i + 0.5) / 4
            o = box(f"Box_{cid}_{i}", 0.75, 1.4, 0.55, (D.sx(st), 0, z), mm, root, 0.03)
            objs.append(o)
        off = {"FWD": (0, 3.5, -5.5), "AFT": (0, 3.5, -5.5), "BULK": (0, 4.0, -6.0)}[cid]
        for o in objs:
            o["gx"], o["gy"], o["gz"] = off
            o["ax"], o["ay"], o["az"] = o.location
            o["group"] = f"CARGO_{cid}"

    # 燃油
    wing_x = D.sx(D.WING_SPAR_ST)
    for side, nm in ((-1, "FWL"), (1, "FWR")):
        o = box(f"FW_{side}", 4.0, 5.2, 0.22, (wing_x, side * 4.8, -1.45), M["fW"], root, 0.03)
        o["gx"], o["gy"], o["gz"] = (0, side * 8.5, 0.0)
        o["ax"], o["ay"], o["az"] = o.location
        o["group"] = "FUEL_WING"
    o = box("FC", 2.6, 1.6, 0.25, (D.sx(D.CTR_TANK_ST), 0, -1.0), M["fC"], root, 0.03)
    o["gx"], o["gy"], o["gz"] = (0, 0, -3.5)
    o["ax"], o["ay"], o["az"] = o.location
    o["group"] = "FUEL_CTR"

    # 外部零件爆炸（发动机/起落架/尾翼）
    for name, off in (
        ("E_L", (0, -5.5, -1.2)), ("E_R", (0, 5.5, -1.2)),
        ("GN", (1.5, 0, -3.2)), ("GM-1", (0, -4.0, -3.2)), ("GM1", (0, 4.0, -3.2)),
        ("HS_L", (-4.5, -3.5, 2.2)), ("HS_R", (-4.5, 3.5, 2.2)), ("VS", (-5.5, 0, 3.2)),
        ("E_LN", (0, -5.5, -1.2)), ("E_RN", (0, 5.5, -1.2)),
        ("E_LX", (0, -5.5, -1.2)), ("E_RX", (0, 5.5, -1.2)),
        ("E_LP", (0, -5.5, -1.2)), ("E_RP", (0, 5.5, -1.2)),
    ):
        o = bpy.data.objects.get(name)
        if o:
            o["gx"], o["gy"], o["gz"] = off
            o["ax"], o["ay"], o["az"] = o.location
            o["group"] = "PART_" + name


def build():
    reset()
    os.makedirs(PREVIEW, exist_ok=True)
    M = {
        "hull": mkmat("M_Hull", (0.97, 0.98, 1.0), 0.15, 0.20, alpha=1.0),
        "solid": mkmat("M_Solid", (0.70, 0.74, 0.82), 0.45, 0.28),
        "wing": mkmat("M_Wing", (0.78, 0.82, 0.88), 0.50, 0.22, alpha=1.0),
        "eng": mkmat("M_Eng", (0.18, 0.19, 0.22), 0.75, 0.22),
        "gear": mkmat("M_Gear", (0.10, 0.10, 0.12), 0.4, 0.35),
        "white": mkmat("M_PaintWhite", (0.97, 0.98, 1.0), 0.15, 0.18),
        "blue": mkmat("M_PaintBlue", (0.04, 0.16, 0.42), 0.35, 0.22),
        "glass": mkmat("M_Glass", (0.05, 0.12, 0.20), 0.55, 0.08, alpha=0.95),
        "dark": mkmat("M_Dark", (0.08, 0.08, 0.10), 0.5, 0.28),
        "floor": mkmat("M_Floor2", (0.25, 0.28, 0.32), 0.1, 0.55),
        "paxF": mkmat("M_pF", D.ZONES["FWD"]["color"], 0, 0.5),
        "paxM": mkmat("M_pM", D.ZONES["MID"]["color"], 0, 0.5),
        "paxA": mkmat("M_pA", D.ZONES["AFT"]["color"], 0, 0.5),
        "cF": mkmat("M_cF", D.CARGO["FWD"]["color"], 0, 0.45),
        "cA": mkmat("M_cA", D.CARGO["AFT"]["color"], 0, 0.45),
        "cB": mkmat("M_cB", D.CARGO["BULK"]["color"], 0, 0.45),
        "bag": mkmat("M_Bag", (0.55, 0.4, 0.28), 0, 0.7),
        "fW": mkmat("M_fW", (0.25, 0.8, 0.5), 0, 0.3, alpha=0.4),
        "fC": mkmat("M_fC", (0.2, 0.6, 0.9), 0, 0.3, alpha=0.4),
        "mac": mkmat("M_MAC", (0.25, 0.95, 1), emis=(0.2, 0.85, 1), estr=2),
        "cg": mkmat("M_CG", (1, 0.3, 0.25), emis=(1, 0.25, 0.2), estr=2.5),
        "datum": mkmat("M_Dat", (1, 0.88, 0.2), emis=(1, 0.8, 0.15), estr=1.2),
        "limit": mkmat("M_Lim", (1, 0.55, 0.15), emis=(1, 0.45, 0.1), estr=1),
        "green": mkmat("M_Gr", (0.2, 0.9, 0.45), emis=(0.15, 0.8, 0.4), estr=1.2),
        "red": mkmat("M_Rd", (1, 0.25, 0.2), emis=(1, 0.2, 0.15), estr=1.5),
        "whiteUI": mkmat("M_Wh", (0.95, 0.97, 1), emis=(1, 1, 1), estr=0.8),
        "yellow": mkmat("M_Ye", (1, 0.85, 0.2), emis=(1, 0.8, 0.15), estr=1),
        "panel": mkmat("M_Pn", (0.06, 0.08, 0.12), 0, 0.45),
        "ground": mkmat("M_Gnd", (0.12, 0.13, 0.16), 0, 0.9),
        "band": mkmat("M_Bd", (0.2, 0.85, 0.45), emis=(0.15, 0.7, 0.35), estr=0.8),
    }

    root = bpy.data.objects.new("AC_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 1.5
    bpy.context.collection.objects.link(root)

    build_fuselage(M["hull"], root)
    build_exterior(M, root)
    box("Ground", 100, 70, 0.1, (0, 0, -3.3), M["ground"], root, 0)
    build_seats_cargo(M, root)

    # DATUM / MAC
    dx = D.sx(0.0)
    box("DatumBar", 0.08, 0.08, 8.5, (dx, 0, 1.2), M["datum"], root, 0)
    text("T_Dat", "DATUM 机头 FS=0", (dx + 0.2, 0, 5.2), 0.38, M["datum"], root)
    le, te = D.sx(D.LEMAC_ST), D.sx(D.TEMAC_ST)
    my = 4.4
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
    # 横向 CG y 标尺（机腹侧，左负右正）
    y_bar_x = D.sx(18.0)
    box("YRuler", 0.08, 1.6, 0.08, (y_bar_x, 0, -2.55), M["yellow"], root, 0.01)
    for yi, lab in ((-0.5, "-0.5"), (0.0, "0"), (0.5, "+0.5")):
        box(f"YTick_{lab}", 0.12, 0.06, 0.18, (y_bar_x, yi * 1.6 / 0.5 * 0.5, -2.55), M["limit"], root, 0)
        text(f"TY_{lab}", lab, (y_bar_x + 0.15, yi, -2.2), 0.18, M["limit"], root)
    text("T_YRuler", "横向CG y (左负右正)", (y_bar_x - 1.2, 0, -2.0), 0.22, M["yellow"], root)
    # y 指针
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.28, depth=0.45,
                                    location=(y_bar_x, 0, -2.85),
                                    rotation=(math.radians(-90), 0, 0))
    yptr = bpy.context.active_object
    yptr.name = "YPointer"
    yptr.data.materials.append(M["cg"])
    par(yptr, root)
    text("TY_cur", "y=+0.00", (y_bar_x + 0.3, 0, -3.15), 0.20, M["cg"], root)
    text("TY_lim", "限 ±0.35 m", (y_bar_x + 0.3, 0, -3.45), 0.18, M["whiteUI"], root)

    res = D.compute()
    cgx = D.sx(res["cg"])
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.5, depth=0.9,
                                    location=(cgx, 0, 2.8), rotation=(math.radians(180), 0, 0))
    cone = bpy.context.active_object; cone.name = "CGCone"
    cone.data.materials.append(M["cg"]); par(cone, root)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=5.5, location=(cgx, 0, 0.2))
    line = bpy.context.active_object; line.name = "CGLine"
    line.data.materials.append(M["cg"]); par(line, root)
    empty = bpy.data.objects.new("CG_Empty", None)
    empty.location = (cgx, 0, 0)
    empty.empty_display_type = "ARROWS"
    empty.empty_display_size = 1.0
    bpy.context.collection.objects.link(empty); par(empty, root)
    text("UI_DYN", f"CG={res['cg']:.2f}  %MAC={res['mac']:.1f}%",
         (cgx + 0.3, 0.8, 3.4), 0.26, M["cg"], root)

    # 浮动 HUD 文字（无大墙）：放在机腹侧前方，薄半透明衬底
    hud_bg = mkmat("M_HUD", (0.04, 0.06, 0.10), 0.0, 0.5, alpha=0.55)
    box("HUD_BG", 9.8, 0.06, 5.2, (10.5, -14.5, 2.8), hud_bg, root, 0.04)
    py = -14.55
    lines = [
        ("Title", "A320 配载平衡", (6.2, py, 5.0), 0.38, M["whiteUI"]),
        ("Src", "ACAP · WBM · LOPA 3+3", (6.2, py, 4.45), 0.24, M["mac"]),
        ("W", f"TOW {res['tow']:.0f} kg", (6.2, py, 3.9), 0.28, M["whiteUI"]),
        ("M", f"力矩 {res['moment']:.0f} kg·m", (6.2, py, 3.4), 0.24, M["whiteUI"]),
        ("CG", f"CG FS {res['cg']:.2f} m", (6.2, py, 2.9), 0.26, M["green"]),
        ("MAC", f"%MAC {res['mac']:.1f}%  {res['pitch']}", (6.2, py, 2.4), 0.28, M["cg"]),
        ("Y", f"y={res['cg_y']:+.2f} m  {res['roll']}", (6.2, py, 1.9), 0.24, M["whiteUI"]),
        ("ZFW", f"ZFW {res['zfw']:.0f}  油差 {res['fuel_imb']:.0f}", (6.2, py, 1.4), 0.22, M["whiteUI"]),
        ("TRIM", res["trim_pitch"], (6.2, py, 0.9), 0.22, M["yellow"]),
        ("PAX", f"旅客 {res['pax']}", (6.2, py, 0.4), 0.22, M["whiteUI"]),
        ("F1", f"CG = ΣM/ΣW = {res['cg']:.3f} m", (6.2, py, -0.1), 0.20, M["yellow"]),
        ("F2", f"%MAC = (CG-LE)/MAC×100 = {res['mac']:.2f}%", (6.2, py, -0.5), 0.20, M["mac"]),
        ("F3", f"y = Σ(W·yi)/ΣW = {res['cg_y']:+.4f} m", (6.2, py, -0.9), 0.20, M["yellow"]),
    ]
    for k, body, loc, size, mm in lines:
        text(f"UI_{k}", body, loc, size, mm, root)

    # 场景属性
    sc = bpy.context.scene
    for z, n in D.INIT_PAX.items():
        sc[f"pax_{z}"] = n
    for c, kg in D.INIT_CARGO.items():
        sc[f"cargo_{c}"] = kg
    for f, kg in D.INIT_FUEL.items():
        sc[f"fuel_{f}"] = kg
    sc.frame_start = 1
    sc.frame_end = 120

    # 相机灯光
    bpy.ops.object.camera_add(location=(48, -38, 16), rotation=(math.radians(68), 0, math.radians(52)))
    cam = bpy.context.active_object; cam.name = "TeachCam"; cam.data.lens = 45
    cam.data.dof.use_dof = False
    sc.camera = cam
    # 三点布光
    bpy.ops.object.light_add(type="SUN", location=(20, -10, 40))
    sun = bpy.context.active_object
    sun.data.energy = 5.0
    sun.data.angle = math.radians(2.5)
    sun.rotation_euler = (math.radians(42), math.radians(18), math.radians(-28))
    bpy.ops.object.light_add(type="AREA", location=(-15, -25, 18))
    fill = bpy.context.active_object
    fill.data.energy = 1400
    fill.data.size = 35
    fill.rotation_euler = (math.radians(55), 0, math.radians(-40))
    bpy.ops.object.light_add(type="AREA", location=(5, 30, 22))
    rim = bpy.context.active_object
    rim.data.energy = 900
    rim.data.size = 30
    rim.rotation_euler = (math.radians(-50), 0, math.radians(160))
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.35, 0.42, 0.55, 1)
        bg.inputs[1].default_value = 1.1
    # EEVEE 写实向
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        sc.render.engine = "BLENDER_EEVEE"
    ee = getattr(sc, "eevee", None)
    if ee:
        for attr, val in (
            ("use_raytracing", True),
            ("use_shadows", True),
            ("use_volumetric_lights", False),
            ("use_bloom", True),
            ("bloom_intensity", 0.08),
            ("use_gtao", True),
            ("gtao_distance", 12),
            ("gtao_factor", 1.2),
            ("use_ssr", True),
            ("use_ssr_refraction", True),
            ("taa_render_samples", 64),
        ):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except Exception:
                    pass

    # 面板
    try:
        spec = importlib.util.spec_from_file_location("lbp", PANEL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
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
        t = bpy.data.texts.new("a320_data.py")
        t.write(open(DATA, encoding="utf-8").read())
    except Exception as e:
        print("embed", e)

    def _boot(*a):
        try:
            t = bpy.data.texts.get("loadbalance_panel.py")
            if t:
                mod = t.as_module()
                if hasattr(mod, "register"):
                    try:
                        if hasattr(mod, "unregister"):
                            mod.unregister()
                    except Exception:
                        pass
                    mod.register()
                    print("panel boot registered")
        except Exception as e:
            print("panel boot fail", e)
    # 先立即注册一次
    try:
        _boot()
    except Exception:
        pass
    if _boot not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_boot)

    # 初始点亮
    try:
        bpy.ops.blendlb.refresh()
    except Exception as e:
        print("refresh", e)

    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("saved", OUT, "seats", sum(1 for o in bpy.data.objects if o.name.startswith("Seat_")))

    # 渲染
    sc.render.resolution_x = 1920
    sc.render.resolution_y = 1080
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False

    def shot(name, loc, rot):
        cam.location = loc
        cam.rotation_euler = rot
        sc.render.filepath = os.path.join(PREVIEW, name)
        bpy.ops.render.render(write_still=True)
        print("shot", name)

    shot("v6_overview.png", (52, -42, 20), (math.radians(64), 0, math.radians(50)))
    shot("v6_side.png", (4, -60, 7), (math.radians(88), 0, 0))
    shot("v6_cabin.png", (8, -18, 8), (math.radians(72), 0, math.radians(15)))
    # 爆炸
    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"] + o["gx"], o["ay"] + o["gy"], o["az"] + o["gz"])
    shot("v6_explode.png", (48, -38, 24), (math.radians(58), 0, math.radians(48)))
    for o in bpy.data.objects:
        if "ax" in o:
            o.location = (o["ax"], o["ay"], o["az"])
    shot("v6_final_quarter.png", (46, -36, 16), (math.radians(66), 0, math.radians(52)))
    cam.location = (48, -38, 18)
    cam.rotation_euler = (math.radians(68), 0, math.radians(52))
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("DONE v6")


if __name__ == "__main__":
    build()

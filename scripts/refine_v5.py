"""
A320 教学模型精修 v5：涂装上色 + 舱门/舷窗/发动机细节 + 尾翼后掠确认
基于 ACAP 图（飞机参考图/_raw/airbus/A320_genDims_p44/45）
在现有 blend 场景上增量精修（可重复执行）。
"""
import bpy, math, bmesh, os

OUT = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
PREVIEW = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"
NOSE_X = 37.57 / 2.0


def sx(st):
    return NOSE_X - st


def mkmat(name, color, metal=0.0, rough=0.4, alpha=1.0, emis=None, estr=0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
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
    if root:
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()


def delete_prefixes(prefixes):
    for o in list(bpy.data.objects):
        if any(o.name.startswith(p) for p in prefixes):
            bpy.data.objects.remove(o, do_unlink=True)


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


def cyl(name, r, depth, loc, material, root, rot=(0, 0, 0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(material)
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
        return (sx(st), y, z)

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


def apply_paint():
    """教学涂装：白机身 + 蓝腰线 + 灰翼面 + 深色发动机。"""
    # 机身：更实的白，略透便于看装载
    hull = bpy.data.materials.get("M_Hull")
    if hull:
        b = next((n for n in hull.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b:
            b.inputs["Base Color"].default_value = (0.92, 0.94, 0.97, 1)
            b.inputs["Roughness"].default_value = 0.28
            b.inputs["Metallic"].default_value = 0.08
            if "Alpha" in b.inputs:
                b.inputs["Alpha"].default_value = 0.48
        try:
            hull.surface_render_method = "BLENDED"
        except Exception:
            pass
    wing = bpy.data.materials.get("M_Wing")
    if wing:
        b = next((n for n in wing.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b:
            b.inputs["Base Color"].default_value = (0.72, 0.76, 0.82, 1)
            b.inputs["Metallic"].default_value = 0.35
            b.inputs["Roughness"].default_value = 0.3
            if "Alpha" in b.inputs:
                b.inputs["Alpha"].default_value = 1.0
    solid = bpy.data.materials.get("M_Solid")
    if solid:
        b = next((n for n in solid.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b:
            b.inputs["Base Color"].default_value = (0.62, 0.68, 0.78, 1)
    eng = bpy.data.materials.get("M_Eng")
    if eng:
        b = next((n for n in eng.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b:
            b.inputs["Base Color"].default_value = (0.22, 0.24, 0.28, 1)
            b.inputs["Metallic"].default_value = 0.65
            b.inputs["Roughness"].default_value = 0.28


def add_details(root):
    # 清旧细节
    delete_prefixes(("Door_", "Win_", "Stripe_", "APU_", "Nacelle_", "RAT_",
                     "Fence_", "Logo_", "CockpitGlass"))

    white = mkmat("M_PaintWhite", (0.95, 0.96, 0.98), metal=0.05, rough=0.25)
    blue = mkmat("M_PaintBlue", (0.05, 0.18, 0.45), metal=0.15, rough=0.3)
    cyan = mkmat("M_PaintCyan", (0.1, 0.45, 0.7), metal=0.1, rough=0.35)
    glass = mkmat("M_Glass", (0.08, 0.18, 0.28), metal=0.3, rough=0.12, alpha=0.92)
    dark = mkmat("M_Dark", (0.12, 0.12, 0.14), metal=0.4, rough=0.35)

    # 腰线（机身两侧）
    for side in (-1, 1):
        box(f"Stripe_{side}", 24.0, 0.06, 0.22, (sx(18.0), side * 1.96, 0.55),
            blue, root, 0.01)
        # 浅蓝下腹条
        box(f"StripeBelly_{side}", 20.0, 0.05, 0.12, (sx(18.0), side * 1.85, -1.1),
            cyan, root, 0.01)

    # 座舱风挡
    box("CockpitGlass", 1.5, 1.75, 0.55, (sx(2.85), 0, 1.0), glass, root, 0.1)

    # 客舱门（A320：L1/R1 约 FS8，L2/R2 约 FS27，尾门 FS33）
    door_specs = [
        ("Door_L1", 7.8, -1), ("Door_R1", 7.8, 1),
        ("Door_L2", 27.2, -1), ("Door_R2", 27.2, 1),
        ("Door_L3", 33.0, -1), ("Door_R3", 33.0, 1),
    ]
    for name, st, side in door_specs:
        box(name, 0.9, 0.06, 1.7, (sx(st), side * 1.97, 0.35), white, root, 0.04)
        box(name + "F", 0.75, 0.04, 1.5, (sx(st), side * 2.0, 0.35), blue, root, 0.03)

    # 货舱门（前 FS11.5，后 FS24.5 下侧）
    for name, st, side in (("Door_C1", 11.5, -1), ("Door_C3", 24.5, -1)):
        box(name, 1.6, 0.05, 1.1, (sx(st), side * 1.85, -0.9), dark, root, 0.03)

    # 舷窗条（简化：连续细条 + 均分窗点）
    for side in (-1, 1):
        box(f"WinRail_{side}", 22.0, 0.04, 0.08, (sx(18.0), side * 1.97, 0.85),
            dark, root, 0)
        n = 22
        for i in range(n):
            st = 9.0 + i * 0.85
            if st > 30:
                break
            cyl(f"Win_{side}_{i}", 0.09, 0.05, (sx(st), side * 1.99, 0.85),
                glass, root, rot=(math.radians(90), 0, 0), verts=12)

    # APU 排气
    cyl("APU_Nozzle", 0.18, 0.35, (sx(37.3), 0, 1.15), dark, root,
        rot=(0, math.radians(90), 0), verts=16)

    # 翼尖小翼加强（替换旧 fence 若存在）
    span_half = 34.10 / 2.0
    sweep_tan = math.tan(math.radians(25))
    le_root = 16.45
    z_root = -1.70
    dih = math.tan(math.radians(5.1))
    for side, nm in ((-1, "Fence_L"), (1, "Fence_R")):
        le_t = le_root + sweep_tan * span_half
        z_t = z_root + dih * span_half
        o = box(nm, 0.9, 0.10, 1.2,
                (sx(le_t + 0.45), side * (span_half + 0.06), z_t + 0.55),
                blue, root, 0.02)
        o.rotation_euler = (0, math.radians(-10), math.radians(side * 15))

    # 发动机短舱高光环（进气唇口金属环）
    for side, nm in ((-1, "E_L"), (1, "E_R")):
        eng = bpy.data.objects.get(nm)
        if eng:
            loc = eng.location
            cyl(f"Nacelle_{side}", 0.92, 0.18,
                (loc.x + 1.7, loc.y, loc.z), white, root,
                rot=(0, math.radians(90), 0), verts=28)


def rebuild_tail(root, M_solid, M_blue):
    """再确保平尾/垂尾向后展开。"""
    for n in ("HS_L", "HS_R", "VS", "VS_Dorsal"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    hs_le = 30.2
    for side, nm in ((1, "HS_R"), (-1, "HS_L")):
        wing_slab(nm, hs_le, 2.8, 1.3, side * 0.3, side * 6.2, 1.35,
                  math.tan(math.radians(32)), math.tan(math.radians(4)),
                  0.18, 0.10, M_solid, root)

    # 垂尾
    le_st, root_c, tip_c, z0, z1 = 29.0, 4.2, 1.8, 1.2, 5.0
    sweep_tan = math.tan(math.radians(35))
    h = z1 - z0
    le_t = le_st + sweep_tan * h
    te_t = le_t + tip_c
    t = 0.16

    def pt(st, z):
        return (sx(st), 0.0, z)

    verts = [
        pt(le_st, z0 + t / 2), pt(le_st + root_c, z0 + t / 2),
        pt(te_t, z1 + t / 2), pt(le_t, z1 + t / 2),
        pt(le_st, z0 - t / 2), pt(le_st + root_c, z0 - t / 2),
        pt(te_t, z1 - t / 2), pt(le_t, z1 - t / 2),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 3, 7, 4), (2, 1, 5, 6), (1, 0, 4, 5), (3, 2, 6, 7)]
    me = bpy.data.meshes.new("VS")
    me.from_pydata(verts, [], faces)
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free(); me.update()
    vs = bpy.data.objects.new("VS", me)
    bpy.context.collection.objects.link(vs)
    vs.data.materials.append(M_solid)
    par(vs, root)
    # 垂尾蓝色蒙皮条
    box("Logo_Tail", 2.2, 0.18, 1.6, (sx(32.5), 0, 3.4), M_blue, root, 0.03,
        rot=(0, math.radians(-35), 0))
    box("VS_Dorsal", 4.0, 0.12, 0.55, (sx(26.5), 0, 1.75), M_solid, root, 0.03,
        rot=(0, math.radians(8), 0))


def check_tail():
    for nm in ("HS_L", "HS_R"):
        o = bpy.data.objects.get(nm)
        if not o:
            continue
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        root_xs = [p.x for p in pts if abs(p.y) < 1.0]
        tip_xs = [p.x for p in pts if abs(p.y) > 4.0]
        if root_xs and tip_xs:
            print(nm, "tip_aft", sum(tip_xs)/len(tip_xs) < sum(root_xs)/len(root_xs),
                  "dX", round(sum(tip_xs)/len(tip_xs) - sum(root_xs)/len(root_xs), 3))


def main():
    os.makedirs(PREVIEW, exist_ok=True)
    root = bpy.data.objects.get("ROOT")
    M_solid = bpy.data.materials.get("M_Solid") or mkmat("M_Solid", (0.6, 0.65, 0.72))
    M_blue = mkmat("M_PaintBlue", (0.05, 0.18, 0.45), metal=0.15, rough=0.3)

    apply_paint()
    rebuild_tail(root, M_solid, M_blue)
    add_details(root)
    check_tail()

    # 相机与渲染
    sc = bpy.context.scene
    cam = bpy.data.objects.get("TeachCam") or sc.camera
    if cam:
        cam.data.lens = 40
        sc.camera = cam
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 900
    sc.render.image_settings.file_format = "PNG"
    # 环境略亮便于看颜色
    if sc.world and sc.world.use_nodes:
        bg = sc.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.12, 0.14, 0.18, 1)
            bg.inputs[1].default_value = 0.85

    def shot(name, loc, rot):
        if not cam:
            return
        cam.location = loc
        cam.rotation_euler = rot
        sc.render.filepath = os.path.join(PREVIEW, name)
        bpy.ops.render.render(write_still=True)
        print("shot", name)

    shot("v5_overview.png", (52, -40, 20), (math.radians(64), 0, math.radians(50)))
    shot("v5_side.png", (6, -58, 7), (math.radians(88), 0, math.radians(2)))
    shot("v5_top.png", (4, -1, 58), (0, 0, math.radians(2)))
    shot("v5_quarter.png", (45, -28, 14), (math.radians(70), 0, math.radians(58)))
    shot("v5_tail.png", (-30, -25, 12), (math.radians(70), 0, math.radians(-35)))

    # 恢复教学默认视角
    if cam:
        cam.location = (48, -38, 18)
        cam.rotation_euler = (math.radians(68), 0, math.radians(52))

    # 面板刷新
    try:
        bpy.ops.blendlb.refresh()
    except Exception as e:
        print("refresh", e)

    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("SAVED", OUT)


if __name__ == "__main__":
    main()

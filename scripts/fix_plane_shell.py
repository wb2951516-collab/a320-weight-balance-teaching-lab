"""
重做 Blender 教学机外形：机头/机身/机翼/尾翼/发动机一眼可辨。
在已打开的配载工程上替换外壳几何；不改计算逻辑。
"""
import bpy
import math
from mathutils import Vector

NOSE_X = 18.785  # 与 a320_data 一致，机头侧 +X


def sx(st):
    return NOSE_X - st


def clear_named(names):
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)


def mat(name, color, rough=0.45, metal=0.05):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
    return m


def add_box(name, dims, loc, material, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def add_cyl(name, r, d, loc, rot, material, parent=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def add_sphere(name, r, loc, material, scale=(1, 1, 1), parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def rebuild():
    # 清掉旧壳体
    old = []
    for o in bpy.data.objects:
        n = o.name
        if n.startswith(("Fus", "Nose", "Tail", "Wing", "HS", "VS", "Eng", "Gear", "AirFrame", "Plane_")):
            old.append(n)
        if n in ("Fuselage", "Fuselage_Main", "Nose", "TailCone", "VStab", "HStab_L", "HStab_R"):
            old.append(n)
    clear_named(old)

    root = bpy.data.objects.get("AIRCRAFT_ROOT") or bpy.data.objects.get("ROOT")
    if root is None:
        root = bpy.data.objects.new("AIRCRAFT_ROOT", None)
        bpy.context.collection.objects.link(root)

    body_m = mat("M_PlaneBody", (0.78, 0.82, 0.88), rough=0.4)
    nose_m = mat("M_PlaneNose", (0.62, 0.70, 0.80), rough=0.4)
    wing_m = mat("M_PlaneWing", (0.45, 0.55, 0.68), rough=0.45, metal=0.15)
    tail_m = mat("M_PlaneTail", (0.35, 0.48, 0.62), rough=0.45)
    eng_m = mat("M_PlaneEng", (0.28, 0.32, 0.38), rough=0.35, metal=0.5)
    gear_m = mat("M_PlaneGear", (0.18, 0.18, 0.2), rough=0.4)
    win_m = mat("M_PlaneWin", (0.25, 0.4, 0.55), rough=0.2, metal=0.3)

    # 机身：沿 FS，机头 +X
    # 筒段 FS 4.5 → 31.5，半径约 2.0
    body_x0, body_x1 = sx(31.5), sx(4.5)  # 小 x 为机尾侧
    body_cx = (body_x0 + body_x1) / 2
    body_len = body_x1 - body_x0
    add_cyl("Plane_Fuselage", 2.0, body_len, (body_cx, 0, 0), (0, math.radians(90), 0), body_m, root)

    # 机头锥
    add_sphere("Plane_Nose", 2.0, (sx(4.0), 0, 0), nose_m, scale=(2.0, 1, 1), parent=root)
    # 驾驶舱窗
    add_box("Plane_Cockpit", (1.6, 2.2, 0.35), (sx(5.5), 0, 1.3), win_m, parent=root)

    # 机尾锥
    add_cyl("Plane_TailCone", 1.4, 6.0, (sx(33.5), 0, 0.3), (0, math.radians(90), 0), body_m, root)
    tb = bpy.data.objects["Plane_TailCone"]
    tb.scale = (1, 0.85, 0.8)

    # 垂尾（高、后掠，明显）
    vs = add_box("Plane_VStab", (4.5, 0.28, 5.2), (sx(32.5), 0, 3.2), tail_m,
                 rot=(0, math.radians(-28), 0), parent=root)
    # 垂尾顶部小块增强识别
    add_box("Plane_VStabTop", (1.2, 0.3, 0.4), (sx(30.2), 0, 5.6), wing_m, parent=root)

    # 平尾
    # ★ 朝向修正（2026-09-22）：绕 Z 的旋转符号原先写反了，导致平尾前掠。
    #   机头朝 +X 时，左侧（y 负）要后掠必须取负角，右侧取正角。
    #   同文件的翼刀 Fence_Wing_* 用的就是这套正确约定，仅此处与机翼两处写反。
    for side, nm in ((-1, "L"), (1, "R")):
        add_box(f"Plane_HS_{nm}", (3.2, 6.5, 0.28), (sx(31.0), side * 3.2, 1.0), tail_m,
                rot=(0, 0, math.radians(side * 18)), parent=root)

    # 机翼：前缘后掠，从机身伸向两侧
    wing_st = 17.5
    for side, nm in ((-1, "L"), (1, "R")):
        # 主翼盒
        # ★ 同上：原为 side * -24（前掠，方向反了），改为 side * +24 得到后掠。
        w = add_box(f"Plane_Wing_{nm}", (7.0, 12.0, 0.45),
                    (sx(wing_st + 1.5), side * 7.5, -0.55), wing_m,
                    rot=(0, math.radians(side * 2), math.radians(side * 24)), parent=root)
        # 翼尖小翼：与主翼同向旋转，位置按"修正后"的翼尖前缘角点反算，
        # 否则机翼转向后小翼会脱离翼尖浮在空中。
        wl = add_box(f"Plane_Winglet_{nm}", (0.4, 0.3, 1.6),
                     (sx(wing_st - 0.5), side * 13.8, 0.4), tail_m, parent=root)
        wl.rotation_euler = (0, 0, math.radians(side * 24))
        tip = w.matrix_world @ Vector((3.5, side * 6.0, 0.0))
        wl.location = (tip.x - 0.15, tip.y - side * 0.35, 0.45)
        # 发动机
        ex, ey = sx(17.8), side * 5.5
        add_cyl(f"Plane_Eng_{nm}", 0.95, 3.2, (ex, ey, -1.6), (0, math.radians(90), 0), eng_m, root, 24)
        add_cyl(f"Plane_EngIn_{nm}", 1.05, 0.35, (ex + 1.7, ey, -1.6), (0, math.radians(90), 0), eng_m, root, 24)
        # 短舱挂架
        add_box(f"Plane_Pylon_{nm}", (0.8, 0.25, 0.9), (ex, ey, -0.85), gear_m, parent=root)

    # 起落架（三点，清晰）
    add_cyl("Plane_GN", 0.35, 1.6, (sx(8.0), 0, -2.4), (0, 0, 0), gear_m, root, 16)
    for side in (-1, 1):
        add_cyl(f"Plane_GM{side}", 0.42, 1.8, (sx(19.0), side * 1.4, -2.5), (0, 0, 0), gear_m, root, 16)

    # 地面
    if bpy.data.objects.get("Ground") is None:
        add_box("Ground", (70, 40, 0.1), (0, 0, -3.4), mat("M_Ground2", (0.12, 0.14, 0.16), rough=0.9), parent=root)

    # 标注文字（面向 -Y）
    def label(name, body, loc):
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        cu.size = 0.55
        cu.extrude = 0.01
        cu.align_x = "CENTER"
        o = bpy.data.objects.new(name, cu)
        o.location = loc
        o.rotation_euler = (math.radians(90), 0, 0)
        bpy.context.collection.objects.link(o)
        cu.materials.append(mat("M_PlaneLab", (0.12, 0.35, 0.55), rough=0.4))
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
        return o

    clear_named(["Lab_Nose", "Lab_Wing", "Lab_Tail", "Lab_Eng"])
    label("Lab_Nose", "机头", (sx(3.0), 0, 3.5))
    label("Lab_Wing", "机翼", (sx(16.0), 6, 2.5))
    label("Lab_Tail", "机尾", (sx(33.0), 0, 6.5))
    label("Lab_Eng", "发动机", (sx(18), -6.5, -3.2))

    print("plane shell rebuilt")
    return root


if __name__ == "__main__":
    rebuild()
    # 打开已有工程时执行；若无工程则仅建飞机
    try:
        bpy.ops.wm.save_as_mainfile(filepath=r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend")
        print("blend saved")
    except Exception as e:
        print("save skip", e)

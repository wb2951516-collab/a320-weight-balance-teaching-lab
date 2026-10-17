# -*- coding: utf-8 -*-
"""
Stage 2 · 外形重建（参数化）
=============================

解决的问题
----------
原模型里机翼/平尾/垂尾不是"翼面"，而是 **add_box 造的长方体绕轴旋转**：

    Plane_Wing_L: dims(7.0,12.0,0.45) rot=(0,-2,+24)
    Plane_HS_L  : dims(3.2, 6.5,0.28) rot=(0, 0,+18)
    Plane_VStab : dims(4.5, 0.28,5.2) rot=(0,-28, 0)

旋转长方体在俯视图里必然是**平行四边形**：翼根弦线不垂直于机身。因此即使把
旋转符号改对（数值上后掠了），看上去仍然"方向不对"。改符号治不了这个病。

本脚本改为**按实机参数生成梯形翼面**（前缘后掠、根弦粗尖弦细、带上反角）：

    平面形状 4 个角点 → 沿厚度方向挤出成棱柱，厚度从根到尖收薄
    ┌──────────┐ 翼根弦（垂直于机身）
    │＼         │
    │  ＼       │   前缘后掠
    │    ＼─────┤ 翼尖弦
    └──────────┘

参数全部取自 scripts/a320_data.py（唯一数据源），因此**换机型只需改数字**。

另外两件事
----------
1. 客舱座位补到 31 排（真实 186Y = 31×6），并延长客舱地板覆盖新排。
2. 移除 WING_FENCE（翼刀）——原位置（x≈-6，跨全展向）在新机翼上已无对应几何。

由 stage1_export.py 调用；源 .blend 只读，绝不覆盖。
"""
import bpy
import bmesh
import math
import sys
import os
from mathutils import Vector

SP = os.path.dirname(os.path.abspath(__file__))
if SP not in sys.path:
    sys.path.insert(0, SP)
import a320_data as D


# ---------------------------------------------------------------------------
# 通用：按 4 个平面角点 + 根/尖厚度，生成梯形棱柱
# ---------------------------------------------------------------------------
def tapered_slab(name, le_root, te_root, le_tip, te_tip, t_root, t_tip,
                 thick_axis, material, parent):
    """thick_axis: 'z' = 厚度沿竖直（机翼/平尾）；'y' = 厚度沿横向（垂尾）"""
    up = Vector((0.0, 0.0, 1.0)) if thick_axis == 'z' else Vector((0.0, 1.0, 0.0))
    hr, ht = t_root * 0.5, t_tip * 0.5

    verts = [
        le_root + up * hr, le_root - up * hr,      # 0,1 根前缘 上/下
        te_root + up * hr, te_root - up * hr,      # 2,3 根后缘 上/下
        le_tip + up * ht,  le_tip - up * ht,       # 4,5 尖前缘 上/下
        te_tip + up * ht,  te_tip - up * ht,       # 6,7 尖后缘 上/下
    ]
    faces = [
        (0, 2, 6, 4),   # 上表面
        (1, 5, 7, 3),   # 下表面
        (0, 4, 5, 1),   # 前缘面
        (2, 3, 7, 6),   # 后缘面
        (0, 1, 3, 2),   # 根部端面
        (4, 6, 7, 5),   # 尖部端面
    ]

    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    me.update()

    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()

    # 法线统一朝外：梯形棱柱手工写面容易有内外面混用，
    # 必须重算（否则剖切/双面渲染会看着发黑）。
    # 用 bmesh 而**不用 bpy.ops**：ops 依赖 GUI 上下文，在 Blender MCP 远程调用
    # 与"open_mainfile 之后同一段代码里继续执行"两种情形下会抛
    # `mode_set.poll() 上下文缺失活动物体`（2026-09-22 实际踩过两次）。
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return o


def mat_of(name, fallback=(0.6, 0.65, 0.72)):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*fallback, 1)
    return m


def drop(names):
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def rebuild(verbose=print):
    NX = D.NOSE_X
    root = bpy.data.objects.get("AIRCRAFT_ROOT")

    wing_m = mat_of("M_PlaneWing", (0.45, 0.55, 0.68))
    tail_m = mat_of("M_PlaneTail", (0.35, 0.48, 0.62))
    body_m = mat_of("M_PlaneBody", (0.78, 0.82, 0.88))

    # ---------------- 机翼 ----------------
    # 根弦 5.6 / 尖弦 1.6 → 平均弦 3.6 × 展长 34.10 ≈ 122.8 m²（a320_data.WING_AREA = 122.6）
    CR, CT = 5.6, 1.6
    HALF = D.WINGSPAN / 2.0                    # 17.05
    Y_ROOT = D.FUS_DIA / 2.0                   # 1.98
    sweep = math.radians(D.WING_SWEEP_DEG)     # 25°
    dihed = math.radians(D.WING_DIHEDRAL_DEG)  # 5.1°
    span = HALF - Y_ROOT

    wing_root_le_x = D.sx(D.WING_ROOT_LE_ST)   # 前缘站位 14.80 → x
    z_root = -0.55
    dy = HALF - Y_ROOT
    tip_le_x = wing_root_le_x - dy * math.tan(sweep)
    z_tip = z_root + dy * math.tan(dihed)

    drop(["Plane_Wing_L", "Plane_Wing_R"])
    wings = {}
    for side, nm in ((-1, "L"), (1, "R")):
        y_r, y_t = side * Y_ROOT, side * HALF
        o = tapered_slab(
            f"Plane_Wing_{nm}",
            Vector((wing_root_le_x, y_r, z_root)),
            Vector((wing_root_le_x - CR, y_r, z_root)),
            Vector((tip_le_x, y_t, z_tip)),
            Vector((tip_le_x - CT, y_t, z_tip)),
            0.78, 0.18, 'z', wing_m, root)
        wings[nm] = o
        verbose("   机翼 %s: 根弦 %.2f 尖弦 %.2f 后掠 %.1f° 上反 %.1f° 展长 %.2f"
                % (nm, CR, CT, D.WING_SWEEP_DEG, D.WING_DIHEDRAL_DEG, dy))

    # 翼尖小翼：吸附到新翼尖前缘，同向后掠，竖直小翼
    drop(["Plane_Winglet_L", "Plane_Winglet_R"])
    for side, nm in ((-1, "L"), (1, "R")):
        y_t = side * HALF
        base = Vector((tip_le_x - 0.35, y_t, z_tip + 0.02))
        wl = tapered_slab(
            f"Plane_Winglet_{nm}",
            base + Vector((0, 0, 0)),
            base + Vector((-1.25, 0, 0)),
            base + Vector((-0.85, 0, 1.45)),
            base + Vector((-1.75, 0, 1.45)),
            0.30, 0.14, 'y', tail_m, root)
        verbose("   小翼 %s: 位于翼尖 (%.2f, %.2f, %.2f)" % (nm, base.x, base.y, base.z))

    # ---------------- 平尾 ----------------
    # 展长 12.45（a320_data 未存，用 ACAP 值），根弦 3.6 / 尖弦 1.3，后掠 8°
    HS_HALF, HS_YROOT, HS_CR, HS_CT = 6.225, 1.20, 3.6, 1.3
    HS_SWEEP = math.radians(8.0)
    hs_root_le_x = D.sx(31.0 + 1.0)      # 略前于原位置，落座于尾锥上方
    hs_z = 1.0
    hs_dy = HS_HALF - HS_YROOT
    hs_tip_le = hs_root_le_x - hs_dy * math.tan(HS_SWEEP)
    hs_tip_z = hs_z + hs_dy * math.tan(math.radians(5.0))

    drop(["Plane_HS_L", "Plane_HS_R"])
    for side, nm in ((-1, "L"), (1, "R")):
        y_r, y_t = side * HS_YROOT, side * HS_HALF
        tapered_slab(
            f"Plane_HS_{nm}",
            Vector((hs_root_le_x, y_r, hs_z)),
            Vector((hs_root_le_x - HS_CR, y_r, hs_z)),
            Vector((hs_tip_le, y_t, hs_tip_z)),
            Vector((hs_tip_le - HS_CT, y_t, hs_tip_z)),
            0.34, 0.14, 'z', tail_m, root)
    verbose("   平尾: 根弦 %.2f 尖弦 %.2f 后掠 8.0° 半展 %.2f" % (HS_CR, HS_CT, HS_HALF))

    # ---------------- 垂尾 ----------------
    VS_CR, VS_CT, VS_SWEEP = 6.3, 2.2, math.radians(28.0)
    vs_z0, vs_z1 = 0.80, 6.40
    vs_root_le_x = D.sx(32.5 + 0.6)
    vs_dz = vs_z1 - vs_z0
    vs_tip_le = vs_root_le_x - vs_dz * math.tan(VS_SWEEP)

    drop(["Plane_VStab", "Plane_VStabTop", "Logo_Tail"])
    tapered_slab(
        "Plane_VStab",
        Vector((vs_root_le_x, -0.175, vs_z0)),
        Vector((vs_root_le_x - VS_CR, -0.175, vs_z0)),
        Vector((vs_tip_le, -0.10, vs_z1)),
        Vector((vs_tip_le - VS_CT, -0.10, vs_z1)),
        0.35, 0.15, 'y', tail_m, root)
    verbose("   垂尾: 根弦 %.2f 尖弦 %.2f 后掠 28.0° 高度 %.2f" % (VS_CR, VS_CT, vs_dz))

    # ---------------- 翼刀：原有几何与新机翼对不上，移除 ----------------
    drop(["Fence_Wing_L", "Fence_Wing_R"])

    # ---------------- 移除无用的展示屏幕与旧地面 ----------------
    # HUD_BG 是一块 9.80 × 5.20 × 0.06 m 的平板，位于 Z=+14.5（左翼外侧），
    # 在三维视图里读起来就是"飞机旁边立了一块屏幕"，用户要求直接移除。
    # Ground 是 Blender 里那块 100×70 的深色板，已由视图侧的程序化网格 + 接影面替代；
    # 它的顶面在 y=−3.25，比起落架最低点 −3.40 还高 0.15 m —— 留着会让"轮子陷进地里"，
    # 与"不得穿透地面"的硬约束冲突，故一并移除。
    drop(["HUD_BG", "HUD", "Ground"])

    # ---------------- 座位补到 31 排（真实 186Y）----------------
    added = add_aft_row(verbose)
    extend_cabin_floor(verbose)

    # ---------------- 机体外观精修（参数化旋成体）----------------
    # 原 .blend 的机身是"椭球机头 + 等径尾锥"，实测有台阶、后舱门悬空、
    # 机身比整机长少 1.67 m。详见 stage2_refine.py 的模块说明。
    import stage2_refine
    stage2_refine.refine(verbose)
    return added


def add_aft_row(verbose=print):
    """把各区座位补齐到 a320_data.ZONES 声明的排数（真实 A320 186Y = 31 排）。

    注意：目标排数从 a320_data 读，但**现有末排必须从场景里实际扫描**得到 ——
    不能用 ZONES 的 rows 反推，否则 .blend 还停在旧排数时会找不到源物件而静默跳过
    （2026-09-22 实际踩过：数据已改 31 排，.blend 只有 30 排，结果"新增 0 个物件"）。
    """
    made = 0
    for zid, z in D.ZONES.items():
        target_last = z["rows"][1]
        rows = set()
        for o in bpy.data.objects:
            nm = o.name
            if not nm.startswith(("Seat_", "SeatB_", "SeatH_")):
                continue
            parts = nm.split("_")
            if len(parts) >= 4 and parts[1] == zid:
                try:
                    rows.add(int(parts[2]))
                except ValueError:
                    pass
        if not rows:
            verbose("   区 %s 未找到任何座椅物件，跳过" % zid)
            continue
        cur_last = max(rows)
        if cur_last >= target_last:
            verbose("   区 %s 已是 %d 排（目标 %d），无需补排" % (zid, cur_last, target_last))
            continue
        for r_new in range(cur_last + 1, target_last + 1):
            src_row = r_new - 1
            for col in range(6):
                for pref in ("Seat_", "SeatB_", "SeatH_"):
                    src = bpy.data.objects.get(f"{pref}{zid}_{src_row}_{col}")
                    if not src:
                        continue
                    new = src.copy()
                    new.data = src.data.copy()
                    new.name = f"{pref}{zid}_{r_new}_{col}"
                    for c in list(new.keys()):
                        if c != "_RNA_UI":
                            del new[c]
                    bpy.context.collection.objects.link(new)
                    new.location = src.location.copy()
                    new.location.x -= D.SEAT_PITCH
                    new["zone"] = zid
                    new["row"] = r_new
                    made += 1
            verbose("   区 %s 新增第 %d 排（源排 %d）" % (zid, r_new, src_row))
    # 汇总各区实际座位数
    cnt = {}
    for o in bpy.data.objects:
        if o.name.startswith("Seat_") and not o.name.startswith(("SeatB_", "SeatH_")):
            parts = o.name.split("_")
            if len(parts) >= 3:
                cnt[parts[1]] = cnt.get(parts[1], 0) + 1
    verbose("   补排合计新增 %d 个物件；各区座垫数 %s，合计 %d 座"
            % (made, cnt, sum(cnt.values())))
    return made


def extend_cabin_floor(verbose=print):
    """客舱地板向后延长，覆盖新增的第 31 排。"""
    o = bpy.data.objects.get("CabinFloor")
    if not o:
        verbose("   客舱地板 CabinFloor 未找到，跳过延长")
        return
    old_len = 22.0
    new_len = 23.6
    front_edge = o.location.x + old_len * 0.5
    o.scale.x *= new_len / old_len
    o.location.x = front_edge - new_len * 0.5
    verbose("   客舱地板: 长 %.1f → %.1f m（向后延长 %.1f）"
            % (old_len, new_len, new_len - old_len))

# -*- coding: utf-8 -*-
"""
Stage 2b · 外观精修（参数化旋成体）
==================================

为什么要有这一层
----------------
Stage 2 只换掉了"旋转长方体"式机翼；机身与发动机仍沿用原 .blend 的方块化示意体。
2026-09-22 用 `tools/dump_group.mjs` + Blender 顶点实测，查出**四处形状错误**——
不是"不够精细"，是"画错了"，而且错得很显眼：

1. `Plane_Nose` 是**对称椭球**（X 10.79~18.78，半径从 2.00 对称掉到 0）。
   来源：`fix_plane_shell.py` 里的 `add_sphere("Plane_Nose", 2.0, ..., scale=(2,1,1))`。
   → 机头是个"橄榄球头"，侧视完全是圆的，没有雷达罩锥度。
2. `Plane_TailCone` 名叫"尾锥"，实测是**等径圆柱**（两圈顶点半径都是 1.700、Y 半宽 1.19），
   而机身筒半径是 2.000 → **后机身有一道 0.81 m 的突缩台阶**。
3. 由此引发更严重的问题：后舱门 `Door_L3/R3` 位于 X[−14.69,−13.74]、|Y| 1.94~2.02，
   而该处只有那个 Y 半宽 1.19 的"尾锥"
   → **后舱门悬在机体外 0.75 m**（原模型遗留缺陷，肉眼可见为门上悬空）。
4. `Shell_Upper` 全长 37.57 m，而机身只有 35.89 m（尾端 −17.11）；
   `a320_data.LENGTH = 37.57`、`NOSE_X = LENGTH/2 = 18.785`
   → **尾锥末端应在 −18.785，机身短了 1.675 m**，与"整机长 37.57 m"自相矛盾。

本模块的做法
------------
**用一条半径剖面（station table）同时生成机身筒 / 机头 / 尾锥 / 上壳体**，
从根上消除台阶与悬空；再新增驾驶舱风挡（契约里早已预留 `CockpitGlass → WINDOWS`）。

* 截面用 `(r_y, r_z, z_off)` 三个量描述。尾段 **Y 向保持宽、Z 向收窄并整体上翘**
  ——这正是 A320 尾锥"海狸尾"的形态，也顺便让后舱门重新落回机体表面。
* 机身半径取 `FUS_DIA/2 = 1.975`（权威值），不再用原模型的 2.000：
  舱门/舷窗面板位于 |Y| 1.94~2.02，正好**骑在蒙皮上**（外凸 0.045），符合真实做法。
* 几何**按世界坐标烘焙**、对象变换保持单位阵（沿用 Stage 2 的约定）。
* 法线统一用 **bmesh** 重算，**不用 `bpy.ops`**：ops 依赖 GUI 上下文，
  在 MCP 远程调用与"open_mainfile 之后立即执行"两种情形下都曾因
  `mode_set.poll() 上下文缺失活动物体` 失败（2026-09-22 实际踩过）。

对象命名保持与契约一致（前缀匹配，见 stage1_export.RULES）：
    Plane_TailCone / Plane_Fuselage / Plane_Nose  → HULL_UPPER
    Shell_Upper                                   → HULL_UPPER
    CockpitGlass                                  → WINDOWS   （契约第 105 行，首次使用）

由 stage2_shape.rebuild() 调用；源 .blend 只读。
"""
import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

SP = os.path.dirname(os.path.abspath(__file__))
if SP not in sys.path:
    sys.path.insert(0, SP)
import a320_data as D

# ---------------------------------------------------------------------------
# 基准量（全部来自 a320_data，换机型只改数据）
# ---------------------------------------------------------------------------
R_BODY = D.FUS_DIA / 2.0            # 1.975 —— 机身筒半径（权威）
X_TIP_F = D.NOSE_X                  # +18.785 机头尖端
X_TIP_A = -D.NOSE_X                 # -18.785 尾锥末端（整机长 = LENGTH）
X_NOSE_BASE = D.sx(7.0)             # 11.785 —— 机头锥起点（前舱门之前 0.02 m）
X_TAIL_BASE = D.sx(33.05)           # -14.265 —— 尾锥起点（后舱门之后）
NSEG = 32                           # 周向分段（与原筒体一致）
SHELL_HALF = math.radians(27.0)     # 上壳体半张角（原 |Y|max 0.897 @ r=2 → 26.6°）

# 机头 ogive：r = R·(1 − t^p)^(1/q)，t 从机头锥起点算到尖端
NOSE_P, NOSE_Q, NOSE_N = 2.8, 2.0, 18

def _build_stations():
    S = [
        # —— 尾锥（后 → 前）：Y 保持宽、Z 收窄并整体上翘 ——
        (X_TIP_A, 0.44, 0.30, 0.620),
        (-18.45,  0.96, 0.56, 0.565),
        (-18.05,  1.32, 0.78, 0.490),
        (-17.62,  1.58, 0.99, 0.405),
        (-17.18,  1.76, 1.20, 0.315),
        (-16.74,  1.885, 1.42, 0.230),
        (-16.30,  1.950, 1.62, 0.145),
        (-15.86,  1.972, 1.79, 0.075),
        (-15.42,  1.975, 1.905, 0.030),
        (-14.90,  R_BODY, 1.962, 0.006),
        (X_TAIL_BASE, R_BODY, R_BODY, 0.0),
        # —— 等径段 ——
        (-10.0, R_BODY, R_BODY, 0.0),
        (-6.0,  R_BODY, R_BODY, 0.0),
        (-2.0,  R_BODY, R_BODY, 0.0),
        (2.0,   R_BODY, R_BODY, 0.0),
        (6.0,   R_BODY, R_BODY, 0.0),
        (9.0,   R_BODY, R_BODY, 0.0),
        (X_NOSE_BASE, R_BODY, R_BODY, 0.0),
    ]
    span = X_TIP_F - X_NOSE_BASE
    for i in range(1, NOSE_N + 1):
        t = i / NOSE_N
        r = R_BODY * (1.0 - t ** NOSE_P) ** (1.0 / NOSE_Q)
        S.append((X_NOSE_BASE + span * t, r, r, 0.0))
    return S

STATIONS = _build_stations()
X_MIN, X_MAX = STATIONS[0][0], STATIONS[-1][0]


def interp(x):
    """线性插值取 (r_y, r_z, z_off)。站点足够密，线性即可。"""
    S = STATIONS
    if x <= S[0][0]:
        return S[0][1], S[0][2], S[0][3]
    if x >= S[-1][0]:
        return S[-1][1], S[-1][2], S[-1][3]
    for i in range(len(S) - 1):
        a, b = S[i], S[i + 1]
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
            return (a[1] + (b[1] - a[1]) * t,
                    a[2] + (b[2] - a[2]) * t,
                    a[3] + (b[3] - a[3]) * t)
    return S[-1][1], S[-1][2], S[-1][3]


def surface_pt(x, th, out=0.0, const_r=None):
    """机体表面点。th 为周向角：0 = 正上方，正方向朝 +Y（右）。out 为外法向偏移。

    const_r 给定则按**等截面**取半径（忽略 x 处的实际剖面）—— 用于生成与位置无关的
    局部几何：同一侧的门/窗外形完全一样，只有 x 不同，可以用一份几何实例化，
    视图侧按几何签名分桶时才能合并成一次 draw call。
    """
    if const_r is None:
        ry, rz, zo = interp(x)
    else:
        ry = rz = const_r
        zo = 0.0
    return Vector((x,
                   (ry + out) * math.sin(th),
                   zo + (rz + out) * math.cos(th)))


# ---------------------------------------------------------------------------
# 通用几何工具（不用 bpy.ops，保证后台与 MCP 两种上下文都能跑）
# ---------------------------------------------------------------------------
def _recalc_normals(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()


def mk_obj(name, verts, faces, material, parent, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    _recalc_normals(me)
    if smooth:
        for poly in me.polygons:
            poly.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def drop(names):
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)


def parent_of(name, fallback_name="AIRCRAFT_ROOT"):
    """取原对象的父级 —— **必须保留**。
    父级决定导出后的 `lb_src`（视图侧 `?src=AC_ROOT / AIRCRAFT_ROOT` 过滤靠它），
    随手改父级会让"只看外观壳 / 只看载荷"的行为变掉（Shell_Upper 原属 AC_ROOT）。
    """
    o = bpy.data.objects.get(name)
    if o and o.parent:
        return o.parent
    return bpy.data.objects.get(fallback_name)


def theta_of(z, r=R_BODY):
    """把竖向高度换算成周向角（0 = 正上方，π = 正下方）。"""
    return math.acos(max(-1.0, min(1.0, z / r)))


def loft(name, secs, material, parent, cap_a=True, cap_b=True, smooth=True):
    """把一串等点数的环放样成实体。secs: [[Vector,...], ...]"""
    n = len(secs[0])
    verts = []
    for sec in secs:
        verts.extend(sec)
    faces = []
    for i in range(len(secs) - 1):
        a, b = i * n, (i + 1) * n
        for j in range(n):
            j2 = (j + 1) % n
            faces.append((a + j, a + j2, b + j2, b + j))
    if cap_a:
        c = sum(secs[0], Vector()) / n
        ci = len(verts); verts.append(c)
        for j in range(n):
            faces.append((ci, (j + 1) % n, j))
    if cap_b:
        base = (len(secs) - 1) * n
        c = sum(secs[-1], Vector()) / n
        ci = len(verts); verts.append(c)
        for j in range(n):
            faces.append((ci, base + j, base + (j + 1) % n))
    return mk_obj(name, verts, faces, material, parent, smooth)


def ring(x, th0, th1, n, out=0.0, const_r=None):
    """一段周向弧（th0→th1，等分 n 段）。"""
    return [surface_pt(x, th0 + (th1 - th0) * i / n, out, const_r) for i in range(n + 1)]


def panel_mesh(name, x0, x1, th0, th1, nx, nt, out_off, thickness, const_r=None):
    """贴在机体表面上的薄板 —— **只生成网格数据，不建对象**。
    返回 mesh；调用方可以把它复用给多个对象（obj_from_mesh）。"""
    outer, inner = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        outer.append(ring(x, th0, th1, nt, out_off, const_r))
        inner.append(ring(x, th0, th1, nt, -thickness, const_r))
    n = nt + 1
    verts, faces = [], []
    for sec in outer:
        verts.extend(sec)
    off_in = len(verts)
    for sec in inner:
        verts.extend(sec)
    # 外表面
    for i in range(nx):
        for j in range(nt):
            a, b = i * n, (i + 1) * n
            faces.append((a + j, a + j + 1, b + j + 1, b + j))
    # 内表面（反向）
    for i in range(nx):
        for j in range(nt):
            a, b = off_in + i * n, off_in + (i + 1) * n
            faces.append((a + j, b + j, b + j + 1, a + j + 1))
    # 四条边界
    for i in range(nx):
        a, b = i * n, (i + 1) * n
        c, d = off_in + i * n, off_in + (i + 1) * n
        faces.append((a, b, d, c))                                    # th = th0 边
        faces.append((a + nt, c + nt, d + nt, b + nt))                # th = th1 边
    for j in range(nt):
        a = j
        c = off_in + j
        faces.append((a, a + 1, c + 1, c))                            # x = x0 端
        b = nx * n + j
        d = off_in + nx * n + j
        faces.append((b, d, d + 1, b + 1))                            # x = x1 端
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    _recalc_normals(me)
    for poly in me.polygons:
        poly.use_smooth = True
    return me


def obj_from_mesh(name, mesh, material, parent, loc=(0.0, 0.0, 0.0)):
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    if material and len(mesh.materials) == 0:
        mesh.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    o.location = Vector(loc)
    return o


def panel(name, x0, x1, th0, th1, nx, nt, out_off, thickness, material, parent):
    """单件薄板（自带几何，用世界坐标烘焙）。"""
    mesh = panel_mesh(name, x0, x1, th0, th1, nx, nt, out_off, thickness)
    return _obj_from_existing(name, mesh, material, parent)


def _obj_from_existing(name, mesh, material, parent):
    """把已有 mesh 挂成新对象。"""
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    if material:
        mesh.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


# ---------------------------------------------------------------------------
# 材质
# ---------------------------------------------------------------------------
def _principled(m, color, rough=0.5, metal=0.0):
    """按**节点类型**取 Principled BSDF，取不到就重建节点树。

    踩过（2026-09-22）：原写法 `nodes.get("Principled BSDF")` 依赖节点**名字**，
    而原 .blend 里的 `M_CockpitGlass` 是早期脚本建的、节点名不是这个
    → `.get()` 返回 None → 颜色根本没写进去 → 风挡渲染成一块浅灰平板，
    查了半天以为是几何问题。
    """
    m.use_nodes = True
    nt = m.node_tree
    b = None
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            b = n
            break
    if b is None:
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    b.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)
    if 'Roughness' in b.inputs:
        b.inputs['Roughness'].default_value = rough
    if 'Metallic' in b.inputs:
        b.inputs['Metallic'].default_value = metal
    if 'Alpha' in b.inputs:
        b.inputs['Alpha'].default_value = 1.0
    return b


def mat_body():
    """机身白（批次2：近白现代极简，与 M_PaintWhite 家族一致）。"""
    m = bpy.data.materials.get("M_PlaneBody") or bpy.data.materials.new("M_PlaneBody")
    _principled(m, (0.93, 0.95, 0.98), rough=0.45, metal=0.05)
    return m


def mat_paintwhite():
    """白漆（批次2）：短舱主体/吊挂与机身同一族白。
    统一刷成与 M_PlaneBody 完全一致的参数 —— 若 .blend 里残留旧脚本的
    M_PaintWhite（偏蓝/更低粗糙），这里一并归正。"""
    m = bpy.data.materials.get("M_PaintWhite") or bpy.data.materials.new("M_PaintWhite")
    _principled(m, (0.93, 0.95, 0.98), rough=0.45, metal=0.05)
    return m


def unify_body_colors(verbose=print):
    """机身/翼面/尾翼颜色统一（批次2）：M_PlaneBody/M_PlaneTail/M_PlaneWing
    原偏灰蓝，统一为近白 (0.93,0.95,0.98)、rough 0.45、metal 0.05。"""
    for name in ("M_PlaneBody", "M_PlaneTail", "M_PlaneWing"):
        m = bpy.data.materials.get(name)
        if m:
            _principled(m, (0.93, 0.95, 0.98), rough=0.45, metal=0.05)
    verbose("   机身/翼面/尾翼颜色统一：近白 (0.93,0.95,0.98) rough 0.45 metal 0.05")
    return True


def mat_glass():
    """驾驶舱风挡/舷窗：不透明深色 + 高光泽。用不透明而非半透明，避免 three.js 里
    透明物体排序与剖切平面叠加产生的渲染瑕疵（教学模型不需要透过风挡看内部）。
    批次2：metal 0.40→0.15 / rough 0.10→0.18 —— 压掉朝天空面的镜面白反，
    深色基底更稳。"""
    m = bpy.data.materials.get("M_CockpitGlass") or bpy.data.materials.new("M_CockpitGlass")
    _principled(m, (0.045, 0.070, 0.105), rough=0.18, metal=0.15)
    for attr, val in (("blend_method", 'OPAQUE'), ("surface_render_method", 'DITHERED')):
        if hasattr(m, attr):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    return m


def mat_frame():
    """窗框/橡胶密封：近黑。"""
    m = bpy.data.materials.get("M_Frame") or bpy.data.materials.new("M_Frame")
    _principled(m, (0.02, 0.02, 0.025), rough=0.7, metal=0.0)
    return m


def mat_accent():
    """点缀色：深蓝青 (0.05, 0.35, 0.55) —— 小翼/短舱环带/垂尾标。"""
    m = bpy.data.materials.get("M_Accent") or bpy.data.materials.new("M_Accent")
    _principled(m, (0.05, 0.35, 0.55), rough=0.42, metal=0.10)
    return m


def mat_nozzle():
    """尾喷管/中心锥：深色金属。"""
    m = bpy.data.materials.get("M_Nozzle") or bpy.data.materials.new("M_Nozzle")
    _principled(m, (0.13, 0.13, 0.14), rough=0.35, metal=0.90)
    return m


def mat_fandark():
    """进气风扇面：深洞盘。"""
    m = bpy.data.materials.get("M_FanDark") or bpy.data.materials.new("M_FanDark")
    _principled(m, (0.02, 0.02, 0.03), rough=0.90, metal=0.10)
    return m


def mat_outline():
    """门阴影轮廓等深色贴面。"""
    m = bpy.data.materials.get("M_Outline") or bpy.data.materials.new("M_Outline")
    _principled(m, (0.10, 0.11, 0.13), rough=0.75, metal=0.0)
    return m


def mat_nav(name, color):
    """航行灯：彩色 + 轻微自发光感。"""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    b = _principled(m, color, rough=0.30, metal=0.0)
    if 'Emission Color' in b.inputs:
        b.inputs['Emission Color'].default_value = (color[0], color[1], color[2], 1.0)
        b.inputs['Emission Strength'].default_value = 0.6
    return m


def fix_gear_shell(verbose=print):
    """把外观壳起落架对齐到实际起落架。

    实测（2026-09-22）：`AIRCRAFT_ROOT` 的 `Plane_GN / Plane_GM1 / Plane_GM-1`
    与 `AC_ROOT` 的 `GN / GM1 / GM-1` 明显错位 ——
      · Plane_GN   X[10.43,11.14] 而 GN   X[14.98,15.59]  → 前起落架外观偏后 4.2 m
      · Plane_GM1  |Y| 0.98~1.82  而 GM1  |Y| 3.39~4.20   → 主起落架外观挂到了机身中线下
    结果是侧视图上"轮子在空旷处漂着"。

    **以实际起落架为准**（有独立证据）：
      主起中心 x=2.645 + a320_data.WHEELBASE 12.64 = 15.285 = GWN（前轮）中心
      → 前后轮距自洽，说明 G*/GW* 那一组才是对的。
    """
    pairs = (("Plane_GN", "GN"), ("Plane_GM1", "GM1"), ("Plane_GM-1", "GM-1"))
    for shell, real in pairs:
        a = bpy.data.objects.get(shell)
        b = bpy.data.objects.get(real)
        if not a or not b or a.type != 'MESH' or b.type != 'MESH':
            continue
        va = [a.matrix_world @ v.co for v in a.data.vertices]
        vb = [b.matrix_world @ v.co for v in b.data.vertices]
        dx = sum(v.x for v in vb) / len(vb) - sum(v.x for v in va) / len(va)
        dy = sum(v.y for v in vb) / len(vb) - sum(v.y for v in va) / len(va)
        if abs(dx) < 1e-3 and abs(dy) < 1e-3:
            verbose("   %-12s 已对齐 %-6s" % (shell, real))
            continue
        # 位移量要换算到对象局部空间（这些对象通常是单位变换，但不能假设）
        d = a.matrix_world.inverted().to_3x3() @ Vector((dx, dy, 0.0))
        for v in a.data.vertices:
            v.co += d
        a.data.update()
        verbose("   %-12s 对齐到 %-6s  Δx %+.2f  Δy %+.2f" % (shell, real, dx, dy))


# ---------------------------------------------------------------------------
# 三段机体：用同一条剖面，端点取同一站点 → 拼接处半径完全相等，没有台阶
# ---------------------------------------------------------------------------
def build_body(verbose=print):
    mat = mat_body()
    i_tail = min(range(len(STATIONS)), key=lambda i: abs(STATIONS[i][0] - X_TAIL_BASE))
    i_nose = min(range(len(STATIONS)), key=lambda i: abs(STATIONS[i][0] - X_NOSE_BASE))

    segs = (("Plane_TailCone", 0, i_tail, True, False),
            ("Plane_Fuselage", i_tail, i_nose, False, False),
            ("Plane_Nose", i_nose, len(STATIONS) - 1, False, True))
    pars = {n: parent_of(n) for n, _, _, _, _ in segs}      # 先记父级，再删
    drop([n for n, _, _, _, _ in segs])
    out = {}
    for name, a, b, cap_a, cap_b in segs:
        secs = [[Vector((x, ry * math.sin(2 * math.pi * j / NSEG),
                         zo + rz * math.cos(2 * math.pi * j / NSEG)))
                 for j in range(NSEG)]
                for (x, ry, rz, zo) in STATIONS[a:b + 1]]
        o = loft(name, secs, mat, pars[name], cap_a=cap_a, cap_b=cap_b)
        out[name] = o
        verbose("   %-16s 站点 %2d  顶点 %4d  X[%7.2f,%7.2f]  端盖 %s/%s"
                % (name, len(secs), len(o.data.vertices),
                   STATIONS[a][0], STATIONS[b][0],
                   "有" if cap_a else "无", "有" if cap_b else "无"))
    return out


def build_shell(verbose=print):
    """上壳体：跟随机身剖面的一条顶弧板（不再是一条等宽长条）。
    原壳体全长 37.57 m 而机身 35.89 m，尾部多出 1.67 m；且它在筒体表面之外
    0.17 m 处悬空。改为一律贴面外偏 0.02 m。"""
    mat = mat_body()
    par = parent_of("Shell_Upper")
    drop(["Shell_Upper"])
    xs = [x for (x, _, _, _) in STATIONS if -17.55 <= x <= 17.30]
    secs_o, secs_i = [], []
    for x in xs:
        secs_o.append(ring(x, -SHELL_HALF, SHELL_HALF, 8, 0.02))
        secs_i.append(ring(x, -SHELL_HALF, SHELL_HALF, 8, -0.05))
    n = 9
    verts, faces = [], []
    for sec in secs_o:
        verts.extend(sec)
    off = len(verts)
    for sec in secs_i:
        verts.extend(sec)
    for i in range(len(xs) - 1):
        for j in range(n - 1):
            a, b = i * n, (i + 1) * n
            faces.append((a + j, a + j + 1, b + j + 1, b + j))
            c, d = off + i * n, off + (i + 1) * n
            faces.append((c + j, d + j, d + j + 1, c + j + 1))
        a, b = i * n, (i + 1) * n
        c, d = off + i * n, off + (i + 1) * n
        faces.append((a, b, d, c))
        faces.append((a + n - 1, c + n - 1, d + n - 1, b + n - 1))
    for j in range(n - 1):
        faces.append((j, j + 1, off + j + 1, off + j))
        base = (len(xs) - 1) * n
        faces.append((base + j, off + base + j, off + base + j + 1, base + j + 1))
    o = mk_obj("Shell_Upper", verts, faces, mat, par, smooth=False)
    verbose("   %-16s 站点 %2d  顶点 %4d  X[%7.2f,%7.2f]  parent=%s"
            % ("Shell_Upper", len(xs), len(o.data.vertices), xs[0], xs[-1],
               par.name if par else "-"))
    return o


def build_doors_windows(verbose=print):
    """把舱门 / 舷窗从"切于筒体的平板"改成"贴面曲板"。

    实测（2026-09-22）：原模型的门窗都是 `add_box` 造的平板，没有跟随机身曲率 ——
    48 扇舷窗**整条外飘 0.147~0.257 m**（全部悬在蒙皮之外），
    舱门上下边缘外飘最多 0.370 m。从侧前方看就是"一排骨片浮在机身旁边"。

    做法：保留原名与原父级，按各自的 X 范围 + 竖向高度换算成周向角后重建为曲板。
      door  骑在蒙皮上（外偏 0.012 / 厚 0.060）
      frame 略微凸出（外偏 0.030 / 厚 0.030）
      win   平贴蒙皮（外偏 0.008 / 厚 0.050）→ 批次1 起改用深色高光泽 mat_glass()
    批次1 追加（2026-09-24）：
      · 每扇门下加"门阴影轮廓"（各边大 0.05 的深色贴面板，读出门框线，共享几何）
      · 客舱门上加观察窗（小玻璃贴面，共享几何；货舱门在腹部，不加）
    """
    # 二次执行的防重影清理（Win_Door_*/Mark_DoorShad_* 为本函数产物）
    drop([o.name for o in list(bpy.data.objects)
          if o.name.startswith("Win_Door_") or o.name.startswith("Mark_DoorShad_")])
    OFFS = {
        # kind: (nx 纵向分段, nt 周向分段, out_off 外偏, thickness 厚度)
        "door":   (3, 3, 0.012, 0.060),
        "frame":  (3, 3, 0.030, 0.030),
        "win":    (3, 3, 0.008, 0.050),
        "stripe": (24, 3, 0.006, 0.030),   # 腰线很长（24 m），纵向要足够分段才顺
    }
    targets = []
    for o in list(bpy.data.objects):
        if o.type != 'MESH':
            continue
        n = o.name
        if n.startswith("Door_"):
            targets.append((o, "frame" if n.endswith("F") else "door"))
        elif n.startswith("Win_"):
            targets.append((o, "win"))
        elif n.startswith("Stripe_"):
            targets.append((o, "stripe"))
    cnt = {"door": 0, "frame": 0, "win": 0, "stripe": 0}
    cache = {}          # (kind, side, 宽, 张角) -> mesh，同尺寸同侧共享一份几何
    cache_sh = {}       # 门阴影轮廓共享缓存
    cache_dw = {}       # 门观察窗共享缓存
    m_glass = mat_glass()
    m_outl = mat_outline()
    for o, kind in targets:
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        x0, x1 = min(v.x for v in vs), max(v.x for v in vs)
        z0, z1 = min(v.z for v in vs), max(v.z for v in vs)
        side = 1.0 if (sum(v.y for v in vs) / len(vs)) >= 0 else -1.0
        t_lo = theta_of(z1) * side
        t_hi = theta_of(z0) * side
        if t_hi < t_lo:
            t_lo, t_hi = t_hi, t_lo
        mat = o.data.materials[0] if o.data.materials else None
        if kind == "win":
            mat = m_glass                     # 舷窗：深色高光泽玻璃（批次1）
        elif kind == "frame":
            # 门框随机身白（批次2）：原 .blend 的 Door_*F 用 M_PaintBlue，
            # 在机头/机尾两侧形成突兀的蓝色门板 —— 强制 M_PaintWhite
            mat = bpy.data.materials.get("M_PaintWhite") or mat
        name, par = o.name, o.parent
        nx, nt, out, th = OFFS[kind]
        xc = (x0 + x1) * 0.5
        w = x1 - x0
        drop([name])
        if kind == "stripe":
            # 腰线横跨机头锥起点（x=11.79），剖面半径在长度方向是变的，
            # 无法用等截面局部几何 —— 单件世界坐标生成，只有 2 件，无所谓。
            panel(name, x0, x1, t_lo, t_hi, nx, nt, out, th, mat, par)
        else:
            key = (kind, side, round(w, 3), round(t_hi - t_lo, 4))
            mesh = cache.get(key)
            if mesh is None:
                half = w * 0.5
                mesh = panel_mesh(f"_{kind}_{len(cache)}", -half, half, t_lo, t_hi,
                                  nx, nt, out, th, const_r=R_BODY)
                cache[key] = mesh
            if kind == "win" and mesh.materials:
                # 共享 mesh 上的旧材质换成玻璃（L/R 两份各处理一次）
                mesh.materials.clear()
                mesh.materials.append(m_glass)
            obj_from_mesh(name, mesh, mat, par, loc=(xc, 0.0, 0.0))
            if kind == "door":
                # —— 门阴影轮廓：各边外扩 0.05，压在门片下方（外偏 0.004 < 门 0.012）——
                key_sh = (side, round(w + 0.1, 3),
                          round(theta_of(z0 - 0.05) * side - theta_of(z1 + 0.05) * side, 4))
                mesh_sh = cache_sh.get(key_sh)
                if mesh_sh is None:
                    half = (w + 0.1) * 0.5
                    tlo2 = theta_of(z1 + 0.05) * side
                    thi2 = theta_of(z0 - 0.05) * side
                    if thi2 < tlo2:
                        tlo2, thi2 = thi2, tlo2
                    mesh_sh = panel_mesh(f"_doorshad_{len(cache_sh)}", -half, half,
                                         tlo2, thi2, 3, 3, 0.004, 0.030, const_r=R_BODY)
                    cache_sh[key_sh] = mesh_sh
                obj_from_mesh(f"Mark_DoorShad_{name}", mesh_sh, m_outl, par,
                              loc=(xc, 0.0, 0.0))
                # —— 客舱门观察窗：门上部靠前的小玻璃（货舱门 z0<-1 为腹部门，跳过）——
                if z0 > -1.0:
                    key_dw = (side, round(w, 3))
                    mesh_dw = cache_dw.get(key_dw)
                    if mesh_dw is None:
                        wx0, wx1 = -w * 0.5 + 0.03, -w * 0.5 + 0.33   # 靠前 1/3 处
                        wz0, wz1 = 0.55, 0.80
                        tlo3 = theta_of(wz1) * side
                        thi3 = theta_of(wz0) * side
                        if thi3 < tlo3:
                            tlo3, thi3 = thi3, tlo3
                        mesh_dw = panel_mesh(f"_doorwin_{len(cache_dw)}", wx0, wx1,
                                             tlo3, thi3, 2, 2, 0.020, 0.020,
                                             const_r=R_BODY)
                        mesh_dw.materials.append(m_glass)
                        cache_dw[key_dw] = mesh_dw
                    obj_from_mesh(f"Win_Door_{name}", mesh_dw, m_glass, par,
                                  loc=(xc, 0.0, 0.0))
        cnt[kind] += 1
    verbose("   门/窗/腰线改为贴面曲板：门 %d 框 %d 窗 %d 腰线 %d（共享几何 %d 份）；"
            " 门轮廓 %d 份、门观察窗 %d 份"
            % (cnt["door"], cnt["frame"], cnt["win"], cnt["stripe"], len(cache),
               len(cache_sh), len(cache_dw)))
    return cnt


def check_skin_fit(verbose=print):
    """复核"贴面要素是否真的贴在蒙皮上"。返回最大外飘量（米）。

    排除 `BellyFairing`：翼身整流罩本来就是**凸出机身**的鼓包结构，
    不算"外飘"（实测 +0.834 m 属设计如此）。
    """
    worst = (0.0, "")
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        n = o.name
        if n.startswith("Belly"):
            continue
        if not (n.startswith(("Door_", "Win_", "Stripe_", "CockpitGlass"))):
            continue
        hi = -9.9
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            ry, rz, zo = interp(p.x)
            sr = ((p.y / ry) ** 2 + ((p.z - zo) / rz) ** 2) ** 0.5
            hi = max(hi, (sr - 1.0) * min(ry, rz))
        if hi > worst[0]:
            worst = (hi, n)
    verbose("   贴面复核：最大外飘 %.3f m（%s）%s"
            % (worst[0], worst[1], "OK" if worst[0] < 0.06 else "★ 仍偏"))
    return worst[0]


def _band_geo(outer, inner):
    """由外/内两层点阵生成贴面薄板的几何数据 (verts, faces)。
    行 = 周向（θ），列 = 纵向（x）。只产数据不建对象，供镜像/复用。"""
    nr, nc = len(outer), len(outer[0])
    verts, faces = [], []
    for row in outer:
        verts.extend(row)
    off_in = len(verts)
    for row in inner:
        verts.extend(row)
    for i in range(nr - 1):
        for j in range(nc - 1):
            a, b = i * nc, (i + 1) * nc
            faces.append((a + j, a + j + 1, b + j + 1, b + j))                 # 外表面
            c, d = off_in + i * nc, off_in + (i + 1) * nc
            faces.append((c + j, d + j, d + j + 1, c + j + 1))                 # 内表面（反向）
    for i in range(nr - 1):                                                   # 两条纵向边
        a, b = i * nc, (i + 1) * nc
        c, d = off_in + i * nc, off_in + (i + 1) * nc
        faces.append((a, b, d, c))
        faces.append((a + nc - 1, c + nc - 1, d + nc - 1, b + nc - 1))
    for j in range(nc - 1):                                                   # 两条横向端
        faces.append((j, j + 1, off_in + j + 1, off_in + j))
        base = (nr - 1) * nc
        faces.append((base + j, off_in + base + j, off_in + base + j + 1, base + j + 1))
    return verts, faces



def _grid_surface_geo(rows):
    """网格行 → 单面片几何（无厚度、无侧墙）。用于玻璃：避免楔缝处露出
    玻璃侧墙/内面的高光，缝内直接读到下层黑色基底。"""
    verts = [v for row in rows for v in row]
    nr, nc = len(rows), len(rows[0])
    faces = []
    for i in range(nr - 1):
        for j in range(nc - 1):
            a = i * nc + j
            faces.append((a, a + 1, a + 1 + nc, a + nc))
    return verts, faces

def band_from_rows(name, outer, inner, material, parent):
    """由外/内两层点阵生成贴面薄板（拓扑同 panel，但**每行点数可变**）。
    行 = 周向（θ），列 = 纵向（x）。"""
    verts, faces = _band_geo(outer, inner)
    return mk_obj(name, verts, faces, material, parent)


def _mirror_geo(verts, faces):
    """把几何数据按 Y 镜像（左/右舷共用一份参数化生成的形状）。
    镜像会翻转绕向，逐面反序恢复外法向。"""
    mv = [Vector((v.x, -v.y, v.z)) for v in verts]
    mf = [tuple(reversed(f)) for f in faces]
    return mv, mf


def _cyl_geo(p0, p1, r0, r1, n, cap=True):
    """局部坐标回转体几何 (verts, faces)，p0→p1 为轴（不建对象）。"""
    ax = Vector(p1) - Vector(p0)
    u, v = _ortho(ax)
    secs = []
    for t, r in ((0.0, r0), (1.0, r1)):
        c = Vector(p0) + ax * t
        secs.append([c + (u * math.cos(2 * math.pi * j / n) + v * math.sin(2 * math.pi * j / n)) * r
                     for j in range(n)])
    verts = [p for sec in secs for p in sec]
    faces = []
    for j in range(n):
        j2 = (j + 1) % n
        faces.append((j, j2, n + j2, n + j))
    if cap:
        faces.append(tuple(reversed(range(n))))
        faces.append(tuple(n + j for j in range(n)))
    return verts, faces


def _sphere_geo(r, nseg=10, nring=6):
    """局部坐标低模球 (verts, faces)，用于航行灯。"""
    verts, faces = [], []
    for i in range(nring + 1):
        ph = math.pi * i / nring
        for j in range(nseg):
            th = 2 * math.pi * j / nseg
            verts.append(Vector((r * math.sin(ph) * math.cos(th),
                                 r * math.sin(ph) * math.sin(th),
                                 r * math.cos(ph))))
    for i in range(nring):
        for j in range(nseg):
            j2 = (j + 1) % nseg
            a, b = i * nseg + j, i * nseg + j2
            c, d = (i + 1) * nseg + j, (i + 1) * nseg + j2
            faces.append((a, b, d, c))
    return verts, faces


def _box_geo(sx, sy, sz):
    """局部坐标轴对齐长方体（中心在原点），供小件共享几何。"""
    v = [Vector((x, y, z)) for x in (-sx / 2, sx / 2)
         for y in (-sy / 2, sy / 2) for z in (-sz / 2, sz / 2)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4),
         (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6)]
    return v, f


def _combine_geos(geos):
    """把多份 (verts, faces) 合并成一份（偏移索引），小件拼一件共享几何。"""
    verts, faces = [], []
    for v, f in geos:
        off = len(verts)
        verts.extend(v)
        faces.extend([tuple(off + i for i in face) for face in f])
    return verts, faces


def _loc_obj(name, mesh, material, parent, loc, rot=None):
    """共享 mesh + 对象级 location/rotation（局部几何的实例化用法）。"""
    o = obj_from_mesh(name, mesh, material, parent, loc=loc)
    if rot is not None:
        o.rotation_euler = rot
    return o


def curved_band(name, th0, th1, nt, xc_fn, w_fn, out_off, thickness, material, parent, nx=5):
    """贴面**弧形带**：沿周向分 nt 段，每段的纵向位置/宽度由 xc_fn(θ)、w_fn(θ) 给出。
    用来做"环绕式风挡"——一条带跨过机头顶部、向两侧包覆并自然收窄后掠，
    而不是用几块方玻璃拼（原方案的问题）。"""
    outer, inner = [], []
    for i in range(nt + 1):
        th = th0 + (th1 - th0) * i / nt
        xc, w = xc_fn(th), w_fn(th)
        ro, ri = [], []
        for j in range(nx + 1):
            x = xc - w * 0.5 + w * j / nx
            ro.append(surface_pt(x, th, out_off))
            ri.append(surface_pt(x, th, -thickness))
        outer.append(ro)
        inner.append(ri)
    return band_from_rows(name, outer, inner, material, parent)


def build_cockpit_glass(verbose=print):
    """驾驶舱风挡：A320 经典 **6 块分窗 + 黑色橡胶窗框**（替换旧"环绕墨镜带"）。

    参数化思路：在 (站位 st, 横向半宽 yl) 空间定义四边形窗格，
    映射到机体表面 surface_pt(x=NOSE_X−st, th=±asin(yl/r(x)))；
    前/后缘随横向后掠（sw·u²，u=yl/1.19）。每侧 3 块：
      ① 前风挡   st∈[1.55+0.62u², 2.68+0.42u²]，yl∈[0.06,1.19]
      ② 侧固定窗 st∈[A柱+0.07,    3.28+0.12u²]，yl∈[0.10,1.19]
      ③ 滑动窗   st∈[中缝+0.07,    3.85−0.10u²]，yl∈[0.10,1.19]
    窗框：每块玻璃外周黑色框带（外扩 0.07、外偏 0.012，内圈缩进压在玻璃下），
    加 中柱(yl≈0.015~0.085 通高) / A柱(随 2.68+0.42u² 后掠) / 中缝(st≈3.28~3.42 随 0.12u²) 三条黑窄条。
    批次2（2026-09-24 复审）：**单层黑色基底** —— 覆盖整个风挡 footprint、各边比玻璃
    外缘再外扩 0.16 的整面黑色薄板（M_Frame）。三明治自上而下：窄条 0.038 /
    玻璃 0.034（边界外扩 0.03 搭接、厚 0.008）/ 框带 0.028 / 基底 0.024 —
    — **全部高于上壳体 Shell_Upper 的 0.02**（壳体横跨风挡区±27°，初版基底
    0.008~0.016 被压在壳体下露出白垫层，经射线排查定位），无白色件；
    玻璃弦边横跨曲面产生的楔缝显示为黑色密封而非露白。
    右舷参数化生成，左舷 _mirror_geo 镜像（逐面反序恢复法向）。
    """
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    mat_g = mat_glass()
    m_frame = mat_frame()
    # 按**前缀**清理：只 drop("CockpitGlass") 清不掉多片 CockpitGlass_*，
    # 二次执行时会生成 CockpitGlass_xxx.001 这类副本（两套都在 WINDOWS 组里 → 重影）。
    drop([o.name for o in list(bpy.data.objects) if o.name.startswith("CockpitGlass")])
    drop(["Plane_Cockpit"])

    YL_MAX = 1.19

    def grid(st_f_fn, st_a_fn, yl0, yl1, out, ny=10, nx=5):
        """(st,yl) 四边形 → 表面网格行（ny+1 行 × nx+1 列），行方向 = yl。"""
        rows = []
        for i in range(ny + 1):
            yl = yl0 + (yl1 - yl0) * i / ny
            u = yl / YL_MAX
            stf, sta = st_f_fn(u), st_a_fn(u)
            xf, xa = D.NOSE_X - stf, D.NOSE_X - sta
            rf = interp(xf)[1]
            ra = interp(xa)[1]
            thf = math.asin(max(-0.97, min(0.97, yl / rf)))
            tha = math.asin(max(-0.97, min(0.97, yl / ra)))
            row = []
            for j in range(nx + 1):
                x = xf + (xa - xf) * j / nx
                th = thf + (tha - thf) * j / nx
                row.append(surface_pt(x, th, out))
            rows.append(row)
        return rows

    def shell_geo(rows, out, thick):
        """单面网格 → 带厚度的双层面板几何（内层 = 沿当地向径缩 thick）。"""
        inner = []
        for row in rows:
            ir = []
            for v in row:
                ry, rz, zo = interp(v.x)
                r_now = math.sqrt(v.y ** 2 + (v.z - zo) ** 2)
                if r_now < 1e-6:
                    ir.append(Vector((v.x, v.y, v.z - thick)))
                    continue
                k = (r_now - thick) / r_now
                ir.append(Vector((v.x, v.y * k, zo + (v.z - zo) * k)))
            inner.append(ir)
        return _band_geo(rows, inner)

    def pane_pair(tag, st_f_fn, st_a_fn, yl0, yl1, ny=10, nx=5):
        """一块玻璃 + 外周黑框，左右舷各一套。玻璃 (st,yl) 边界外扩 0.03 与基底搭接。"""
        rows = grid(lambda u: st_f_fn(u) - 0.03, lambda u: st_a_fn(u) + 0.03,
                    yl0 - 0.03, yl1 + 0.03, 0.034, ny, nx)
        gv, gf = _grid_surface_geo(rows)   # 单面玻璃：无侧墙/内面，楔缝直露黑色基底
        # 框带：外圈外扩 0.07，内圈缩进 0.03（压在玻璃边缘下方，避免拼缝露底）
        rows_o = grid(lambda u: st_f_fn(u) - 0.07, lambda u: st_a_fn(u) + 0.07,
                      yl0 - 0.07, yl1 + 0.07, 0.028, ny, nx)
        rows_i = grid(lambda u: st_f_fn(u) + 0.03, lambda u: st_a_fn(u) - 0.03,
                      yl0 + 0.03, yl1 - 0.03, 0.028, ny, nx)
        fv, ff = _band_geo(rows_o, rows_i)
        for side, sgn in (("R", 1), ("L", -1)):
            if sgn > 0:
                mk_obj(f"CockpitGlass_{tag}_{side}", gv, gf, mat_g, root)
                mk_obj(f"CockpitGlass_{tag}F_{side}", fv, ff, m_frame, root)
            else:
                mv, mf = _mirror_geo(gv, gf)
                mk_obj(f"CockpitGlass_{tag}_{side}", mv, mf, mat_g, root)
                mv, mf = _mirror_geo(fv, ff)
                mk_obj(f"CockpitGlass_{tag}F_{side}", mv, mf, m_frame, root)

    # ① 前风挡 / ② 侧固定窗 / ③ 滑动窗（右舷；左舷镜像）
    pane_pair("W",
              lambda u: 1.55 + 0.62 * u * u,
              lambda u: 2.68 + 0.42 * u * u, 0.06, YL_MAX)
    pane_pair("S",
              lambda u: 2.68 + 0.42 * u * u + 0.07,
              lambda u: 3.28 + 0.12 * u * u, 0.10, YL_MAX)
    pane_pair("A",
              lambda u: 3.35,
              lambda u: 3.85 - 0.10 * u * u, 0.10, YL_MAX)

    # —— 整块黑色基底（三明治底层）：覆盖风挡 footprint、各边外扩 0.16 ——
    def _bf(u): return 1.55 + 0.62 * u * u - 0.16
    def _ba(u): return 3.85 - 0.10 * u * u + 0.16
    rows_bo = grid(_bf, _ba, 0.02, YL_MAX + 0.16, 0.024, ny=16, nx=8)
    rows_bi = grid(_bf, _ba, 0.02, YL_MAX + 0.16, 0.024 - 0.020, ny=16, nx=8)
    bv, bf_ = _band_geo(rows_bo, rows_bi)
    for side, sgn in (("R", 1), ("L", -1)):
        if sgn > 0:
            mk_obj(f"CockpitGlass_Base_{side}", bv, bf_, m_frame, root)
        else:
            mv, mf = _mirror_geo(bv, bf_)
            mk_obj(f"CockpitGlass_Base_{side}", mv, mf, m_frame, root)

    def strip_pair(tag, st_f_fn, st_a_fn, yl0, yl1, ny=6, nx=3):
        """黑色窄条（中柱/A柱/中缝），外浮 0.030（高于玻璃 0.024，避免 z-fight）。"""
        rows_o = grid(st_f_fn, st_a_fn, yl0, yl1, 0.038, ny, nx)
        rows_i = grid(st_f_fn, st_a_fn, yl0, yl1, 0.038 - 0.020, ny, nx)
        fv, ff = _band_geo(rows_o, rows_i)
        for side, sgn in (("R", 1), ("L", -1)):
            if sgn > 0:
                mk_obj(f"CockpitGlass_{tag}_{side}", fv, ff, m_frame, root)
            else:
                mv, mf = _mirror_geo(fv, ff)
                mk_obj(f"CockpitGlass_{tag}_{side}", mv, mf, m_frame, root)

    # 中柱：机头中线通高细条（yl 0.015~0.085，st 随玻璃前后缘）
    strip_pair("PillarC",
               lambda u: 1.55 + 0.62 * u * u,
               lambda u: 3.85 - 0.10 * u * u, 0.015, 0.085, ny=8)
    # A柱：随 2.68+0.42u² 后掠的竖条
    strip_pair("PillarA",
               lambda u: 2.68 + 0.42 * u * u,
               lambda u: 2.68 + 0.42 * u * u + 0.07, 0.06, YL_MAX, ny=10)
    # 中缝：st 3.28~3.42 随 0.12u²（与②后缘/③前缘咬合，黑窄条）
    strip_pair("Seam",
               lambda u: 3.28 + 0.12 * u * u,
               lambda u: 3.42 + 0.12 * u * u, 0.10, YL_MAX, ny=10)
    verbose("   驾驶舱风挡：黑基底×2 + 6 块分窗（前风挡/侧固定/滑动 ×2）+ 黑框带 6 + 中柱/A柱/中缝 6")
    return True


def fix_vertical_stab(verbose=print):
    """垂尾根弦后缘原本伸到 X=-20.61，比尾锥末端（-18.785）还远 1.83 m，
    使"整机长"名不副实。把根前缘前移，让后缘正好落在尾锥末端。"""
    o = bpy.data.objects.get("Plane_VStab")
    if not o:
        verbose("   垂尾 Plane_VStab 不存在，跳过")
        return
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    te_x = min(v.x for v in vs)
    # 注意符号：机头在 +X，尾在 −X，所以"后缘超出尾锥末端"意味着
    # te_x < X_TIP_A（更负）。位移量必须是 X_TIP_A − te_x（正数=向前）。
    # 初版写成 te_x − X_TIP_A 把垂尾又向后推了 1.83 m（整机长变成 41.27 m，已实测踩过）。
    shift = X_TIP_A - te_x
    if abs(shift) < 1e-4:
        verbose("   垂尾后缘与尾锥末端齐平，无需移动")
        return
    for v in o.data.vertices:
        v.co.x += shift
    o.data.update()
    verbose("   垂尾后缘 %.2f → %.2f（前移 %.2f m，与尾锥末端 %.2f 齐平）"
            % (te_x, te_x + shift, shift, X_TIP_A))


# ---------------------------------------------------------------------------
# 发动机短舱：把"两组半截圆筒"合成一个连续旋成体
# ---------------------------------------------------------------------------
# 实测原状（2026-09-22）：一台发动机被拆成两组物件，直径还不一致 ——
#   AIRCRAFT_ROOT: Plane_Eng_L  X[-0.62,2.59] 直径 1.90 + Plane_EngIn_L (直径 2.10 的环)
#   AC_ROOT      : E_L           X[ 2.08,5.88] 直径 1.76 + E_LN (直径 1.90 的进气唇盘)
# 外表面沿轴向是 1.90 → 2.10 → 1.76 → 1.90 的**凹凸交替**，前段风扇罩比后段还细，
# 与真实涡扇短舱（最粗处在风扇罩、向后收成尾喷口）正好相反。
NAC_Y, NAC_Z = 5.55, -1.90          # 短舱轴线位置（右发；左发取 Y 负）
# (x, r) 从尾喷口到进气唇口；最后四站是唇口内卷，形成圆钝的进气唇。
# 唇口的卷边长度要够（≥0.12 m），否则从侧面看是一条"切边"而不是圆唇。
# 2026-09-24 批次1：最大半径 1.05→1.00（CFM56-5B 风扇罩更收敛），
# 轮廓保持 "尾喷 0.62 → 风扇罩 1.00 → 唇口 0.93"。
NAC_PROF = [
    (-0.62, 0.62), (-0.10, 0.72), (0.45, 0.85), (1.10, 0.95),
    (1.80, 1.00), (2.50, 1.00), (3.20, 1.00), (3.90, 0.995),
    (4.60, 0.97), (5.30, 0.945), (5.62, 0.945), (5.80, 0.94),
    (5.88, 0.92), (5.90, 0.885), (5.86, 0.855), (5.78, 0.83),
]
NACSEG = 32
# 尾喷锥（原 E_LX 在 X[1.53,2.43]、直径 0.97，位置在短舱**中部**内部；
# 真实尾喷锥应在尾喷口内，重新摆到尾端）
# 2026-09-24 批次1：拉长为更明显的收敛喷管（伸进短舱 ~0.95 m）+
# 尖头中心锥（E_LXSpike，尾端小锥，深色金属 M_Nozzle）。
NOZZLE_PROF = [(-0.60, 0.34), (-0.25, 0.40), (0.15, 0.46), (0.55, 0.50), (0.95, 0.53)]
NOZZLE_SEG = 24


def _nac_r(x):
    """短舱剖面半径插值（用于环带定位）。"""
    P = NAC_PROF
    if x <= P[0][0]:
        return P[0][1]
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
            return a[1] + (b[1] - a[1]) * t
    return P[-1][1]


def build_nacelles(verbose=print):
    # ★ 清理清单必须包含 **旧版短舱的所有零件**：
    #   E_LN/E_RN 是旧短舱的进气唇盘（直径 1.90、厚 0.40），漏删的话它会套在
    #   新短舱（唇口半径 0.945）外面形成一个错位套环 —— 实测踩过，
    #   截图里"发动机前面多出一截圆柱/发动机像脱开"就是它。
    drop(["Plane_Eng_L", "Plane_Eng_R", "Plane_EngIn_L", "Plane_EngIn_R",
          "E_LN", "E_RN"])
    # 批次2：短舱主体与吊挂改白漆（M_PaintWhite，与机身同族）；
    # 尾喷锥/中心锥仍 M_Nozzle 深色金属（下方 name.endswith("X") 分支），
    # 进气风扇盘仍 M_FanDark —— 按任务口径只换主体与吊挂。
    mat_eng = mat_paintwhite()
    made = 0
    for side, tag in ((-1, "L"), (1, "R")):
        yc = side * NAC_Y
        for name, prof, seg in ((f"E_{tag}", NAC_PROF, NACSEG),
                                (f"E_{tag}X", NOZZLE_PROF, NOZZLE_SEG)):
            if not bpy.data.objects.get(name):
                continue
            par = parent_of(name, "AC_ROOT")
            drop([name])
            secs = [[Vector((x, yc + r * math.sin(2 * math.pi * j / seg),
                             NAC_Z + r * math.cos(2 * math.pi * j / seg)))
                     for j in range(seg)] for (x, r) in prof]
            # 2026-09-24 批次1：CFM56 标志性**底部微扁** —— 下半弧（z < 轴线）
            # 向轴线压缩 0.90；上半夜保持圆。注意只压短舱壳体，不压尾喷锥。
            if name == f"E_{tag}":
                for sec in secs:
                    for v in sec:
                        if v.z < NAC_Z:
                            v.z = NAC_Z + (v.z - NAC_Z) * 0.90
            mat = mat_nozzle() if name.endswith("X") else mat_eng
            loft(name, secs, mat, par)
            made += 1
        # 尾喷中心锥：从喷管尾端（x=-0.60, r≈0.30）收到尖点（x=-0.82）
        par = parent_of(f"E_{tag}X", "AC_ROOT")
        drop([f"E_{tag}XSpike"])
        secs = [[Vector((-0.60, yc + 0.26 * math.sin(2 * math.pi * j / 16),
                         NAC_Z + 0.26 * math.cos(2 * math.pi * j / 16)))
                 for j in range(16)],
                [Vector((-0.82, yc, NAC_Z)) for j in range(16)]]
        loft(f"E_{tag}XSpike", secs, mat_nozzle(), par, cap_a=True, cap_b=True)
        # 进气风扇面：唇口内侧深色圆盘（看进去是深洞而非穿透机身/吊挂）。
        # 局部几何（原点在盘心、轴沿 X），左右发共享一份 mesh。
        nm = f"FanFace_{tag}"
        drop([nm])
        par_ff = parent_of(f"E_{tag}", "AC_ROOT")
        fv, ff = _cyl_geo((-0.03, 0, 0), (0.03, 0, 0), 0.86, 0.86, 28, cap=True)
        me = bpy.data.meshes.new(nm)
        me.from_pydata([tuple(v) for v in fv], [], ff)
        me.validate()
        _recalc_normals(me)
        me.materials.append(mat_fandark())
        _loc_obj(nm, me, mat_fandark(), par_ff, (5.70, yc, NAC_Z))
        made += 2
    # 吊挂：原 Plane_Pylon_* 只有 0.8 m 的一小块，前段吊挂 E_LP 又已删除，
    # 发动机前半段（x 1.4~5.9）完全悬空、看起来像"吊挂断了、短舱脱开"。
    # 重建为沿短舱长度的主吊挂：上端插进机翼下表面（翼下缘 z≈−0.54），
    # 下端包住短舱顶（短舱顶 z≈−0.85），纵向覆盖短舱大半段。
    # 批次2：吊挂与短舱同用白漆（原 M_PlaneGear 深灰会让"白短舱"断成两色）
    m_pyl = mat_paintwhite()
    for tag, sgn in (("L", -1.0), ("R", 1.0)):
        nm = "Plane_Pylon_" + tag
        par = parent_of(nm, "AC_ROOT")
        drop([nm])
        box_at(nm, Vector((2.45, sgn * NAC_Y, -0.86)), (3.70, 0.28, 0.68), m_pyl, par)
    verbose("   短舱重建 %d 件 + 吊挂重做 2 件（白漆短舱/吊挂、风扇罩 max r=1.00、"
            " 底部微扁 0.90、收敛尾喷+中心锥、风扇面深洞盘）" % made)
    return made


# ---------------------------------------------------------------------------
# 翼面：把等厚棱柱换成真翼型（NACA 四位厚度分布 + 2% 弯度）
# ---------------------------------------------------------------------------
def airfoil_loop(c, tc, n=14):
    """返回剖面闭合环 (ξ, η)：ξ 从 0（前缘）到 c（后缘），η 为厚度方向偏移。
    厚度用 NACA 四位公式：前缘圆钝、后缘尖锐；再叠 2% 弯度（m=0.02, p=0.4）。"""
    us = [0.5 * (1.0 - math.cos(math.pi * i / n)) for i in range(n + 1)]   # 余弦分布，前缘加密
    up, lo = [], []
    for u in us:
        yt = 5.0 * tc * (0.2969 * math.sqrt(u) - 0.1260 * u
                         - 0.3516 * u * u + 0.2843 * u ** 3 - 0.1036 * u ** 4)
        yc = (0.02 / 0.16) * (2 * 0.4 * u - u * u) if u < 0.4 else \
             (0.02 / 0.36) * (0.2 + 0.8 * u - u * u)
        up.append((u * c, c * (yc + yt)))
        lo.append((u * c, c * (yc - yt)))
    return up + list(reversed(lo[1:n]))          # 2n 点：上表面去、下表面回，前后缘各只取一次


def wing_sections(loop, x_le, z_c, y, up='z'):
    """把 2D 剖面环放到 3D：弦沿 −X（前缘在 +X），厚度沿 up。"""
    if up == 'z':
        return [Vector((x_le - xi, y, z_c + eta)) for (xi, eta) in loop]
    return [Vector((x_le - xi, y, z)) for (xi, eta) in loop]   # 由调用方给 z


def build_airfoil_surfaces(verbose=print):
    """机翼 / 平尾 / 垂尾：棱柱 → 翼型放样。

    原状：`tapered_slab` 只给 4 个平面角点沿厚度挤出 → 上下都是平面、前缘是直角，
    侧看就是一"板"。改后前缘圆钝、后缘收尖、厚度从根到尖渐薄。
    根/尖弦长、后掠角、上反角、安装位置全部沿用 Stage 2 的参数（不改变气动数据）。
    """
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    wing_m = bpy.data.materials.get("M_PlaneWing") or mat_body()
    tail_m = bpy.data.materials.get("M_PlaneTail") or mat_body()

    CR, CT = 5.6, 1.6
    HALF = D.WINGSPAN / 2.0
    Y_ROOT = D.FUS_DIA / 2.0
    sweep = math.radians(D.WING_SWEEP_DEG)
    dihed = math.radians(D.WING_DIHEDRAL_DEG)
    x_le0 = D.sx(D.WING_ROOT_LE_ST)
    z0 = -0.55
    TR, TT = 0.78, 0.18
    loop_n = 14

    def span_frac(ay):
        return (ay - Y_ROOT) / (HALF - Y_ROOT)

    made = 0
    for side, tag in ((-1, "L"), (1, "R")):
        drop([f"Plane_Wing_{tag}"])
        ys = [Y_ROOT + (HALF - Y_ROOT) * f for f in (0.0, 0.22, 0.45, 0.68, 0.86, 1.0)]
        secs = []
        for ay in ys:
            fr = span_frac(ay)
            c = CR + (CT - CR) * fr
            x_le = x_le0 - (ay - Y_ROOT) * math.tan(sweep)
            z_c = z0 + (ay - Y_ROOT) * math.tan(dihed)
            tc = (TR + (TT - TR) * fr) / c
            secs.append(wing_sections(airfoil_loop(c, tc, loop_n), x_le, z_c, side * ay))
        loft(f"Plane_Wing_{tag}", secs, wing_m, root)
        made += 1

    # 平尾：展长 12.45、根弦 3.6 / 尖弦 1.3、后掠 8°、上反 5°
    HS_HALF, HS_YR, HS_CR, HS_CT = 6.225, 1.20, 3.6, 1.3
    hs_x = D.sx(32.0)
    for side, tag in ((-1, "L"), (1, "R")):
        drop([f"Plane_HS_{tag}"])
        secs = []
        for f in (0.0, 0.3, 0.6, 1.0):
            ay = HS_YR + (HS_HALF - HS_YR) * f
            c = HS_CR + (HS_CT - HS_CR) * f
            x_le = hs_x - (ay - HS_YR) * math.tan(math.radians(8.0))
            z_c = 1.0 + (ay - HS_YR) * math.tan(math.radians(5.0))
            tc = (0.34 + (0.14 - 0.34) * f) / c
            secs.append(wing_sections(airfoil_loop(c, tc, 12), x_le, z_c, side * ay))
        loft(f"Plane_HS_{tag}", secs, tail_m, root)
        made += 1

    # 垂尾：厚度沿 Y，展向沿 Z；后缘落在尾锥末端（X_TIP_A）
    VS_CR, VS_CT = 6.3, 2.2
    z_lo, z_hi = 0.80, 6.40
    vs_x = X_TIP_A + VS_CR                     # 使后缘 = X_TIP_A
    drop(["Plane_VStab", "Plane_VStabTop"])
    secs = []
    for f in (0.0, 0.35, 0.7, 1.0):
        z = z_lo + (z_hi - z_lo) * f
        c = VS_CR + (VS_CT - VS_CR) * f
        x_le = vs_x - (z - z_lo) * math.tan(math.radians(28.0))
        tc = (0.35 + (0.15 - 0.35) * f) / c
        loop = airfoil_loop(c, tc, 12)
        secs.append([Vector((x_le - xi, -0.175 + eta, z)) for (xi, eta) in loop])
    loft("Plane_VStab", secs, tail_m, root)
    made += 1
    verbose("   翼面改为真翼型放样 %d 件（机翼根厚弦比 %.3f、尖 %.3f；前缘圆钝、后缘收尖）"
            % (made, TR / CR, TT / CT))
    return made


def build_wing_tanks(verbose=print):
    """翼内燃油箱：原来悬在翼下 ~0.8 m（箱体 Z[-1.56,-1.34]，而翼面 Z[-0.94,0.89]），
    从下方看就是"机翼下挂着一块青板"。改为按同一条机翼参数生成、嵌在翼盒内。"""
    CR, CT = 5.6, 1.6
    HALF = D.WINGSPAN / 2.0
    Y_ROOT = D.FUS_DIA / 2.0
    sweep = math.radians(D.WING_SWEEP_DEG)
    dihed = math.radians(D.WING_DIHEDRAL_DEG)
    x_le0 = D.sx(D.WING_ROOT_LE_ST)
    z0 = -0.55
    TR, TT = 0.78, 0.18
    made = 0
    for side, nm in ((-1, "FW_-1"), (1, "FW_1")):
        o = bpy.data.objects.get(nm)
        if not o:
            continue
        mat = o.data.materials[0] if o.data.materials else None
        par = o.parent
        drop([nm])
        secs = []
        for f in (0.06, 0.35, 0.70):
            ay = Y_ROOT + (HALF - Y_ROOT) * f
            c = CR + (CT - CR) * f
            x_le = x_le0 - (ay - Y_ROOT) * math.tan(sweep)
            z_c = z0 + (ay - Y_ROOT) * math.tan(dihed)
            t = (TR + (TT - TR) * f) * 0.42          # 占翼型厚度的 42%，确保在翼盒内
            u0, u1 = 0.28, 0.68                       # 弦向 28%~68%，避开前缘与襟翼
            xa, xb = x_le - u0 * c, x_le - u1 * c
            secs.append([Vector((xa, side * ay, z_c + t / 2)),
                         Vector((xb, side * ay, z_c + t / 2)),
                         Vector((xb, side * ay, z_c - t / 2)),
                         Vector((xa, side * ay, z_c - t / 2))])
        loft(nm, secs, mat, par)
        made += 1
    verbose("   翼内燃油箱嵌入翼盒 %d 件（弦向 28%%~68%%、厚度占翼型 42%%）" % made)
    return made


# ---------------------------------------------------------------------------
# 起落架重建模：减震支柱 + 扭力臂 + 双轮轮组（不再是柱状体 + 方块）
# ---------------------------------------------------------------------------
# 原状（实测）：`GN / GM1 / GM-1` 是**柱状体**，`GW11 / GW1-1 / GW-11 / GW-1-1 / GWN`
# 是**方块**，与机身/机翼之间**没有任何可见的连接结构** —— 侧视就是"几根棍子 + 几块砖
# 悬在飞机下面"。
# 重建为真实构型：
#   主起落架：支柱（外筒 + 内筒活塞，插进翼根/翼身整流罩）+ 扭力臂 + 轮轴 + **双轮**
#   前起落架：支柱（插进前机身）+ 扭力臂 + 轮轴 + **双轮**
# A320 参考量：主轮直径 1.13 m、前轮直径 0.71 m、主轮距 7.59 m（半 3.795）、
#              前轮位于站位 ~3.5 m、主轮位于站位 ~16.1 m（均来自 a320_data 的轮距自洽校验）。
GROUND_Z = -3.40                # 地面高度（与"不得穿地"硬约束同一基准）
R_MAIN_W = 0.565                # 主轮半径
R_NOSE_W = 0.355                # 前轮半径

# ★ 主/前起落架的站位必须与配载重心自洽，否则会出现物理上不可能的姿态。
#  历史（都踩过）：
#   ① 原模型主轮在站位 16.14 m —— 重心正常范围 17.67~18.43 m
#      → **重心永远在主轮之后**，三轮车式起落架的飞机早就尾坐了。
#   ② 改到 LEMAC+0.365×MAC ≈ 18.45 m —— 尾坐阈值贴住了包线后限 36%，
#      且正常前轮载荷只有 (18.45−18.27)/12.64 ≈ 1.4%，太轻，同样不合理。
#  本版按**前轮载荷**反推：三轮车式起落架前轮通常承担 8~10% 全重，取 9%：
#      Xmg = (LEMAC + 0.27×MAC) + 0.09×轮距 ≈ 18.05 + 1.14 ≈ 19.19 m（≈54% MAC）
#  于是：正常配载前轮载荷 7~8% ✓；尾坐阈值远在包线后限之后，只有"严重后重"才触发 ✓。
# 站位常量定义在 **a320_data.py**（唯一真源），导出脚本与视图侧共用同一份，
# 避免"几何一套、配载一套"的口径漂移。这里只做引用。
MG_STATION = D.MG_STATION                                           # ≈ 19.19 m
NG_STATION = D.NG_STATION                                           # ≈ 6.55 m
MG_X = D.NOSE_X - MG_STATION                                        # 模型 x ≈ -0.405
NG_X = D.NOSE_X - NG_STATION                                        # 模型 x ≈ 12.235
NOSE_LOAD_MAX = D.NOSE_LOAD_MAX
# 前轮载荷按站位算：NoseLoad = (Xmg − cg) / (Xmg − Xng)。
# 线路由载重滑块可达 —— 严重前重工况 cg≈17.2 m → 载荷 ≈16% > 15%。


def _ortho(ax):
    ax = ax.normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(ax.z) < 0.9 else Vector((0.0, 1.0, 0.0))
    u = ref.cross(ax).normalized()
    v = ax.cross(u).normalized()
    return u, v


def tube(name, p0, p1, r0, r1, n, mat, parent, stations=None):
    """沿 p0→p1 的回转体（r0→r1）。stations 可给 [(t, r), ...] 做多段轮廓（如轮胎鼓形）。"""
    ax = p1 - p0
    u, v = _ortho(ax)
    prof = stations or [(0.0, r0), (1.0, r1)]
    secs = []
    for t, r in prof:
        c = p0 + ax * t
        secs.append([c + (u * math.cos(2 * math.pi * j / n) + v * math.sin(2 * math.pi * j / n)) * r
                     for j in range(n)])
    return loft(name, secs, mat, parent)


def box_at(name, center, size, mat, parent):
    """轴对齐长方体（用于扭力臂这类小件）。"""
    sx, sy, sz = size
    verts = [Vector((x, y, z)) for x in (-sx / 2, sx / 2)
             for y in (-sy / 2, sy / 2) for z in (-sz / 2, sz / 2)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4),
             (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6)]
    me = bpy.data.meshes.new(name)
    me.from_pydata([(c.x, c.y, c.z) for c in
                    [center + Vector(v) for v in verts]], [], faces)
    me.validate()
    _recalc_normals(me)
    return _obj_from_existing(name, me, mat, parent)


def _wheel(name, axle, y0, y1, r, mat, parent):
    """一个轮胎：沿 Y 向的鼓形回转体（胎面外鼓、胎侧内收）。"""
    return tube(name, Vector((0, y0, 0)) + axle, Vector((0, y1, 0)) + axle, r, r, 20, mat, parent,
                stations=[(0.0, r * 0.62), (0.12, r * 0.96), (0.5, r),
                          (0.88, r * 0.96), (1.0, r * 0.62)])


def build_landing_gear(verbose=print):
    drop(["GN", "GWN", "GM1", "GM-1", "GW11", "GW1-1", "GW-11", "GW-1-1",
          "Plane_GN", "Plane_GM1", "Plane_GM-1"])
    # 注意 `_principled()` 返回的是 **BSDF 节点**，不是材质 ——
    # 直接把它当材质传给 materials.append() 会抛
    # `Function.material expected a Material type, not ShaderNodeBsdfPrincipled`（已踩）。
    ms = bpy.data.materials.get("M_GearStrut") or bpy.data.materials.new("M_GearStrut")
    _principled(ms, (0.30, 0.32, 0.36), rough=0.42, metal=0.90)
    mw = bpy.data.materials.get("M_GearWheel") or bpy.data.materials.new("M_GearWheel")
    _principled(mw, (0.10, 0.11, 0.13), rough=0.80, metal=0.05)
    m_strut, m_wh = ms, mw

    def leg(strut_name, wh_names, x, y, z_att, z_axle, r_wh, spr, par):
        """支柱 + 扭力臂 + 轮轴 + 双轮。z_att = 支柱顶端（插入机身/翼根），z_axle = 轮轴高度。"""
        # 外筒（上端粗）→ 内筒活塞（下端细）
        z_mid = z_att + (z_axle - z_att) * 0.42
        tube(strut_name + "_Cyl", Vector((x, y, z_att)), Vector((x, y, z_mid)),
             0.135, 0.115, 16, m_strut, par)
        tube(strut_name + "_Rod", Vector((x, y, z_mid - 0.05)), Vector((x, y, z_axle)),
             0.088, 0.078, 14, m_strut, par)
        # 扭力臂：两小段，接在支柱与轮轴之间（真实起落架的防扭结构）
        box_at(strut_name + "_Tq1", Vector((x - 0.10, y, (z_mid + z_axle) * 0.5)),
               (0.09, 0.07, abs(z_mid - z_axle) * 0.72), m_strut, par)
        box_at(strut_name + "_Tq2", Vector((x - 0.18, y, (z_mid + z_axle) * 0.5 + 0.06)),
               (0.07, 0.06, abs(z_mid - z_axle) * 0.52), m_strut, par)
        # 轮轴
        tube(strut_name + "_Axle", Vector((x, y - spr, z_axle)), Vector((x, y + spr, z_axle)),
             0.055, 0.055, 10, m_strut, par)
        # 双轮
        half = 0.115
        _wheel(wh_names[0], Vector((x, y - spr * 0.55, z_axle)), -half, half, r_wh, m_wh, par)
        _wheel(wh_names[1], Vector((x, y + spr * 0.55, z_axle)), -half, half, r_wh, m_wh, par)

    par_ac = bpy.data.objects.get("AC_ROOT")
    # 主起落架：支柱插到**机翼下表面**（|y|=3.795 处翼下缘 z≈−0.74，实测算出），
    #           站位用 MG_X（后梁附近）—— 重心正常范围在它之前，物理自洽。
    leg("GM1", ["GW11", "GW1-1"], MG_X, 3.795, -0.72, GROUND_Z + R_MAIN_W, R_MAIN_W, 0.30, par_ac)
    leg("GM-1", ["GW-11", "GW-1-1"], MG_X, -3.795, -0.72, GROUND_Z + R_MAIN_W, R_MAIN_W, 0.30, par_ac)
    # 前起落架：支柱插进**前机身**（NG_X 处机身下缘 z≈−1.83，由机身剖面算得）
    leg("GN", ["GWN", "GWN_B"], NG_X, 0.0, -1.85, GROUND_Z + R_NOSE_W, R_NOSE_W, 0.22, par_ac)
    verbose("   起落架重建模：主起 2×（支柱+扭力臂+双轮，|y|=3.795）、前起 1×（双轮）"
            "，轮底统一 %.2f m（地面）" % GROUND_Z)
    return True


# ---------------------------------------------------------------------------
# 批次 1 · 外观几何精修（2026-09-24）：只动几何与材质，不动 viewer
# ---------------------------------------------------------------------------
def _loft_geo(secs, cap_a=False, cap_b=False):
    """loft() 的几何数据版 (verts, faces)：一串等点数环放样。"""
    n = len(secs[0])
    verts = []
    for sec in secs:
        verts.extend(sec)
    faces = []
    for i in range(len(secs) - 1):
        a, b = i * n, (i + 1) * n
        for j in range(n):
            j2 = (j + 1) % n
            faces.append((a + j, a + j2, b + j2, b + j))
    if cap_a:
        faces.append(tuple(reversed(range(n))))
    if cap_b:
        base = (len(secs) - 1) * n
        faces.append(tuple(base + j for j in range(n)))
    return verts, faces


def _shift_geo(geo, off):
    """几何数据整体平移（拼组合件用）。"""
    v, f = geo
    off = Vector(off)
    return [p + off for p in v], f


def _flatten_bottom(verts, z_axis=0.0, k=0.90):
    """短舱底部微扁：z < 轴线处向轴线压缩（原地修改 verts 列表）。"""
    for v in verts:
        if v.z < z_axis:
            v.z = z_axis + (v.z - z_axis) * k


def _wing_section(fr):
    """展向分数 fr → (ay, c, x_le, z_c, tc)，与 build_airfoil_surfaces 同一套参数。"""
    CR, CT = 5.6, 1.6
    HALF = D.WINGSPAN / 2.0
    Y_ROOT = D.FUS_DIA / 2.0
    sweep = math.radians(D.WING_SWEEP_DEG)
    dihed = math.radians(D.WING_DIHEDRAL_DEG)
    x_le0 = D.sx(D.WING_ROOT_LE_ST)
    TR, TT = 0.78, 0.18
    ay = Y_ROOT + (HALF - Y_ROOT) * fr
    c = CR + (CT - CR) * fr
    x_le = x_le0 - (ay - Y_ROOT) * math.tan(sweep)
    z_c = -0.55 + (ay - Y_ROOT) * math.tan(dihed)
    tc = (TR + (TT - TR) * fr) / c
    return ay, c, x_le, z_c, tc


def _uplift(u, c, tc):
    """NACA 四位厚度 + 2% 弯度的上表面偏移（×c），与 airfoil_loop 同公式。"""
    yt = 5.0 * tc * (0.2969 * math.sqrt(u) - 0.1260 * u
                     - 0.3516 * u * u + 0.2843 * u ** 3 - 0.1036 * u ** 4)
    yc = (0.02 / 0.16) * (2 * 0.4 * u - u * u) if u < 0.4 else \
         (0.02 / 0.36) * (0.2 + 0.8 * u - u * u)
    return c * (yc + yt)


def _chord_ribbon(x_le, c, z_c, tc, ay, u0, u1, side, n=8, span_w=0.05,
                  float_=0.010, thick=0.012):
    """上表面弦向贴面细条（舵面铰链线/扰流板刻线）的几何数据。
    沿弦向采样 NACA 上表面，顶面外浮 float_、厚 thick；span_w 为展向宽度。
    四排点：顶面前/后缘 + 底面前/后缘，闭合。"""
    def samp(u, y):
        return Vector((x_le - u * c, y, z_c + _uplift(u, c, tc)))
    yF = side * (ay - span_w * 0.5)
    yB = side * (ay + span_w * 0.5)
    topF = [samp(u0 + (u1 - u0) * i / n, yF) + Vector((0, 0, float_)) for i in range(n + 1)]
    topB = [samp(u0 + (u1 - u0) * i / n, yB) + Vector((0, 0, float_)) for i in range(n + 1)]
    botF = [p - Vector((0, 0, thick)) for p in topF]
    botB = [p - Vector((0, 0, thick)) for p in topB]
    verts = topF + topB + botF + botB
    m = n + 1
    faces = []
    for i in range(n):
        faces.append((i, i + 1, m + i + 1, m + i))                      # 顶
        faces.append((2 * m + i, 3 * m + i, 3 * m + i + 1, 2 * m + i + 1))  # 底
        faces.append((i, 2 * m + i, 2 * m + i + 1, i + 1))              # 前缘墙
        faces.append((m + i, m + i + 1, 3 * m + i + 1, 3 * m + i))      # 后缘墙
    faces.append((0, m, 3 * m, 2 * m))                                  # 两端
    faces.append((n, 2 * m + n, 3 * m + n, m + n))
    return verts, faces


def _wing_line(tag, fr, u0, u1, side, span_w=0.05):
    """机翼上表面弦向刻线：与 build_airfoil_surfaces 同一套翼型公式定位。"""
    ay, c, x_le, z_c, tc = _wing_section(fr)
    return _chord_ribbon(x_le, c, z_c, tc, ay, u0, u1, side,
                         span_w=span_w)


def build_winglet_fences(verbose=print):
    """翼尖 fence 重做：A320-200 经典构型 = 翼尖上、下各一片小 fence
    （替换 stage2_shape 留下的单竖板 Plane_Winglet_L/R）。
    上片高 1.0、下片 0.55，弦 1.3、后掠 30°，厚度沿 Y；点缀色。"""
    from stage2_shape import tapered_slab
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    m_acc = mat_accent()
    HALF = D.WINGSPAN / 2.0
    Y_ROOT = D.FUS_DIA / 2.0
    sweep = math.radians(D.WING_SWEEP_DEG)
    dihed = math.radians(D.WING_DIHEDRAL_DEG)
    x_le0 = D.sx(D.WING_ROOT_LE_ST)
    tip_le = x_le0 - (HALF - Y_ROOT) * math.tan(sweep)
    z_tip = -0.55 + (HALF - Y_ROOT) * math.tan(dihed)
    sw = math.tan(math.radians(30.0))
    drop(["Plane_Winglet_L", "Plane_Winglet_R", "Plane_WingletLo_L", "Plane_WingletLo_R"])
    for side, tag in ((-1, "L"), (1, "R")):
        y_t = side * HALF
        base = Vector((tip_le - 0.30, y_t, z_tip + 0.02))
        # 上 fence：高 1.0，前后缘同步后掠（平行四边形）
        tapered_slab(f"Plane_Winglet_{tag}",
                     base, base + Vector((-1.30, 0, 0)),
                     base + Vector((-1.00 * sw, 0, 1.00)),
                     base + Vector((-1.30 - 1.00 * sw, 0, 1.00)),
                     0.16, 0.09, 'y', m_acc, root)
        # 下 fence：高 0.55，微向前倾（A320 下 fence 略前扣）
        blo = base + Vector((0.06, 0, -0.02))
        tapered_slab(f"Plane_WingletLo_{tag}",
                     blo, blo + Vector((-1.10, 0, 0)),
                     blo + Vector((+0.30 * sw, 0, -0.55)),
                     blo + Vector((-1.10 + 0.30 * sw, 0, -0.55)),
                     0.14, 0.08, 'y', m_acc, root)
    verbose("   翼尖 fence 重做：上 1.0 m + 下 0.55 m ×2，后掠 30°，点缀色")
    return True


def build_control_lines(verbose=print):
    """舵面刻线（贴面细条，深色）+ 航行灯。
    机翼每侧：副翼铰链 1（外段后缘）、襟翼铰链 2（内段后缘）、扰流板 4（上表面前中段）；
    平尾升降舵铰链 1/侧；垂尾方向舵铰链 1。上表面用与 build_airfoil_surfaces
    同一套 NACA 公式定位。"""
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    m_line = mat_outline()
    made = 0
    for side, tag in ((-1, "L"), (1, "R")):
        sfx = "L" if side < 0 else "R"
        # 副翼铰链：外段（fr 0.80）后缘 u 0.70~0.77
        gv, gf = _wing_line(sfx, 0.80, 0.70, 0.77, side, span_w=0.06)
        mk_obj(f"WingLine{sfx}_Ail", gv, gf, m_line, root, smooth=False)
        made += 1
        # 襟翼铰链 2：内段（fr 0.30 / 0.52）后缘
        for i, fr in enumerate((0.30, 0.52), 1):
            gv, gf = _wing_line(sfx, fr, 0.68, 0.74, side, span_w=0.06)
            mk_obj(f"WingLine{sfx}_Flap{i}", gv, gf, m_line, root, smooth=False)
            made += 1
        # 扰流板 4：上表面前中段 u 0.42~0.60
        for i, fr in enumerate((0.18, 0.32, 0.46, 0.60), 1):
            gv, gf = _wing_line(sfx, fr, 0.42, 0.60, side, span_w=0.34)
            mk_obj(f"Spoiler_{sfx}_{i}", gv, gf, m_line, root, smooth=False)
            made += 1
    # 平尾升降舵铰链：fr 0.55，u 0.82~0.88（HS 参数与 build_airfoil_surfaces 一致）
    HS_HALF, HS_YR, HS_CR, HS_CT = 6.225, 1.20, 3.6, 1.3
    hs_x = D.sx(32.0)
    for side, tag in ((-1, "L"), (1, "R")):
        f = 0.55
        ay = HS_YR + (HS_HALF - HS_YR) * f
        c = HS_CR + (HS_CT - HS_CR) * f
        x_le = hs_x - (ay - HS_YR) * math.tan(math.radians(8.0))
        z_c = 1.0 + (ay - HS_YR) * math.tan(math.radians(5.0))
        tc = (0.34 + (0.14 - 0.34) * f) / c
        gv, gf = _chord_ribbon(x_le, c, z_c, tc, ay, 0.82, 0.88, side, span_w=0.06)
        mk_obj(f"WingLine{'L' if side < 0 else 'R'}_Elev", gv, gf, m_line, root,
               smooth=False)
        made += 1
    # 垂尾方向舵铰链：ξ≈0.78 弦长处竖向细条（z 1.3~5.7），
    # 板厚随当地翼厚贴住垂尾两侧面（+0.008 外浮），不贯穿悬空
    VS_CR, VS_CT = 6.3, 2.2
    z_lo, z_hi = 0.80, 6.40
    vs_x = X_TIP_A + VS_CR
    t2, b2 = [], []
    for i in range(13):
        z = 1.3 + (5.7 - 1.3) * i / 12
        frz = (z - z_lo) / (z_hi - z_lo)
        c = VS_CR + (VS_CT - VS_CR) * frz
        x_le = vs_x - (z - z_lo) * math.tan(math.radians(28.0))
        x = x_le - 0.78 * c
        t_half = (0.35 + (0.15 - 0.35) * frz) * 0.5 + 0.008
        t2.append(Vector((x, -0.175 + t_half, z)))
        b2.append(Vector((x, -0.175 - t_half, z)))
    verts = t2 + b2
    faces = [(i, i + 1, 13 + i + 1, 13 + i) for i in range(12)]
    faces.append(tuple(reversed(range(13))))
    faces.append(tuple(13 + i for i in range(13)))
    mk_obj("RudderHinge", verts, faces, m_line, root, smooth=False)
    made += 1
    # 航行灯：翼尖 左红/右绿 + 垂尾顶白（小圆球 r=0.06，rough 0.3 带自发光感）
    HALF = D.WINGSPAN / 2.0
    Y_ROOT = D.FUS_DIA / 2.0
    sweep = math.radians(D.WING_SWEEP_DEG)
    dihed = math.radians(D.WING_DIHEDRAL_DEG)
    tip_le = D.sx(D.WING_ROOT_LE_ST) - (HALF - Y_ROOT) * math.tan(sweep)
    z_tip = -0.55 + (HALF - Y_ROOT) * math.tan(dihed)
    sv, sf = _sphere_geo(0.06)
    for nm, mat, loc in (
            ("NavLight_L", mat_nav("M_NavRed", (0.6, 0.05, 0.05)),
             (tip_le - 0.55, -(HALF - 0.06), z_tip + 0.03)),
            ("NavLight_R", mat_nav("M_NavGreen", (0.05, 0.5, 0.1)),
             (tip_le - 0.55, (HALF - 0.06), z_tip + 0.03)),
            ("NavLight_T", mat_nav("M_NavWhite", (0.92, 0.92, 0.88)),
             (vs_x - (z_hi - z_lo) * math.tan(math.radians(28.0)) - 1.1, -0.175, z_hi + 0.05))):
        me = bpy.data.meshes.new(nm)
        me.from_pydata([tuple(v) for v in sv], [], sf)
        me.validate()
        _recalc_normals(me)
        me.materials.append(mat)
        _loc_obj(nm, me, mat, root, loc)
        made += 1
    verbose("   舵面刻线 %d 条（副翼/襟翼×2/扰流板×4/升降舵/方向舵）+ 航行灯 3 个" % made)
    return made


def _blade_geo(chord=0.40, h=0.22, th=0.024):
    """VHF 刀片天线局部几何：顺航向竖直刀片（X-Z 平面四边形，Y 向厚度）。"""
    xz = [(0.0, 0.0), (chord, 0.0), (chord * 0.72, h), (chord * 0.20, h)]
    verts = [Vector((x, -th / 2, z)) for x, z in xz] + [Vector((x, th / 2, z)) for x, z in xz]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
             (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return verts, faces


def build_nose_details(verbose=print):
    """机头/机身小件（全部局部几何共享，L/R 同 mesh 只设 location）：
    雷达罩缝线、皮托管×2、攻角传感器×2、VHF 刀片×3、GPS 贴片×2、排水口×2。"""
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    made = 0
    # —— 雷达罩缝线：机头 ogive 站位 1.0~1.2 一圈窄带（机身色略深）——
    drop([o.name for o in list(bpy.data.objects) if o.name.startswith("Mark_Radome")])
    m_rd = bpy.data.materials.get("M_Radome") or bpy.data.materials.new("M_Radome")
    _principled(m_rd, (0.66, 0.70, 0.76), rough=0.55, metal=0.0)
    panel("Mark_Radome", D.sx(1.2), D.sx(1.0), -math.pi, math.pi, 2, NSEG, 0.006, 0.012,
          m_rd, root)
    made += 1
    # —— 皮托管 ×2：站位 ~3.5、周向略低于腰线的小 L 形圆柱 ——
    # 机身在站位 3.5 处仍在 ogive 锥面上（向前半径每 0.38 m 收 ~0.05），
    # 探管若严格水平会"悬空" —— 让探管随锥面下斜 0.06，并加安装底座垫。
    drop([o.name for o in list(bpy.data.objects) if o.name.startswith("Pitot_")])
    pitot_geo = _combine_geos([
        _cyl_geo((0, 0, -0.01), (0.38, 0, -0.06), 0.022, 0.018, 12),
        _shift_geo(_cyl_geo((0, 0, -0.05), (0, 0, 0.0), 0.042, 0.030, 12), (0.02, 0, 0)),
        _shift_geo(_cyl_geo((0, 0, -0.06), (0, 0, 0.05), 0.014, 0.012, 10), (0.33, 0, 0)),
    ])
    me = bpy.data.meshes.new("Pitot_shaft")
    me.from_pydata([tuple(v) for v in pitot_geo[0]], [], pitot_geo[1])
    me.validate()
    _recalc_normals(me)
    me.materials.append(mat_nozzle())
    th = math.radians(63.0)
    for side, tag in ((-1, "L"), (1, "R")):
        p = surface_pt(D.sx(3.5), side * th, 0.01)
        _loc_obj(f"Pitot_{tag}", me, mat_nozzle(), root, p)
        made += 1
    # —— 攻角传感器 ×2：小圆柱 + 小翼片（同样随锥面微斜 + 底座垫）——
    drop([o.name for o in list(bpy.data.objects) if o.name.startswith("Aoa_")])
    aoa_geo = _combine_geos([
        _cyl_geo((0, 0, -0.005), (0.14, 0, -0.025), 0.028, 0.024, 12),
        _shift_geo(_cyl_geo((0, 0, -0.03), (0, 0, 0.0), 0.045, 0.032, 12), (0.02, 0, 0)),
        _shift_geo(_box_geo(0.09, 0.012, 0.08), (0.12, 0, 0.045)),
    ])
    me = bpy.data.meshes.new("Aoa_body")
    me.from_pydata([tuple(v) for v in aoa_geo[0]], [], aoa_geo[1])
    me.validate()
    _recalc_normals(me)
    me.materials.append(mat_nozzle())
    th = math.radians(68.0)
    for side, tag in ((-1, "L"), (1, "R")):
        p = surface_pt(D.sx(4.4), side * th, 0.01)
        _loc_obj(f"Aoa_{tag}", me, mat_nozzle(), root, p)
        made += 1
    # —— VHF 刀片天线 ×3（背部 2 @ st 9/16，腹部 1 @ st 28）+ GPS 贴片 ×2 ——
    drop([o.name for o in list(bpy.data.objects) if o.name.startswith("Ant_")])
    bv, bf = _blade_geo()
    me_blade = bpy.data.meshes.new("Ant_vhf")
    me_blade.from_pydata([tuple(v) for v in bv], [], bf)
    me_blade.validate()
    _recalc_normals(me_blade)
    me_blade.materials.append(mat_nozzle())
    for st in (9.0, 16.0):
        _loc_obj(f"Ant_VHF_{int(st)}", me_blade, mat_nozzle(), root,
                 surface_pt(D.sx(st), 0.0, 0.005))
        made += 1
    _loc_obj("Ant_VHF_28", me_blade, mat_nozzle(), root,
             surface_pt(D.sx(28.0), math.pi, 0.005), rot=(math.pi, 0, 0))
    made += 1
    gv, gf = _cyl_geo((0, 0, 0), (0, 0, 0.035), 0.10, 0.10, 20)
    me_gps = bpy.data.meshes.new("Ant_gps")
    me_gps.from_pydata([tuple(v) for v in gv], [], gf)
    me_gps.validate()
    _recalc_normals(me_gps)
    me_gps.materials.append(mat_nozzle())
    for i, st in enumerate((5.8, 7.2), 1):
        _loc_obj(f"Ant_GPS_{i}", me_gps, mat_nozzle(), root,
                 surface_pt(D.sx(st), 0.0, 0.008))
        made += 1
    # —— 排水口 ×2：腹部小锥（st 12 / 20）——
    drop([o.name for o in list(bpy.data.objects) if o.name.startswith("Drain_")])
    dv, df = _cyl_geo((0, 0, 0), (0, 0, -0.15), 0.035, 0.012, 10)
    me_drain = bpy.data.meshes.new("Drain_cone")
    me_drain.from_pydata([tuple(v) for v in dv], [], df)
    me_drain.validate()
    _recalc_normals(me_drain)
    me_drain.materials.append(mat_outline())
    for i, st in enumerate((12.0, 20.0), 1):
        _loc_obj(f"Drain_{i}", me_drain, mat_outline(), root,
                 surface_pt(D.sx(st), math.pi, 0.01))
        made += 1
    verbose("   机头/机身细节 %d 件：雷达罩缝线、皮托管×2、AoA×2、VHF×3、GPS×2、排水×2"
            % made)
    return made


def _text_mesh(name, text, size, font=None, extrude=0.008):
    """FONT 曲线求值为网格（背景模式安全，不用 bpy.ops.convert）。"""
    cu = bpy.data.curves.new(name + "_c", 'FONT')
    cu.body = text
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = 0.0
    if font:
        cu.font = font
    ob = bpy.data.objects.new(name + "_t", cu)
    bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(ob, do_unlink=True)
    me.name = name
    _recalc_normals(me)
    return me


def _surface_basis(th):
    """机身表面定向基（th 处）：right(沿机头) / up / outward normal。"""
    from mathutils import Matrix
    n = Vector((0.0, math.sin(th), math.cos(th)))
    zup = Vector((0.0, 0.0, 1.0))
    up = (zup - n * zup.dot(n)).normalized()
    right = up.cross(n).normalized()
    return Matrix((right, up, n)).transposed()


def build_markings(verbose=print):
    """标识 MARKINGS（脱敏红线：绝不出现真实航司）：
    注册号 B-XXXX1（后机身两侧）、titles「教学航空」（前机身两侧、腰线以上，
    CJK 字体加载失败时回退拉丁 JIAOXUE AIR）、垂尾整面贴附点缀面板。"""
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    m_dark = bpy.data.materials.get("M_MarkDark") or bpy.data.materials.new("M_MarkDark")
    _principled(m_dark, (0.08, 0.09, 0.11), rough=0.60, metal=0.0)
    m_acc = mat_accent()
    made = 0
    drop([o.name for o in list(bpy.data.objects)
          if o.name.startswith(("Mark_Reg_", "Mark_Title_", "LogoTail_", "NacBand_"))])
    # —— 注册号 B-XXXX1：站位 ~30、周向 ±80° ——
    x = D.sx(30.0)
    for side, tag in ((-1, "L"), (1, "R")):
        th = side * math.radians(80.0)
        me = _text_mesh(f"Mark_Reg_{tag}", "B-XXXX1", 0.30)
        me.materials.append(m_dark)
        o = _loc_obj(f"Mark_Reg_{tag}", me, m_dark, root,
                     surface_pt(x, th, 0.03), rot=_surface_basis(th).to_euler())
        made += 1
    # —— 前机身 titles：站位 ~5.5，腰线以上（字底 z≈0.62、字高 0.45、顶≈1.07）——
    try:
        fnt = bpy.data.fonts.load(r"C:\Windows\Fonts\msyh.ttc")
        title = "教学航空"
    except Exception:
        fnt = None
        title = "JIAOXUE AIR"
    x = D.sx(5.5)
    for side, tag in ((-1, "L"), (1, "R")):
        th = side * math.radians(64.5)      # 锚点 z≈0.845（字中心），随表面法线定向
        me = _text_mesh(f"Mark_Title_{tag}", title, 0.45, font=fnt)
        me.materials.append(m_acc)
        _loc_obj(f"Mark_Title_{tag}", me, m_acc, root,
                 surface_pt(x, th, 0.03), rot=_surface_basis(th).to_euler())
        made += 1
    # —— 垂尾点缀面板：按 build_airfoil_surfaces 同一套垂尾剖面
    #    （z 0.80~6.40、弦 6.3→2.2、后掠 28°、厚度沿 Y），
    #    平面形状四边各内缩 0.18 m 的贴面薄板（厚 0.02、外浮 0.012），
    #    y 两侧表面各一。纯色、贴合、不悬浮（批次2 重做，替换碎三角方案）——
    VS_CR, VS_CT = 6.3, 2.2
    z_lo, z_hi = 0.80, 6.40
    vs_x = X_TIP_A + VS_CR
    INS = 0.18

    def fin_rows(sgn, out, nz=12):
        rows = []
        for i in range(nz + 1):
            z = z_lo + INS + (z_hi - z_lo - 2 * INS) * i / nz
            frz = (z - z_lo) / (z_hi - z_lo)
            c = VS_CR + (VS_CT - VS_CR) * frz
            x_le = vs_x - (z - z_lo) * math.tan(math.radians(28.0))
            t_half = (0.35 + (0.15 - 0.35) * frz) * 0.5
            y = -0.175 + sgn * (t_half + out)
            rows.append([Vector((x_le - INS, y, z)),
                         Vector((x_le - c + INS, y, z))])
        return rows

    for sgn, tag in ((1, "R"), (-1, "L")):
        ro = fin_rows(sgn, 0.012)
        ri = fin_rows(sgn, 0.012 - 0.020)
        lv, lf = _band_geo(ro, ri)
        mk_obj(f"LogoTail_{tag}", lv, lf, m_acc, root, smooth=False)
        made += 1
    verbose("   标识 %d 件：注册号 B-XXXX1×2、titles「%s」×2（腰线以上）、垂尾点缀面板×2"
            % (made, title))
    return made


def build_apu_exhaust(verbose=print):
    """APU 排气口：尾椎末端下方短圆筒（深灰金属）+ 内凹格栅盘。
    （经探查，现状尾椎末端无独立 APU 旧件 —— x<-17 仅有 Plane_TailCone 本身，
      故无旧件可删，直接新增。）"""
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    drop([o.name for o in list(bpy.data.objects) if o.name.startswith("APU_")])
    tube("APU_Exhaust", Vector((-18.42, -0.15, 0.30)), Vector((-18.84, -0.15, 0.20)),
         0.12, 0.115, 16, mat_nozzle(), root)
    gv, gf = _cyl_geo((0, 0, 0), (-0.05, 0, -0.005), 0.10, 0.10, 16)
    me = bpy.data.meshes.new("APU_grille")
    me.from_pydata([tuple(v) for v in gv], [], gf)
    me.validate()
    _recalc_normals(me)
    me.materials.append(mat_fandark())
    _loc_obj("APU_Grille", me, mat_fandark(), root, (-18.80, -0.15, 0.205))
    verbose("   APU 排气口：尾椎末端短圆筒 + 格栅盘（深灰金属/深洞盘）")
    return True


def build_gear_doors(verbose=print):
    """起落架舱门：主起舱门 GearDoor_ML/MR（翼根腹部 |y|≈3.795、MG_X 前后各一）、
    前起舱门 NoseGearDoor_L/R（前机身腹部 NG_X 两侧）。薄板门片共享几何。"""
    root = bpy.data.objects.get("AIRCRAFT_ROOT")
    m_body = mat_body()
    drop([o.name for o in list(bpy.data.objects)
          if o.name.startswith(("GearDoor_", "NoseGearDoor_"))])
    bv, bf = _box_geo(1.60, 0.70, 0.035)
    me_main = bpy.data.meshes.new("GearDoor_mesh")
    me_main.from_pydata([tuple(v) for v in bv], [], bf)
    me_main.validate()
    _recalc_normals(me_main)
    me_main.materials.append(m_body)
    for side, tag in ((-1, "L"), (1, "R")):
        for i, dx in enumerate((-1.05, 0.55), 1):
            # 门片随翼下表面外倾（dihedral 5.1°），嵌贴而非悬空
            _loc_obj(f"GearDoor_M{tag}{i}", me_main, m_body, root,
                     (MG_X + dx, side * 3.795, -0.76),
                     rot=(side * math.radians(5.1), 0, 0))
    nv, nf = _box_geo(0.85, 0.42, 0.030)
    me_nose = bpy.data.meshes.new("NoseGearDoor_mesh")
    me_nose.from_pydata([tuple(v) for v in nv], [], nf)
    me_nose.validate()
    _recalc_normals(me_nose)
    me_nose.materials.append(m_body)
    for side, tag in ((-1, "L"), (1, "R")):
        _loc_obj(f"NoseGearDoor_{tag}", me_nose, m_body, root,
                 (NG_X + 0.55, side * 0.40, -1.925))
    verbose("   起落架舱门：主起 4 片（|y|=3.795）+ 前起 2 片（共享几何 2 份）")
    return True


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def refine(verbose=print):
    """按顺序施加全部外观修正。**只能有一个定义** ——
    踩过：文件里曾同时存在两个同名 refine()，后者覆盖前者，
    导致 build_doors_windows / check_skin_fit 写了却没被调用。"""
    verbose("--- 机体精修（参数化旋成体）---")
    verbose("   半径剖面：%d 个站点，机身半径 %.3f m（FUS_DIA %.2f）"
            % (len(STATIONS), R_BODY, D.FUS_DIA))
    verbose("   整机长 %.2f m（机头 %+.2f → 尾端 %+.2f）"
            % (X_TIP_F - X_TIP_A, X_TIP_F, X_TIP_A))
    # ① 机头那根黄线 = `DatumBar`（ANNO_SCALE 组，8.5 m 长 / 0.08 m 粗的 DATUM
    #    站位基准杆，锚在机头尖端 x=18.78）。用户要求删除。
    #    注意保留 `T_Dat` 那条文字（"DATUM 机头 FS=0"）—— 它才是基准的定义说明。
    drop(["DatumBar"])
    # ② 短舱前端多余模块：原 `E_LP` / `E_RP` 是**前段吊挂块**，浮在短舱前上方，
    #    而吊挂已由 `Plane_Pylon_L/R` 完整表示 —— 它是重复件，删掉。
    drop(["E_LP", "E_RP"])

    build_body(verbose)          # 机头锥 + 等径段 + 尾锥（同一条剖面，无台阶）
    build_shell(verbose)         # 上壳体跟随机身收细
    build_cockpit_glass(verbose) # 驾驶舱风挡：A320 六块分窗 + 黑框
    build_airfoil_surfaces(verbose)  # 机翼/平尾/垂尾改为真翼型
    fix_vertical_stab(verbose)   # 翼型重建后复核垂尾后缘与尾锥末端齐平
    build_nacelles(verbose)      # 短舱：剖面收敛/底部微扁/尾喷锥/风扇面深洞
    unify_body_colors(verbose)   # 机身/翼面/尾翼统一近白（现代极简）
    build_winglet_fences(verbose)    # 翼尖 fence：上 1.0 m + 下 0.55 m，点缀色
    build_control_lines(verbose)     # 舵面刻线 + 航行灯
    build_nose_details(verbose)      # 雷达罩缝线/皮托管/AoA/天线/排水
    build_markings(verbose)          # 注册号/titles/垂尾 Logo/短舱环带
    build_apu_exhaust(verbose)       # 尾椎末端 APU 排气口
    build_gear_doors(verbose)        # 主起/前起舱门
    build_landing_gear(verbose)  # 起落架重建模：支柱 + 扭力臂 + 双轮
    build_doors_windows(verbose) # 门/窗/腰线改为贴面曲板 + 门轮廓/门观察窗
    build_wing_tanks(verbose)    # 翼内燃油箱嵌回翼盒
    check_skin_fit(verbose)      # 复核贴面
    return True


if __name__ == "__main__":
    refine()

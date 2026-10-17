# -*- coding: utf-8 -*-
"""楔缝网格归属探查：对每个采样点找最小外飘面片及其对象/材质/法向。"""
import bpy
import math
import os
import sys
from mathutils import Vector

SP = os.path.dirname(os.path.abspath(__file__))
if SP not in sys.path:
    sys.path.insert(0, SP)
ROOT = os.path.dirname(SP)
MID = os.path.join(ROOT, "output", "stage1", "配载平衡教学模型.stage1.blend")
bpy.ops.wm.open_mainfile(filepath=MID)
import stage2_refine as R

objs = [bpy.data.objects[n] for n in
        ("CockpitGlass_W_R", "CockpitGlass_WF_R", "CockpitGlass_Base_R",
         "CockpitGlass_S_R", "CockpitGlass_SF_R",
         "CockpitGlass_A_R", "CockpitGlass_AF_R",
         "CockpitGlass_PillarA_R", "CockpitGlass_PillarC_R", "CockpitGlass_Seam_R")
        if bpy.data.objects.get(n)]

mesh_cache = {}
def top_face(px, py, pz):
    best = None
    for o in objs:
        me = mesh_cache.get(o.name)
        if me is None:
            me = [(o.matrix_world @ p.co).copy() for p in o.data.vertices]
            mesh_cache[o.name] = me
        vs = me
        for poly in o.data.polygons:
            if len(poly.vertices) < 3:
                continue
            pts = [vs[i] for i in poly.vertices]
            n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            ln = n.length
            if ln < 1e-12:
                continue
            n /= ln
            d = n.dot(Vector((px, py, pz)) - pts[0])
            if abs(d) > 0.02:
                continue
            # 射线竖直（Z）与面求交：找覆盖该 (x,y) 且 z 最高处 < 采样点的面
            if abs(n.z) < 0.05:
                continue
            # 平面方程 z at (px,py)
            if abs(n.z) < 1e-9:
                continue
            t = (Vector((px, py, 0)) - Vector((pts[0].x, pts[0].y, 0)))
            z_at = pts[0].z - (n.x * (px - pts[0].x) + n.y * (py - pts[0].y)) / n.z
            if z_at > pz + 0.05 or z_at < pz - 0.60:
                continue
            # 重心法判断 (px,py) 是否在面内（投影到 XY）
            inside = False
            q = (px, py)
            pp = [(v.x, v.y) for v in pts]
            j = len(pp) - 1
            for i in range(len(pp)):
                xi, yi = pp[i]
                xj, yj = pp[j]
                if ((yi > q[1]) != (yj > q[1])) and \
                   (q[0] < (xj - xi) * (q[1] - yi) / (yj - yi + 1e-15) + xi):
                    inside = not inside
                j = i
            if not inside:
                continue
            mat = o.data.materials[poly.material_index].name if o.data.materials else "-"
            key = (round(z_at, 3), o.name, mat, round(n.z, 2))
            if best is None or z_at > best[0]:
                best = key
    return best

print("st    yl   | skin_z  top_z  owner")
for st, yl in [(1.47, 0.10), (1.47, 0.18), (1.47, 0.26), (1.49, 0.14),
               (1.45, 0.14), (1.51, 0.14), (1.47, 0.34)]:
    x = R.D.NOSE_X - st
    th = math.asin(yl / R.interp(x)[1])
    p = R.surface_pt(x, th, 0.0)
    ry, rz, zo = R.interp(p.x)
    skin = math.sqrt(p.y ** 2 + (p.z - zo) ** 2)
    top = top_face(p.x, p.y, p.z + 0.05)
    print("%.2f %.2f | z=%.3f r=%.3f  %s" % (st, yl, p.z, skin, top))
print("OWNER_PROBE_DONE")

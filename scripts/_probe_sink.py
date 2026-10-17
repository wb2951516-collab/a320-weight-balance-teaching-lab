# -*- coding: utf-8 -*-
"""量化检查：风挡玻璃各顶点的蒙皮外飘量 + 前缘盒内面片法向朝内数。"""
import bpy
from mathutils import Vector
import math
import os
import sys

SP = os.path.dirname(os.path.abspath(__file__))
if SP not in sys.path:
    sys.path.insert(0, SP)

ROOT = os.path.dirname(SP)
MID = os.path.join(ROOT, "output", "stage1", "配载平衡教学模型.stage1.blend")
bpy.ops.wm.open_mainfile(filepath=MID)

import stage2_refine as R

worst = (0.0, "")
for nm in ("CockpitGlass_W_R", "CockpitGlass_S_R", "CockpitGlass_A_R",
           "CockpitGlass_Base_R"):
    o = bpy.data.objects.get(nm)
    if not o:
        continue
    for v in o.data.vertices:
        p = o.matrix_world @ v.co
        ry, rz, zo = R.interp(p.x)
        sr = math.sqrt((p.y / ry) ** 2 + ((p.z - zo) / rz) ** 2)
        off = (sr - 1.0) * min(ry, rz)
        if off < worst[0]:
            worst = (off, "%s@(%.2f,%.2f,%.2f)" % (nm, p.x, p.y, p.z))
print("WORST_SINK %.4f m  %s" % worst)

# 前缘关注盒内、法向朝内（n·radial < 0）的面片计数
BOX = (16.9, 18.0, 0.15, 1.2, 1.0, 1.60)
for nm in ("CockpitGlass_W_R", "CockpitGlass_Base_R", "CockpitGlass_WF_R"):
    o = bpy.data.objects.get(nm)
    if not o:
        continue
    inward = 0
    for p in o.data.polygons:
        c = o.matrix_world @ p.center
        x0, x1, y0, y1, z0, z1 = BOX
        if not (x0 <= c.x <= x1 and y0 <= c.y <= y1 and z0 <= c.z <= z1):
            continue
        n = o.matrix_world.to_3x3() @ p.normal
        ry, rz, zo = R.interp(c.x)
        rad = Vector((0, c.y / ry, (c.z - zo) / rz))
        if rad.length > 1e-6 and n.dot(rad.normalized()) < -0.2:
            inward += 1
    print("INWARD %s: %d" % (nm, inward))
print("SINK_PROBE_DONE")

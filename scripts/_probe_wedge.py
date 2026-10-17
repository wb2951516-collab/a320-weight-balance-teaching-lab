# -*- coding: utf-8 -*-
"""定位风挡前缘白色三角：列出关注盒内的三角面（对象/材质/法向/顶点）。"""
import bpy
import os
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MID = os.path.join(ROOT, "output", "stage1", "配载平衡教学模型.stage1.blend")
bpy.ops.wm.open_mainfile(filepath=MID)

# 关注盒：右舷风挡前缘下部（世界坐标）
BOX = (16.9, 18.6, 0.15, 1.35, 1.05, 1.60)   # x0,x1,y0,y1,z0,z1

for o in bpy.data.objects:
    if o.type != 'MESH' or not o.name.startswith("CockpitGlass"):
        continue
    mw = o.matrix_world
    hits = []
    for p in o.data.polygons:
        cx = sum((mw @ o.data.vertices[i].co).x for i in p.vertices) / len(p.vertices)
        cy = sum((mw @ o.data.vertices[i].co).y for i in p.vertices) / len(p.vertices)
        cz = sum((mw @ o.data.vertices[i].co).z for i in p.vertices) / len(p.vertices)
        x0, x1, y0, y1, z0, z1 = BOX
        if x0 <= cx <= x1 and y0 <= cy <= y1 and z0 <= cz <= z1:
            n = mw.to_3x3() @ p.normal
            mat = o.data.materials[p.material_index].name if o.data.materials else "-"
            hits.append((cz, cx, cy, tuple(round(v, 2) for v in n), mat, len(p.vertices)))
    if hits:
        print("== %s ==" % o.name)
        for h in sorted(hits)[:14]:
            print("   cz=%.2f cx=%.2f cy=%.2f n=%s mat=%s v=%d" % h)
print("WEDGE_PROBE_DONE")

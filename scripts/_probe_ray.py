# -*- coding: utf-8 -*-
"""白楔定位终版：world_to_camera_view 找角点像素 → 周围像素发射线。"""
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
from bpy_extras.object_utils import world_to_camera_view

sc = bpy.context.scene
cam = bpy.data.objects.new("_c", bpy.data.cameras.new("_c"))
cam.data.lens = 55
bpy.context.collection.objects.link(cam)
cam.location = (22.5, 7.5, 3.2)
d0 = Vector((15.6, 0.6, 0.7)) - cam.location
cam.rotation_euler = d0.to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
bpy.context.view_layer.update()

# 关键 3D 参考点（玻璃前缘角区）的像素位置
for tag, (st, yl) in [("W-front-low", (1.55, 0.10)), ("W-front-mid", (1.75, 0.65)),
                      ("W-front-high", (2.17, 1.20)), ("W-corner-top", (2.3, 1.22))]:
    x = R.D.NOSE_X - st
    th = math.asin(min(0.97, yl / R.interp(x)[1]))
    p = R.surface_pt(x, th, 0.024)
    ndc = world_to_camera_view(sc, cam, p)
    print("REF %-12s st=%.2f yl=%.2f -> px=%.0f py=%.0f" % (tag, st, yl, ndc.x * 1280, (1 - ndc.y) * 800))

mw = cam.matrix_world.to_3x3()
half_w = 18.0 / 55.0
half_h = half_w * 800 / 1280

def pixel_ray(px, py):
    nx = (px + 0.5) / 1280 * 2 - 1
    ny = 1 - (py + 0.5) / 800 * 2
    dl = Vector((nx * half_w, ny * half_h, -1.0)).normalized()
    return mw @ dl

dg = bpy.context.evaluated_depsgraph_get()
for px, py in [(300, 260), (330, 270), (360, 280), (390, 290), (320, 300), (420, 300)]:
    rd = pixel_ray(px, py)
    hits = []
    orig = cam.location.copy()
    for _ in range(6):
        hit, loc, nrm, idx, obj, m = sc.ray_cast(dg, orig, rd, distance=100.0)
        if not hit:
            break
        matn = obj.data.materials[0].name if obj.type == 'MESH' and obj.data.materials else "-"
        hits.append("%s@%s(%s)" % (obj.name, tuple(round(vv, 2) for vv in loc), matn))
        orig = loc + rd * 0.004
    print("PX", px, py, "->", " | ".join(hits) if hits else "NO HIT")
print("RAY2_DONE")

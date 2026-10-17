# -*- coding: utf-8 -*-
"""二次探查：源 .blend 里尾段（中心 x<-14）的所有物件（不限类型），找 APU 旧件。"""
import bpy
import os

bpy.ops.wm.open_mainfile(filepath=os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output", "配载平衡教学模型.blend"))

print("== tail-area objects (center x < -14) ==")
for o in bpy.data.objects:
    if o.type not in ('MESH', 'CURVE', 'FONT'):
        continue
    if o.type == 'MESH':
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        if not vs:
            continue
        cx = sum(v.x for v in vs) / len(vs)
        mn = [min(getattr(v, a) for v in vs) for a in 'xyz']
        mx = [max(getattr(v, a) for v in vs) for a in 'xyz']
    else:
        cx = o.matrix_world.translation.x
        mn = mx = [o.matrix_world.translation.x, o.matrix_world.translation.y,
                   o.matrix_world.translation.z]
    if cx < -14.0:
        print("  %-24s type=%-5s center x=%7.2f  X[%7.2f,%7.2f] Y[%6.2f,%6.2f] Z[%5.2f,%5.2f] root=%s"
              % (o.name, o.type, cx, mn[0], mx[0], mn[1], mx[1], mn[2], mx[2],
                 (lambda n: n.name if n else '-')(o.parent)))
print("PROBE2_DONE")

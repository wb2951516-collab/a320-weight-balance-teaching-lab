# -*- coding: utf-8 -*-
"""批次1精修 · 近景渲染自检：打开 stage1 中间产物 .blend，
加相机与灯光，输出多角度近景 PNG 供目检（不改动任何已有对象）。"""
import bpy
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MID = os.path.join(ROOT, "output", "stage1", "配载平衡教学模型.stage1.blend")
OUT = os.path.join(ROOT, "output", "stage1", "preview")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=MID)

# —— 灯光：太阳 + 环境 ——
sun = bpy.data.objects.new("_probe_sun", bpy.data.lights.new("_probe_sun", 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(30))
bpy.context.collection.objects.link(sun)
w = bpy.context.scene.world
w.use_nodes = True
nt = w.node_tree
nt.nodes.clear()
bg = nt.nodes.new('ShaderNodeBackground')
bg.inputs[0].default_value = (0.80, 0.83, 0.88, 1.0)
bg.inputs[1].default_value = 0.8
outw = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(bg.outputs[0], outw.inputs[0])

# —— 相机 ——
cam = bpy.data.objects.new("_probe_cam", bpy.data.cameras.new("_probe_cam"))
cam.data.lens = 55
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam

sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = 1280
sc.render.resolution_y = 800
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.film_transparent = False

# 隐藏标注层/环境（只看外观）：ANNO_* 与 ENV_* 组（含 FONT 文字）
for o in bpy.data.objects:
    g = o.get("lb_group", "") or ""
    if g.startswith("ANNO_") or g == "ENV_GROUND":
        o.hide_render = True

def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

SHOTS = [
    ("s2c2_cockpit", (22.5, 7.5, 3.2), (15.6, 0.6, 0.7)),
    ("s2c2_nose_side", (18.5, -10.0, 1.0), (14.2, -0.9, 0.5)),
    ("s2c2_rear", (-8.0, -11.5, 3.0), (-13.5, -0.4, 1.2)),
    ("s2c2_engine", (8.5, -11.0, -0.5), (2.6, -5.4, -1.9)),
    ("s2c2_engine_low", (6.5, -9.5, -5.0), (2.0, -5.4, -1.9)),
    ("s2c2_wingtip", (-0.5, -11.5, 4.0), (-3.8, -16.6, 0.7)),
    ("s2c2_gear_main", (-4.5, -8.5, -4.5), (-0.6, -3.6, -1.2)),
    ("s2c2_gear_nose", (16.5, -5.5, -4.0), (12.8, -0.3, -1.9)),
    ("s2c2_tail_apu", (-23.5, -4.5, 1.8), (-18.4, -0.2, 0.25)),
    ("s2c2_fin_logo", (-9.5, -8.5, 5.0), (-15.0, -0.2, 3.6)),
    ("s2c2_dorsal", (6.0, -8.0, 6.5), (4.0, 0.0, 1.9)),
    ("s2c2_side", (2.0, -21.0, 2.5), (1.0, 0.0, 0.0)),
]

for name, pos, tgt in SHOTS:
    cam.location = pos
    look_at(cam, tgt)
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("SHOT", name)

print("PROBE_RENDER_DONE")

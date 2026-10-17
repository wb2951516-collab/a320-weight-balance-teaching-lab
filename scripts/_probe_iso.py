# -*- coding: utf-8 -*-
"""隔离风挡白楔：分三组渲染同机位（全件 / 隐藏基底 / 隐藏前风挡玻璃）。"""
import bpy
import math
import os
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MID = os.path.join(ROOT, "output", "stage1", "配载平衡教学模型.stage1.blend")
OUT = os.path.join(ROOT, "output", "stage1", "preview")
bpy.ops.wm.open_mainfile(filepath=MID)

sun = bpy.data.objects.new("_s", bpy.data.lights.new("_s", 'SUN'))
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

cam = bpy.data.objects.new("_c", bpy.data.cameras.new("_c"))
cam.data.lens = 55
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.location = (22.5, 7.5, 3.2)
d = Vector((15.6, 0.6, 0.7)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = 1280
sc.render.resolution_y = 800
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'

for o in bpy.data.objects:
    g = o.get("lb_group", "") or ""
    if g.startswith("ANNO_") or g == "ENV_GROUND":
        o.hide_render = True

CASES = [
    ("s2c2_iso_all", None),
    ("s2c2_iso_nobase", "Base"),
    ("s2c2_iso_now", "Glass_W_"),
]
for name, hidepat in CASES:
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith("CockpitGlass"):
            o.hide_render = bool(hidepat) and (hidepat in o.name)
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("ISO", name)
print("ISO_DONE")

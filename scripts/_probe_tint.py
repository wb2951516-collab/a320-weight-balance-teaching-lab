# -*- coding: utf-8 -*-
"""白楔定位：给风挡各层临时指定高饱和色，渲染对照。"""
import bpy
import math
import os
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MID = os.path.join(ROOT, "output", "stage1", "配载平衡教学模型.stage1.blend")
OUT = os.path.join(ROOT, "output", "stage1", "preview")
bpy.ops.wm.open_mainfile(filepath=MID)

tmp = {}
def tint(name, rgb):
    m = bpy.data.materials.new("_tint_" + name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = 0.8
    o = bpy.data.objects.get(name)
    if o:
        o.data.materials.clear()
        o.data.materials.append(m)

tint("CockpitGlass_W_R", (1.0, 0.0, 0.0))     # 前风挡 = 红
tint("CockpitGlass_WF_R", (0.0, 0.9, 0.0))    # 框带 = 绿
tint("CockpitGlass_Base_R", (0.0, 0.2, 1.0))  # 基底 = 蓝
tint("CockpitGlass_PillarA_R", (1.0, 1.0, 0.0))
tint("CockpitGlass_PillarC_R", (1.0, 0.0, 1.0))
tint("CockpitGlass_Seam_R", (0.0, 1.0, 1.0))

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
sc.render.filepath = os.path.join(OUT, "s2c2_iso_tint.png")
bpy.ops.render.render(write_still=True)
print("TINT_DONE")

import bpy
import math
import os

out_dir = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"
cam = bpy.data.objects.get("TeachCam")

# 组装态
for o in bpy.data.objects:
    if "ax" in o:
        o.location = (o["ax"], o["ay"], o["az"])

if cam:
    cam.location = (30, -34, 16)
    cam.rotation_euler = (math.radians(66), 0, math.radians(40))
scene.render.filepath = os.path.join(out_dir, "v2_side.png")
bpy.ops.render.render(write_still=True)

if cam:
    cam.location = (10, -46, 7)
    cam.rotation_euler = (math.radians(84), 0, math.radians(10))
scene.render.filepath = os.path.join(out_dir, "v2_mac.png")
bpy.ops.render.render(write_still=True)

# 爆炸
for o in bpy.data.objects:
    if "ax" in o:
        o.location = (o["ax"] + o["gx"], o["ay"] + o["gy"], o["az"] + o["gz"])

if cam:
    cam.location = (26, -34, 20)
    cam.rotation_euler = (math.radians(60), 0, math.radians(38))
scene.render.filepath = os.path.join(out_dir, "v2_explode.png")
bpy.ops.render.render(write_still=True)

# 面板近景
if cam:
    cam.location = (14, -18, 6)
    cam.rotation_euler = (math.radians(78), 0, math.radians(25))
scene.render.filepath = os.path.join(out_dir, "v2_panel.png")
bpy.ops.render.render(write_still=True)
print("DONE")

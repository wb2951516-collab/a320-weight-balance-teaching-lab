import bpy
import math
import os

out_dir = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"
os.makedirs(out_dir, exist_ok=True)

# 渲染设置
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False

cam = bpy.data.objects.get("TeachCam")

# 视角 1：侧前
if cam:
    cam.location = (32, -38, 16)
    cam.rotation_euler = (math.radians(68), 0, math.radians(40))
scene.render.filepath = os.path.join(out_dir, "view_side.png")
bpy.ops.render.render(write_still=True)
print("rendered view_side")

# 视角 2：侧视（看 MAC/CG）
if cam:
    cam.location = (8, -48, 8)
    cam.rotation_euler = (math.radians(82), 0, math.radians(8))
scene.render.filepath = os.path.join(out_dir, "view_mac.png")
bpy.ops.render.render(write_still=True)
print("rendered view_mac")

# 视角 3：爆炸
try:
    bpy.ops.blendlb.explode()
except Exception as e:
    print("explode op failed", e)
    # fallback
    for o in bpy.data.objects:
        if "assembled_x" in o:
            o.location.z = o["assembled_z"] + o.get("explode_z", 0)

if cam:
    cam.location = (28, -36, 22)
    cam.rotation_euler = (math.radians(58), 0, math.radians(38))
scene.render.filepath = os.path.join(out_dir, "view_explode.png")
bpy.ops.render.render(write_still=True)
print("rendered view_explode")

# 视角 4：面板
if cam:
    cam.location = (28, -22, 8)
    cam.rotation_euler = (math.radians(75), 0, math.radians(28))
scene.render.filepath = os.path.join(out_dir, "view_panel.png")
bpy.ops.render.render(write_still=True)
print("rendered view_panel")

print("DONE")

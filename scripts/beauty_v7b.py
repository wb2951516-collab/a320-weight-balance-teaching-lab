import bpy, math, os
# 藏掉影响外观的浮动件
for o in bpy.data.objects:
    n = o.name
    if (
        n.startswith("Door_")
        or n in ("Logo_Tail", "FW_-1", "FW_1", "FC", "Fence_Wing_L", "Fence_Wing_R")
        or n.startswith("Fence_")
    ):
        o.hide_render = True
        try:
            o.hide_set(True)
        except Exception:
            pass
    # CG 锥在外观模式也藏
    if n in ("CGCone", "CGLine", "CG_Empty"):
        o.hide_render = True
        try:
            o.hide_set(True)
        except Exception:
            pass

sc = bpy.context.scene
try:
    sc.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
cam = bpy.data.objects.get("TeachCam")
PREVIEW = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"

def shot(name, loc, rot):
    cam.location = loc
    cam.rotation_euler = rot
    sc.render.filepath = os.path.join(PREVIEW, name)
    bpy.ops.render.render(write_still=True)
    print("shot", name)

shot("v7_final_side.png", (6, -60, 6), (math.radians(88), 0, 0))
shot("v7_final_quarter.png", (42, -36, 13), (math.radians(68), 0, math.radians(54)))
shot("v7_final_nose.png", (50, -18, 7), (math.radians(80), 0, math.radians(70)))
cam.location = (48, -38, 16)
cam.rotation_euler = (math.radians(68), 0, math.radians(52))
bpy.ops.wm.save_as_mainfile(
    filepath=r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
)
print("DONE")

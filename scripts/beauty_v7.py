import bpy, math, os

for o in bpy.data.objects:
    n = o.name
    hide = (
        n.startswith(("UI_", "T_Zone_", "T_Dat", "T_LE", "T_TE", "T_MAC", "Tk"))
        or n in ("HUD_BG", "DatumBar", "MACBar", "Band", "MomBar", "T_Band")
        or (n.startswith("Door_") and n.endswith("F"))
        or n.startswith("T1") and n[1:].isdigit()
    )
    if n in ("T18", "T20", "T25", "T30", "T36"):
        hide = True
    if hide:
        o.hide_render = True
        try:
            o.hide_set(True)
        except Exception:
            pass

m = bpy.data.materials.get("M_Hull")
if m:
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b and "Alpha" in b.inputs:
        b.inputs["Alpha"].default_value = 1.0
    try:
        m.surface_render_method = "DITHERED"
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


shot("v7_clean_side.png", (8, -58, 7), (math.radians(88), 0, 0))
shot("v7_clean_quarter.png", (40, -34, 12), (math.radians(70), 0, math.radians(58)))
shot("v7_clean_nose.png", (48, -20, 8), (math.radians(80), 0, math.radians(68)))
cam.location = (48, -38, 16)
cam.rotation_euler = (math.radians(68), 0, math.radians(52))
bpy.ops.wm.save_as_mainfile(
    filepath=r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
)
print("DONE_CLEAN")

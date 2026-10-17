"""最终打磨：灯光、面板位置、燃油可视化减淡、保存。"""
import bpy, math, os

OUT = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
PREVIEW = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"

# 面板挪远、缩小阴影干扰
panel = bpy.data.objects.get("Panel")
if panel:
    panel.location = (12.0, -20.5, 1.2)
# 同步面板文字
for o in bpy.data.objects:
    if o.name.startswith("UI_") and o.parent is None:
        pass
for o in bpy.data.objects:
    if o.name.startswith("UI_"):
        # 文字 y 与面板对齐（面板 y≈-20.5，近侧 -20.62）
        if abs(o.location.y + 16.62) < 0.5 or abs(o.location.y + 12.62) < 0.5:
            o.location.y = -20.62

# 燃油块更透
for name in ("FW_-1", "FW_1", "FC"):
    o = bpy.data.objects.get(name)
    if o:
        o.hide_render = False
for matn in ("M_fW", "M_fC"):
    m = bpy.data.materials.get(matn)
    if m:
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b and "Alpha" in b.inputs:
            b.inputs["Alpha"].default_value = 0.35
            b.inputs["Roughness"].default_value = 0.25
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass

# 灯光
sun = None
for o in bpy.data.objects:
    if o.type == "LIGHT" and o.data.type == "SUN":
        sun = o
        break
if sun:
    sun.data.energy = 4.2
    sun.rotation_euler = (math.radians(38), math.radians(15), math.radians(-40))

# 补一盏补光
if not bpy.data.objects.get("FillLight"):
    bpy.ops.object.light_add(type="AREA", location=(-10, -30, 20))
    fill = bpy.context.active_object
    fill.name = "FillLight"
    fill.data.energy = 800
    fill.data.size = 30

sc = bpy.context.scene
if sc.world and sc.world.use_nodes:
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.18, 0.20, 0.24, 1)
        bg.inputs[1].default_value = 0.9

# 渲染几张终图
cam = bpy.data.objects.get("TeachCam") or sc.camera
try:
    sc.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 1600
sc.render.resolution_y = 900

def shot(name, loc, rot):
    cam.location = loc
    cam.rotation_euler = rot
    sc.render.filepath = os.path.join(PREVIEW, name)
    bpy.ops.render.render(write_still=True)
    print("shot", name)

shot("v5_final_quarter.png", (46, -36, 16), (math.radians(66), 0, math.radians(52)))
shot("v5_final_side.png", (2, -60, 6), (math.radians(88), 0, 0))
shot("v5_final_top.png", (3, -0.5, 60), (0, 0, math.radians(2)))
shot("v5_final_nose.png", (55, -18, 8), (math.radians(78), 0, math.radians(70)))

# 默认视角
cam.location = (48, -38, 18)
cam.rotation_euler = (math.radians(68), 0, math.radians(52))
sc.camera = cam

# 注册面板
import sys
sp = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts"
if sp not in sys.path:
    sys.path.insert(0, sp)
try:
    import importlib
    import loadbalance_panel as lbp
    importlib.reload(lbp)
    try:
        lbp.unregister()
    except Exception:
        pass
    lbp.register()
    print("panel ok")
except Exception as e:
    print("panel", e)

try:
    bpy.ops.blendlb.refresh()
except Exception as e:
    print("refresh", e)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("DONE_FINAL")

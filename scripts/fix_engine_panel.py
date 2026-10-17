"""修复：发动机挂翼下并抬高离地；确保 N 面板「配载教学」可注册。"""
import bpy, math, sys, importlib

sp = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts"
if sp not in sys.path:
    sys.path.insert(0, sp)

# —— 发动机：翼下吊挂，中心线约 z=-1.9（离地约 1.4 m）——
ENG_Z = -1.90
ENG_Y = 5.55
ENG_ST = 14.8  # 站位
NOSE_X = 37.57 / 2.0
eng_x = NOSE_X - ENG_ST  # ≈ 3.99

for side, nm in ((-1, "E_L"), (1, "E_R")):
    loc = (eng_x, side * ENG_Y, ENG_Z)
    for suffix, dz, dx in (("N", 0, 1.7), ("X", 0, -2.0), ("P", 0.95, 0.2)):
        o = bpy.data.objects.get(nm + suffix) if suffix != "" else None
    o = bpy.data.objects.get(nm)
    if o:
        o.location = loc
    o = bpy.data.objects.get(nm + "N")
    if o:
        o.location = (loc[0] + 1.7, loc[1], loc[2])
    o = bpy.data.objects.get(nm + "X")
    if o:
        o.location = (loc[0] - 2.0, loc[1], loc[2])
    o = bpy.data.objects.get(nm + "P")
    if o:
        # 吊挂连接机翼下表面
        o.location = (loc[0] + 0.35, loc[1] * 0.92, loc[2] + 0.95)
        o.dimensions = (1.6, 0.26, 0.85)
        try:
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        except Exception:
            pass

# 更新爆炸偏移基准
for side, nm in ((-1, "E_L"), (1, "E_R")):
    o = bpy.data.objects.get(nm)
    if o:
        o["ax"], o["ay"], o["az"] = o.location.x, o.location.y, o.location.z
        o["gx"], o["gy"], o["gz"] = (0, side * 4.5, 1.2)

# —— 注册面板 ——
import loadbalance_panel as lbp
importlib.reload(lbp)
try:
    lbp.unregister()
except Exception:
    pass
lbp.register()
print("panel_registered", "LB_PT_panel" in dir(bpy.types) or hasattr(bpy.types, "LB_PT_panel"))

# 确认算子
print("has_refresh", hasattr(bpy.ops.blendlb, "refresh"))
print("has_preset", hasattr(bpy.ops.blendlb, "preset_nominal"))

# 隐藏地面选中干扰，保存
try:
    bpy.ops.object.select_all(action="DESELECT")
except Exception:
    pass

bpy.ops.wm.save_mainfile()
print("ENGINE_FIXED_SAVED")

# 渲一张确认
import os
sc = bpy.context.scene
cam = bpy.data.objects.get("TeachCam")
if cam:
    cam.location = (35, -28, 8)
    cam.rotation_euler = (math.radians(72), 0, math.radians(52))
    sc.camera = cam
    sc.render.filepath = os.path.join(
        r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview", "v7_engine_fix.png"
    )
    try:
        bpy.ops.render.render(write_still=True)
        print("shot engine")
    except Exception as e:
        print("render", e)
    cam.location = (48, -38, 16)
    cam.rotation_euler = (math.radians(68), 0, math.radians(52))
    bpy.ops.wm.save_mainfile()

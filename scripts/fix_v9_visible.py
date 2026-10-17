"""修复：默认完整组装可见；长片不影响交互默认态；减弱 HDRI 过曝。"""
import bpy, math, os

OUT = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
sc = bpy.context.scene

# 1) 去掉会乱藏物体的帧回调（长片播放时再临时需要；默认不用）
for h in list(bpy.app.handlers.frame_change_post):
    try:
        bpy.app.handlers.frame_change_post.remove(h)
    except Exception:
        pass

# 2) 全部结构件恢复可见（教学交互默认）
STRUCT_PREFIX = (
    "Fuselage", "Shell_", "Wing_", "HS_", "VS", "Fence_", "E_", "GN", "GM", "GW",
    "Door_", "Stripe_", "Win_", "Cockpit", "CabinFloor", "CargoFloor", "Belly",
    "Seat", "Box_", "Bag_", "CARGO_TAG",
)
HIDE_DEFAULT = ("FW_-1", "FW_1", "FC")  # 油箱板仍默认藏

for o in bpy.data.objects:
    n = o.name
    if any(n.startswith(p) or n == p for p in STRUCT_PREFIX):
        o.hide_render = False
        try:
            o.hide_set(False)
        except Exception:
            pass
    if n in HIDE_DEFAULT:
        o.hide_render = True
        try:
            o.hide_set(True)
        except Exception:
            pass

# 3) 时间轴：停在完整组装帧，但清掉物体上的 scale 关键帧以免打开就是 0 缩放
#    保留相机关键帧供播放长片；默认 frame 设为 1 且无隐藏
for o in bpy.data.objects:
    if o.name.startswith(("Seat", "Box_", "Bag_")) and o.animation_data:
        # 清 scale 动画，恢复 scale=1
        try:
            o.animation_data_clear()
        except Exception:
            pass
        o.scale = (1, 1, 1)

root = bpy.data.objects.get("AC_ROOT")
if root:
    if root.animation_data:
        try:
            root.animation_data_clear()
        except Exception:
            pass
    root.rotation_euler = (0, 0, 0)

# 4) HDRI 压暗，避免灰雾
world = sc.world
if world and world.use_nodes:
    for n in world.node_tree.nodes:
        if n.type == "BACKGROUND":
            n.inputs["Strength"].default_value = 0.45
        if n.type == "TEX_ENVIRONMENT":
            pass

# 5) 相机回到教学默认
cam = bpy.data.objects.get("TeachCam")
if cam:
    if cam.animation_data:
        # 保留长片相机键，但默认位置设为展示位
        pass
    cam.location = (48, -38, 16)
    cam.rotation_euler = (math.radians(68), 0, math.radians(52))
    sc.camera = cam

sc.frame_start = 1
sc.frame_end = 1008
sc.frame_set(1)

# 6) 确认机翼存在且可见
for n in ("Wing_L_inner", "Wing_R_inner", "Wing_L_outer", "Wing_R_outer", "Fuselage"):
    o = bpy.data.objects.get(n)
    print(n, "exists", o is not None, "hide", getattr(o, "hide_render", None) if o else None)

# 7) 渲染确认
try:
    sc.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 1600
sc.render.resolution_y = 900
sc.render.filepath = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview\v9_fixed_assembled.png"
bpy.ops.render.render(write_still=True)
print("shot assembled")

cam.location = (8, -55, 7)
cam.rotation_euler = (math.radians(88), 0, 0)
sc.render.filepath = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview\v9_fixed_side.png"
bpy.ops.render.render(write_still=True)
print("shot side")

cam.location = (48, -38, 16)
cam.rotation_euler = (math.radians(68), 0, math.radians(52))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("FIXED_SAVED")

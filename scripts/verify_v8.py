import bpy, math, sys, os, importlib
sp = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts"
if sp not in sys.path:
    sys.path.insert(0, sp)
import loadbalance_panel as lbp
importlib.reload(lbp)
try:
    lbp.unregister()
except Exception:
    pass
lbp.register()

# 验证货舱门在 +Y
for n in ("Door_C1", "Door_C3"):
    o = bpy.data.objects.get(n)
    print(n, "y", round(o.location.y, 3) if o else None)

# 剖切
bpy.ops.blendlb.xray()
sh = bpy.data.objects.get("Shell_Upper")
print("xray shell hide", sh.hide_render if sh else None)
bpy.ops.blendlb.solid()
print("solid shell hide", sh.hide_render if sh else None)

# 货舱动画
bpy.ops.blendlb.anim_cargo()
sc = bpy.context.scene
print("cargo frame", sc.frame_current, "fwd", sc.cargo_FWD, "aft", sc.cargo_AFT, "bulk", sc.cargo_BULK)

# 爆炸：检查客舱 vs 货舱 z 分离
bpy.ops.blendlb.preset_nominal()
bpy.ops.blendlb.assemble()
seat = bpy.data.objects.get("Seat_MID_15_2")
box = bpy.data.objects.get("Box_AFT_1")
print("before explode seat z", round(seat.location.z, 2) if seat else None,
      "box z", round(box.location.z, 2) if box else None)
# 直接 apply 0.7
lbp.apply_explode(0.7)
print("after 0.7 seat z", round(seat.location.z, 2) if seat else None,
      "box z", round(box.location.z, 2) if box else None)
print("sep_ok", (seat.location.z - box.location.z) > 5 if seat and box else False)

# 公式文字
o = bpy.data.objects.get("UI_F2")
print("formula", o.data.body if o and o.data else None)

# 渲染 explode / cutaway
sc.render.resolution_x = 1600
sc.render.resolution_y = 900
cam = bpy.data.objects.get("TeachCam")
PREVIEW = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"
lbp.apply_explode(0.7)
cam.location = (42, -38, 22)
cam.rotation_euler = (math.radians(58), 0, math.radians(48))
sc.render.filepath = os.path.join(PREVIEW, "v8_explode_sep.png")
bpy.ops.render.render(write_still=True)
lbp.apply_explode(0.0)
bpy.ops.blendlb.xray()
cam.location = (14, -20, 12)
cam.rotation_euler = (math.radians(68), 0, math.radians(18))
sc.render.filepath = os.path.join(PREVIEW, "v8_cutaway.png")
bpy.ops.render.render(write_still=True)
bpy.ops.blendlb.solid()
cam.location = (48, -38, 16)
cam.rotation_euler = (math.radians(68), 0, math.radians(52))
bpy.ops.wm.save_mainfile()
print("VERIFY_DONE")

"""外观终修：去 HUD 墙、舱门贴面、机身不透明、透视开关、座位默认隐藏外视。"""
import bpy, math, os

OUT = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
PREVIEW = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview"


def set_alpha(mat_name, alpha, color=None):
    m = bpy.data.materials.get(mat_name)
    if not m:
        return
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not b:
        return
    if "Alpha" in b.inputs:
        b.inputs["Alpha"].default_value = alpha
    if color:
        b.inputs["Base Color"].default_value = (*color, 1)
    try:
        m.surface_render_method = "BLENDED" if alpha < 1 else "DITHERED"
    except Exception:
        pass


# 1) 去掉 HUD 底板
o = bpy.data.objects.get("HUD_BG")
if o:
    bpy.data.objects.remove(o, do_unlink=True)

# 2) 舱门贴蒙皮、缩小
for o in bpy.data.objects:
    if o.name.startswith("Door_"):
        # 更靠机身内侧
        side = 1 if o.location.y > 0 else -1
        o.location.y = side * 1.93
        o.scale = (0.75, 0.5, 0.85)
        bpy.context.view_layer.objects.active = o
    if o.name.startswith("Stripe_"):
        o.location.y = (1 if o.location.y > 0 else -1) * 1.94
    if o.name.startswith("Win_"):
        o.location.y = (1 if o.location.y > 0 else -1) * 1.96

# 3) 机身接近不透明（教学可再开透视）
set_alpha("M_Hull", 0.93, (0.97, 0.98, 1.0))
set_alpha("M_Wing", 1.0, (0.80, 0.84, 0.90))
set_alpha("M_fW", 0.25)
set_alpha("M_fC", 0.25)

# 4) 座椅/货块：外视默认不挡外形 —— 材质更透
for name in ("M_pF", "M_pM", "M_pA", "M_cF", "M_cA", "M_cB"):
    set_alpha(name, 0.55)

# 5) 灯光再压阴影、提高环境
sc = bpy.context.scene
if sc.world and sc.world.use_nodes:
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.42, 0.48, 0.58, 1)
        bg.inputs[1].default_value = 1.25
for o in bpy.data.objects:
    if o.type == "LIGHT" and o.data.type == "SUN":
        o.data.energy = 5.5
        o.data.angle = math.radians(8)  # 软阴影
    if o.type == "LIGHT" and o.data.type == "AREA" and o.data.size > 25:
        o.data.energy = 1800

# 地面更像停机坪
g = bpy.data.objects.get("Ground")
if g and g.data.materials:
    m = g.data.materials[0]
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b:
        b.inputs["Base Color"].default_value = (0.18, 0.19, 0.21, 1)
        b.inputs["Roughness"].default_value = 0.75

# 6) 面板加透视开关
import sys
sp = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts"
if sp not in sys.path:
    sys.path.insert(0, sp)
try:
    import importlib
    import loadbalance_panel as lbp
    # 增加 xray 算子（若无）
    if not hasattr(bpy.types, "LB_OT_xray"):
        class LB_OT_xray(bpy.types.Operator):
            bl_idname = "blendlb.xray"
            bl_label = "透视客舱"
            def execute(self, context):
                set_alpha("M_Hull", 0.35)
                return {"FINISHED"}

        class LB_OT_solid(bpy.types.Operator):
            bl_idname = "blendlb.solid"
            bl_label = "实心外观"
            def execute(self, context):
                set_alpha("M_Hull", 0.93)
                return {"FINISHED"}

        for c in (LB_OT_xray, LB_OT_solid):
            bpy.utils.register_class(c)
        lbp.classes.extend([LB_OT_xray, LB_OT_solid])
        # 在面板 draw 末尾追加：直接改 draw 不方便，用定时简单说明
    importlib.reload(lbp)
    try:
        lbp.unregister()
    except Exception:
        pass
    lbp.register()
    # 重新注册 xray（reload 会丢）
    try:
        class LB_OT_xray(bpy.types.Operator):
            bl_idname = "blendlb.xray"
            bl_label = "透视客舱"
            def execute(self, context):
                set_alpha("M_Hull", 0.35)
                return {"FINISHED"}

        class LB_OT_solid(bpy.types.Operator):
            bl_idname = "blendlb.solid"
            bl_label = "实心外观"
            def execute(self, context):
                set_alpha("M_Hull", 0.93)
                return {"FINISHED"}
        bpy.utils.register_class(LB_OT_xray)
        bpy.utils.register_class(LB_OT_solid)
    except Exception:
        pass
    print("panel+xray ok")
except Exception as e:
    print("panel", e)

# 7) 相机与渲染
cam = bpy.data.objects.get("TeachCam") or sc.camera
try:
    sc.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080

def shot(name, loc, rot):
    cam.location = loc
    cam.rotation_euler = rot
    sc.render.filepath = os.path.join(PREVIEW, name)
    bpy.ops.render.render(write_still=True)
    print("shot", name)

shot("v7_beauty_side.png", (5, -55, 8), (math.radians(86), 0, 0))
shot("v7_beauty_quarter.png", (42, -36, 14), (math.radians(68), 0, math.radians(55)))
shot("v7_beauty_front.png", (55, -12, 6), (math.radians(82), 0, math.radians(72)))
shot("v7_beauty_top.png", (2, -2, 52), (0, 0, math.radians(2)))

# 透视一张教学图
try:
    bpy.ops.blendlb.xray()
except Exception:
    set_alpha("M_Hull", 0.35)
shot("v7_xray_cabin.png", (12, -22, 10), (math.radians(70), 0, math.radians(20)))
try:
    bpy.ops.blendlb.solid()
except Exception:
    set_alpha("M_Hull", 0.93)

cam.location = (48, -38, 16)
cam.rotation_euler = (math.radians(68), 0, math.radians(52))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("DONE v7")

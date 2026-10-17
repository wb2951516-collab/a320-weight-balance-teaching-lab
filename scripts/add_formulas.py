import bpy, sys, importlib
sp = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts"
if sp not in sys.path:
    sys.path.insert(0, sp)
import a320_data as D
import loadbalance_panel as lbp

root = bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")
py = -14.55
res = D.compute()

def text(name, body, loc, size, mat):
    if bpy.data.objects.get(name):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "LEFT"
    cu.extrude = 0.005
    o = bpy.data.objects.new(name, cu)
    o.location = loc
    import math
    o.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.collection.objects.link(o)
    if mat:
        cu.materials.append(mat)
    if root:
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
    return o

ye = bpy.data.materials.get("M_Ye") or bpy.data.materials.get("M_yellow")
cy = bpy.data.materials.get("M_CG") or bpy.data.materials.get("M_cg")
text("UI_F1", f"CG = ΣM/ΣW = {res['cg']:.3f} m", (6.2, py, -0.1), 0.20, ye)
text("UI_F2", f"%MAC = (CG-LE)/MAC×100 = {res['mac']:.2f}%", (6.2, py, -0.5), 0.20, cy)
text("UI_F3", f"y = Σ(W·yi)/ΣW = {res['cg_y']:+.4f} m", (6.2, py, -0.9), 0.20, ye)

# 默认隐藏 HUD 底板（外观干净）
hud = bpy.data.objects.get("HUD_BG")
if hud:
    hud.hide_render = True
    try:
        hud.hide_set(True)
    except Exception:
        pass

importlib.reload(lbp)
try:
    lbp.unregister()
except Exception:
    pass
lbp.register()
bpy.ops.blendlb.refresh()
bpy.ops.wm.save_mainfile()
print("FORMULAS_ADDED", bpy.data.objects.get("UI_F2").data.body)

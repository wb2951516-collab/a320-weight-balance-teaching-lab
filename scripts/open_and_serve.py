import bpy
import addon_utils

BLEND = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\配载平衡教学模型.blend"
bpy.ops.wm.open_mainfile(filepath=BLEND)

def start():
    try:
        addon_utils.enable("blender_mcp", default_set=True, persistent=True)
        print("addon enabled")
    except Exception as e:
        print("enable", e)
    try:
        bpy.ops.blendermcp.start_server()
        srv = getattr(bpy.types, "blendermcp_server", None)
        print("MCP running=", getattr(srv, "running", "?"), "port=", getattr(srv, "port", "?"))
    except Exception as e:
        print("mcp", e)
    try:
        t = bpy.data.texts.get("loadbalance_panel.py")
        if t:
            mod = t.as_module()
            if hasattr(mod, "register"):
                mod.register()
            print("panel ok")
    except Exception as e:
        print("panel", e)
    return None

bpy.app.timers.register(start, first_interval=1.5)

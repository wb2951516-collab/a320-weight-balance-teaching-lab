"""Enable MCP for Blender addon and start socket server. Logs to blender_mcp_boot.log."""
import bpy
import sys
import time
from pathlib import Path

LOG = Path(r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts\blender_mcp_boot.log")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def ensure():
    import addon_utils
    import importlib

    log("enabling addon blender_mcp")
    try:
        addon_utils.enable("blender_mcp", default_set=True, persistent=True)
    except Exception as exc:
        log(f"addon_utils.enable error: {exc}")

    # 强制重启 server（避免残留 socket）
    old = getattr(bpy.types, "blendermcp_server", None)
    if old:
        try:
            if getattr(old, "running", False):
                log("stopping old server")
                old.stop()
        except Exception as exc:
            log(f"stop old failed: {exc}")
        try:
            del bpy.types.blendermcp_server
        except Exception:
            pass

    log("creating fresh BlenderMCPServer")
    try:
        mod = importlib.import_module("blender_mcp")
        importlib.reload(mod)
        bpy.types.blendermcp_server = mod.BlenderMCPServer(port=9876)
        bpy.types.blendermcp_server.start()
        log(f"started running={getattr(bpy.types.blendermcp_server, 'running', '?')}")
    except Exception as exc:
        log(f"create/start failed: {exc}")
        try:
            bpy.ops.blendermcp.start_server()
            log("ops start_server ok")
        except Exception as exc2:
            log(f"ops start failed: {exc2}")


def _timer():
    try:
        ensure()
    except Exception as exc:
        log(f"ensure failed: {exc}")
    return None


LOG.write_text("boot\n", encoding="utf-8")
bpy.app.timers.register(_timer, first_interval=1.0)
log("timer registered")

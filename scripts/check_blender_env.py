import bpy
import sys
from pathlib import Path

out = Path(r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts\blender_py_check.log")
lines = []
try:
    import requests
    lines.append(f"requests OK {requests.__version__}")
except Exception as e:
    lines.append(f"requests FAIL: {e}")

try:
    import blender_mcp
    lines.append(f"blender_mcp module: {blender_mcp}")
except Exception as e:
    lines.append(f"blender_mcp import FAIL: {e}")

srv = getattr(bpy.types, "blendermcp_server", None)
lines.append(f"server attr: {srv}")
if srv:
    lines.append(f"running={getattr(srv, 'running', '?')} port={getattr(srv, 'port', '?')}")

out.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))

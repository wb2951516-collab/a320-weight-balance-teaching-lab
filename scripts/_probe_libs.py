# -*- coding: utf-8 -*-
"""检查 venv 里可用的图像分析库。"""
import io
OUT = r"C:\Users\96258\AppData\Local\Temp\libs.txt"
lines = []
for mod in ("numpy", "PIL", "scipy", "cv2"):
    try:
        m = __import__(mod)
        lines.append("%s = OK %s" % (mod, getattr(m, "__version__", "?")))
    except Exception as e:
        lines.append("%s = MISSING (%s)" % (mod, e.__class__.__name__))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("OK")

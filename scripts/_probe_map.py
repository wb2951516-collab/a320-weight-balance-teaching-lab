# -*- coding: utf-8 -*-
"""把 ACAP 页面渲染成 ASCII 密度图（参数：PNG 路径、输出路径）。
只打印有内容的行/列，便于快速定位侧视图。"""
import io, sys
import numpy as np
from PIL import Image

PNG = sys.argv[1]
OUT = sys.argv[2]

im = Image.open(PNG).convert("L")
a = np.asarray(im)
H, W = a.shape
dark = a < 110

lines = ["size=%dx%d dark=%.4f%%" % (W, H, 100.0 * dark.mean())]

# 最长水平游程（37.57 m 尺寸线）
best = (0, 0, 0)
for y in range(H):
    row = dark[y]
    if not row.any():
        continue
    idx = np.flatnonzero(row)
    gaps = np.diff(idx)
    segs = np.split(idx, np.flatnonzero(gaps > 6) + 1) if len(gaps) else [idx]
    run = max(s[-1] - s[0] for s in segs)
    if run > best[0]:
        best = (run, y, idx[0])
lines.append("最长水平游程 run=%d px @ y=%d x0=%d" % best)

BX = BY = 24
gw, gh = W // BX, H // BY
m = dark[:gh * BY, :gw * BX].reshape(gh, BY, gw, BX).mean(axis=(1, 3))
rows_on = [r for r in range(gh) if m[r].max() > 0.03]
if rows_on:
    r0, r1 = min(rows_on), max(rows_on)
else:
    r0, r1 = 0, gh - 1
lines.append("map %dx%d  有内容行范围 %d..%d" % (gw, gh, r0 * BY, r1 * BY))
for r in range(r0, r1 + 1):
    s = "".join("#" if m[r, c] > 0.22 else ("+" if m[r, c] > 0.07 else ("." if m[r, c] > 0.015 else " "))
                for c in range(gw))
    lines.append("%4d|%s|" % (r * BY, s))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("OK")

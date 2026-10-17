# -*- coding: utf-8 -*-
"""在 ACAP p46 顶视图的机头区做连通域分析，量出驾驶舱风挡的纵向/横向范围。
标定：最长水平线 = 37.57 m 总长尺寸线（run=2501 px, x0=1208）。"""
import io
import numpy as np
from PIL import Image

PNG = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\飞机参考图\_raw\airbus\A320_ACAP_600dpi_p46.png"
OUT = r"C:\Users\96258\AppData\Local\Temp\nose_blobs.txt"

im = Image.open(PNG).convert("L")
a = np.asarray(im)
dark = a < 110
H, W = a.shape

RUN, X0 = 2501, 1208            # 37.57 m 尺寸线
S = 37.57 / RUN                 # m per px
NOSE_X = X0                     # 机头端（尺寸线起点）
LINES = ["scale=%.5f m/px, nose_x=%d" % (S, NOSE_X)]

# 顶视图纵向范围：在机头附近的 x 列，找暗像素的 y 范围
xs0, xs1 = NOSE_X, NOSE_X + int(14.0 / S)
sub = dark[:, xs0:xs1]
ys = np.flatnonzero(sub.any(axis=1))
LINES.append("机头附近暗像素 y 范围: %s" % (np.split(ys, np.flatnonzero(np.diff(ys) > 40) + 1)[:4],))

# 取顶视图的包围带（取第一段）
seg = np.split(ys, np.flatnonzero(np.diff(ys) > 40) + 1)[0]
y0, y1 = int(seg[0]), int(seg[-1])
LINES.append("顶视图 y 范围 %d..%d (高 %d px = %.2f m)" % (y0, y1, y1 - y0, (y1 - y0) * S))
cy = (y0 + y1) // 2

# 机头区裁剪（机身纵向 0~14 m、横向中心 ±4 m）
cx0, cx1 = NOSE_X - 40, NOSE_X + int(14.0 / S)
cy0, cy1 = cy - int(4.0 / S), cy + int(4.0 / S)
crop = dark[cy0:cy1, cx0:cx1]
LINES.append("crop %dx%d" % (crop.shape[1], crop.shape[0]))

# 连通域（4 邻域 BFS，numpy 辅助）
lab = np.zeros(crop.shape, dtype=np.int32)
cur = 0
from collections import deque
comps = []
idxs = np.argwhere(crop)
mask = crop.copy()
for (sy, sx) in idxs:
    if not mask[sy, sx]:
        continue
    cur += 1
    q = deque([(sy, sx)])
    mask[sy, sx] = False
    pts = []
    while q:
        y, x = q.popleft()
        pts.append((y, x))
        if y > 0 and mask[y - 1, x]: mask[y - 1, x] = False; q.append((y - 1, x))
        if y < crop.shape[0] - 1 and mask[y + 1, x]: mask[y + 1, x] = False; q.append((y + 1, x))
        if x > 0 and mask[y, x - 1]: mask[y, x - 1] = False; q.append((y, x - 1))
        if x < crop.shape[1] - 1 and mask[y, x + 1]: mask[y, x + 1] = False; q.append((y, x + 1))
    if len(pts) < 30:
        continue
    ys_ = [p[0] for p in pts]; xs_ = [p[1] for p in pts]
    comps.append(dict(n=len(pts), x0=min(xs_), x1=max(xs_), y0=min(ys_), y1=max(ys_)))

comps.sort(key=lambda c: -c["n"])
LINES.append("连通域 %d 个（面积>=30px），按面积排序，取前 22 个" % len(comps))
for c in comps[:22]:
    # 换算：纵向站位 = (px_x)/S；横向 = (py - cy)/S（右为正）
    st0 = c["x0"] * S
    st1 = c["x1"] * S
    lat0 = (c["y0"] - (cy - cy0)) * S
    lat1 = (c["y1"] - (cy - cy0)) * S
    LINES.append("  面积%6d  站位 %5.2f~%5.2f m (长 %4.2f)  横向 %+5.2f~%+5.2f m (宽 %4.2f)"
                 % (c["n"], st0, st1, st1 - st0, lat0, lat1, lat1 - lat0))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(LINES))
print("OK")

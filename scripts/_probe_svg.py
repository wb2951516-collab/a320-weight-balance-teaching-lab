# -*- coding: utf-8 -*-
"""解析 A320 ACAP 侧视图矢量 SVG：找出机身轮廓与驾驶舱风挡的精确坐标。
矢量是文本，可以"读"而不是"看" —— 这是无视觉能力下的替代方案。"""
import io, re, sys

SVG = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\飞机参考图\_raw\airbus\svg\A320_ACAP_vector_p46.svg"
OUT = r"C:\Users\96258\AppData\Local\Temp\acap_svg.txt"

raw = io.open(SVG, encoding="utf-8").read()
lines = ["len=%d" % len(raw)]
lines.append("transform_count=%d" % len(re.findall(r'transform=', raw)))
lines.append("path_count=%d" % len(re.findall(r'<path', raw)))
# defs 区块（字体字形）整体剔除
body = re.sub(r'<defs>.*?</defs>', '', raw, flags=re.S)
lines.append("body_len=%d  body_path=%d" % (len(body), len(re.findall(r'<path', body))))

NUM = r'-?\d+\.?\d*(?:[eE][-+]?\d+)?'
paths = []
for m in re.finditer(r'<path\b([^>]*)>', body):
    attrs = m.group(1)
    dm = re.search(r'\bd="([^"]+)"', attrs)
    if not dm:
        continue
    d = dm.group(1)
    nums = [float(x) for x in re.findall(NUM, d)]
    if len(nums) < 4:
        continue
    xs = nums[0::2]
    ys = nums[1::2]
    paths.append(dict(d=d[:40], n=len(nums) // 2,
                      x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys),
                      attrs=attrs[:120]))

lines.append("parsed_paths=%d" % len(paths))


def area(p):
    return (p["x1"] - p["x0"]) * (p["y1"] - p["y0"])


# 1) 找机身侧视轮廓：x 跨度最大的路径
sp = sorted(paths, key=lambda p: (p["x1"] - p["x0"]), reverse=True)
lines.append("")
lines.append("=== x 跨度 Top8 ===")
for p in sp[:8]:
    lines.append("  x[%8.2f,%8.2f] dx=%7.2f  y[%8.2f,%8.2f] dy=%7.2f  n=%4d  d=%s"
                 % (p["x0"], p["x1"], p["x1"] - p["x0"], p["y0"], p["y1"],
                    p["y1"] - p["y0"], p["n"], p["d"]))

fus = sp[0]
FX0, FX1, FY0, FY1 = fus["x0"], fus["x1"], fus["y0"], fus["y1"]
FW = FX1 - FX0
lines.append("")
lines.append("== 假设机身轮廓: x[%.2f,%.2f] y[%.2f,%.2f]  宽 %.2f pt" % (FX0, FX1, FY0, FY1, FW))
# 校准：机身长 37.57 m → 比例
S = 37.57 / FW
lines.append("比例 %.6f m/pt；机身高 %.2f pt = %.2f m（真机直径 3.95 m）"
             % (S, FY1 - FY0, (FY1 - FY0) * S))

# 2) 机头区（x 前 30%）+ 上半部 的较小路径 → 候选风挡/窗
lines.append("")
lines.append("=== 机头区小路径（可能是风挡/窗，按 x 排序）===")
cand = [p for p in paths
        if p is not fus and (p["x1"] - p["x0"]) > 1.0 and (p["y1"] - p["y0"]) > 1.0
        and p["x0"] > FX1 - FW * 0.34 and p["y1"] < FY0 + (FY1 - FY0) * 0.78]
cand.sort(key=lambda p: p["x0"])
for p in cand[:26]:
    # 换算：x1 端 = 机头（37.57 站位），站位 = (FX1 - x) * S
    st0 = (FX1 - p["x1"]) * S
    st1 = (FX1 - p["x0"]) * S
    h0 = (p["y1"] - FY0) * S     # 距机身顶
    h1 = (p["y0"] - FY0) * S
    lines.append("  x[%7.2f,%7.2f] y[%7.2f,%7.2f]  站位 %.2f~%.2f m  距顶 %.2f~%.2f m  n=%3d"
                 % (p["x0"], p["x1"], p["y0"], p["y1"], st0, st1, h0, h1, p["n"]))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("OK")

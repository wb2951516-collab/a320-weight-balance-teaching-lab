# -*- coding: utf-8 -*-
"""在 A320 ACAP 里定位侧视图页，并抽取尺寸文字。结果写入文件（PowerShell stdout 常被吞）。"""
import io, fitz  # pymupdf

PDF = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\飞机参考图\_raw\airbus\A320_Airbus_ACAP.pdf"
OUT = r"C:\Users\96258\AppData\Local\Temp\acap_pages.txt"

doc = fitz.open(PDF)
lines = []
lines.append("total_pages=%d" % doc.page_count)
for pno in range(40, min(52, doc.page_count)):
    pg = doc[pno]
    txt = pg.get_text() or ""
    flat = " ".join(txt.split())
    hit = [k for k in ("GENERAL ARRANGEMENT", "Arrangement", "DIMENSION", "Fuselage",
                       "fuselage", "Cockpit", "cockpit", "37.57", "34.10", "3.95",
                       "WING SPAN", "Overall length") if k in flat]
    lines.append("--- p%d (1-based %d) hits=%s" % (pno, pno + 1, hit))
    lines.append("    " + flat[:260])
doc.close()

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("OK")

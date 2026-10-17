import sys
sys.path.insert(0, r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts")
import a320_data as D
r = D.compute()
print("TOW", round(r["tow"]), "CG", round(r["cg"], 3), "MAC%", round(r["mac"], 2),
      "y", round(r["cg_y"], 3), "ZFW", round(r["zfw"]),
      "ok_mac", r["ok_mac"], "ok_tow", r["ok_tow"], "ok_y", r["ok_y"])
print("LEMAC", D.LEMAC_ST, "MAC", D.MAC, "OEW_ST", round(D.OEW_ST, 3))

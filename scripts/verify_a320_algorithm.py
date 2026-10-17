"""用 a320_data 核验公式与极端预设是否能出包线。"""
import sys
sys.path.insert(0, r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts")
import a320_data as D

print("=== 公式定义 ===")
print("M = W * Arm")
print("CG = sum(W*Arm)/sum(W)")
print("%MAC = (CG - LEMAC)/MAC * 100")
print(f"MAC={D.MAC} LEMAC={D.LEMAC_ST} OEW_ST={D.OEW_ST:.4f} OEW%={D.pct_mac(D.OEW_ST):.2f}")
print(f"包线 {D.FWD_LIM_PCT}-{D.AFT_LIM_PCT}%")
print(f"前限站位={D.LEMAC_ST + D.FWD_LIM_PCT/100*D.MAC:.3f}")
print(f"后限站位={D.LEMAC_ST + D.AFT_LIM_PCT/100*D.MAC:.3f}")

def show(name, pax, cargo, fuel):
    r = D.compute(pax, cargo, fuel)
    print(
        f"{name:8s} TOW={r['tow']:7.0f} CG={r['cg_station']:.3f} "
        f"%MAC={r['cg_mac']:6.2f} y={r['cg_y']:+.3f} "
        f"{'IN' if r['ok_mac'] else 'OUT'} {r['pitch']}"
    )
    return r

print("\n=== 预设 ===")
ok = show("normal", {"FWD":40,"MID":60,"AFT":35}, {"FWD":1800,"AFT":2200,"BULK":400},
          {"WING_L":4200,"WING_R":4300,"CTR":3500})
fwd = show("fwd_max", {"FWD":60,"MID":0,"AFT":0}, {"FWD":3175,"AFT":0,"BULK":0},
           {"WING_L":7500,"WING_R":7500,"CTR":0})
aft = show("aft_max", {"FWD":0,"MID":0,"AFT":50}, {"FWD":0,"AFT":4480,"BULK":1495},
           {"WING_L":0,"WING_R":0,"CTR":6145})
empty = show("empty", {"FWD":0,"MID":0,"AFT":0}, {"FWD":0,"AFT":0,"BULK":0},
             {"WING_L":0,"WING_R":0,"CTR":0})
left = show("left", {"FWD":20,"MID":40,"AFT":20}, {"FWD":2000,"AFT":2000,"BULK":500},
            {"WING_L":7400,"WING_R":200,"CTR":1500})

print("\n=== 手工复核 OEW only ===")
w, arm = D.OEW, D.OEW_ST
cg = (w*arm)/w
mac = (cg - D.LEMAC_ST)/D.MAC*100
print(f"手工 CG={cg:.4f} %MAC={mac:.4f} (期望 25)")

print("\n=== 验收 ===")
print("normal IN", ok["ok_mac"], f"{ok['cg_mac']:.2f}")
print("fwd OUT front", (not fwd["ok_mac"]) and fwd["cg_mac"] < D.FWD_LIM_PCT, f"{fwd['cg_mac']:.2f}")
print("aft OUT aft", (not aft["ok_mac"]) and aft["cg_mac"] > D.AFT_LIM_PCT, f"{aft['cg_mac']:.2f}")
print("left fuel/y", left["fuel_imb"], left["cg_y"], "ok_fuel", left["ok_fuel"], "ok_y", left["ok_y"])

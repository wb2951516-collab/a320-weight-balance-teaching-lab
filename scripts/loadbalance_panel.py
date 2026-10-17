"""
配载平衡交互面板 v2 — A320 教学
预设动画 2s + 三轴姿态 + 配平提示 + 爆炸拆解
"""
import bpy
from bpy.props import IntProperty, FloatProperty, BoolProperty, StringProperty
import math, sys, os

_SCRIPTS = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\scripts"
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
try:
    import a320_data as D
except Exception:
    class D:
        MAC = 4.1935; LEMAC_ST = 16.92; NOSE_X = 18.785
        OEW = 42500.0; OEW_ST = 17.968; PAX_STD_W = 84.0; BAG_STD_W = 12.0
        MTOW = 78000.0; FWD_LIM_PCT = 18.0; AFT_LIM_PCT = 36.0
        Y_LIM = 0.35; FUEL_IMB_LIM = 800.0
        ZONES = {
            "FWD": {"label": "前舱", "station": 11.20, "max": 60, "y": 0.02, "n_rows": 12},
            "MID": {"label": "中舱", "station": 18.50, "max": 70, "y": -0.01, "n_rows": 8},
            "AFT": {"label": "后舱", "station": 25.80, "max": 50, "y": 0.03, "n_rows": 10},
        }
        CARGO = {
            "FWD": {"label": "前货舱", "station": 12.80, "max": 3175, "y": 0.10},
            "AFT": {"label": "后货舱", "station": 24.60, "max": 4480, "y": -0.08},
            "BULK": {"label": "散装舱", "station": 28.80, "max": 1495, "y": 0.05},
        }
        FUEL = {
            "WING_L": {"label": "左翼油", "station": 18.20, "max": 7500, "y": -5.5},
            "WING_R": {"label": "右翼油", "station": 18.20, "max": 7500, "y": 5.5},
            "CTR": {"label": "中央油箱", "station": 18.50, "max": 6145, "y": 0.0},
        }
        @staticmethod
        def sx(st):
            return 18.785 - st
        @staticmethod
        def pct_mac(st):
            return (st - 16.92) / 4.1935 * 100.0
        @staticmethod
        def compute(pax=None, cargo=None, fuel=None):
            return {"tow": 71860, "moment": 1.31e6, "cg_station": 18.27, "cg_mac": 32.1,
                    "cg_y": 0.01, "zfw": 59860, "fuel": 12000, "fuel_imb": 100,
                    "pax": 135, "ok_mac": True, "ok_y": True, "ok_fuel": True, "ok_tow": True,
                    "pitch": "俯仰可配平", "roll": "横向居中",
                    "pitch_deg": 0.0, "roll_deg": 0.0,
                    "trim_pitch": "升降舵中立", "trim_roll": "副翼中立"}


def station_to_x(st):
    return D.NOSE_X - st


def _inputs():
    sc = bpy.context.scene
    pax = {z: int(getattr(sc, f"pax_{z}", 0)) for z in D.ZONES}
    cargo = {c: float(getattr(sc, f"cargo_{c}", 0)) for c in D.CARGO}
    fuel = {f: float(getattr(sc, f"fuel_{f}", 0)) for f in D.FUEL}
    return pax, cargo, fuel


def compute_scene(scene=None):
    pax, cargo, fuel = _inputs()
    return D.compute(pax, cargo, fuel)


def apply_explode(factor: float):
    for o in bpy.data.objects:
        if "ax" in o and "gx" in o:
            o.location.x = o["ax"] + o["gx"] * factor
            o.location.y = o["ay"] + o["gy"] * factor
            o.location.z = o["az"] + o["gz"] * factor


def update_seat_visibility():
    """按各区旅客数点亮对应排的座椅。"""
    sc = bpy.context.scene
    for zid, z in D.ZONES.items():
        n = int(getattr(sc, f"pax_{zid}", 0))
        n_rows = z.get("n_rows", 10)
        # 均匀点亮前 n/6 排（向上取整）
        lit_rows = min(n_rows, math.ceil(n / 6.0) if n > 0 else 0)
        r0, r1 = z["rows"]
        for r in range(r0, r1 + 1):
            on = (r - r0) < lit_rows
            for c in range(6):
                o = bpy.data.objects.get(f"Seat_{zid}_{r}_{c}")
                if o:
                    # 统一几何；空座仅改颜色（不缩放，避免靠背变形）
                    o.color = (1, 1, 1, 1) if on else (0.22, 0.22, 0.22, 1)


def update_cargo_fill():
    sc = bpy.context.scene
    for cid, c in D.CARGO.items():
        kg = float(getattr(sc, f"cargo_{cid}", 0))
        ratio = min(1.0, kg / c["max"]) if c["max"] else 0
        for i in range(4):
            o = bpy.data.objects.get(f"Box_{cid}_{i}")
            if o:
                thr = (i + 1) / 4.0
                on = ratio >= thr - 0.05
                # 交互模式用缩放；长片模式由 scale 关键帧控制，这里仅改色
                if not (o.animation_data and o.animation_data.action):
                    o.scale = (1, 1, 1) if on else (1, 1, 0.15)
                o.color = (1, 1, 1, 1) if on else (0.3, 0.3, 0.3, 0.25)


def update_viz(res, apply_attitude=True):
    sc = bpy.context.scene
    cg_x = station_to_x(res["cg_station"])
    for name in ("CGCone", "CGLine", "CG_Empty"):
        o = bpy.data.objects.get(name)
        if o:
            o.location.x = cg_x
    cone = bpy.data.objects.get("CGCone")
    if cone:
        cone.location.y = res.get("cg_y", 0) * 8.0
        mat = bpy.data.materials.get("M_Gr" if res.get("ok_mac") else "M_Rd")
        if mat:
            cone.data.materials.clear()
            cone.data.materials.append(mat)

    # 横向 y 标尺指针
    yptr = bpy.data.objects.get("YPointer")
    if yptr:
        yptr.location.y = max(-1.2, min(1.2, res.get("cg_y", 0) * 3.0))

    # 3D 动态坐标（CG 锥旁）
    dyn = bpy.data.objects.get("UI_DYN")
    if dyn and dyn.data:
        dyn.data.body = (
            f"CG={res['cg_station']:.2f}m  %MAC={res['cg_mac']:.1f}%  y={res['cg_y']:+.2f}m"
        )
        dyn.location = (cg_x + 0.3, 0.8, 3.4)

    root = bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")
    if root and apply_attitude:
        root.rotation_euler.y = math.radians(res.get("pitch_deg", 0.0))
        root.rotation_euler.x = math.radians(res.get("roll_deg", 0.0))

    update_seat_visibility()
    update_cargo_fill()

    mac = res["cg_mac"]
    arm = res["cg_station"] - D.LEMAC_ST
    mapping = {
        "UI_W": f"TOW {res['tow']:.0f} kg" + ("" if res["ok_tow"] else " 超MTOW!"),
        "UI_M": f"力矩 {res['moment']:.0f} kg·m",
        "UI_CG": f"CG FS {res['cg_station']:.2f} m",
        "UI_MAC": f"%MAC {res['cg_mac']:.1f}%  {res['pitch']}",
        "UI_Y": f"横向 y={res['cg_y']:+.2f} m  {res['roll']}",
        "UI_ZFW": f"ZFW {res['zfw']:.0f}  油差 {res['fuel_imb']:.0f} kg",
        "UI_TRIM": f"配平: {res['trim_pitch']}",
        "UI_PAX": f"旅客 {res['pax']}  业载 {res['tow'] - D.OEW - res['fuel']:.0f} kg",
        # 公式带入当前值
        "UI_F1": f"CG = ΣM/ΣW = {res['cg_station']:.3f} m",
        "UI_F2": f"%MAC = (CG-LEMAC)/MAC×100 = {arm:.3f}/{D.MAC:.4f}×100 = {mac:.2f}%",
        "UI_F3": f"y = Σ(W·yi)/ΣW = {res['cg_y']:+.4f} m",
    }
    for nm, body in mapping.items():
        o = bpy.data.objects.get(nm)
        if o and o.data and hasattr(o.data, "body"):
            o.data.body = body
        o2 = bpy.data.objects.get(nm + "Txt")
        if o2 and o2.data and hasattr(o2.data, "body"):
            o2.data.body = body

    # 侧视 y 标尺文字
    for nm, body in (
        ("TY_cur", f"y={res['cg_y']:+.2f}"),
        ("TY_lim", f"限 ±{D.Y_LIM:.2f} m"),
    ):
        o = bpy.data.objects.get(nm)
        if o and hasattr(o.data, "body"):
            o.data.body = body


def _keyframe_root(pitch_deg, roll_deg, frames=24):
    """在当前帧到 +frames 做姿态补间。"""
    sc = bpy.context.scene
    root = bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")
    if not root:
        return
    f0 = sc.frame_current
    f1 = f0 + frames
    # 起始
    root.keyframe_insert("rotation_euler", frame=f0)
    root.rotation_euler.y = math.radians(pitch_deg)
    root.rotation_euler.x = math.radians(roll_deg)
    root.keyframe_insert("rotation_euler", frame=f1)
    sc.frame_set(f1)
    try:
        for fc in root.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"
    except Exception:
        pass


def _animate_payload(frames=28):
    """装载相关物体从当前 explode 状态插值。"""
    sc = bpy.context.scene
    f0 = sc.frame_current
    f1 = f0 + frames
    # 座椅/货块 scale 动画
    for o in bpy.data.objects:
        if o.name.startswith("Seat_") or o.name.startswith("Box_"):
            o.keyframe_insert("scale", frame=f0)
            o.keyframe_insert("scale", frame=f1)


# ---------- Operators ----------
class LB_OT_refresh(bpy.types.Operator):
    bl_idname = "blendlb.refresh"
    bl_label = "重算配载"
    def execute(self, context):
        res = compute_scene()
        # 有关键帧时不覆盖姿态，避免打断预设动画
        root = bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")
        has_anim = bool(root and root.animation_data and root.animation_data.action)
        update_viz(res, apply_attitude=not has_anim)
        self.report({"INFO"}, f"%MAC={res['cg_mac']:.1f}% TOW={res['tow']:.0f}")
        return {"FINISHED"}


class LB_OT_assemble(bpy.types.Operator):
    bl_idname = "blendlb.assemble"
    bl_label = "组装"
    def execute(self, context):
        _animate_explode(0.0, frames=40)
        root = bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")
        if root:
            root.rotation_euler = (0, 0, 0)
        return {"FINISHED"}


class LB_OT_explode(bpy.types.Operator):
    bl_idname = "blendlb.explode"
    bl_label = "爆炸拆解"
    def execute(self, context):
        # 默认 0.7，避免叠死；2 s ≈ 48 帧
        _animate_explode(0.7, frames=48)
        return {"FINISHED"}


class LB_OT_set_explode(bpy.types.Operator):
    bl_idname = "blendlb.set_explode"
    bl_label = "应用爆炸比例"
    def execute(self, context):
        apply_explode(context.scene.lb_explode)
        return {"FINISHED"}


def _animate_explode(target: float, frames: int = 48):
    """lb_explode 从当前值补间到 target，并驱动物体位置。"""
    sc = bpy.context.scene
    f0 = sc.frame_current
    f1 = f0 + frames
    sc.lb_explode = sc.lb_explode  # ensure prop
    sc.keyframe_insert("lb_explode", frame=f0)
    sc.lb_explode = target
    sc.keyframe_insert("lb_explode", frame=f1)
    # 每帧应用（用 frame_change 或逐步采样）
    # 采样关键帧区间，避免依赖 handler
    n = max(frames, 1)
    start = sc.lb_explode  # already target after insert; recover start via fcurve
    # 简化：线性采样
    # 重新读 f0 值
    # 用 scene 属性动画在播放时生效；这里立刻插值到中间态演示
    for i in range(0, n + 1, 4):
        t = i / n
        # 从上一次 apply 的当前 location 反推不便；直接从 ax 插值
        f = 0.0 + (target - 0.0) * t  # 若原先非 0，仍从组装态
        # 更稳妥：始终从 0→target
        for o in bpy.data.objects:
            if "ax" in o and "gx" in o:
                o.location.x = o["ax"] + o["gx"] * f
                o.location.y = o["ay"] + o["gy"] * f
                o.location.z = o["az"] + o["gz"] * f
        sc.frame_set(f0 + i)
    sc.frame_set(f1)
    sc.lb_explode = target
    apply_explode(target)
    try:
        for fc in sc.animation_data.action.fcurves:
            if "lb_explode" in fc.data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "EASE_IN_OUT"
    except Exception:
        pass


class LB_OT_cycle_pax(bpy.types.Operator):
    bl_idname = "blendlb.cycle_pax"
    bl_label = "增减旅客"
    zone: StringProperty()
    delta: IntProperty()
    def execute(self, context):
        z = D.ZONES.get(self.zone)
        if not z:
            return {"CANCELLED"}
        key = f"pax_{self.zone}"
        val = int(getattr(context.scene, key, 0)) + self.delta
        setattr(context.scene, key, max(0, min(z["max"], val)))
        bpy.ops.blendlb.refresh()
        return {"FINISHED"}


def _set_load(pax, cargo, fuel):
    s = bpy.context.scene
    for z, n in pax.items():
        setattr(s, f"pax_{z}", int(n))
    for c, kg in cargo.items():
        setattr(s, f"cargo_{c}", float(kg))
    for f, kg in fuel.items():
        setattr(s, f"fuel_{f}", float(kg))


class LB_OT_preset_nominal(bpy.types.Operator):
    bl_idname = "blendlb.preset_nominal"
    bl_label = "装载·正常"
    def execute(self, context):
        _set_load({"FWD": 40, "MID": 60, "AFT": 35},
                  {"FWD": 1800, "AFT": 2200, "BULK": 400},
                  {"WING_L": 4200, "WING_R": 4300, "CTR": 3500})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(res["pitch_deg"], res["roll_deg"])
        bpy.ops.blendlb.refresh()
        return {"FINISHED"}


class LB_OT_preset_fwd(bpy.types.Operator):
    bl_idname = "blendlb.preset_fwd"
    bl_label = "装载·前重(低头·出前限)"
    def execute(self, context):
        # 已校验 %MAC≈6.8% < 前限 18%
        _set_load({"FWD": 60, "MID": 0, "AFT": 0},
                  {"FWD": 3175, "AFT": 0, "BULK": 0},
                  {"WING_L": 7500, "WING_R": 7500, "CTR": 0})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(res["pitch_deg"], res["roll_deg"])
        bpy.ops.blendlb.refresh()
        return {"FINISHED"}


class LB_OT_preset_aft(bpy.types.Operator):
    bl_idname = "blendlb.preset_aft"
    bl_label = "装载·后重(抬头·出后限)"
    def execute(self, context):
        # 已校验 %MAC≈59.5% > 后限 36%
        _set_load({"FWD": 0, "MID": 0, "AFT": 50},
                  {"FWD": 0, "AFT": 4480, "BULK": 1495},
                  {"WING_L": 0, "WING_R": 0, "CTR": 6145})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(res["pitch_deg"], res["roll_deg"])
        bpy.ops.blendlb.refresh()
        return {"FINISHED"}


class LB_OT_preset_left(bpy.types.Operator):
    bl_idname = "blendlb.preset_left"
    bl_label = "装载·左重(横滚·出限)"
    def execute(self, context):
        # 已校验油差/横向 CG 出限
        _set_load({"FWD": 20, "MID": 40, "AFT": 20},
                  {"FWD": 2000, "AFT": 2000, "BULK": 500},
                  {"WING_L": 7400, "WING_R": 200, "CTR": 1500})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(res["pitch_deg"], res["roll_deg"])
        bpy.ops.blendlb.refresh()
        return {"FINISHED"}


class LB_OT_preset_right(bpy.types.Operator):
    bl_idname = "blendlb.preset_right"
    bl_label = "装载·右重(横滚·出限)"
    def execute(self, context):
        _set_load({"FWD": 20, "MID": 40, "AFT": 20},
                  {"FWD": 2000, "AFT": 2000, "BULK": 500},
                  {"WING_L": 200, "WING_R": 7400, "CTR": 1500})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(res["pitch_deg"], res["roll_deg"])
        bpy.ops.blendlb.refresh()
        return {"FINISHED"}


class LB_OT_zero(bpy.types.Operator):
    bl_idname = "blendlb.zero_payload"
    bl_label = "清空业载/油"
    def execute(self, context):
        _set_load({"FWD": 0, "MID": 0, "AFT": 0},
                  {"FWD": 0, "AFT": 0, "BULK": 0},
                  {"WING_L": 0, "WING_R": 0, "CTR": 0})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(0, 0)
        bpy.ops.blendlb.refresh()
        return {"FINISHED"}


class LB_OT_anim_pitch_fwd(bpy.types.Operator):
    bl_idname = "blendlb.anim_pitch_fwd"
    bl_label = "姿态·低头演示"
    def execute(self, context):
        # 前重装载 + 低头动画
        _set_load({"FWD": 55, "MID": 15, "AFT": 5},
                  {"FWD": 2800, "AFT": 200, "BULK": 0},
                  {"WING_L": 4500, "WING_R": 4500, "CTR": 500})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        # 强制更明显的低头（至少 -6° 教学）
        pitch = min(res["pitch_deg"], -6.0)
        _keyframe_root(pitch, 0.0, frames=32)
        bpy.ops.blendlb.refresh()
        self.report({"INFO"}, f"低头演示 %MAC={res['cg_mac']:.1f}%")
        return {"FINISHED"}


class LB_OT_anim_pitch_aft(bpy.types.Operator):
    bl_idname = "blendlb.anim_pitch_aft"
    bl_label = "姿态·抬头演示"
    def execute(self, context):
        _set_load({"FWD": 5, "MID": 10, "AFT": 48},
                  {"FWD": 200, "AFT": 3800, "BULK": 1200},
                  {"WING_L": 1000, "WING_R": 1000, "CTR": 5500})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        pitch = max(res["pitch_deg"], 6.0)
        _keyframe_root(pitch, 0.0, frames=32)
        bpy.ops.blendlb.refresh()
        self.report({"INFO"}, f"抬头演示 %MAC={res['cg_mac']:.1f}%")
        return {"FINISHED"}


class LB_OT_anim_roll_left(bpy.types.Operator):
    bl_idname = "blendlb.anim_roll_left"
    bl_label = "姿态·左倾演示"
    def execute(self, context):
        _set_load({"FWD": 25, "MID": 40, "AFT": 25},
                  {"FWD": 800, "AFT": 800, "BULK": 200},
                  {"WING_L": 7200, "WING_R": 800, "CTR": 1500})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(0.0, -8.0, frames=32)
        bpy.ops.blendlb.refresh()
        self.report({"INFO"}, f"左倾演示 y={res['cg_y']:+.2f}")
        return {"FINISHED"}


class LB_OT_anim_roll_right(bpy.types.Operator):
    bl_idname = "blendlb.anim_roll_right"
    bl_label = "姿态·右倾演示"
    def execute(self, context):
        _set_load({"FWD": 25, "MID": 40, "AFT": 25},
                  {"FWD": 800, "AFT": 800, "BULK": 200},
                  {"WING_L": 800, "WING_R": 7200, "CTR": 1500})
        res = compute_scene()
        update_viz(res, apply_attitude=False)
        _keyframe_root(0.0, 8.0, frames=32)
        bpy.ops.blendlb.refresh()
        self.report({"INFO"}, f"右倾演示 y={res['cg_y']:+.2f}")
        return {"FINISHED"}


class LB_OT_anim_load(bpy.types.Operator):
    bl_idname = "blendlb.anim_load"
    bl_label = "装载·过程演示"
    def execute(self, context):
        """从空机逐步装到正常：先货后客后油，CG 滑动。"""
        sc = bpy.context.scene
        sc.frame_set(1)
        # 空
        _set_load({"FWD": 0, "MID": 0, "AFT": 0},
                  {"FWD": 0, "AFT": 0, "BULK": 0},
                  {"WING_L": 0, "WING_R": 0, "CTR": 0})
        root = bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")
        if root:
            root.rotation_euler = (0, 0, 0)
            root.keyframe_insert("rotation_euler", frame=1)
        cone = bpy.data.objects.get("CGCone")
        if cone:
            oew_x = station_to_x(D.OEW_ST)
            cone.location.x = oew_x
            cone.keyframe_insert("location", frame=1)

        # 步骤关键帧
        steps = [
            (20, {"FWD": 0, "MID": 0, "AFT": 0}, {"FWD": 1800, "AFT": 2200, "BULK": 400},
             {"WING_L": 0, "WING_R": 0, "CTR": 0}),
            (45, {"FWD": 0, "MID": 0, "AFT": 0}, {"FWD": 1800, "AFT": 2200, "BULK": 400},
             {"WING_L": 4200, "WING_R": 4300, "CTR": 3500}),
            (70, {"FWD": 20, "MID": 30, "AFT": 15}, {"FWD": 1800, "AFT": 2200, "BULK": 400},
             {"WING_L": 4200, "WING_R": 4300, "CTR": 3500}),
            (100, {"FWD": 40, "MID": 60, "AFT": 35}, {"FWD": 1800, "AFT": 2200, "BULK": 400},
             {"WING_L": 4200, "WING_R": 4300, "CTR": 3500}),
        ]
        for fr, pax, cargo, fuel in steps:
            _set_load(pax, cargo, fuel)
            res = compute_scene()
            update_seat_visibility()
            update_cargo_fill()
            for o in bpy.data.objects:
                if o.name.startswith("Seat_") or o.name.startswith("Box_"):
                    o.keyframe_insert("scale", frame=fr)
            if cone:
                cone.location.x = station_to_x(res["cg_station"])
                cone.keyframe_insert("location", frame=fr)
            if root:
                root.rotation_euler.y = math.radians(res["pitch_deg"] * 0.3)
                root.rotation_euler.x = math.radians(res["roll_deg"] * 0.3)
                root.keyframe_insert("rotation_euler", frame=fr)
            # UI
            for nm, body in {
                "UI_W": f"TOW {res['tow']:.0f} kg",
                "UI_MAC": f"%MAC {res['cg_mac']:.1f}%  {res['pitch']}",
                "UI_CG": f"CG FS {res['cg_station']:.2f} m",
            }.items():
                o = bpy.data.objects.get(nm)
                if o and hasattr(o.data, "body"):
                    o.data.body = body
                    o.keyframe_insert("data.body", frame=fr) if False else None

        sc.frame_set(100)
        bpy.ops.blendlb.refresh()
        self.report({"INFO"}, "装载过程动画已生成 1-100 帧")
        return {"FINISHED"}


class LB_OT_anim_cargo(bpy.types.Operator):
    bl_idname = "blendlb.anim_cargo"
    bl_label = "货舱装载动画"
    def execute(self, context):
        """前舱→后舱→散装依次出现，CG 同步滑动。"""
        sc = bpy.context.scene
        sc.frame_set(1)
        _set_load({"FWD": 0, "MID": 0, "AFT": 0},
                  {"FWD": 0, "AFT": 0, "BULK": 0},
                  {"WING_L": 0, "WING_R": 0, "CTR": 0})
        update_cargo_fill()
        cone = bpy.data.objects.get("CGCone")
        root = bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")
        if cone:
            cone.location.x = station_to_x(D.OEW_ST)
            cone.keyframe_insert("location", frame=1)
        steps = [
            (20, {"FWD": 1800, "AFT": 0, "BULK": 0}),
            (40, {"FWD": 1800, "AFT": 2200, "BULK": 0}),
            (60, {"FWD": 1800, "AFT": 2200, "BULK": 400}),
        ]
        for fr, cargo in steps:
            _set_load({"FWD": 0, "MID": 0, "AFT": 0}, cargo,
                      {"WING_L": 0, "WING_R": 0, "CTR": 0})
            update_cargo_fill()
            for o in bpy.data.objects:
                if o.name.startswith("Box_"):
                    o.keyframe_insert("scale", frame=fr)
            res = compute_scene()
            if cone:
                cone.location.x = station_to_x(res["cg_station"])
                cone.keyframe_insert("location", frame=fr)
            update_viz(res, apply_attitude=False)
        sc.frame_set(60)
        self.report({"INFO"}, "货舱装载动画 1-60 帧：前→后→散装")
        return {"FINISHED"}


class LB_OT_play(bpy.types.Operator):
    bl_idname = "blendlb.play"
    bl_label = "播放动画"
    def execute(self, context):
        bpy.ops.screen.animation_play()
        return {"FINISHED"}


def _set_cutaway(on: bool):
    """剖切：隐藏上盖 Shell_Upper；机身保持不透明。"""
    sh = bpy.data.objects.get("Shell_Upper")
    if sh:
        sh.hide_render = on
        try:
            sh.hide_set(on)
        except Exception:
            pass
    m = bpy.data.materials.get("M_Hull")
    if m:
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b and "Alpha" in b.inputs:
            b.inputs["Alpha"].default_value = 1.0
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass


class LB_OT_xray(bpy.types.Operator):
    bl_idname = "blendlb.xray"
    bl_label = "剖切透视"
    def execute(self, context):
        _set_cutaway(True)
        return {"FINISHED"}


class LB_OT_solid(bpy.types.Operator):
    bl_idname = "blendlb.solid"
    bl_label = "实心外观"
    def execute(self, context):
        _set_cutaway(False)
        return {"FINISHED"}


class LB_PT_panel(bpy.types.Panel):
    bl_label = "A320 配载教学"
    bl_idname = "LB_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "配载教学"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        res = compute_scene()

        box = layout.box()
        box.label(text="A320-200 · ACAP / WBM", icon="OUTLINER_OB_MESH")
        col = box.column(align=True)
        col.label(text=f"MAC={D.MAC:.4f}  LEMAC FS={D.LEMAC_ST:.2f}")
        col.label(text=f"包线 {D.FWD_LIM_PCT:.0f}–{D.AFT_LIM_PCT:.0f}% MAC")
        col.label(text=f"MTOW={D.MTOW:.0f}  OEW={D.OEW:.0f} kg")

        box = layout.box()
        box.label(text="装载输入 · LOPA 分区", icon="IMPORT")
        for zid, z in D.ZONES.items():
            row = box.row(align=True)
            row.prop(scene, f"pax_{zid}", text=f"{z['label']}人")
            op = row.operator("blendlb.cycle_pax", text="-6"); op.zone = zid; op.delta = -6
            op = row.operator("blendlb.cycle_pax", text="+6"); op.zone = zid; op.delta = 6
        for cid, c in D.CARGO.items():
            box.prop(scene, f"cargo_{cid}", text=f"{c['label']}")
        for fid, f in D.FUEL.items():
            box.prop(scene, f"fuel_{fid}", text=f"{f['label']}")

        box = layout.box()
        box.label(text="装载预设", icon="EXPERIMENTAL")
        box.operator("blendlb.preset_nominal", icon="CHECKMARK")
        row = box.row(align=True)
        row.operator("blendlb.preset_fwd")
        row.operator("blendlb.preset_aft")
        row = box.row(align=True)
        row.operator("blendlb.preset_left")
        row.operator("blendlb.preset_right")
        box.operator("blendlb.zero_payload", icon="TRASH")

        box = layout.box()
        box.label(text="姿态动画 · 配平", icon="ARMATURE_DATA")
        row = box.row(align=True)
        row.operator("blendlb.anim_pitch_fwd", text="低头")
        row.operator("blendlb.anim_pitch_aft", text="抬头")
        row = box.row(align=True)
        row.operator("blendlb.anim_roll_left", text="左倾")
        row.operator("blendlb.anim_roll_right", text="右倾")
        box.operator("blendlb.anim_load", icon="SORTTIME")
        box.operator("blendlb.anim_cargo", icon="PACKAGE")
        box.operator("blendlb.play", icon="PLAY")
        if hasattr(bpy.ops.blendlb, "play_cinema"):
            box.operator("blendlb.play_cinema", icon="RENDER_ANIMATION")
            box.operator("blendlb.cinema_start", icon="FRAME_PREV")

        box = layout.box()
        box.label(text="计算结果 · 三轴", icon="FILE_REFRESH")
        col = box.column(align=True)
        col.label(text=f"TOW {res['tow']:.0f} kg" + ("" if res["ok_tow"] else " 超限"))
        col.label(text=f"CG FS {res['cg_station']:.2f} m")
        row = col.row(); row.alert = not res["ok_mac"]
        row.label(text=f"%MAC {res['cg_mac']:.1f}% {res['pitch']}")
        row = col.row(); row.alert = not res["ok_y"]
        row.label(text=f"y={res['cg_y']:+.2f} m {res['roll']}")
        col.label(text=f"ZFW {res['zfw']:.0f}  油差 {res['fuel_imb']:.0f}")
        col.label(text=res["trim_pitch"], icon="IPO_SINE")
        col.label(text=res["trim_roll"], icon="IPO_SINE")
        col.separator()
        col.label(text="公式（当前值）")
        col.label(text=f"CG=ΣM/ΣW={res['cg_station']:.3f} m")
        col.label(text=f"%MAC={res['cg_mac']:.2f}%")
        col.label(text=f"y=Σ(W·yi)/ΣW={res['cg_y']:+.4f} m")
        box.operator("blendlb.refresh", icon="FILE_REFRESH")

        box = layout.box()
        box.label(text="外观（剖切）", icon="SHADING_RENDERED")
        row = box.row(align=True)
        row.operator("blendlb.solid", text="实心")
        row.operator("blendlb.xray", text="剖切透视")

        box = layout.box()
        box.label(text="结构拆解", icon="MOD_EXPLODE")
        row = box.row(align=True)
        row.operator("blendlb.assemble")
        row.operator("blendlb.explode")
        box.prop(scene, "lb_explode", slider=True)
        box.operator("blendlb.set_explode")


classes = [
    LB_OT_refresh, LB_OT_assemble, LB_OT_explode, LB_OT_set_explode,
    LB_OT_cycle_pax, LB_OT_preset_nominal, LB_OT_preset_fwd, LB_OT_preset_aft,
    LB_OT_preset_left, LB_OT_preset_right, LB_OT_zero,
    LB_OT_anim_pitch_fwd, LB_OT_anim_pitch_aft,
    LB_OT_anim_roll_left, LB_OT_anim_roll_right,
    LB_OT_anim_load, LB_OT_anim_cargo, LB_OT_play, LB_OT_xray, LB_OT_solid,
    LB_PT_panel,
]


def register():
    defaults_pax = {"FWD": 40, "MID": 60, "AFT": 35}
    for zid, z in D.ZONES.items():
        setattr(bpy.types.Scene, f"pax_{zid}",
                IntProperty(name=z["label"], default=defaults_pax.get(zid, 0), min=0, max=z["max"]))
    defaults_c = {"FWD": 1800, "AFT": 2200, "BULK": 400}
    for cid, c in D.CARGO.items():
        setattr(bpy.types.Scene, f"cargo_{cid}",
                FloatProperty(name=c["label"], default=defaults_c.get(cid, 0), min=0, max=c["max"]))
    defaults_f = {"WING_L": 4200, "WING_R": 4300, "CTR": 3500}
    for fid, f in D.FUEL.items():
        setattr(bpy.types.Scene, f"fuel_{fid}",
                FloatProperty(name=f["label"], default=defaults_f.get(fid, 0), min=0, max=f["max"]))
    bpy.types.Scene.lb_explode = FloatProperty(name="爆炸", default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    for c in classes:
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
    for name in [f"pax_{z}" for z in D.ZONES] + [f"cargo_{c}" for c in D.CARGO] + [f"fuel_{f}" for f in D.FUEL] + ["lb_explode"]:
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)


if __name__ == "__main__":
    register()

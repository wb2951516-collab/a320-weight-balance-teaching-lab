"""
v9 教学长片 + 结构修正
- 发动机挂翼下，油箱板默认隐藏
- 座椅统一（有靠背）
- 分层爆炸：货下、客上、发动机前
- 剖切货舱 1/3/4
- 7 段×6s 组装长片（24fps，共 1008 帧）
- 帧回调刷新 MAC/公式
"""
import bpy, math, os, sys, importlib
from mathutils import Vector

ROOT_DIR = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模"
OUT = os.path.join(ROOT_DIR, "output", "配载平衡教学模型.blend")
PREVIEW = os.path.join(ROOT_DIR, "output", "preview")
SP = os.path.join(ROOT_DIR, "scripts")
sys.path.insert(0, SP)
import a320_data as D
import loadbalance_panel as lbp

FPS = 24
STAGE_S = 6
STAGE_F = FPS * STAGE_S  # 144
N_STAGES = 7
TOTAL_F = STAGE_F * N_STAGES  # 1008

# 阶段：名称, 装载, 相机位置, 相机旋转(deg), 出现的对象名前缀
# 装载: pax, cargo, fuel
def L(pax=None, cargo=None, fuel=None):
    p = {"FWD": 0, "MID": 0, "AFT": 0}
    c = {"FWD": 0, "AFT": 0, "BULK": 0}
    f = {"WING_L": 0, "WING_R": 0, "CTR": 0}
    if pax: p.update(pax)
    if cargo: c.update(cargo)
    if fuel: f.update(fuel)
    return p, c, f

STAGES = [
    # 0 机身下壳
    ("机身结构", L(), (40, -35, 12), (68, 0, 50),
     ["Fuselage", "CabinFloor", "CargoFloor", "BellyFairing", "Ground"]),
    # 1 机翼尾翼
    ("机翼与尾翼", L(), (42, -40, 16), (64, 0, 52),
     ["Wing_", "HS_", "VS", "Fence_", "Stripe_", "Win_"]),
    # 2 发动机
    ("发动机吊挂", L(), (30, -25, 8), (72, 0, 58),
     ["E_L", "E_R", "Nacelle_", "GN", "GM", "GW", "Door_"]),
    # 3 货舱 1/3/4
    ("货舱 1→3→4", L(cargo={"FWD": 1800, "AFT": 2200, "BULK": 400}),
     (20, -18, 10), (70, 0, 25),
     ["Box_", "Bag_"]),
    # 4 座椅
    ("客舱座椅", L(pax={"FWD": 40, "MID": 60, "AFT": 35},
                  cargo={"FWD": 1800, "AFT": 2200, "BULK": 400}),
     (12, -16, 12), (68, 0, 15),
     ["Seat_"]),
    # 5 燃油
    ("燃油", L(pax={"FWD": 40, "MID": 60, "AFT": 35},
               cargo={"FWD": 1800, "AFT": 2200, "BULK": 400},
               fuel={"WING_L": 4200, "WING_R": 4300, "CTR": 3500}),
     (35, -30, 14), (66, 0, 48),
     ["FW_", "FC"]),
    # 6 姿态配平
    ("姿态与配平", L(pax={"FWD": 40, "MID": 60, "AFT": 35},
                    cargo={"FWD": 1800, "AFT": 2200, "BULK": 400},
                    fuel={"WING_L": 4200, "WING_R": 4300, "CTR": 3500}),
     (48, -38, 16), (68, 0, 52),
     []),
]


def sx(st):
    return D.NOSE_X - st


def get_root():
    return bpy.data.objects.get("AC_ROOT") or bpy.data.objects.get("ROOT")


def match_prefixes(name, prefixes):
    if not prefixes:
        return False
    return any(name.startswith(p) for p in prefixes)


def fix_engines_fuel_seats():
    root = get_root()
    # 发动机：翼下
    eng_z = -1.90
    eng_y = 5.55
    eng_x = sx(14.8)
    for side, nm in ((-1, "E_L"), (1, "E_R")):
        for base in (nm,):
            o = bpy.data.objects.get(base)
            if o:
                o.location = (eng_x, side * eng_y, eng_z)
        for suf, dx in (("N", 1.7), ("X", -2.0), ("P", 0.35)):
            o = bpy.data.objects.get(nm + suf)
            if o:
                if suf == "P":
                    o.location = (eng_x + dx, side * eng_y * 0.92, eng_z + 0.95)
                else:
                    o.location = (eng_x + dx, side * eng_y, eng_z)
    # 油箱绿板：默认隐藏（教学长片第 5 段再显示）
    for n in ("FW_-1", "FW_1", "FC"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = True
            try:
                o.hide_set(True)
            except Exception:
                pass
    # 座椅：取消压扁空座，统一几何；空座改暗色
    for o in bpy.data.objects:
        if o.name.startswith("Seat_") and not o.name.startswith("SeatB") and not o.name.startswith("SeatH"):
            o.scale = (1, 1, 1)
    # 货舱编号标签
    labels = [
        ("CARGO_TAG_1", "1舱 前货舱", sx(12.8), 0, -0.3),
        ("CARGO_TAG_3", "3舱 后货舱", sx(24.6), 0, -0.3),
        ("CARGO_TAG_4", "4舱 散装", sx(28.8), 0, -0.3),
    ]
    ye = bpy.data.materials.get("M_Ye") or bpy.data.materials.get("M_Lim")
    for name, body, x, y, z in labels:
        if bpy.data.objects.get(name):
            continue
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        cu.size = 0.28
        cu.extrude = 0.004
        o = bpy.data.objects.new(name, cu)
        o.location = (x, y, z)
        o.rotation_euler = (math.radians(90), 0, 0)
        bpy.context.collection.objects.link(o)
        if ye:
            cu.materials.append(ye)
        if root:
            o.parent = root
            o.matrix_parent_inverse = root.matrix_world.inverted()
    print("engines_seats_fixed")


def setup_layered_explode_offsets():
    """货舱下、行李下、座椅上、发动机前、尾翼后上。"""
    for o in bpy.data.objects:
        n = o.name
        if n.startswith("Seat_") and not n.startswith("SeatB") and not n.startswith("SeatH"):
            o["gx"], o["gy"], o["gz"] = (0, 0, 5.5)
        elif n.startswith("SeatB_") or n.startswith("SeatH_"):
            o["gx"], o["gy"], o["gz"] = (0, 0, 5.5)
        elif n.startswith("Box_"):
            # 1舱/3舱/4舱
            if "FWD" in n:
                o["gx"], o["gy"], o["gz"] = (0, 3.5, -6.0)
            elif "AFT" in n:
                o["gx"], o["gy"], o["gz"] = (0, 3.5, -7.0)
            else:
                o["gx"], o["gy"], o["gz"] = (0, 3.5, -8.0)
        elif n.startswith("Bag_"):
            o["gx"], o["gy"], o["gz"] = (0, 2.5, -5.0)
        elif n.startswith("E_") and len(n) <= 4:
            side = -1 if "L" in n else 1
            o["gx"], o["gy"], o["gz"] = (6.0, side * 4.0, -0.5)
        elif n in ("HS_L", "HS_R", "VS"):
            o["gx"], o["gy"], o["gz"] = (-6.0, 0, 3.5)
        if "ax" not in o and ("gx" in o):
            o["ax"], o["ay"], o["az"] = o.location.x, o.location.y, o.location.z


def clear_anim():
    for o in bpy.data.objects:
        if o.animation_data:
            o.animation_data_clear()
    sc = bpy.context.scene
    if sc.animation_data:
        sc.animation_data_clear()
    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") == "lb_cinema_handler" or "lb_cinema" in str(h):
            bpy.app.handlers.frame_change_post.remove(h)


def hide_stage_objects(only_show_prefixes, all_prefixes):
    """按阶段显示/隐藏。only_show 为空表示全显（最终态）。"""
    for o in bpy.data.objects:
        if not match_prefixes(o.name, all_prefixes):
            continue
        if not only_show_prefixes:
            show = True
        else:
            show = match_prefixes(o.name, only_show_prefixes)
        o.hide_render = not show
        try:
            o.hide_set(not show)
        except Exception:
            pass


def build_cinema():
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = TOTAL_F
    cam = bpy.data.objects.get("TeachCam") or sc.camera
    root = get_root()

    all_pref = []
    for st in STAGES:
        all_pref.extend(st[4])
    all_pref = list(dict.fromkeys(all_pref))

    # 阶段装载表（供 handler）
    sc["lb_stage_count"] = N_STAGES
    sc["lb_stage_frames"] = STAGE_F
    for i, (title, loads, cam_loc, cam_rot, prefs) in enumerate(STAGES):
        sc[f"lb_stage_{i}_title"] = title
        # 存 JSON 简表
        p, c, f = loads
        sc[f"lb_stage_{i}_pax"] = ",".join(str(p[k]) for k in ("FWD", "MID", "AFT"))
        sc[f"lb_stage_{i}_cargo"] = ",".join(str(int(c[k])) for k in ("FWD", "AFT", "BULK"))
        sc[f"lb_stage_{i}_fuel"] = ",".join(str(int(f[k])) for k in ("WING_L", "WING_R", "CTR"))

    for i, (title, loads, cam_loc, cam_rot, prefs) in enumerate(STAGES):
        f0 = 1 + i * STAGE_F
        f1 = f0 + STAGE_F - 1
        # 显示集合：本阶段起累积
        show = []
        for j in range(i + 1):
            show.extend(STAGES[j][4])
        show = list(dict.fromkeys(show))
        # 在 f0 设置可见性关键帧（用 hide_render 不易关键帧，用 handler）
        # 相机
        if cam:
            cam.location = cam_loc
            cam.rotation_euler = tuple(math.radians(a) for a in cam_rot)
            cam.keyframe_insert("location", frame=f0)
            cam.keyframe_insert("rotation_euler", frame=f0)
            cam.keyframe_insert("location", frame=f1)
            cam.keyframe_insert("rotation_euler", frame=f1)
        # 机身姿态：最后阶段轻微俯仰
        if root and i == N_STAGES - 1:
            root.rotation_euler = (0, 0, 0)
            root.keyframe_insert("rotation_euler", frame=f0)
            root.rotation_euler.y = math.radians(-8)
            root.keyframe_insert("rotation_euler", frame=f0 + STAGE_F // 2)
            root.rotation_euler.y = math.radians(5)
            root.rotation_euler.x = math.radians(-3)
            root.keyframe_insert("rotation_euler", frame=f1)

    # 相机曲线缓动（兼容 4.x/5.x Action）
    if cam and cam.animation_data and cam.animation_data.action:
        act = cam.animation_data.action
        fcurves = []
        if hasattr(act, "fcurves"):
            fcurves = list(act.fcurves)
        else:
            try:
                for layer in act.layers:
                    for strip in layer.strips:
                        for cb in strip.channelbags:
                            fcurves.extend(cb.fcurves)
            except Exception:
                pass
        for fc in fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_IN_OUT"

    # 货舱内部按 1→3→4 出现：Box_FWD / Box_AFT / Box_BULK 在阶段 3 内分三段
    f3 = 1 + 3 * STAGE_F
    for cid, frac in (("FWD", 0.0), ("AFT", 0.33), ("BULK", 0.66)):
        for i in range(4):
            o = bpy.data.objects.get(f"Box_{cid}_{i}")
            if not o:
                continue
            fr = f3 + int(frac * STAGE_F)
            o.scale = (0.01, 0.01, 0.01)
            o.keyframe_insert("scale", frame=max(1, fr - 2))
            o.scale = (1, 1, 1)
            o.keyframe_insert("scale", frame=fr + 18)

    # 座椅分排出现
    f4 = 1 + 4 * STAGE_F
    rows = []
    for zid, z in D.ZONES.items():
        r0, r1 = z["rows"]
        for r in range(r0, r1 + 1):
            rows.append((zid, r))
    rows.sort(key=lambda x: x[1])
    for idx, (zid, r) in enumerate(rows):
        fr = f4 + int(idx / max(len(rows), 1) * (STAGE_F - 20))
        for c in range(6):
            for pref in ("Seat_", "SeatB_", "SeatH_"):
                o = bpy.data.objects.get(f"{pref}{zid}_{r}_{c}")
                if not o:
                    continue
                o.scale = (0.01, 0.01, 0.01)
                o.keyframe_insert("scale", frame=max(1, fr - 2))
                o.scale = (1, 1, 1)
                o.keyframe_insert("scale", frame=fr + 12)

    # 帧处理器：可见性 + MAC 文字
    def lb_cinema_handler(scene, deps=None):
        f = scene.frame_current
        i = min(max(0, (f - 1) // STAGE_F), N_STAGES - 1)
        title = scene.get(f"lb_stage_{i}_title", "")
        show = []
        for j in range(i + 1):
            show.extend(STAGES[j][4])
        show = list(dict.fromkeys(show))
        for o in bpy.data.objects:
            if not match_prefixes(o.name, all_pref):
                continue
            # 已有 scale 动画的物体不靠 hide
            vis = match_prefixes(o.name, show) if show else True
            if o.name.startswith("FW_") or o.name == "FC":
                vis = i >= 5
            if o.name.startswith("Shell_"):
                vis = True
            o.hide_render = not vis
            try:
                if o.name.startswith(("Seat", "Box", "Bag", "E_", "FW", "FC", "Wing", "HS", "VS", "Fuselage")):
                    o.hide_set(not vis)
            except Exception:
                pass
        # 装载计算
        def parse(key):
            s = scene.get(key, "0,0,0")
            return [int(float(x)) for x in str(s).split(",")]
        p = parse(f"lb_stage_{i}_pax")
        c = parse(f"lb_stage_{i}_cargo")
        fu = parse(f"lb_stage_{i}_fuel")
        pax = dict(zip(("FWD", "MID", "AFT"), p))
        cargo = dict(zip(("FWD", "AFT", "BULK"), c))
        fuel = dict(zip(("WING_L", "WING_R", "CTR"), fu))
        res = D.compute(pax, cargo, fuel)
        for nm, body in (
            ("UI_DYN", f"[{title}] CG={res['cg_station']:.2f}m %MAC={res['cg_mac']:.1f}% y={res['cg_y']:+.2f}m"),
            ("UI_W", f"TOW {res['tow']:.0f} kg"),
            ("UI_MAC", f"%MAC {res['cg_mac']:.1f}% {res['pitch']}"),
            ("UI_CG", f"CG FS {res['cg_station']:.2f} m"),
            ("UI_F1", f"CG=ΣM/ΣW={res['cg_station']:.3f} m"),
            ("UI_F2", f"%MAC={res['cg_mac']:.2f}%  {res['pitch']}"),
            ("UI_F3", f"y=Σ(W·yi)/ΣW={res['cg_y']:+.4f} m"),
            ("UI_STAGE", f"阶段 {i+1}/{N_STAGES} {title}"),
        ):
            o = bpy.data.objects.get(nm)
            if o and o.data and hasattr(o.data, "body"):
                o.data.body = body
        # CG 锥
        cone = bpy.data.objects.get("CGCone")
        if cone:
            cone.location.x = sx(res["cg_station"])
            cone.location.y = res["cg_y"] * 8

    # 注册 handler
    for h in list(bpy.app.handlers.frame_change_post):
        if "lb_cinema" in getattr(h, "__name__", str(h)):
            bpy.app.handlers.frame_change_post.remove(h)
    lb_cinema_handler.__name__ = "lb_cinema_handler"
    bpy.app.handlers.frame_change_post.append(lb_cinema_handler)
    sc.frame_set(1)
    lb_cinema_handler(sc)
    print("cinema_built frames", TOTAL_F)


def try_hdri():
    """尝试下载小尺寸 HDRI；失败则用日光天空。"""
    dest = os.path.join(ROOT_DIR, "assets", "studio_small_08_1k.hdr")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.isfile(dest):
        url = "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/studio_small_08_1k.hdr"
        try:
            import urllib.request
            urllib.request.urlretrieve(url, dest)
            print("hdri_downloaded", dest)
        except Exception as e:
            print("hdri_fail", e)
            return
    sc = bpy.context.scene
    world = sc.world or bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    try:
        tex = nt.nodes.new("ShaderNodeTexEnvironment")
        tex.image = bpy.data.images.load(dest)
        nt.links.new(tex.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.9
        print("hdri_applied")
    except Exception as e:
        bg.inputs[0].default_value = (0.4, 0.45, 0.55, 1)
        bg.inputs[1].default_value = 1.0
        print("hdri_sky_fallback", e)
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def register_panel():
    importlib.reload(lbp)
    try:
        lbp.unregister()
    except Exception:
        pass
    lbp.register()
    # 长片播放算子
    if not hasattr(bpy.ops.blendlb, "play_cinema"):
        class LB_OT_play_cinema(bpy.types.Operator):
            bl_idname = "blendlb.play_cinema"
            bl_label = "播放组装长片"

            def execute(self, context):
                sc = context.scene
                sc.frame_start = 1
                sc.frame_end = TOTAL_F
                sc.frame_set(1)
                bpy.ops.screen.animation_play()
                self.report({"INFO"}, f"组装长片 {TOTAL_F} 帧 / {TOTAL_F/FPS:.0f} 秒")
                return {"FINISHED"}

        class LB_OT_cinema_start(bpy.types.Operator):
            bl_idname = "blendlb.cinema_start"
            bl_label = "长片·回到开头"
            def execute(self, context):
                context.scene.frame_set(1)
                return {"FINISHED"}

        try:
            bpy.utils.register_class(LB_OT_play_cinema)
            bpy.utils.register_class(LB_OT_cinema_start)
            lbp.classes.extend([LB_OT_play_cinema, LB_OT_cinema_start])
        except Exception as e:
            print("cinema ops", e)


def main():
    os.makedirs(PREVIEW, exist_ok=True)
    fix_engines_fuel_seats()
    setup_layered_explode_offsets()
    clear_anim()
    build_cinema()
    try_hdri()
    register_panel()
    # 标题物体
    root = get_root()
    if not bpy.data.objects.get("UI_STAGE"):
        cu = bpy.data.curves.new("UI_STAGE", "FONT")
        cu.body = "阶段 1/7"
        cu.size = 0.32
        o = bpy.data.objects.new("UI_STAGE", cu)
        o.location = (8, -14.5, 5.8)
        o.rotation_euler = (math.radians(90), 0, 0)
        bpy.context.collection.objects.link(o)
        m = bpy.data.materials.get("M_Wh") or bpy.data.materials.get("M_White")
        if m:
            cu.materials.append(m)
        if root:
            o.parent = root
            o.matrix_parent_inverse = root.matrix_world.inverted()

    sc = bpy.context.scene
    sc.frame_set(1)
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 900
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("SAVED_V9", OUT)

    # 预览：第1/4/7段
    cam = bpy.data.objects.get("TeachCam")
    for label, fr in (("s1_hull", 30), ("s4_seats", 1 + 4 * STAGE_F + 80), ("s7_final", TOTAL_F - 10)):
        sc.frame_set(fr)
        sc.render.filepath = os.path.join(PREVIEW, f"v9_{label}.png")
        bpy.ops.render.render(write_still=True)
        print("shot", label, "frame", fr)
    sc.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("DONE_V9")


if __name__ == "__main__":
    main()

"""修复 v9：默认整机可见；长片仅在播放时分阶段显隐；恢复机翼/发动机/座椅。"""
import bpy, math, os, sys, importlib

ROOT_DIR = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模"
SP = os.path.join(ROOT_DIR, "scripts")
OUT = os.path.join(ROOT_DIR, "output", "配载平衡教学模型.blend")
sys.path.insert(0, SP)

FPS = 24
STAGE_F = 144
N_STAGES = 7
TOTAL_F = STAGE_F * N_STAGES

def show_all():
    for o in bpy.data.objects:
        o.hide_render = False
        try:
            o.hide_set(False)
        except Exception:
            pass
        # 座椅/货块 scale 若被关键帧压成 0.01，强制恢复组装态
        if o.name.startswith(("Seat", "Box_", "Bag_")):
            # 若有 scale 动画，跳到最后一帧再恢复
            pass
    # 时间轴末尾=组装完成
    sc = bpy.context.scene
    sc.frame_set(TOTAL_F)
    for o in bpy.data.objects:
        if o.name.startswith(("Seat", "Box_", "Bag_")):
            o.scale = (1, 1, 1)
    # 油箱板：教学默认可见但半透明（翼内），不再当「发动机绿板」
    for n in ("FW_-1", "FW_1"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = False
            try:
                o.hide_set(False)
            except Exception:
                pass


def rebuild_handler():
    """长片 handler：仅当 1≤frame<TOTAL 且处于播放/拖动时按阶段显隐；
    组装完成帧(TOTAL_F)全部显示。"""
    # 移除旧 handler
    for h in list(bpy.app.handlers.frame_change_post):
        name = getattr(h, "__name__", str(h))
        if "lb_cinema" in name or "cinema" in name.lower():
            try:
                bpy.app.handlers.frame_change_post.remove(h)
            except Exception:
                pass

    STAGES_PREF = [
        ["Fuselage", "CabinFloor", "CargoFloor", "BellyFairing", "Ground", "Shell_"],
        ["Wing_", "HS_", "VS", "Fence_", "Stripe_", "Win_", "CockpitGlass", "Logo_"],
        ["E_L", "E_R", "Nacelle_", "GN", "GM", "GW", "Door_"],
        ["Box_", "Bag_", "CARGO_TAG_"],
        ["Seat_"],
        ["FW_", "FC"],
        [],  # 终态全显
    ]

    def lb_cinema_handler(scene, deps=None):
        f = scene.frame_current
        # 组装完成或超出：全部显示
        if f >= TOTAL_F:
            for o in bpy.data.objects:
                if o.name.startswith(("Seat", "Box_")):
                    o.scale = (1, 1, 1)
                o.hide_render = False
                try:
                    o.hide_set(False)
                except Exception:
                    pass
            _update_hud(scene, N_STAGES - 1)
            return
        i = min(max(0, (f - 1) // STAGE_F), N_STAGES - 1)
        show = []
        for j in range(i + 1):
            show.extend(STAGES_PREF[j])
        show = list(dict.fromkeys(show))
        control_prefixes = (
            "Fuselage", "Shell_", "CabinFloor", "CargoFloor", "BellyFairing",
            "Wing_", "HS_", "VS", "Fence_", "Stripe_", "Win_", "CockpitGlass",
            "E_", "Nacelle_", "GN", "GM", "GW", "Door_", "Box_", "Bag_",
            "Seat", "FW_", "FC", "Logo_",
        )
        for o in bpy.data.objects:
            if not o.name.startswith(control_prefixes):
                continue
            if o.name.startswith("SeatB_") or o.name.startswith("SeatH_"):
                # 靠背跟随 Seat_
                vis = any(s in show for s in ("Seat_",)) or "Seat_" in "".join(show)
                vis = "Seat_" in show
            else:
                vis = any(o.name.startswith(p) for p in show) if show else False
            # 阶段 7 前最后阶段：全显
            if i == N_STAGES - 1:
                vis = True
            o.hide_render = not vis
            try:
                o.hide_set(not vis)
            except Exception:
                pass
            if vis and o.name.startswith(("Seat", "Box_")):
                o.scale = (1, 1, 1)
        _update_hud(scene, i)

    def _update_hud(scene, i):
        # 装载表
        def parse(key, n):
            s = scene.get(key, ",".join(["0"] * n))
            return [int(float(x)) for x in str(s).split(",")]
        try:
            import a320_data as D
        except Exception:
            return
        p = parse(f"lb_stage_{i}_pax", 3)
        c = parse(f"lb_stage_{i}_cargo", 3)
        fu = parse(f"lb_stage_{i}_fuel", 3)
        pax = dict(zip(("FWD", "MID", "AFT"), p))
        cargo = dict(zip(("FWD", "AFT", "BULK"), c))
        fuel = dict(zip(("WING_L", "WING_R", "CTR"), fu))
        res = D.compute(pax, cargo, fuel)
        title = scene.get(f"lb_stage_{i}_title", f"阶段{i+1}")
        sx = D.NOSE_X - res["cg_station"]
        for nm, body in (
            ("UI_DYN", f"[{title}] CG={res['cg_station']:.2f}m %MAC={res['cg_mac']:.1f}%"),
            ("UI_STAGE", f"阶段 {i+1}/{N_STAGES} {title}"),
            ("UI_W", f"TOW {res['tow']:.0f} kg"),
            ("UI_MAC", f"%MAC {res['cg_mac']:.1f}%"),
            ("UI_CG", f"CG FS {res['cg_station']:.2f} m"),
            ("UI_F1", f"CG=ΣM/ΣW={res['cg_station']:.3f} m"),
            ("UI_F2", f"%MAC={res['cg_mac']:.2f}%"),
            ("UI_F3", f"y=Σ(W·yi)/ΣW={res['cg_y']:+.4f} m"),
        ):
            o = bpy.data.objects.get(nm)
            if o and o.data and hasattr(o.data, "body"):
                o.data.body = body
        cone = bpy.data.objects.get("CGCone")
        if cone:
            cone.location.x = sx
            cone.location.y = res["cg_y"] * 8

    lb_cinema_handler.__name__ = "lb_cinema_handler"
    bpy.app.handlers.frame_change_post.append(lb_cinema_handler)
    return lb_cinema_handler


def fix_cam_end():
    sc = bpy.context.scene
    cam = bpy.data.objects.get("TeachCam") or sc.camera
    if cam:
        # 末帧已是组装完成机位；默认也停在末帧
        sc.frame_set(TOTAL_F)
        # 确保末帧机位正确
        cam.location = (48, -38, 16)
        cam.rotation_euler = (math.radians(68), 0, math.radians(52))
        cam.keyframe_insert("location", frame=TOTAL_F)
        cam.keyframe_insert("rotation_euler", frame=TOTAL_F)


def main():
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = TOTAL_F
    rebuild_handler()
    fix_cam_end()
    show_all()
    # 应用 handler 在末帧
    for h in bpy.app.handlers.frame_change_post:
        if getattr(h, "__name__", "") == "lb_cinema_handler":
            h(sc, None)
            break

    # 面板
    sys.path.insert(0, SP)
    import loadbalance_panel as lbp
    importlib.reload(lbp)
    try:
        lbp.unregister()
    except Exception:
        pass
    lbp.register()

    sc.frame_set(TOTAL_F)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    print("FIXED default frame", sc.frame_current)

    # 验证机翼可见
    for n in ("Wing_L_inner", "Wing_R_inner", "E_L", "E_R", "Seat_MID_15_2"):
        o = bpy.data.objects.get(n)
        print(n, "hide_render", o.hide_render if o else "missing")

    PREVIEW = os.path.join(ROOT_DIR, "output", "preview")
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 900
    cam = bpy.data.objects.get("TeachCam")
    sc.render.filepath = os.path.join(PREVIEW, "v9_fixed_assembled.png")
    bpy.ops.render.render(write_still=True)
    print("DONE_FIXED")


if __name__ == "__main__":
    main()

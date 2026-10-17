# -*- coding: utf-8 -*-
"""
Stage 1 · 元数据契约注入 + GLB 导出
=====================================

读：output/配载平衡教学模型.blend        （**只读打开，绝不覆盖**）
写：output/stage1/配载平衡教学模型.stage1.blend   （中间产物，含全部契约字段）
    output/stage1/teach_model.glb                 （交付用：纯几何 + Draco + extras）
    output/stage1/teach_model_nodrc.glb           （同源未压缩版，用于体积对比）
    output/stage1/labels.json                     （标注层：文字内容 + 锚点，替代 3D 挤出文字）
    output/stage1/stage1_report.txt               （自校验报告）

契约依据：docs/GLB元数据契约.md

关键修复：
  1. 现有 540 个座椅件中靠背(SeatB_)/头枕(SeatH_) 共 360 件无分组标签，
     本脚本按名字补齐 zone/row/group → 100% 覆盖。
  2. 40 个文字物体占原 GLB 体积的 50.4%、顶点 78.3%，
     本脚本把文字导出为 labels.json，GLB 只留几何 → 体积直接砍半。

运行：
  & 'D:\\Blender\\blender-5.2.1-windows-x64\\blender.exe' --background \
    --python scripts\\stage1_export.py
"""
import bpy, os, sys, math, json, struct, io
from mathutils import Vector

# 以脚本位置推导项目根（scripts/ 的上一级），项目目录搬迁后不需要再改这里。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "output", "配载平衡教学模型.blend")
OUTDIR = os.path.join(ROOT, "output", "stage1")
MID_BLEND = os.path.join(OUTDIR, "配载平衡教学模型.stage1.blend")

# ── 产物命名规范（唯一口径，别再手工改名）─────────────────────────────
#   teach_model_raw.glb    Blender 直接导出（未压缩，含全部 extras）  ← 本脚本
#   teach_model_draco.glb  Draco 压缩版（备选格式）                    ← 本脚本
#   teach_model.glb        ★ 交付版：dedup + prune 之后               ← tools/optimize_glb.mjs
# 教训（2026-09-22）：曾把 raw 改名成 teach_model_raw.glb 却没同步改这里，
# 脚本继续写 teach_model_nodrc.glb，导致下游一直读到旧文件、排查半天。
GLB_RAW = os.path.join(OUTDIR, "teach_model_raw.glb")
GLB_DRC = os.path.join(OUTDIR, "teach_model_draco.glb")
LABELS = os.path.join(OUTDIR, "labels.json")
REPORT = os.path.join(OUTDIR, "stage1_report.txt")
os.makedirs(OUTDIR, exist_ok=True)

lines = []
def p(*a):
    lines.append(" ".join(str(x) for x in a))

N = lambda *v: list(v)
ZONE_MAP = {"FWD": "0A", "MID": "0B", "AFT": "0C"}

RULES = [
    # ---- 座椅三件套：靠背/头枕原先无标签，按名字补齐（本轮关键修复）----
    ("SeatB_", "PAX", 4, N(0, 0, 1), "payload"),
    ("SeatH_", "PAX", 4, N(0, 0, 1), "payload"),
    ("Seat_",  "PAX", 4, N(0, 0, 1), "payload"),
    # ---- 行李 ----
    ("Bag_FWD_", "BAG_1", 4, N(0, 0, -1), "payload"),
    ("Bag_AFT_", "BAG_3", 4, N(0, 0, -1), "payload"),
    # ---- 货物（Stage 1 只有 3 个货块；CARGO_4 由 Stage 2 拆分后货舱时填充）----
    ("Box_FWD_",  "CARGO_1", 4, N(0, 0, -1), "payload"),
    ("Box_AFT_",  "CARGO_3", 4, N(0, 0, -1), "payload"),
    ("Box_BULK_", "CARGO_5", 4, N(0, 0, -1), "payload"),
    # ---- 燃油 ----
    ("FW_-1", "FUEL_WING_L", 4, N(0, -1, 0), "system"),
    ("FW_1",  "FUEL_WING_R", 4, N(0,  1, 0), "system"),
    ("FC",    "FUEL_CTR",    4, N(0, 0, -1), "system"),
    # ---- 发动机与吊挂 ----
    ("E_L", "ENG_L", 1, N(0.6, -0.8, 0), "system"),
    ("E_R", "ENG_R", 1, N(0.6,  0.8, 0), "system"),
    # ---- 起落架 ----
    ("GM1",  "GEAR_ML",    1, N(0, 0, -1), "system"),
    ("GM-1", "GEAR_MR",    1, N(0, 0, -1), "system"),
    ("GN",   "GEAR_N",     1, N(0, 0, -1), "system"),
    ("GW",   "GEAR_WHEEL", 1, N(0, 0, -1), "system"),
    # ---- AIRCRAFT_ROOT 外观壳：映射到同一套组 ID，共用动画逻辑 ----
    ("Plane_Winglet_L", "WING_L", 1, N(0, -1, 0), "structure"),
    ("Plane_Winglet_R", "WING_R", 1, N(0,  1, 0), "structure"),
    # 翼尖下 fence（上 fence 沿用 Plane_Winglet_* 名；下 fence 名必须排在通用
    # ("Plane_", HULL_UPPER) 之前，否则会被机身上壳组收走、拆解时脱离机翼）
    ("Plane_WingletLo_L", "WING_L", 1, N(0, -1, 0), "structure"),
    ("Plane_WingletLo_R", "WING_R", 1, N(0,  1, 0), "structure"),
    ("Plane_Wing_L",    "WING_L", 1, N(0, -1, 0), "structure"),
    ("Plane_Wing_R",    "WING_R", 1, N(0,  1, 0), "structure"),
    ("Plane_HS_L",  "TAIL_HS", 1, N(-1, 0, 0), "structure"),
    ("Plane_HS_R",  "TAIL_HS", 1, N(-1, 0, 0), "structure"),
    ("Plane_VStabTop", "TAIL_VS", 1, N(-1, 0, 0), "structure"),
    ("Plane_VStab",    "TAIL_VS", 1, N(-1, 0, 0), "structure"),
    ("Plane_EngIn_L", "ENG_L", 1, N(0.6, -0.8, 0), "system"),
    ("Plane_EngIn_R", "ENG_R", 1, N(0.6,  0.8, 0), "system"),
    ("Plane_Eng_L",   "ENG_L", 1, N(0.6, -0.8, 0), "system"),
    ("Plane_Eng_R",   "ENG_R", 1, N(0.6,  0.8, 0), "system"),
    ("Plane_Pylon_L", "ENG_L", 1, N(0.6, -0.8, 0), "system"),
    ("Plane_Pylon_R", "ENG_R", 1, N(0.6,  0.8, 0), "system"),
    ("Plane_GN",   "GEAR_N",  1, N(0, 0, -1), "system"),
    ("Plane_GM1",  "GEAR_ML", 1, N(0, 0, -1), "system"),
    ("Plane_GM-1", "GEAR_MR", 1, N(0, 0, -1), "system"),
    ("Plane_",  "HULL_UPPER", 2, N(0, 0, 1), "structure"),
    # ---- 机体与地板 ----
    ("Shell_",       "HULL_UPPER",    2, N(0, 0,  1), "structure"),
    ("BellyFairing", "BELLY_FAIRING", 1, N(0, 0, -1), "structure"),
    ("CabinFloor",   "FLOOR_CABIN",   3, N(0, 0,  1), "structure"),
    ("CargoFloor",   "FLOOR_CARGO",   3, N(0, 0, -1), "structure"),
    # ---- 舱门 / 舷窗 / 附件 ----
    ("Door_L",  "DOORS",  1, N(0, -1, 0), "structure"),
    ("Door_R",  "DOORS",  1, N(0,  1, 0), "structure"),
    ("Door_",   "DOORS",  1, N(0,  1, 0), "structure"),
    ("Win_",    "WINDOWS", 1, N(0, 1, 0), "structure"),
    ("CockpitGlass", "WINDOWS", 1, N(0, 0, 1), "structure"),
    ("Fence_",  "WING_FENCE", 1, N(0, -1, 0), "structure"),
    ("Stripe_", "MARKINGS",   1, N(0, 1, 0),  "structure"),
    # ---- 外观精修批次 1（stage2_refine 新增件；顺序敏感项说明见下）----
    # LogoTail_ 必须排在 ("Logo", ANNO_UI) 之前 —— 否则垂尾 Logo 被当标注层隐藏。
    ("LogoTail_",  "TAIL_VS",  1, N(-1, 0, 0), "structure"),
    ("Ant_",       "MARKINGS", 1, N(0, 0,  1), "structure"),
    ("Pitot_",     "MARKINGS", 1, N(0, 1,  0), "structure"),
    ("Aoa_",       "MARKINGS", 1, N(0, 1,  0), "structure"),
    ("Drain_",     "MARKINGS", 1, N(0, 0, -1), "structure"),
    ("GearDoor_",  "DOORS",    1, N(0, 0, -1), "structure"),
    ("NoseGearDoor_", "DOORS", 1, N(0, 0, -1), "structure"),
    ("Mark_",      "MARKINGS", 1, N(0, 1,  0), "structure"),
    # 舵面刻线/扰流板/航行灯：按侧分前缀，组随翼面走（拆解时与机翼同波同向）
    ("WingLineL_", "WING_L",   1, N(0, -1, 0), "structure"),
    ("WingLineR_", "WING_R",   1, N(0,  1, 0), "structure"),
    ("Spoiler_L",  "WING_L",   1, N(0, -1, 0), "structure"),
    ("Spoiler_R",  "WING_R",   1, N(0,  1, 0), "structure"),
    ("NavLight_L", "WING_L",   1, N(0, -1, 0), "structure"),
    ("NavLight_R", "WING_R",   1, N(0,  1, 0), "structure"),
    ("NavLight_T", "TAIL_VS",  1, N(-1, 0, 0), "structure"),
    ("Rudder",   "TAIL_VS",  1, N(-1, 0, 0), "structure"),
    ("APU_",       "MARKINGS", 1, N(0, 0, -1), "structure"),
    ("FanFace_L",  "ENG_L",    1, N(0.6, -0.8, 0), "system"),
    ("FanFace_R",  "ENG_R",    1, N(0.6,  0.8, 0), "system"),
    # ---- 标注层（layer 9，不参与拆解；几何保留，文字改走 labels.json）----
    ("CGCone",   "ANNO_CG",    9, N(0, 0, 0), "annotation"),
    ("CGLine",   "ANNO_CG",    9, N(0, 0, 0), "annotation"),
    ("CG_Empty", "ANNO_CG",    9, N(0, 0, 0), "annotation"),
    ("DatumBar", "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("MACBar",   "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("Band",     "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("YRuler",   "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("YPointer", "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("YTick",    "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("Tk",       "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("TY",       "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("T",        "ANNO_SCALE", 9, N(0, 0, 0), "annotation"),
    ("UI_",      "ANNO_UI",    9, N(0, 0, 0), "annotation"),
    ("CARGO_TAG_", "ANNO_UI",  9, N(0, 0, 0), "annotation"),
    ("Lab_",     "ANNO_LABEL", 9, N(0, 0, 0), "annotation"),
    ("HUD",      "ANNO_UI",    9, N(0, 0, 0), "annotation"),
    ("Logo",     "ANNO_UI",    9, N(0, 0, 0), "annotation"),
    ("AIRCRAFT", "ANNO_UI",    9, N(0, 0, 0), "annotation"),
    # ---- 环境 ----
    ("Ground", "ENV_GROUND", 9, N(0, 0, 0), "env"),
]

# UI_ 前缀里哪些是随装载实时变化的动态标签
DYNAMIC_UI = {"UI_DYN", "UI_W", "UI_MAC", "UI_CG", "UI_F1", "UI_F2", "UI_F3",
              "UI_STAGE", "UI_M", "UI_Y", "UI_PAX", "UI_ZFW", "UI_TRIM", "TY_cur"}

# ---------------------------------------------------------------------------
# 标签口径修正表
# 原 .blend 里的文字有真实口径错误（把散货舱标成「4 舱」，而《载重平衡手册》明确
# 散货舱为 5 舱、4 舱属后货舱），必须在校正后才允许进入交付物。
# 原文字一律保留在 text_original 字段，便于审计与回溯。
# Stage 2 起这些文案改为由「机型数据表」驱动，届时删除本表。
# ---------------------------------------------------------------------------
LABEL_FIX = {
    "CARGO_TAG_1": "1 舱 前货舱",
    "CARGO_TAG_3": "3/4 舱 后货舱",
    "CARGO_TAG_4": "5 舱 散货舱",
    "T_Zone_FWD": "前舱 0A 排1-12",
    "T_Zone_MID": "中舱 0B 排13-20",
    "T_Zone_AFT": "后舱 0C 排21-31",   # 真实 186Y = 31 排（原为 30 排）
    "UI_TRIM": "STAB TRIM 水平安定面配平",
}



def norm(v):
    m = math.sqrt(sum(x * x for x in v))
    if m < 1e-9:
        return [0.0, 0.0, 0.0]
    return [round(x / m, 4) for x in v]


def root_of(o):
    n, guard = o, 0
    while n.parent is not None and guard < 64:
        n = n.parent
        guard += 1
    return n.name


def parse_seat_zone_row(name):
    parts = name.split("_")
    if len(parts) >= 3:
        if parts[1] in ZONE_MAP:
            z = ZONE_MAP[parts[1]]
        elif parts[1] in ("0A", "0B", "0C"):
            z = parts[1]
        else:
            return None, None
        try:
            return z, int(parts[2])
        except ValueError:
            return z, None
    return None, None


def classify(name):
    for pref, grp, layer, d, role in RULES:
        if name.startswith(pref):
            return grp, layer, d, role
    return "UNMAPPED", 0, N(0, 0, 0), "unknown"


# ---------------------------------------------------------------------------
# 契约 v2 · 自下而上的分层爆炸
# ---------------------------------------------------------------------------
# v1 的分波是"轴向四波"（货舱向下、座椅向上、机翼侧向、发动机前向）—— 方向对，
# 但**没有顺序**，拆解时"谁先谁后"不成叙事，观感上是同时炸开。
# v2 改为**按高度自下而上逐层剥离**：先移走最下层（起落架），逐层向上露，
# 最后掀起上壳体看到全部客舱。这正是用户要的"从下到上、充分展示各结构"。
#
#   layer 1  起落架            ↓ 落地腾空
#   layer 2  腹板/下壳          ↓ 露出货舱
#   layer 3  货舱 1/3/5 + 行李   ↓ 抽出货物
#   layer 4  货舱地板           ↓ 露出结构与油路
#   layer 5  客舱地板           ↓ 客/货舱彻底分离
#   layer 6  客舱座椅 186 座     ↑ 上抬成排
#   layer 7  上壳体             ↑ 最后掀起
#   layer 8  机翼（含小翼）       侧向外 —— 以下为"结构展开段"（原 B 组）
#   layer 9  燃油               侧向外
#   layer 10 发动机 + 吊挂       侧前
#   layer 11 平尾 / 垂尾         后向外
#   layer 12 舱门 / 舷窗 / 标识   法向外
#   layer 0  标注与环境          不参与拆解
#
# 注意 v1 用 9 表示"不拆解"，v2 改用 **0**（与波次 1..12 不冲突）。
# ═══ v2.3 覆盖（当前生效）：剖视 + 分区抽出 ═══════════════════════════════
# 用户规格：机身（含门、窗）与起落架**不拆、留在地面**；机翼往两边拆；
#           主要展示客舱内部的客货舱布局。
#
# 专业修正（关键）：机身不拆 → 客舱封闭 → 看不见内部，所以分两段：
#   ① 剖视：壳体沿纵剖面切掉一侧（视图侧用 clip plane 实现，不改几何）；
#   ② 抽出：载荷**朝剖口方向水平抽出**。
#   ⚠️ 为何不做"座椅上抽 / 货箱下抽"：货舱在机身下部（y≈−1.35），地面在 y=−3.40，
#      向下只有约 2 m 空间 → 必然穿透地面。朝剖口抽则物理通顺且完全不碰地面。
#   → 本版**所有运动都是水平的**（±Z 或 −X），零竖直位移，
#     "不得低于/穿透地面"自动满足。
#
# 方向：Blender 系机头 +X、左为 −Y；导出映射 (x,y,z)→(x,z,−y)，
#       故 Blender (0,−1,0) → Three.js (0,0,+1) = 左侧 = **剖口侧**。
#       Three.js 默认相机就在 +Z 侧，正对剖口，可直接看进客舱。
V2_LAYER = {
    # 固定参照（layer 0）—— 就是那架"停在地面"的飞机
    "HULL_UPPER": 0, "DOORS": 0, "WINDOWS": 0, "MARKINGS": 0,
    "GEAR_N": 0, "GEAR_ML": 0, "GEAR_MR": 0, "GEAR_WHEEL": 0,
    "BELLY_FAIRING": 0, "FLOOR_CABIN": 0, "FLOOR_CARGO": 0, "FUEL_CTR": 0,
    # 客舱载荷：朝剖口水平抽出，三区/三舱各自错开（错开量在视图侧）
    "PAX_0A": 1, "PAX_0B": 2, "PAX_0C": 3,
    "BAG_1": 4, "BAG_3": 4,
    "CARGO_1": 5, "CARGO_3": 6, "CARGO_5": 7,
    # 翼面 / 动力 / 尾翼：两侧与后方展开
    # 发动机**与机翼同波同位移**：发动机吊在翼下，若单独移出会"脱离吊挂悬空"，
    # 物理上不合理；而且发动机不属配载载荷（计入 OEW），教学上无需单独拆出。
    "WING_L": 8, "ENG_L": 8,
    "WING_R": 9, "ENG_R": 9,
    "FUEL_WING_L": 10, "FUEL_WING_R": 11,
    "TAIL_HS": 12, "TAIL_VS": 12,
}
# 逐组方向（Blender 系）。未列出的组方向归零（即不动）。
# 翼内燃油带**向上**分量：油在机翼内部，若与机翼同位移就永远被机翼挡住看不见；
# 纯水平又无法脱离翼面遮挡（机翼长 15 m），所以让它"边外移边向上举出"——
# 物理上就是"把油箱从翼内吊出来"，既可见又不碰地面（向下是被禁止的）。
V2_DIR = {
    "PAX_0A": (0, -1, 0), "PAX_0B": (0, -1, 0), "PAX_0C": (0, -1, 0),
    "BAG_1": (0, -1, 0), "BAG_3": (0, -1, 0),
    "CARGO_1": (0, -1, 0), "CARGO_3": (0, -1, 0), "CARGO_5": (0, -1, 0),
    "WING_L": (0, -1, 0), "ENG_L": (0, -1, 0),
    "WING_R": (0, 1, 0), "ENG_R": (0, 1, 0),
    "FUEL_WING_L": (0, -1, 0.55), "FUEL_WING_R": (0, 1, 0.55),
    "TAIL_HS": (-1, 0, 0), "TAIL_VS": (-1, 0, 0),
}


def v2_wave(grp):
    """返回 (layer, dir_override)。layer 0 = 不拆；方向取自 V2_DIR。"""
    if grp.startswith("ANNO_") or grp == "ENV_GROUND" or grp == "UNMAPPED":
        return 0, None
    layer = V2_LAYER.get(grp, 0)
    if layer == 0:
        return 0, None
    return layer, V2_DIR.get(grp, (0, 0, 0))



def main():
    p("=" * 78)
    p("Stage 1 · 元数据契约注入 + GLB 导出")
    p("=" * 78)
    p("源文件（只读打开）:", SRC)

    bpy.ops.wm.open_mainfile(filepath=SRC)
    p("已加载。对象总数:", len(bpy.data.objects))
    p("")

    # ---------- 0. 外形重建（参数化，替代"旋转长方体"机翼）----------
    # 背景：原来的机翼/平尾/垂尾是 add_box 造的长方体绕轴旋转，俯视图里是**平行四边形**，
    #       翼根弦线不垂直于机身 → 即使把旋转符号改对，看上去仍"方向反了"。
    #       改符号治不了这个病，必须换成真梯形翼面。详见 stage2_shape.py。
    # 同时把座位补到 31 排（真实 186Y）并延长客舱地板。
    # 几何在此**按世界坐标烘焙**、对象变换保持单位阵，从根本上消除"旋转符号写反"这类错误。
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import stage2_shape
    p("=== 0. 外形重建（参数化梯形翼面 + 186Y 座位）===")
    stage2_shape.rebuild(verbose=p)
    bpy.context.view_layer.update()

    # ---------- 朝向断言：用几何证明，而不是嘴上说"改好了" ----------
    p("")
    p("=== 0b. 朝向断言（负值 = 后掠/后倾，正确）===")
    orient_fail = []
    for nm, side in (("Plane_Wing_L", -1), ("Plane_Wing_R", 1)):
        o = bpy.data.objects.get(nm)
        if not o:
            continue
        # 取网格里最内侧与最外侧的顶点，比较其前缘 X（不依赖对象旋转）
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        y_abs = [abs(v.y) for v in vs]
        y_in, y_out = min(y_abs), max(y_abs)
        inner = [v for v in vs if abs(v.y) <= y_in + 0.05]
        outer = [v for v in vs if abs(v.y) >= y_out - 0.05]
        dx = max(v.x for v in outer) - max(v.x for v in inner)
        span = y_out - y_in
        deg = math.degrees(math.atan2(-dx, span))
        ok = dx < -0.01
        p("   %-16s 内端前缘 x=%+7.3f → 外端 x=%+7.3f   Δx=%+6.3f  后掠角 %+5.1f°  %s"
          % (nm, max(v.x for v in inner), max(v.x for v in outer), dx, deg,
             "PASS" if ok else "★ FAIL"))
        if not ok:
            orient_fail.append(nm)
    for nm, side in (("Plane_HS_L", -1), ("Plane_HS_R", 1)):
        o = bpy.data.objects.get(nm)
        if not o:
            continue
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        y_abs = [abs(v.y) for v in vs]
        y_in, y_out = min(y_abs), max(y_abs)
        inner = [v for v in vs if abs(v.y) <= y_in + 0.05]
        outer = [v for v in vs if abs(v.y) >= y_out - 0.05]
        dx = max(v.x for v in outer) - max(v.x for v in inner)
        deg = math.degrees(math.atan2(-dx, y_out - y_in))
        ok = dx < -0.01
        p("   %-16s 内侧前缘 x=%+7.3f → 外侧 x=%+7.3f   Δx=%+6.3f  后掠角 %+5.1f°  %s"
          % (nm, max(v.x for v in inner), max(v.x for v in outer), dx, deg,
             "PASS" if ok else "★ FAIL"))
        if not ok:
            orient_fail.append(nm)
    vs_o = bpy.data.objects.get("Plane_VStab")
    if vs_o:
        vs = [vs_o.matrix_world @ v.co for v in vs_o.data.vertices]
        zs = [v.z for v in vs]
        z0, z1 = min(zs), max(zs)
        bot = [v for v in vs if v.z <= z0 + 0.05]
        top = [v for v in vs if v.z >= z1 - 0.05]
        d = max(v.x for v in top) - max(v.x for v in bot)
        ok = d < -0.01
        p("   %-16s 前缘 顶部x=%+7.3f 底部x=%+7.3f  Δx=%+6.3f  后倾 %s"
          % ("Plane_VStab", max(v.x for v in top), max(v.x for v in bot), d,
             "PASS" if ok else "★ FAIL"))
        if not ok:
            orient_fail.append("Plane_VStab")
    p("   朝向断言结果:", "全部 PASS" if not orient_fail else ("★ 失败: " + ", ".join(orient_fail)))
    if orient_fail:
        p("   !! 朝向仍不正确，继续导出会产出错模型 —— 请先修脚本")
    p("")

    # ---------- 1. 注入 extras ----------
    counts = {}
    group_hist = {}
    unmapped = []
    dir_bad = []
    seat_fixed = 0
    labels = []
    text_objs = []

    for o in bpy.data.objects:
        if o.type not in ("MESH", "FONT", "CURVE"):
            counts["<" + o.type + ">"] = counts.get("<" + o.type + ">", 0) + 1
            continue
        counts[o.type] = counts.get(o.type, 0) + 1

        if o.type in ("FONT", "CURVE"):
            text_objs.append(o)

        grp, layer, d, role = classify(o.name)
        if grp == "UNMAPPED":
            unmapped.append(o.name)

        lb_zone = None
        lb_row = None
        if grp == "PAX":
            z, r = parse_seat_zone_row(o.name)
            if z:
                grp = "PAX_" + z
                lb_zone, lb_row = z, r
                if "zone" not in o.keys():
                    seat_fixed += 1
            else:
                grp = "UNMAPPED"

        if grp in ("CARGO_1", "CARGO_3", "CARGO_5"):
            lb_zone = {"CARGO_1": "HOLD_1", "CARGO_3": "HOLD_3", "CARGO_5": "HOLD_5"}[grp]

        if o.type in ("FONT", "CURVE"):
            grp, lb_zone, lb_row = "ANNO_TEXT", None, None
            role = "annotation"

        # 契约 v2：按高度自下而上重排波次（layer 0 = 不参与拆解）
        layer, dir_fix = v2_wave(grp)
        if dir_fix is not None:
            d = dir_fix

        if "ax" in o.keys():
            anchor = [round(float(o["ax"]), 4), round(float(o["ay"]), 4), round(float(o["az"]), 4)]
        else:
            w = o.matrix_world.translation
            anchor = [round(w.x, 4), round(w.y, 4), round(w.z, 4)]

        nd = norm(d)
        if sum(abs(x) for x in nd) > 0 and abs(math.sqrt(sum(x * x for x in nd)) - 1.0) > 0.01:
            dir_bad.append((o.name, nd))

        o["lb_group"] = grp
        o["lb_layer"] = int(layer)
        o["lb_dir"] = nd
        o["lb_anchor"] = anchor
        o["lb_role"] = role
        o["lb_src"] = root_of(o)
        o["group"] = grp                      # 兼容旧字段
        if lb_zone:
            o["lb_zone"] = lb_zone
        if lb_row is not None:
            o["lb_row"] = int(lb_row)

        group_hist[grp] = group_hist.get(grp, 0) + 1

        # 文字 → labels.json
        if o.type in ("FONT", "CURVE"):
            body = getattr(o.data, "body", None)
            if body is not None:
                fixed = LABEL_FIX.get(o.name)
                entry = {
                    "name": o.name,
                    "text": fixed if fixed else body,
                    "anchor": anchor,
                    "blender_rot_x": round(math.degrees(o.rotation_euler.x), 2),
                    "size": round(float(getattr(o.data, "size", 0.28)), 4),
                    "dynamic": o.name in DYNAMIC_UI,
                    "src": o["lb_src"],
                }
                if fixed and fixed != body:
                    entry["text_original"] = body
                    entry["fix_reason"] = "原文字与《载重平衡手册》货舱编号口径不符，已按 1/3+4/5 更正"
                labels.append(entry)

    p("--- 分类统计 ---")
    for k, v in sorted(counts.items()):
        p("   %-10s %d" % (k, v))
    p("")
    p("--- 拆解组分布 ---")
    for k, v in sorted(group_hist.items(), key=lambda x: (-x[1], x[0])):
        p("   %-16s %d" % (k, v))
    p("组数:", len(group_hist))
    p("")
    p("★ 本轮补齐 zone/row 的座椅件（原先缺失）:", seat_fixed)
    p("未映射对象数:", len(unmapped))
    for n in unmapped[:30]:
        p("   ! ", n)
    p("lb_dir 非单位向量数（0 向量除外）:", len(dir_bad))
    p("")

    # ---------- 2. 标注层导出 ----------
    with io.open(LABELS, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(labels),
            "note": "Blender 内置 Bfont 生成的 3D 挤出文字。Stage 1 起改由视图侧用 canvas 贴图绘制，"
                    "本文件只提供内容与锚点。坐标同 .blend（Z-up，机头 +X，单位 m）。",
            "labels": labels,
        }, f, ensure_ascii=False, indent=2)
    p("已写出标注清单（%d 条）: %s" % (len(labels), LABELS))

    # ---------- 3. 保存中间 .blend（原文件未动）----------
    bpy.ops.wm.save_as_mainfile(filepath=MID_BLEND)
    p("已保存中间产物（含全部契约字段）:", MID_BLEND)
    p("→ 原文件 %s 全程只读，未修改。" % os.path.basename(SRC))

    # ---------- 4. 剔除文字几何后导出 GLB ----------
    for o in text_objs:
        bpy.data.objects.remove(o, do_unlink=True)
    p("")
    p("已从导出场景中移除文字物体 %d 个（几何改由 labels.json + 视图侧贴图承担）" % len(text_objs))
    remaining_mesh = [o for o in bpy.data.objects if o.type == "MESH"]
    p("剩余待导出网格:", len(remaining_mesh))

    def do_export(path, draco):
        kw = dict(filepath=path, export_format="GLB", export_apply=True,
                  export_animations=False, export_extras=True, export_yup=True,
                  export_cameras=False, export_lights=False)
        if draco:
            kw.update(export_draco_mesh_compression_enable=True,
                      export_draco_mesh_compression_level=6,
                      export_draco_position_quantization=14,
                      export_draco_normal_quantization=10,
                      export_draco_texcoord_quantization=12)
        try:
            # 必须检查返回值：glTF 导出器在部分失败时会打印错误却仍返回 CANCELLED，
            # 旧版忽略返回值，于是"导出失败"被报成 OK，下游一直读旧文件（已踩过）。
            res = bpy.ops.export_scene.gltf(**kw)
            if res != {"FINISHED"}:
                return False, "操作符返回 %s（未完成）" % res
            if not os.path.isfile(path):
                return False, "操作符返回 FINISHED 但文件不存在"
            return True, ""
        except TypeError as e:
            for k in ("export_draco_texcoord_quantization", "export_draco_normal_quantization",
                      "export_draco_position_quantization", "export_draco_mesh_compression_level",
                      "export_draco_mesh_compression_enable", "export_yup"):
                kw.pop(k, None)
                try:
                    res = bpy.ops.export_scene.gltf(**kw)
                    if res == {"FINISHED"} and os.path.isfile(path):
                        return True, "降级成功（移除参数后，原因: %s）" % e
                except TypeError:
                    continue
            return False, str(e)

    p("")
    p("--- 导出 ---")
    ok1, m1 = do_export(GLB_RAW, False)
    p("未压缩版: %s %s %s" % ("OK" if ok1 else "FAIL", m1,
                            ("%.2f MB" % (os.path.getsize(GLB_RAW) / 1048576.0)) if ok1 else ""))
    ok2, m2 = do_export(GLB_DRC, True)
    p("Draco 版: %s %s %s" % ("OK" if ok2 else "FAIL", m2,
                            ("%.2f MB" % (os.path.getsize(GLB_DRC) / 1048576.0)) if ok2 else ""))

    # ---------- 5. 自校验 ----------
    def inspect(path, label):
        p("")
        p("=== GLB 校验 · %s ===" % label)
        if not os.path.isfile(path):
            p("文件不存在，跳过")
            return None
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            struct.unpack("<4sII", f.read(12))
            clen, _ = struct.unpack("<II", f.read(8))
            js = json.loads(f.read(clen).decode("utf-8"))
        nodes = js.get("nodes", [])
        meshes = js.get("meshes", [])
        accs = js.get("accessors", [])
        prim = sum(len(m.get("primitives", [])) for m in meshes)
        p("体积: %.2f MB | nodes %d | meshes %d | primitives %d | materials %d"
          % (size / 1048576.0, len(nodes), len(meshes), prim, len(js.get("materials", []))))
        p("extensionsUsed:", js.get("extensionsUsed", []))
        p("extensionsRequired:", js.get("extensionsRequired", []))

        rn = [n for n in nodes if n.get("mesh") is not None]
        def cov(key):
            return sum(1 for n in rn if key in n.get("extras", {}))
        p("")
        p("断言1 · 渲染节点属性覆盖: group %d/%d | layer %d/%d | dir %d/%d | anchor %d/%d"
          % (cov("lb_group"), len(rn), cov("lb_layer"), len(rn),
             cov("lb_dir"), len(rn), cov("lb_anchor"), len(rn)))
        full = sum(1 for n in rn if n.get("extras", {}).get("lb_group"))
        p("         → %s" % ("PASS" if full == len(rn) and rn else "FAIL"))

        groups = sorted(set(n["extras"]["lb_group"] for n in rn if n.get("extras", {}).get("lb_group")))
        core = [g for g in groups if not g.startswith("ANNO_") and not g.startswith("ENV_")]
        p("断言3 · 拆解组数（非标注/环境）: %d %s" % (len(core), "PASS" if len(core) >= 12 else "FAIL"))
        p("         组清单: %s" % ", ".join(groups))

        bad = 0
        for n in rn:
            d = n.get("extras", {}).get("lb_dir")
            if not d:
                continue
            m = math.sqrt(sum(float(x) ** 2 for x in d))
            if m > 1e-6 and abs(m - 1.0) > 0.01:
                bad += 1
        p("断言6 · lb_dir 单位向量: %s（异常 %d）" % ("PASS" if bad == 0 else "FAIL", bad))

        anno_v = 0
        for n in rn:
            g = n.get("extras", {}).get("lb_group", "")
            if g.startswith("ANNO_TEXT"):
                for pr in meshes[n["mesh"]].get("primitives", []):
                    at = pr.get("attributes", {})
                    if "POSITION" in at:
                        anno_v += accs[at["POSITION"]].get("count", 0)
        p("断言2 · GLB 内文字几何顶点: %d %s" % (anno_v, "PASS" if anno_v == 0 else "FAIL"))
        # 断言5 · 可复用的几何数
        # 原实现写成 `len(meshes) <= 700` —— 那是在数**网格数**（GLB 里一个网格一个
        # BufferGeometry），与"几何能不能复用"毫不相干：补到 186 座、本轮又加了风挡
        # 等对象之后网格数超过 700，这条断言就长期假 FAIL（实测 707）。阈值上调只是
        # 把假 FAIL 推后，所以改成**按几何内容签名去重**再判 —— 这才是 P1 真正关心的：
        # 相同几何的实例越多，视图侧 InstancedMesh 能压掉的 draw call 越多。
        # 签名用 POSITION 访问器的 (componentType, type, count, min, max)：
        # 顶点数或包围盒不同必然是不同几何；对座椅/舷窗这类整批复制的构件足够可靠。
        sigs = set()
        for n in rn:
            for pr in meshes[n["mesh"]].get("primitives", []):
                ai = pr.get("attributes", {}).get("POSITION")
                if ai is None:
                    continue
                a = accs[ai]
                sigs.add((a.get("componentType"), a.get("type"), a.get("count"),
                          tuple(a.get("min") or ()), tuple(a.get("max") or ())))
        uniq = len(sigs)
        reuse = (len(rn) / uniq) if uniq else 0.0
        p("断言5 · 几何复用: 网格 %d / 唯一几何 %d，平均复用 %.2f× %s"
          % (len(rn), uniq, reuse, "PASS" if reuse >= 2.0 else "FAIL"))
        p("断言4 · 体积 ≤3MB: %s（%.2f MB）"
          % ("PASS" if size <= 3 * 1048576 else "FAIL", size / 1048576.0))
        return dict(size=size, meshes=len(meshes), prim=prim, groups=len(core))

    raw = inspect(GLB_RAW, "未压缩")
    drc = inspect(GLB_DRC, "Draco")
    if raw and drc:
        p("")
        p("=== 压缩收益 ===")
        p("%.2f MB → %.2f MB，压缩比 %.1fx，省 %.2f MB"
          % (raw["size"] / 1048576.0, drc["size"] / 1048576.0,
             raw["size"] / max(drc["size"], 1), (raw["size"] - drc["size"]) / 1048576.0))
    p("")
    p("STAGE1_DONE")
    with io.open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("WROTE", REPORT)


main()

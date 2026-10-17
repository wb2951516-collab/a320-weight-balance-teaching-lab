# img2threejs / edu-3d-studio 集成方案

安装日期：2026-09-22 ｜ 安全审计：通过（LOW，0 项红牌，详见交付说明）

---

## 一、装了什么

| 技能 | 目录 | 体积 | 许可 | 性质 |
|---|---|---|---|---|
| **edu-3d-studio**（SkillHub slug `yuequeai-3d`） | `~/.workbuddy/skills/yuequeai-3d/` | 163 文件 / 2.0 MB | Apache-2.0 | 互动 3D 教学课件工坊 |
| **img2threejs**（独立版 v1.0.1） | `~/.workbuddy/skills/img2threejs/` | 5 文件 / 11 KB | MIT | **纯提示词技能**，无代码 |

**两者关系**：`edu-3d-studio` 内部**完整 vendor 了 img2threejs v1.4.4**
（`vendor/img2threejs/`，含 `forge/` 五阶段 Python 管线 + `grimoire/` 建模知识库 + `docs/` 规范）。
**vendor 版（v1.4.4）比市场上独立版（v1.0.1）更新**，所以真正该用的是 edu-3d-studio 里那一套；
独立版只剩提示词方法论，可作思路参考。

---

## 二、为什么它正好对上本项目

我们的 Stage 1b 是**手写**了交互层（标注 / 爆炸拆解 / 组显隐 / 剖切 / 预设视角）。
而 edu-3d-studio 的模板里**这些全都已经实现好了**：

| 本项目手写的 | 模板已内置 | 结论 |
|---|---|---|
| troika SDF 标注 | 部件标注引线（自动引出名称） | 可替换 |
| 4 波分层爆炸滑块 | 爆炸拆解视图（滑块沿结构轴拆开） | 可替换 |
| 组勾选显隐 | 分步讲解（镜头巡航 + 部件高亮 + 口述稿） | **本项目没有，是增量** |
| — | 点击知识卡（考点） | **本项目没有，是增量** |
| 参数滑块（未做） | 参数实验面板（实时驱动动画） | **本项目没有，是增量** |
| — | 课堂问答（点模型答题、自动计分） | **本项目没有，是增量** |
| `?t=&src=&view=` | 状态深链 `#step=2&explode=0.8` | 等价 |

**即"不要重造交互层"这条硬规则，恰好是我们该听的一条。** 继续手写下去是重复劳动，
而且我们的版本功能更少。

两条建模路线也都对得上本项目：

| | 模式A · 看图重建 | 模式B · 概念建模 |
|---|---|---|
| 引擎 | vendor 的 img2threejs `forge/` 管线 | 直接写 `model.js` |
| 本项目对应 | **用 ACAP 官方三视图驱动** —— `飞机参考图/_raw/airbus/A320-200_three-view_p418.png` 等 | 座椅阵列、货舱、油箱、CG 标记等教学件 |
| 填补什么 | Stage 2 要的"精细化几何" | 装配体与爆炸层次 |

---

## 三、实测证据（不是照文档转述）

在真实项目数据上跑过前两步：

```
$ python forge/stage1_intake/probe_image.py "…/A320-200_three-view_p418.png"
{ "type": "png", "width": 2550, "height": 3296,
  "aspectRatio": 0.7737, "technicalSuitability": "pass", "warnings": [] }

$ python forge/stage2_spec/new_pre_spec_assessment.py "A320 配载教学模型" \
    --image <同上> --complexity moderate --out a320_assessment.json
→ 产出 9.5 KB，字段：targetName, sourceImage, preSpecAssessment,
                      qualityContract, authoringInstruction, localSpecSearch
```

纯 Python 3.10+ 标准库，零安装，五步脚本全部存在。

---

## 四、必须先处理的四个冲突（否则会踩坑）

### 1. three.js 版本不一致 ← 最紧要
模板从 CDN 拉 **three@0.160.0**；本项目本地是 **r186**（`D:\three.js`）。
r160 → r186 有 API 漂移（`outputColorSpace`、光照单位、部分 addons 路径），直接换会报错或画面发暗。

**处理**：不要直接替换。要么保留模板的 0.160.0 一起本地化（多占一份 three，约 700 KB，最省事、零风险），
要么做一次显式升级并逐项验证。**建议前者先跑通，再谈升级。**

### 2. 性能预算冲突
模板硬性要求 **总三角形 ≤ 60k**（教室弱机）。我方 P1 档定的是 **单机几何顶点 ≤ 200k**。
两者差三倍以上。

**处理**：这是真实矛盾，不能糊过去。三个选项：
① 把 P1 下调到 ≤60k（放弃部分结构细节）；
② 保留 P1，但在课件里做 LOD：默认加载轻量壳，进入"结构讲解"步再换精细件；
③ 按教学需要分区：机体骨架走 60k，货舱/座椅等教学件单独精细。
**我倾向 ②**，因为它不牺牲任何教学能力，代价是要实现一次模型切换。

### 3. 契约不对齐
- 本项目：GLB + `extras.lb_group` / `lb_layer` / `lb_dir`（Stage 1 已落地并验证 697/697 覆盖）
- 模板：`lesson.json` 的 `parts[].id` ↔ 模型代码里的 `userData.partId`

**处理**：写一层映射即可——把 `lb_group` 映射为 `partId`，`lb_layer` 映射为爆炸波次。
我们的 `labels.json` 可直接喂进模板的标注层，**不需要重做标注**。

### 4. 教室离线
模板默认走 CDN，首次打开需联网。而本项目此前已明确要"双击即开、教室无网可用"。

**处理**（SKILL.md 已给出正解）：把 `three.module.js` 下到本地、模板改成相对路径，
交付形态变成「HTML + three.module.js 同目录」。**这条路我们已经趟通了**——
Stage 1b 的 `web/` 目录就是这个结构（`vendor/three` + 本地 HTTP 服务）。

> ⚠️ 注意：edu-3d-studio 的模板是**单文件 HTML 直接 `import()` 相对路径**，
> 理论上双击也能开（不再是 import map 被拦的问题）。
> **但必须实测确认**——我们刚刚才因为 `file://` 拦 ES 模块踩过一次坑，不能再假设。

---

## 五、建议的落地顺序

| 阶段 | 做什么 | 为什么这个顺序 |
|---|---|---|
| **第一步** | 用 edu-3d-studio 模板 + `lesson.json`，模型仍用我们已有的 `teach_model.glb`（做法4 的映射层），产出一版课件 | 成本最低、收益最大：直接白拿「分步讲解 / 知识卡 / 参数面板 / 课堂问答」四项我们没做的能力；我们的 GLB 与契约已就绪 |
| **第二步** | 用模式A 基于 ACAP 三视图跑 `forge/` 管线，生成程序化 A320 机体，替换方块几何 | 这才是解决 P1「结构可见」的正路；但它是大活，且要先解决性能预算冲突 |
| **第三步** | 模式B 补教学件（4 个货舱、0A/0B/0C 座椅阵列、油箱、CG 标记）并接 `lb_group` 契约 | 保证与真实舱单口径一致（1/3/4/5 舱、0A/0B/0C） |

**不建议**上来就跑模式A重建整机：几何一换，相机取景、标注避让、爆炸幅度全要重调，
而我们连"标注重叠"这个已知问题都还没修。

---

## 六、复用注意

- **许可**：edu-3d-studio 为 Apache-2.0，vendor 的 img2threejs 为 MIT。
  二者都要求保留版权与许可声明——交付物里要带上 `vendor/img2threejs/NOTICE.md` 的内容。
- **免责声明勿删**：模板底部内置"AI 生成、近似表达，关键结构请教师核对"。
  配载教学虽非医学，但涉及重量限值与重心包线，**这句必须保留并强化**（本项目的口径以该机 WBM 为准）。
- **脱敏**：课件里出现的任何承运人/注册号/机场码，仍须过本项目的 `scripts/desensitize_check.py` 门禁。
- **不要改模板占位符**：`__LESSON_TITLE__` / `__LESSON_DATA__` / `__MODEL_CODE__` 必须完整，
  否则 `assemble_lesson.py` 会直接报错（它会校验）。

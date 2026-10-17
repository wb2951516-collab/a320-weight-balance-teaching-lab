# three.js 生态资源选型与集成

调研日期：2026-09-22 ｜ 检索渠道：GitHub API + npm registry（均经代理实测）

## 一、选型结论

| 资源 | 仓库（★ / 许可） | 版本 | 用途 | 状态 |
|---|---|---|---|---|
| **@gltf-transform/cli** | donmccurdy/glTF-Transform（★1972 / MIT） | 4.5.0 | GLB 优化管线：几何去重、清理孤立资源 | ✅ 已装并接入管线 |
| **three-mesh-bvh** | gkjohnson/three-mesh-bvh（★3492 / MIT） | 0.9.15 | BVH 加速 raycast，支撑"点选部件" | ✅ 已装并接入 |
| **camera-controls** | yomotsu/camera-controls（★2426 / MIT） | 3.1.2 | 平滑运镜、定点视角切换 | ✅ 已装并接入 |
| **troika-three-text** | protectwise/troika（★1972 / MIT） | 0.52.5 | SDF 文字，替代 3D 挤出文字 | ✅ 已装并接入 |

**淘汰（评估后不采用）**

| 资源 | 原因 |
|---|---|
| zeux/meshoptimizer（gltfpack，★8356） | 与 dedup 功能重叠；dedup 已把 5067 KB 压到 463 KB，无需再引入原生二进制 |
| google/draco（★7487） | **降级为备选**。见第四节：dedup 后文件比 Draco 版更小，且省掉浏览器端 ~250 KB 解码器 |
| pmndrs/postprocessing（★2860，Zlib） | 描边高亮可用"选中件加自发光"低成本实现，暂不引入渲染后处理管线 |
| pmndrs/three-stdlib（★858） | 只是 three 官方 examples 的独立打包，本项目已直接用官方 addons，无增益 |
| donmccurdy/three-gltf-viewer（★2469） | 通用拖拽预览器，与本项目的教学交互需求不匹配，仅作参考 |

---

## 二、@gltf-transform/cli —— 收益最大的一项

### 为什么值得引
Blender 的 glTF 导出器**不做几何复用**：697 个物件各自写了一份独立的顶点缓冲，
哪怕它们的局部几何完全一样（实测：697 个 mesh datablock，零共享）。
所以导出的未压缩 GLB 高达 5067 KB。

`dedup` 命令按 accessor 内容做去重，把这些重复缓冲合并成一份。

### 实测效果（本项目的真实数据）

| 阶段 | 体积 | 唯一 BufferGeometry（Three.js 侧） |
|---|---|---|
| Blender 直接导出 | 5067 KB | **697**（完全不复用） |
| `dedup` 后 | 550 KB | **60** |
| `dedup` + `prune` 后 | **463 KB** | 60 |

**压缩比 10.9 倍**，且：
- extras（`lb_group`/`lb_layer`/`lb_dir`/`lb_anchor`）**零丢失**：697 个 mesh 全覆盖，33 个组、5 种 role、2 个来源根全部保留
- 场景级阶段表（`lb_stage_0..6`）完整保留
- 几何**没被动过**：包围盒仍是 37.61 × 9.95 × 34.57
- 浏览器端**不需要任何解码器**

### 集成方式
```powershell
# 一次性安装（已装好，在 tools/gltf/）
cd "D:\AI-coding\XiaomiMiMoProjects\配载教学建模\tools\gltf"
& "D:\node.js\npm.cmd" install "@gltf-transform/cli@4.5.0" --legacy-peer-deps

# 每次导出模型后跑优化管线
& $node "tools\optimize_glb.mjs" "output\stage1\teach_model_raw.glb" "output\stage1\teach_model.glb"
```
`tools/optimize_glb.mjs` 是我封装的管线脚本，串起 `dedup → prune`（`--draco` 可选），
打印每步体积与最终压缩比，输入输出都走临时目录，不会踩坏原文件。

---

## 三、three-mesh-bvh —— 为 P1 的几何量做准备

### 为什么值得引
现在几何只有 37k 顶点，three 原生 raycast 够快。但 Stage 2 要上 P1（≤200k 顶点），
届时"点击货舱 → 显示该舱重量与力矩贡献"这类交互，逐三角形求交会成为帧耗瓶颈。
BVH 把求交从 O(n) 降到 O(log n)。

### 集成方式
```js
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh';
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

// 建实例化网格前，对每个唯一几何建一次 BVH
if (geom.index) { try { geom.computeBoundsTree(); } catch {} }
```
注意：**非索引几何不支持**，须容错跳过（本项目 GLB 是索引几何，正常生效）。
`InstancedMesh` 的 raycast 内部走 `Mesh.prototype.raycast`，所以打了补丁后实例也能命中。

---

## 四、camera-controls —— 替换 OrbitControls

### 为什么值得引
OrbitControls 只能"转"，做不了**带缓动的定点走位**。课堂要"按讲稿逐段讲解"，
必须能一键平滑切到"货舱特写""机头特写"。

### 集成方式
```js
import CameraControls from 'camera-controls';
CameraControls.install({ THREE });

const controls = new CameraControls(camera, renderer.domElement);
controls.smoothTime = 0.42;

// 预设视角：最后一个参数 true = 平滑过渡
controls.setLookAt(px, py, pz, tx, ty, tz, true);

// 主循环：注意必须传 dt
controls.update(dt);
```
**易踩的坑**：`controls.update()` 必须传 `dt`（秒），传空会退化成不插值。
本页已在 `animate()` 里传 `dt`。

页面新增"视角"面板：全景 / 侧视 / 俯视 / 机头 / 货舱 / 客舱，并支持 `?view=cargo` 直达。

---

## 五、troika-three-text —— 解决标注不可读

### 为什么值得引
原方案把文字用 Blender 内置字体生成 **3D 挤出几何**，实测占**求值后顶点的 78.3%**、
GLB 体积的 50.4%，而且在课堂投影尺度下**小且糊**。SDF 文字按需生成纹理，
任意缩放都清晰，且**不产生几何顶点**。

### 集成方式（含 4 个依赖，必须一起映射）
```html
<script type="importmap">
{ "imports": {
  "three": "./vendor/three/build/three.module.js",
  "three/addons/": "./vendor/three/examples/jsm/",
  "troika-three-text": "./vendor/npm/node_modules/troika-three-text/dist/troika-three-text.esm.js",
  "troika-three-utils": "./vendor/npm/node_modules/troika-three-utils/dist/troika-three-utils.esm.js",
  "troika-worker-utils": "./vendor/npm/node_modules/troika-worker-utils/dist/troika-worker-utils.esm.js",
  "webgl-sdf-generator": "./vendor/npm/node_modules/webgl-sdf-generator/dist/webgl-sdf-generator.mjs",
  "bidi-js": "./vendor/npm/node_modules/bidi-js/dist/bidi.mjs"
}}
</script>
```
```js
const m = await import('troika-three-text');
const t = new m.Text();
t.text = '5 舱 散货舱';
t.fontSize = 0.8; t.anchorX = 'center'; t.anchorY = 'middle';
t.outlineWidth = '8%'; t.outlineColor = 0xffffff;   // 保证任意底色上都可读
t.material.depthTest = false;
t.sync();                                            // 改文字后必须同步
```
**两个坑（都踩过）**：
1. `webgl-sdf-generator` 必须指向 **`.mjs`**。指向 `dist/webgl-sdf-generator.js`（UMD/CJS）
   会报 `does not provide an export named 'default'`。
2. troika 的 `Text` 是 `Mesh`，**不会自动朝向相机**，需要每帧
   `t.quaternion.copy(camera.quaternion)`；三点 Sprite 才自带 billboard。

本页对 troika 做了**动态 import + 失败回退**：拿不到就退回 canvas 贴图 Sprite，
标注层失效绝不影响三维显示（实测回退路径也正常）。

---

## 六、安装位置与体积

| 位置 | 内容 | 用途 |
|---|---|---|
| `output\stage1\web\vendor\three` | **目录联接（junction）** → `D:\three.js` | 浏览器端 three.js r186 |
| `output\stage1\web\vendor\npm\node_modules` | three-mesh-bvh / camera-controls / troika-three-text + 4 依赖（8 包） | 浏览器端扩展库 |
| `tools\gltf\node_modules` | @gltf-transform/cli（176 包） | 离线 GLB 优化管线 |
| `tools\optimize_glb.mjs` | 优化管线封装 | 每次导出后跑 |
| `tools\render_check.mjs` | CDP 渲染自检器 | 验证页面是否真能加载并渲染 |

⚠️ **分发注意**：`vendor\three` 是 junction，**拷贝文件夹到别的机器不会带上它**。
对外分发前必须改成实体拷贝：
```powershell
Remove-Item "…\web\vendor\three" -Force
Copy-Item "D:\three.js" "…\web\vendor\three" -Recurse
```

---

## 七、附：Draco 为什么被降级为备选

| | Draco 版 | dedup 版 |
|---|---|---|
| 体积 | 1620 KB | **463 KB** |
| 浏览器解码器 | 必须加载（wasm 188 KB + wrapper 57 KB，另有 500 KB js 回退） | **不需要** |
| 依赖一致性 | `extensionsRequired` 含 `KHR_draco_mesh_compression`，缺解码器直接失败 | 无强制扩展 |
| 几何复用 | 不影响（仍 697 份独立几何） | 直接降到 60 份 |
| 适用场景 | 顶点量很大、网络带宽极紧时 | **本项目的默认选择** |

结论：**默认走 dedup；Draco 保留为 `teach_model_draco.glb` 备用**。
两者 viewer 都支持（`DRACOLoader` 已注册，加载非 Draco 文件时自动闲置）。

---

## 八、验证方式（不靠"应该能用"）

本项目的库集成一律用**真实浏览器**验证，工具是 `tools/render_check.mjs`：

```powershell
& $node "tools\render_check.mjs" "http://127.0.0.1:8777/index.html?t=100&src=AC_ROOT&labels=1" out.png 70
```

它通过 CDP 直连 Chrome，**轮询页面真实状态位**（而不是用 `--virtual-time-budget` 猜），
并抓取 Console 输出与未捕获异常。输出示例（2026-09-22 实测）：

```
模块已启动 : true
加载已完成 : true
自检读数   : 源网格 697 · 几何签名 52 · 实例网格(draw) 73 · 实例 697 · 组 33 · 标注 40 (troika-sdf)
Console 输出 (0 条):
未捕获异常 (0 条):
```

> **为什么不用 `chrome --screenshot --virtual-time-budget`**：该模式以虚拟时间推进，
> GLB 这类真实网络 I/O 会被饿死，同一页面同一服务**时成时败**，制造过假超时。
> 详见 `docs/三维页面排查指南.md`。

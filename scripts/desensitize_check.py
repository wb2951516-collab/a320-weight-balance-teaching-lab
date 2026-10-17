# -*- coding: utf-8 -*-
"""
配载教学建模 · 脱敏检查与替换工具
=================================

规则来源：同目录上级 `脱敏规则/desensitize_map.json`
设计原则：**只改可识别标识，不动数据结构与业务逻辑**
（站位、重量、指数、包线、舱位编号、判限逻辑一律原样保留）

用法（本机 bash PATH 损坏，请用 PowerShell 调用全路径 Python）：

  # 1) 扫描（只报告，不改文件）——推荐先跑这个
  & "$PY" desensitize_check.py scan <文件或目录> [...]

  # 2) 生成脱敏副本（原文件不动，输出到 --out 目录，保持相对路径）
  & "$PY" desensitize_check.py apply <文件或目录> [...] --out <输出目录>

  # 3) 扫描并返回退出码（有命中=1，干净=0），供自动化门禁使用
  & "$PY" desensitize_check.py gate <文件或目录> [...]

其中 $PY = C:\\Users\\96258\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe

报告与映射台账（本机留存，**不得对外发布**）：
  脱敏规则/_scan_report.txt
  脱敏规则/_mapping_ledger.json
"""
import io
import json
import os
import re
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RULE_DIR = os.path.join(os.path.dirname(HERE), "脱敏规则")
MAP_PATH = os.path.join(RULE_DIR, "desensitize_map.json")
LEDGER_PATH = os.path.join(RULE_DIR, "_mapping_ledger.json")
REPORT_PATH = os.path.join(RULE_DIR, "_scan_report.txt")

TEXT_EXT = {".txt", ".md", ".html", ".htm", ".js", ".mjs", ".json", ".py",
            ".csv", ".tsv", ".css", ".xml", ".svg", ".yml", ".yaml", ".log",
            ".ini", ".cfg", ".bat", ".ps1", ".sh"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".mimosa", ".workbuddy",
             "脱敏规则", "_raw", "preview"}


def load_map():
    with io.open(MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ledger():
    if os.path.isfile(LEDGER_PATH):
        try:
            with io.open(LEDGER_PATH, "r", encoding="utf-8") as f:
                led = json.load(f)
            if isinstance(led, dict) and "map" in led and "count" in led:
                return led
        except Exception:
            pass
    return {"map": {}, "count": {}}


def save_ledger(led):
    os.makedirs(RULE_DIR, exist_ok=True)
    with io.open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=2)


def _norm(token, normalize):
    """token 归一化，用于让同一实体的不同写法共用同一占位号。"""
    if normalize == "strip_dash":
        return token.replace("-", "").upper()
    return token


class Scrubber(object):
    def __init__(self, cfg, ledger=None):
        self.cfg = cfg
        self.ledger = ledger if ledger is not None else {}
        self.literal = cfg.get("literal", {})
        # —— 超短规则的词边界约束 ——
        # 两字码（如 `8L`）这类 ≤3 字符的规则，在**压缩后的 JS** 里必然大量误命中：
        # esbuild 生成的 bundle 里短标识符随手就撞上，把真正的泄漏淹没在噪声里
        # （实测：不加约束时门禁报 104 处命中，全部是 bundle 噪声）。
        # 真正的代号是**独立词元**（写作 `8L`、`8L 1234`、`"8L"`），不会嵌在标识符内部，
        # 所以给这些规则加"左侧非字母数字"约束。右侧**允许**接数字 ——
        # 两字码粘航班号（`8L1234`）是常见写法，不能漏。
        _long = [k for k in self.literal if len(k) > 3]
        _short = [k for k in self.literal if len(k) <= 3]
        self.lit_re = re.compile("|".join(
            re.escape(k) for k in sorted(_long, key=len, reverse=True))) if _long else None
        self.lit_short_re = re.compile("|".join(
            r"(?<![0-9A-Za-z])" + re.escape(k)
            for k in sorted(_short, key=len, reverse=True))) if _short else None
        self.pats = []
        for p in cfg.get("patterns", []):
            self.pats.append((p, re.compile(p["regex"])))

    def _seq(self, kind, token, template, normalize=None):
        """按规则分桶编号：同一 token 永远得到同一占位符，编号跨文件跨运行稳定。
        normalize=strip_dash 时，带与不带连字符的同一注册号视为同一架飞机，共用同一占位号。
        注意：桶内已用过的占位号不会被复用，避免已发布内容串号。"""
        key = "%s::%s" % (kind, _norm(token, normalize))
        m = self.ledger["map"]
        if key not in m:
            n = self.ledger["count"].get(kind, 0) + 1
            self.ledger["count"][kind] = n
            m[key] = template.format(n=n)
        return m[key]

    def hits(self, text):
        """Return list of (rule_id, matched_text, masked_text, line_no, line)."""
        found = []
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            for rx in (self.lit_re, self.lit_short_re):
                if not rx:
                    continue
                for m in rx.finditer(line):
                    found.append(("literal", m.group(0),
                                  self.literal[m.group(0)], i, line.strip()))
            for p, rx in self.pats:
                for m in rx.finditer(line):
                    # 防重叠：已被 literal 接管的串不再走 pattern，避免双记与编号浪费
                    if self.literal and m.group(0) in self.literal:
                        continue
                    act = p.get("action")
                    if act == "sequential_mask":
                        masked = self._seq(p["id"], m.group(0), p["template"],
                                           p.get("normalize"))
                    elif act == "literal_prefix":
                        masked = m.group(0).replace(p["from"], p["to"])
                    elif act == "role_title":
                        masked = p["template"]
                    else:
                        masked = "<未定义动作:%s>" % act
                    found.append((p["id"], m.group(0), masked, i, line.strip()))
        return found

    def apply(self, text):
        # 长规则与短规则**一次成批替换**，不是连续两次 sub ——
        # 连续 sub 会把上一次的替换结果再扫一遍，可能链式改写（占位符本身若是某条规则的
        # key 就会被二次替换）。这里先收集全部命中区间，按"起点升序、同起点长者优先"
        # 排序后一遍重建，已覆盖区间直接跳过。
        spans = []
        for rx in (self.lit_re, self.lit_short_re):
            if not rx:
                continue
            for m in rx.finditer(text):
                spans.append((m.start(), m.end(), self.literal[m.group(0)]))
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        parts, pos = [], 0
        for a, b, rep in spans:
            if a < pos:
                continue
            parts.append(text[pos:a])
            parts.append(rep)
            pos = b
        parts.append(text[pos:])
        out = "".join(parts)
        for p, rx in self.pats:
            act = p.get("action")
            if act == "sequential_mask":
                out = rx.sub(lambda m: self._seq(p["id"], m.group(0), p["template"],
                                                 p.get("normalize")), out)
            elif act == "literal_prefix":
                out = rx.sub(lambda m: m.group(0).replace(p["from"], p["to"]), out)
            elif act == "role_title":
                out = rx.sub(p["template"], out)
        return out


def safe_rel(path, start=None):
    """relpath 在跨盘符时会抛 ValueError（本机 C:/D: 混用），此处兜底返回绝对路径。"""
    try:
        return os.path.relpath(path, start) if start else os.path.relpath(path)
    except ValueError:
        return os.path.abspath(path)


def base_of(path):
    """文件取其所在目录，目录取其本身，用于计算脱敏副本的相对路径。"""
    p = os.path.abspath(path)
    return p if os.path.isdir(p) else os.path.dirname(p)


def walk(targets):
    """确定性遍历（排序），保证顺序编号在不同机器/不同次运行下完全一致。"""
    for t in targets:
        if os.path.isfile(t):
            yield t
        elif os.path.isdir(t):
            for root, dirs, files in os.walk(t):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for fn in sorted(files):
                    if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                        yield os.path.join(root, fn)


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1"):
        try:
            with io.open(path, "r", encoding=enc) as f:
                return f.read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None, None


# 内联二进制载荷（单文件课件的 GLB/PNG/字体）—— 扫描前必须先掩掉
INLINE_B64_RE = re.compile(r"(base64,)([A-Za-z0-9+/=]{200,})")
# 裸的 base64 长串（打包器把 WASM/字体塞进 JS 字符串字面量时不带 `base64,` 前缀）
RAW_B64_RE = re.compile(r"[A-Za-z0-9+/=]{300,}")
# SVG 路径数据（图标）：形如 "M8,8L16,8L24,24L16,24Z" 的坐标汤。
# 其中 `8L16` 是"画线到 (16,8)"的指令，却会被两字码规则 `8L` 命中（实测 2 处）。
# 判据用**路径命令序列**（命令字母 + 纯数字/逗号/空格，至少 3 段）而不是长度阈值：
# 长度阈值会误伤正文，例如 "STATION,12.5,ARM,3.2" 这种表格行会被整段掩掉；
# 而命令序列要求每个字母后面只跟坐标字符，正文里的 `TATION`/`SION` 会在此断开。
SVG_CMD = "MmLlHhVvCcSsQqTtAaZz"
SVG_PATH_RE = re.compile(
    r"[%s][0-9.,+\-\s]*(?:[%s][0-9.,+\-\s]*){2,}" % (SVG_CMD, SVG_CMD))


def mask_inline_data(text):
    """把内联二进制载荷 / 机器生成的坐标串换成占位符后再扫描。

    为什么必须有这一步（2026-09-22 实测，四轮才收敛）：
    单文件交付把 GLB 以 base64 内联进 HTML，而 base64 字母表包含大小写字母与数字，
    于是**任何短规则都会在几 MB 的随机串里被命中**。门禁一次报出 332 处命中，
    逐条查看后**全部**是同一规则（两字码 `8L`）撞进机器生成的串 —— 纯噪声，
    却把 exit code 打成 1、把真正的泄漏淹没在噪声里。

    三类形态都要掩（少掩一类就残留噪声，逐轮实测）：
      ① `data:...;base64,<长串>` —— 我们自己的单文件课件（332 → 104）
      ② 打包器塞进 JS 字符串里的**裸** base64（无前缀）（104 → 2）
      ③ SVG 路径坐标串，如 `M8,8L16,8L24,24L16,24Z`（2 → 0）

    残余风险：若某张内联贴图里**真的印着**承运人名称，掩码会漏掉它。
    本项目 GLB 不含任何贴图（材质全是程序化 PBR），故该风险为空；
    一旦引入贴图，应对**源图**单独跑一次 scan。
    """
    text = INLINE_B64_RE.sub(
        lambda m: m.group(1) + "<%d chars of inline base64 masked>" % len(m.group(2)), text)
    text = RAW_B64_RE.sub(
        lambda m: "<%d chars of raw base64 masked>" % len(m.group(0)), text)
    return SVG_PATH_RE.sub(
        lambda m: "<%d chars of svg path masked>" % len(m.group(0)), text)


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    mode = argv[0]
    out_dir = None
    targets = []
    i = 1
    while i < len(argv):
        if argv[i] == "--out":
            out_dir = argv[i + 1]
            i += 2
            continue
        targets.append(argv[i])
        i += 1

    cfg = load_map()
    scr = Scrubber(cfg, load_ledger())

    rep = []
    rep.append("配载教学建模 · 脱敏%s报告" % ("替换" if mode == "apply" else "扫描"))
    rep.append("时间：%s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    rep.append("模式：%s ｜ 规则版本：%s ｜ 生效范围：%s"
               % (cfg["meta"]["mode"], cfg["meta"]["version"],
                  "仅展示/输出" if cfg["meta"]["mode"] == "display_only" else "全部"))
    rep.append("目标：%s" % " ; ".join(targets))
    rep.append("=" * 78)

    n_files = n_hit_lines = n_hits = 0
    per_rule = {}
    for path in walk(targets):
        text, enc = read_text(path)
        if text is None:
            continue
        n_files += 1
        found = scr.hits(mask_inline_data(text))
        if not found:
            continue
        n_hits += len(found)
        lines_hit = len(set(h[3] for h in found))
        n_hit_lines += lines_hit
        rep.append("")
        rep.append("[命中] %s  (编码 %s, 命中 %d 处 / %d 行)"
                   % (safe_rel(path), enc, len(found), lines_hit))
        for rid, raw, masked, ln, line_txt in found:
            per_rule[rid] = per_rule.get(rid, 0) + 1
            rep.append("    L%-5d %-24s %-18s -> %-18s | %s"
                       % (ln, rid, raw, masked, line_txt[:70]))
        if mode == "apply":
            if not out_dir:
                rep.append("    !! apply 模式缺少 --out，跳过写出")
                continue
            rel = safe_rel(path, base_of(targets[0]))
            if rel.startswith("..") or os.path.isabs(rel):
                rel = os.path.basename(path)
            dst = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with io.open(dst, "w", encoding="utf-8") as f:
                f.write(scr.apply(text))
            rep.append("    -> 已写出脱敏副本：%s" % dst)

    rep.append("")
    rep.append("=" * 78)
    rep.append("汇总：扫描文件 %d 个，命中 %d 处 / %d 行" % (n_files, n_hits, n_hit_lines))
    if per_rule:
        rep.append("按规则分布：")
        for k, v in sorted(per_rule.items(), key=lambda x: -x[1]):
            rep.append("    %-24s %d" % (k, v))
    else:
        rep.append("结论：未发现需要脱敏的内容。")

    os.makedirs(RULE_DIR, exist_ok=True)
    with io.open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(rep))
    if mode == "apply":
        save_ledger(scr.ledger)
    print("\n".join(rep))
    print("\n报告已写入：%s" % REPORT_PATH)
    return 1 if (mode == "gate" and n_hits) else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_project.py — 编译前静态自检：一次性把最容易翻车的地方全查一遍。

检查项
------
  1. 路径/文件名是否全 ASCII（EasyFace 读不了中文工程名）
  2. 主 fprj 与 AOD.fprj 的 XML 是否可解析、DeviceType / Widget 数
  3. Bitmap / BitmapList 是否有空项（尾随 | 会拼出 images\\ 目录，编译报
     "unable to open image ... No such file or directory"）、引用图片是否齐全
  4. Lua 容器（Shape=34）是否存在，btn_* 热区是否全部排在它之后
  5. Lua 是否包含点击修复（CLICKABLE / EVENT_BUBBLE / park_veil），
     并报告 START_OPA / FRAMES / MIN_OPA / PERIOD
  6. AOD 素材压暗系数与 START_OPA 是否满足 255*(1-factor) 配对
  7. 全部 PNG 是否可完整解码

用法
----
    python verify_project.py <工程目录>
    python verify_project.py <工程目录> --source <原始AOD素材目录>
    python verify_project.py <工程目录> --strict   # 有警告也返回非 0

退出码：0 全部通过；1 存在错误；2 --strict 下存在警告。
"""

import argparse
import os
import re
import sys
from xml.etree import ElementTree as ET

try:
    from PIL import Image
except ImportError:
    sys.exit("需要 Pillow：pip install pillow")

ERRORS = []
WARNINGS = []


def err(msg):
    ERRORS.append(msg)
    print("  [错误] " + msg)


def warn(msg):
    WARNINGS.append(msg)
    print("  [警告] " + msg)


def ok(msg):
    print("  [OK]   " + msg)


def bitmap_items(value):
    """解析 BitmapList 的 (序号):文件名 形式，返回文件名列表（含空项）。"""
    out = []
    for it in value.split("|"):
        if it.startswith("(") and ":" in it:
            it = it.split(":", 1)[1]
        out.append(it)
    return out


def find_fprjs(project):
    main = [os.path.join(project, n) for n in sorted(os.listdir(project))
            if n.lower().endswith(".fprj") and os.path.isfile(os.path.join(project, n))]
    aod = os.path.join(project, "AOD", "AOD.fprj")
    return main, aod if os.path.isfile(aod) else None


def check_ascii(project):
    print("\n[1] 路径与文件名 ASCII 检查")
    bad = []
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in (".git", "output", "__pycache__")]
        for n in dirs + files:
            if any(ord(c) > 127 for c in n):
                bad.append(os.path.relpath(os.path.join(root, n), project))
    if bad:
        warn("发现 %d 个非 ASCII 路径项，EasyFace 可能读不了：%s" % (len(bad), ", ".join(bad[:5])))
    else:
        ok("工程内文件名/目录名全部为 ASCII（output/ 历史产物已排除）")


def check_fprj(project, path, img_subdir):
    label = os.path.relpath(path, project)
    raw = open(path, "rb").read()
    bom = raw[:3] == b"\xef\xbb\xbf"
    try:
        root = ET.fromstring(raw.decode("utf-8-sig"))
    except Exception as e:
        err("%s XML 解析失败: %s" % (label, e))
        return None
    widgets = list(root.iter("Widget"))
    print("  %-16s bytes=%-6d BOM=%-5s DeviceType=%-6s Widget=%d" %
          (label, len(raw), bom, root.get("DeviceType", "?"), len(widgets)))

    img_dir = os.path.join(project, img_subdir)
    total = empty = missing = 0
    for w in widgets:
        for attr in ("Bitmap", "BitmapList"):
            v = w.get(attr)
            if not v:
                continue
            items = [v] if attr == "Bitmap" else bitmap_items(v)
            for it in items:
                total += 1
                if not it:
                    empty += 1
                    err("%s: %s 有空 Bitmap 项（控件 %s）—— 会拼出目录路径，编译必报错" %
                        (label, attr, w.get("Name")))
                elif not os.path.isfile(os.path.join(img_dir, it)):
                    missing += 1
                    if missing <= 5:
                        err("%s: %s 引用了不存在的图片 %s" % (label, w.get("Name"), it))
    if empty == 0 and missing == 0:
        ok("%s 引用 %d 项，0 空项 / 0 缺文件" % (label, total))
    else:
        err("%s 引用 %d 项，空项 %d / 缺文件 %d" % (label, total, empty, missing))

    lua_idx = None
    hot = []
    for i, line in enumerate(raw.decode("utf-8-sig").splitlines()):
        if not re.match(r"^\s*<Widget\b", line):
            continue
        if 'Shape="34"' in line and "app__lua%2F" in line:
            lua_idx = i
        m = re.search(r'Name="([^"]*)"', line)
        if m and m.group(1).startswith("btn_["):
            hot.append((i, m.group(1)))
    return {"lua_line": lua_idx, "hot": hot, "widget_count": len(widgets)}


def check_layer_order(label, info, require_lua=True):
    if info is None:
        return
    if info["lua_line"] is None:
        # AOD 是独立静态主题，通常不注入 Lua 图层 —— 这是正常状态，不是错误
        if require_lua:
            err("%s 里没有 Shape=34 Lua 容器" % label)
        else:
            ok("%s 无 Lua 容器（AOD 独立静态主题，符合预期）" % label)
        return
    hot = info["hot"]
    if not hot:
        warn("%s 里没找到 btn_* 跳转热区（没有跳转需求可忽略）" % label)
        return
    bad = [n for i, n in hot if i < info["lua_line"]]
    if bad:
        err("%s 有 %d 个热区排在 Lua 容器之下，点击会被吞掉：%s" % (label, len(bad), ", ".join(bad[:5])))
    else:
        ok("%s Lua 容器第 %d 行，%d 个热区全部在其上" %
           (label, info["lua_line"] + 1, len(hot)))


def check_lua(project):
    print("\n[5] Lua 脚本检查")
    lua_dir = os.path.join(project, "app", "_lua")
    if not os.path.isdir(lua_dir):
        err("缺少 app/_lua/ 目录")
        return None
    files = [n for n in sorted(os.listdir(lua_dir)) if n.lower().endswith(".lua")]
    if not files:
        err("app/_lua/ 下没有 .lua 文件")
        return None
    text = ""
    for n in files:
        p = os.path.join(lua_dir, n)
        data = open(p, "rb").read()
        try:
            text += data.decode("utf-8") + "\n"
        except UnicodeDecodeError:
            err("%s 不是 UTF-8，EasyFace 可能读不了" % n)
        print("  %-28s %d bytes" % (n, len(data)))
    for key in ("CLICKABLE", "EVENT_BUBBLE", "park_veil"):
        if key not in text:
            err("Lua 缺少 %s —— 叠加全屏遮罩后跳转很可能失效" % key)
    if all(k in text for k in ("CLICKABLE", "EVENT_BUBBLE", "park_veil")):
        ok("点击修复三要素齐全")
    # 只看代码：剥离 Lua 行注释与字符串，避免把注释里的说明当成实际调用
    code = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "-" and i + 1 < n and text[i + 1] == "-":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c in "'\"":
            q = c
            i += 1
            while i < n and text[i] != q:
                if text[i] == "\\":
                    i += 1
                i += 1
            i += 1
            code.append("S")
            continue
        code.append(c)
        i += 1
    if "string." in "".join(code):
        warn("Lua 代码里使用了 string.*，部分固件可能裁剪该库导致脚本整体不生效")
    params = {}
    for k in ("START_OPA", "FRAMES", "PERIOD", "MIN_OPA"):
        m = re.search(r"local\s+" + k + r"\s*=\s*(\d+)", text)
        params[k] = int(m.group(1)) if m else None
    print("  参数: " + "  ".join("%s=%s" % (k, v) for k, v in params.items()))
    return params


def check_pairing(project, params, source=None, prefix="aod_"):
    print("\n[6] AOD 亮度与 START_OPA 配对")
    if not params or params.get("START_OPA") is None:
        warn("拿不到 START_OPA，跳过配对检查")
        return
    aod_dir = os.path.join(project, "AOD", "images")
    if source:
        backup = os.path.abspath(source)
        src_label = prefix
    else:
        backup = os.path.join(project, "AOD", "images_original")
        src_label = ""
    if not os.path.isdir(backup):
        warn("找不到原始 AOD 素材，无法反推压暗系数；"
             "可用 --source <原始素材目录> 指定，或运行 dim_aod_assets.py 建立工程内副本")
        return
    ratios = []
    # 以工程内 AOD/images/ 为基准，去原始素材源里找同名（或带前缀）的原始文件
    for n in sorted(os.listdir(aod_dir))[:20]:
        if not n.lower().endswith(".png"):
            continue
        src = os.path.join(backup, (prefix + n) if source else n)
        if not os.path.isfile(src) and source:
            src = os.path.join(backup, n)  # 回退同名
        dst = os.path.join(aod_dir, n)
        if not os.path.isfile(src):
            continue
        a = Image.open(src).convert("RGB")
        b = Image.open(dst).convert("RGB")
        amax = max(ch[1] for ch in a.getextrema())
        bmax = max(ch[1] for ch in b.getextrema())
        if amax > 0:
            ratios.append(bmax / amax)
    if not ratios:
        warn("没有可比较的 AOD 素材（检查 --source 与文件名前缀）")
        return
    if src_label:
        print("  原始素材源: %s（前缀 %s）" % (backup, prefix))
    factor = sum(ratios) / len(ratios)
    expected = round(255 * (1 - factor))
    print("  推算 AOD 系数 = %.3f -> 期望 START_OPA = %d；实际 = %d" %
          (factor, expected, params["START_OPA"]))
    if abs(expected - params["START_OPA"]) > 8:
        err("AOD 压暗系数与 START_OPA 未对齐，点亮会出现亮度跳变；"
            "运行 dim_aod_assets.py --sync 修正")
    else:
        ok("两帧亮度配对正确")


def check_png(project):
    print("\n[7] PNG 完整性")
    total = bad = 0
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in (".git", "output", "__pycache__")]
        for n in files:
            if not n.lower().endswith(".png"):
                continue
            total += 1
            p = os.path.join(root, n)
            try:
                with Image.open(p) as im:
                    im.load()
                with Image.open(p) as im2:
                    im2.verify()
            except Exception as e:
                bad += 1
                if bad <= 5:
                    err("PNG 损坏 %s: %s" % (os.path.relpath(p, project), e))
    if bad == 0:
        ok("%d 张 PNG 全部可完整解码" % total)
    else:
        err("%d / %d 张 PNG 损坏" % (bad, total))


def main():
    ap = argparse.ArgumentParser(description="表盘工程编译前静态自检")
    ap.add_argument("project", help="工程目录")
    ap.add_argument("--source", default=None,
                    help="原始 AOD 素材目录（含 aod_*.png），用于反推压暗系数")
    ap.add_argument("--prefix", default="aod_", help="--source 下原始文件名前缀")
    ap.add_argument("--strict", action="store_true", help="有警告也返回非 0")
    args = ap.parse_args()
    project = os.path.abspath(args.project)
    if not os.path.isdir(project):
        sys.exit("找不到工程目录: %s" % project)
    print("工程: %s" % project)

    check_ascii(project)
    print("\n[2-3] fprj 结构与资源引用")
    mains, aod = find_fprjs(project)
    if not mains:
        err("根目录下没有 .fprj")
        main_info = None
    else:
        if len(mains) > 1:
            warn("根目录有多个 .fprj，只检查第一个 %s" % os.path.basename(mains[0]))
        main_info = check_fprj(project, mains[0], "images")
    aod_info = check_fprj(project, aod, "AOD/images") if aod else None
    if aod is None:
        warn("没有 AOD/AOD.fprj（无 AOD 主题可忽略）")

    print("\n[4] 点击层序")
    if main_info:
        check_layer_order(os.path.basename(mains[0]), main_info, require_lua=True)
    if aod_info:
        check_layer_order("AOD/AOD.fprj", aod_info, require_lua=False)

    params = check_lua(project)
    check_pairing(project, params, args.source, args.prefix)
    check_png(project)

    print("\n" + "=" * 60)
    print("错误 %d，警告 %d" % (len(ERRORS), len(WARNINGS)))
    if ERRORS:
        for e in ERRORS:
            print("  ! " + e)
        sys.exit(1)
    if WARNINGS and args.strict:
        sys.exit(2)
    print("自检通过。编译时记得：改了 AOD 素材 -> 两个主题都重编译；"
          "改了 Lua -> 关闭并重开工程再编译。")


if __name__ == "__main__":
    main()

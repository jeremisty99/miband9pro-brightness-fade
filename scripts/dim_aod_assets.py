#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dim_aod_assets.py — 压暗 AOD 主题素材，消除抬腕点亮时的亮度下凹。

背景
----
AOD 与主表盘是两套独立主题。抬腕点亮时引擎先以正常背光重绘 AOD 最后一帧，
再切换到主表盘；Lua 遮罩只作用于主表盘，盖不住 AOD 那一帧。
黑色遮罩只能让「主表盘首帧」变暗，不能提亮，所以：

  - AOD 素材保持全亮 + 想消除亮度跳变 -> 遮罩必须很淡 -> 渐显几乎看不见；
  - 想让渐显明显 -> 遮罩要够深 -> 两帧之间必然出现一次变暗。

唯一能同时兼顾的办法：把 AOD 素材整体压暗，让两帧亮度对齐。

稳定组合（真机确认「有渐显 + 跳转正常」）
----------------------------------------
    AOD 素材 factor = 0.62   &&   Lua START_OPA = 255*(1-factor) = 97
两者必须成对改动，只改一个就会重新出现「AOD 亮帧 -> 主表盘暗帧」的跳变。
--sync 会自动把 Lua 里所有 START_OPA 同步成 255*(1-factor)。

关键性质
--------
每次都从「原始素材」重新生成，幂等、可恢复：
  * 指定 --source 时，从该目录读取（默认文件名前缀 aod_，可用 --prefix 改）；
  * 未指定时，首次运行会把当前 AOD/images/ 复制到 AOD/images_original/ 作为
    永久原始副本，之后一律从它重新生成，重复执行不会越压越暗；
  * --factor 1.0 还原成原始亮度（同时应把 START_OPA 设为 0）。

用法
----
python dim_aod_assets.py <工程目录> --sync              # 默认 0.62，标准状态
python dim_aod_assets.py <工程目录> --factor 0.70 --sync
python dim_aod_assets.py <工程目录> --factor 1.0 --sync # 还原
python dim_aod_assets.py <工程目录> --check
python dim_aod_assets.py <工程目录> --compare-only      # 亮度曲线对比图
python dim_aod_assets.py <工程目录> --source <解包目录> --prefix aod_

依赖：Pillow（pip install pillow）
"""

import argparse
import os
import re
import shutil
import sys

try:
    from PIL import Image, ImageDraw, ImageFont, ImageStat
except ImportError:
    sys.exit("需要 Pillow：pip install pillow")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIRNAME = "images_original"


def luminance(im):
    rgb = im.convert("RGB")
    return sum(ImageStat.Stat(rgb).mean) / 3.0


def dim_image(src_path, dst_path, factor):
    """从原始素材重新生成压暗版，保持 alpha 与像素尺寸。"""
    im = Image.open(src_path).convert("RGBA")
    if factor != 1.0:
        r, g, b, a = im.split()
        lut = [max(0, min(255, round(i * factor))) for i in range(256)]
        im = Image.merge("RGBA", (r.point(lut), g.point(lut), b.point(lut), a))
    # 统一写 RGBA：EasyFace / Mi-Create 编译器均支持；索引色原图转 RGBA 无损
    im.save(dst_path, "PNG", optimize=True)


def resolve_source(project, aod_dir, source_arg, prefix, allow_create=True):
    """返回 (原始素材目录, 每个 AOD 图片对应的原始文件名映射)。"""
    names = sorted(n for n in os.listdir(aod_dir) if n.lower().endswith(".png"))
    if source_arg:
        src_dir = os.path.abspath(source_arg)
        if not os.path.isdir(src_dir):
            sys.exit("找不到 --source 目录: %s" % src_dir)
        mapping = {}
        missing = []
        for n in names:
            cand = os.path.join(src_dir, prefix + n)
            if not os.path.isfile(cand) and os.path.isfile(os.path.join(src_dir, n)):
                cand = os.path.join(src_dir, n)
            if os.path.isfile(cand):
                mapping[n] = cand
            else:
                missing.append(n)
        return src_dir, mapping, missing

    # 自包含模式：工程内维护一份永久原始副本
    backup = os.path.join(os.path.dirname(aod_dir), BACKUP_DIRNAME)
    if not os.path.isdir(backup):
        if not allow_create:
            sys.exit("缺少原始素材副本 %s；请用 --source 指定，或去掉 --check 先生成" % backup)
        os.makedirs(backup, exist_ok=True)
        for n in names:
            shutil.copy2(os.path.join(aod_dir, n), os.path.join(backup, n))
        print("已建立原始素材副本: %s（%d 张）" % (backup, len(names)))
    missing = [n for n in names if not os.path.isfile(os.path.join(backup, n))]
    mapping = {n: os.path.join(backup, n) for n in names if n not in missing}
    return backup, mapping, missing


def sync_lua(project, factor):
    """把 app/_lua/ 下所有 Lua 的 START_OPA 同步成 255*(1-factor)。"""
    lua_dir = os.path.join(project, "app", "_lua")
    opa = round(255 * (1 - factor))
    if not os.path.isdir(lua_dir):
        print("未找到 app/_lua/，跳过同步；请手动把 Lua 的 START_OPA 设为 %d" % opa)
        return
    hit = 0
    for name in sorted(os.listdir(lua_dir)):
        if not name.lower().endswith(".lua"):
            continue
        p = os.path.join(lua_dir, name)
        raw = open(p, "rb").read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        new, n = re.subn(r"(local\s+START_OPA\s*=\s*)\d+",
                         lambda m: m.group(1) + str(opa), text, count=1)
        if n and new != text:
            open(p, "wb").write(new.encode("utf-8"))
            hit += 1
            print("  已同步 %s: START_OPA = %d" % (name, opa))
    if not hit:
        print("  未找到需修改的 START_OPA（可能已是 %d，或脚本里没这个常量）" % opa)


def make_compare(project, path, factor):
    """生成亮度衔接曲线对比图（纯 Pillow 绘制，不依赖表盘预览图与中文字体）。"""
    opa = round(255 * (1 - factor))
    W, H = 660, 260
    canvas = Image.new("RGB", (W, H), (250, 249, 245))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
        bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 13)
    except Exception:
        font = bold = ImageFont.load_default()
    draw.text((20, 14), "DIGIT LUMINANCE DURING WAKE  (factor=%.2f, START_OPA=%d)" %
              (factor, opa), fill=(44, 44, 42), font=bold)

    x0, x1, y_lo, y_hi = 70, W - 20, 200, 44

    def Y(v):
        return y_lo - (v / 255.0) * (y_lo - y_hi)

    for gv in (0, 64, 128, 192, 255):
        yy = Y(gv)
        draw.line((x0, yy, x1, yy), fill=(220, 218, 210), width=1)
        draw.text((x0 - 32, yy - 6), str(gv), fill=(110, 110, 105), font=font)
    xs = [x0 + i * (x1 - x0) / 3.0 for i in range(4)]
    for i, lab in enumerate(("AOD frame", "main 1st", "ramp", "full")):
        draw.text((xs[i] - 30, y_lo + 10), lab, fill=(95, 94, 90), font=font)

    aod_raw = 150.0
    aod_dim = 150.0 * factor
    main_first = 159.0 * (1 - opa / 255.0)
    series = [
        ("before: AOD native + opa150", (200, 80, 80), [aod_raw, 65, 110, 159]),
        ("after: aligned", (46, 158, 99), [aod_dim, main_first,
                                            (main_first + 159) / 2, 159]),
    ]
    for name, color, vals in series:
        pts = [(xs[i], Y(vals[i])) for i in range(4)]
        draw.line(pts, fill=color, width=3)
        for px, py in pts:
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=color)
    lx, ly = x0 + 16, y_hi + 8
    for i, (name, color, _) in enumerate(series):
        draw.text((lx, ly + i * 17), "- " + name, fill=color, font=font)
    draw.text((20, H - 26),
              "START_OPA = 255 * (1 - factor); both themes must be rebuilt after changing AOD assets.",
              fill=(110, 110, 105), font=font)
    canvas.save(path)
    return path


def main():
    ap = argparse.ArgumentParser(
        description="AOD 素材亮度工具（默认 0.62，与 START_OPA=97 配对）")
    ap.add_argument("project", help="工程目录（含 AOD/images/）")
    ap.add_argument("--source", default=None,
                    help="原始解包素材目录（含 aod_img_*.png）；不指定则在工程内自动维护副本")
    ap.add_argument("--prefix", default="aod_",
                    help="--source 模式下原始文件名前缀，默认 aod_；找不到时回退同名文件")
    ap.add_argument("--factor", type=float, default=0.62,
                    help="AOD 素材亮度系数，默认 0.62；1.0 还原原始素材")
    ap.add_argument("--sync", action="store_true",
                    help="把 Lua 的 START_OPA 同步成 255*(1-factor)")
    ap.add_argument("--check", action="store_true", help="只报告、不写文件")
    ap.add_argument("--compare", action="store_true", help="额外生成亮度曲线对比图")
    ap.add_argument("--compare-only", action="store_true", help="只生成对比图，不改素材")
    ap.add_argument("--compare-out", default=None, help="对比图输出路径")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    if not 0.0 < args.factor <= 1.0:
        sys.exit("--factor 必须落在 (0, 1]")
    aod_dir = os.path.join(project, "AOD", "images")
    if not os.path.isdir(aod_dir):
        sys.exit("找不到 AOD 素材目录: %s" % aod_dir)

    if args.compare or args.compare_only:
        out = args.compare_out or os.path.join(HERE, "brightness_compare.png")
        print("对比图: %s" % make_compare(project, out, args.factor))
    if args.compare_only:
        return

    src_dir, mapping, missing = resolve_source(
        project, aod_dir, args.source, args.prefix, allow_create=not args.check)
    print("工程       : %s" % project)
    print("原始素材源 : %s" % src_dir)
    print("AOD 图片数 : %d，缺源 %d" % (len(mapping), len(missing)))
    if missing[:5]:
        print("  缺源示例:", ", ".join(missing[:5]))
    print("亮度系数   : %.2f  (1.00 = 原始 AOD 素材；标准值 0.62)" % args.factor)
    print("配对 Lua START_OPA 应为 = %d" % round(255 * (1 - args.factor)))
    if args.check:
        if mapping:
            sample = list(mapping.items())[:8]
            before = sum(luminance(Image.open(v)) for _, v in sample) / len(sample)
            after = sum(luminance(Image.open(os.path.join(aod_dir, k)))
                        for k, _ in sample) / len(sample)
            print("抽样平均亮度: 原始 %.1f -> 当前 %.1f" % (before, after))
        print("--check：未写入任何文件")
        return

    for name, src in mapping.items():
        dim_image(src, os.path.join(aod_dir, name), args.factor)
    print("已写入 %d 张 AOD 素材（从原始源重新生成，可重复执行）" % len(mapping))
    if args.sync:
        sync_lua(project, args.factor)
    print("下一步：用 EasyFace / Mi-Create 把 AOD 与主表盘两个主题都重新编译。")


if __name__ == "__main__":
    main()

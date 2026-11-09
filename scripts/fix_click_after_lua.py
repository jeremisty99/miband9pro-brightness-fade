#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_click_after_lua.py — 修复「叠加 Lua 缓亮图层后跳转全部失效」的工程层方案。

原理
----
Lua 图层在 .fprj 里是 Shape="34" 基础容器，社区教程要求放在最顶图层
（Screen 内最后一个 Widget）、尺寸覆盖全屏。表盘引擎的触摸命中按图层
z-order 自顶向下匹配，于是这个全屏容器先吃掉所有点击，排在它下面的
btn_[...]_RGBA 跳转热区收不到事件。SmoothlyLight README 亦自述
「2.0 版本暂时不支持下属表盘的点击事件」。

本工具把所有跳转热区 Widget 移到 Lua 容器「之后」（即更顶层）。
热区图通常是 100% 透明的 RGBA 图，因此：
  - 渲染：内容控件仍在 Lua 遮罩之下，黑色渐变依旧盖得住画面；
          热区透明，叠在最上层不改变任何像素。
  - 命中：热区变为最顶层，点击优先落在热区上，跳转恢复。

必须与 Lua 侧的 clear_flag(CLICKABLE) / add_flag(EVENT_BUBBLE) /
park_veil() 同时使用 —— 单独改哪一边都不够（真机验证的「B_组合」）。

只做行级文本搬移，不重序列化 XML，保持原编码 / BOM / 属性顺序 / 缩进。
幂等：热区已在 Lua 容器之后时不改动文件。

用法
----
  python fix_click_after_lua.py <工程目录>
  python fix_click_after_lua.py <工程目录> --check
  python fix_click_after_lua.py <工程目录> --restore
  python fix_click_after_lua.py <工程目录> --pattern "btn_|zone_"
"""

import argparse
import os
import re
import shutil
import sys

WIDGET_RE = re.compile(r"^\s*<Widget\b")
NAME_RE = re.compile(r'Name="([^"]*)"')


def find_fprj(project):
    """取工程根目录下的 .fprj（排除 AOD 子目录）。"""
    cands = [os.path.join(project, n) for n in sorted(os.listdir(project))
             if n.lower().endswith(".fprj")
             and os.path.isfile(os.path.join(project, n))]
    if not cands:
        raise SystemExit("[错误] %s 下没有 .fprj 文件" % project)
    if len(cands) > 1:
        print("[提示] 发现多个 .fprj，使用 %s" % os.path.basename(cands[0]))
    return cands[0]


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), "utf-8", True
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16", True
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc), enc, False
        except UnicodeDecodeError:
            continue
    raise SystemExit("[错误] 无法识别文本编码: %s" % path)


def write_text(path, text, enc, bom):
    if enc == "utf-16":
        data = b"\xff\xfe" + text.encode("utf-16-le")
    else:
        data = (b"\xef\xbb\xbf" if bom else b"") + text.encode(enc)
    with open(path, "wb") as f:
        f.write(data)


def analyze(lines, pattern):
    """返回 (lua_idx, hotzone_idxs, widget_idxs)。"""
    widget_idxs, lua_idx, hotzone_idxs = [], None, []
    for i, line in enumerate(lines):
        if not WIDGET_RE.match(line):
            continue
        widget_idxs.append(i)
        if "/>" not in line and "</Widget>" not in line:
            raise SystemExit(
                "[错误] 第 %d 行的 Widget 是跨行写法，本工具只搬移单行 Widget：\n"
                "       %s" % (i + 1, line.strip()[:120]))
        if 'Shape="34"' in line and "app__lua%2F" in line:
            lua_idx = i
        m = NAME_RE.search(line)
        if m and re.search(pattern, m.group(1)):
            hotzone_idxs.append(i)
    return lua_idx, hotzone_idxs, widget_idxs


def main():
    ap = argparse.ArgumentParser(description="把跳转热区移到 Lua 图层之上，恢复点击")
    ap.add_argument("project", help=".fprj 所在工程目录")
    ap.add_argument("--pattern", default=r"^btn_\[",
                    help="热区 Name 匹配的正则（默认 ^btn_\\[）")
    ap.add_argument("--no-backup", action="store_true", help="不生成 .bak 备份")
    ap.add_argument("--restore", action="store_true", help="从 .bak 还原")
    ap.add_argument("--check", action="store_true", help="只检查层序，不写文件")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    fprj = find_fprj(project)
    bak = fprj + ".bak"

    if args.restore:
        if not os.path.isfile(bak):
            raise SystemExit("[错误] 找不到备份 %s" % bak)
        shutil.copy2(bak, fprj)
        print("[完成] 已从备份还原: %s" % fprj)
        return

    text, enc, bom = read_text(fprj)
    lines = text.splitlines(keepends=True)
    lua_idx, hotzone_idxs, widget_idxs = analyze(lines, args.pattern)

    print("工程: %s" % fprj)
    print("  Widget 总数       : %d" % len(widget_idxs))
    print("  Lua 容器 (Shape34): 第 %d 行" % (lua_idx + 1) if lua_idx is not None
          else "  Lua 容器 (Shape34): 未找到")
    print("  跳转热区          : %d 个 %s" %
          (len(hotzone_idxs), [NAME_RE.search(lines[i]).group(1) for i in hotzone_idxs]))

    if lua_idx is None:
        raise SystemExit("[错误] 工程里没有 Lua 容器，无需此修复")
    if not hotzone_idxs:
        raise SystemExit("[错误] 没找到跳转热区，检查 --pattern")

    if all(i > lua_idx for i in hotzone_idxs):
        print("  状态: 热区已全部位于 Lua 容器之上 —— 无需改动"
              "（幂等，这是点击修复后的预期层序）")
        return

    last_widget = max(widget_idxs)
    if lua_idx != last_widget:
        print("  [提示] Lua 容器不是 Screen 内最后一个 Widget"
              "（最后是第 %d 行），工具仍会把热区放到它之后" % (last_widget + 1))

    if args.check:
        print("  状态: 热区在 Lua 容器之下，点击会被拦截（--check 未写入）")
        sys.exit(2)

    # 抽出热区行（保持原顺序），插入到 Lua 容器行之后
    hot_lines = [lines[i] for i in hotzone_idxs]
    hot_set = set(hotzone_idxs)
    remaining = [ln for i, ln in enumerate(lines) if i not in hot_set]
    new_lua = next(i for i, ln in enumerate(remaining)
                   if 'Shape="34"' in ln and "app__lua%2F" in ln)
    new_lines = remaining[:new_lua + 1] + hot_lines + remaining[new_lua + 1:]

    if not args.no_backup and not os.path.exists(bak):
        shutil.copy2(fprj, bak)
        print("  已备份: %s" % os.path.basename(bak))

    write_text(fprj, "".join(new_lines), enc, bom)

    # 复核
    text2, _, _ = read_text(fprj)
    lines2 = text2.splitlines(keepends=True)
    l2, h2, _ = analyze(lines2, args.pattern)
    l2 = next(i for i, ln in enumerate(lines2)
              if 'Shape="34"' in ln and "app__lua%2F" in ln)
    ok = all(i > l2 for i in h2)
    print("  [完成] 当前顺序: ... Lua(第 %d 行) -> %d 个热区(第 %d~%d 行)" %
          (l2 + 1, len(h2), h2[0] + 1, h2[-1] + 1))
    print("  复核: %s" % ("通过" if ok else "失败"))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_lua_layer.py — 给已有的 .fprj 工程注入一个 Lua 图层（最顶图层）。

典型用途：在资源型表盘上叠加 NineBomb/SmoothlyLight-9 的缓慢亮屏，
而不必重画任何原有控件。

用法
----
    python add_lua_layer.py <工程目录> --lua /path/to/SmoothlyLight.lua
    python add_lua_layer.py <某个.fprj> --lua /path/to/SmoothlyLight.lua
    python add_lua_layer.py <工程目录> --lua <file> --screen 336x480 --check

注意：本仓库不分发 Lua 脚本（AGPL-3.0 衍生作品），请用 --lua 指定你从
https://github.com/NineBomb/SmoothlyLight-9 获取并按本技能 references/ 修好的脚本。

原理（两套路线为什么不冲突）
----------------------------
EasyFace / Mi-Create 的「基础容器」控件 Shape=34，Name 写成
"app__lua%2F<app/_lua/ 下的相对路径>"。编译器把该 .lua 打包进表盘二进制的
Block 5 (App Data)，并在 Block 0 (Elements) 生成一条容器元素。Lua 只是画面
最上层的一个图层，下层原有的图片 / 数字 / 图片列表 / 跳转热区全部照常编译。
所以「资源型表盘」和「Lua 表盘」是同一容器的不同块，并非二选一。

参考出处见仓库 references/05-sources.md。
"""

import argparse
import os
import re
import shutil
import sys

LUA_SHAPE = "34"
LUA_NAME_PREFIX = "app__lua%2F"
LAYER_RE = re.compile(r'<Widget\b[^>]*Shape="34"[^>]*Name="app__lua%2F[^"]*"[^>]*/>')


def read_text(path):
    """兼容 utf-8 / utf-8 BOM / utf-16 / gbk，并记录编码以便原样写回。"""
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


def safe_lua_name(src_path):
    """EasyFace 要求 Lua 文件名用 ASCII 字母/数字/下划线，中文或空格会导致编译失败。"""
    base = os.path.basename(src_path)
    stem, ext = os.path.splitext(base)
    if ext.lower() != ".lua":
        ext = ".lua"
    stem = "".join(c if (c.isascii() and (c.isalnum() or c in "_-")) else "_"
                   for c in stem)
    if not stem or not stem[0].isalpha():
        stem = "watchface_" + (stem or "layer")
    return stem + ext


def find_main_fprj(target):
    """定位主表盘 .fprj；跳过 AOD/ 子目录，只取表层文件。"""
    if os.path.isfile(target) and target.lower().endswith(".fprj"):
        return target
    if not os.path.isdir(target):
        raise SystemExit("[错误] 找不到工程目录: %s" % target)
    candidates = [os.path.join(target, n) for n in sorted(os.listdir(target))
                  if n.lower().endswith(".fprj")
                  and os.path.isfile(os.path.join(target, n))]
    if not candidates:
        raise SystemExit("[错误] %s 下没有 .fprj 文件" % target)
    for c in candidates:
        if "aod" not in os.path.basename(c).lower():
            return c
    return candidates[0]


def main():
    ap = argparse.ArgumentParser(
        description="给 .fprj 注入 Lua 图层（最顶图层），用于缓慢亮屏等效果")
    ap.add_argument("target", help="工程目录，或直接指定 .fprj 文件")
    ap.add_argument("--lua", required=True,
                    help="Lua 源文件路径（本仓库不分发，请从 NineBomb/SmoothlyLight-9 获取）")
    ap.add_argument("--screen", default="336x480",
                    help="画布尺寸，默认 336x480（小米手环 9 Pro）；8 Pro 亦为 336x480")
    ap.add_argument("--alpha", default="0",
                    help="容器 Alpha，默认 0（对齐社区实证工程）")
    ap.add_argument("--no-backup", action="store_true", help="不生成 .bak 备份")
    ap.add_argument("--check", action="store_true", help="只预览将注入的容器，不写文件")
    args = ap.parse_args()

    m = re.fullmatch(r"(\d+)x(\d+)", args.screen.strip().lower())
    if not m:
        raise SystemExit("[错误] --screen 格式应为 宽x高，例如 336x480")
    w, h = int(m.group(1)), int(m.group(2))

    lua_src = os.path.abspath(args.lua)
    if not os.path.isfile(lua_src):
        raise SystemExit("[错误] 找不到 Lua 文件: %s" % lua_src)

    fprj = find_main_fprj(args.target)
    proj_dir = os.path.dirname(os.path.abspath(fprj))
    lua_name = safe_lua_name(lua_src)
    encoded = LUA_NAME_PREFIX + "%2F".join(lua_name.split("/"))
    layer = (f'    <Widget Shape="{LUA_SHAPE}" Name="{encoded}" '
             f'X="0" Y="0" Width="{w}" Height="{h}" '
             f'Alpha="{args.alpha}" Visible_Src="0" />')

    if args.check:
        print("将注入:", layer.strip())
        print("脚本将被复制到:", os.path.join(proj_dir, "app", "_lua", lua_name))
        return

    # 1) 把 Lua 放到工程内 app/_lua/ 下
    lua_dir = os.path.join(proj_dir, "app", "_lua")
    os.makedirs(lua_dir, exist_ok=True)
    shutil.copy2(lua_src, os.path.join(lua_dir, lua_name))

    # 2) 生成容器控件，插到主 Screen 内
    text, enc, bom = read_text(fprj)
    close = "</Screen>"
    if close not in text:
        raise SystemExit("[错误] %s 里找不到 </Screen>" % fprj)
    newline = "\r\n" if "\r\n" in text else "\n"

    # 重注入（换 Lua 脚本）时必须保住已修好的「热区在容器之上」层序，
    # 否则容器又被追加到末尾，热区重新被压到下方、跳转再次失效。
    old_lines = text.splitlines(keepends=True)
    old_lua = next((i for i, ln in enumerate(old_lines) if LAYER_RE.search(ln)), None)
    keep_hot_above = old_lua is not None and any(
        'Name="btn_[' in ln for ln in old_lines[old_lua + 1:])

    # 幂等：已存在同类 Lua 图层则先移除，避免重复注入
    text = LAYER_RE.sub("", text)
    lines = []
    for ln in text.splitlines(keepends=True):
        if not ln.strip() and lines and not lines[-1].strip():
            continue  # 压缩移除容器后留下的多余空行
        lines.append(ln)

    if keep_hot_above:
        pos = next(i for i, ln in enumerate(lines)
                   if re.match(r"^\s*<Widget\b", ln) and 'Name="btn_[' in ln)
    else:
        pos = next(i for i, ln in enumerate(lines) if close in ln)
    lines.insert(pos, layer + newline)
    new_text = "".join(lines)

    if not args.no_backup:
        bak = fprj + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(fprj, bak)
    write_text(fprj, new_text, enc, bom)

    print("[完成] Lua 图层已注入: %s" % fprj)
    print("  容器: %s" % layer.strip())
    print("  位置: " + ("热区在其上，已保持点击修复层序" if keep_hot_above
                      else "最后一个 Widget = 最顶图层"))
    print("  脚本: app/_lua/%s  <- %s" % (lua_name, lua_src))
    print("  编码: %s  BOM=%s" % (enc, bom))
    print()
    print("下一步：python fix_click_after_lua.py <工程目录> 把 btn_* 热区移到容器之上，")
    print("        否则原作者的 Shape=34 全屏容器会吞掉所有点击（SmoothlyLight README 亦自述）。")


if __name__ == "__main__":
    main()

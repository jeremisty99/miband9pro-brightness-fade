# scripts · 亮屏链路工具

4 个 Python 脚本，只覆盖**渐亮实施 + 配套修复 + 自检**这一条链路。

> 本仓库**不含**解包 / `bin`→`.fprj` 转换 / 预览渲染工具。前置条件是一份已经能被
> EasyFace 或 Mi-Create 编译的 `.fprj` 工程，以及从
> [NineBomb/SmoothlyLight-9](https://github.com/NineBomb/SmoothlyLight-9) 获取并按
> [references/03-fixes.md](../references/03-fixes.md) 修好的 Lua 脚本（AGPL-3.0）。

依赖：Python 3.8+；`dim_aod_assets.py` / `verify_project.py` 需要 `Pillow`（`pip install pillow`）。

| 脚本 | 作用 | 何时用 |
| --- | --- | --- |
| `add_lua_layer.py` | 把 Lua 以 `Shape="34"` 容器注入 `.fprj`，复制到 `app/_lua/`，保持编码/BOM/属性顺序，幂等 | 第一次叠加渐亮 |
| `fix_click_after_lua.py` | 把 `btn_*` 热区行级搬移到 Lua 容器之上，恢复跳转 | 注入 Lua 之后**必须**执行 |
| `dim_aod_assets.py` | 把 AOD 素材整体压暗并同步 `START_OPA`，消除亮度下凹 | 核心优化步骤 |
| `verify_project.py` | 编译前静态自检：空 Bitmap 项、缺图、层序、点击修复三要素、亮度配对、PNG 完整性 | 每次编译前 |

## 标准流程

```bash
python add_lua_layer.py      <工程> --lua /path/to/SmoothlyLight.lua
python fix_click_after_lua.py <工程>
python dim_aod_assets.py     <工程> --factor 0.62 --sync
python verify_project.py     <工程>
```

然后用 EasyFace / Mi-Create **关闭重开工程**，把 **AOD 与主表盘两个主题都重新编译**。

## 各脚本要点

### add_lua_layer.py

- `--lua` 必填（本仓库不分发 AGPL Lua）。
- `--screen` 默认 `336x480`；`--alpha` 默认 `0`。
- `--check` 只预览将写入的容器行。
- 换 Lua 重注入时，会**自动保持**「热区在容器之上」的层序，不会把点击修复弄丢。
- 自动备份原 `.fprj` 为 `.bak`（`--no-backup` 可关）。

### fix_click_after_lua.py

- 只搬运单行 `<Widget .../>`；跨行写法会明确报错而不是悄悄改坏。
- 不重序列化 XML，原编码 / BOM / 缩进 / 属性顺序逐字节保持。
- 幂等；`--check` 只报告（层序错误时退出码 2）；`--restore` 从 `.bak` 还原。
- `--pattern` 可改热区匹配规则（默认 `^btn_\[`）。

> 单独跑这个工具不够：Lua 侧还必须有 `clear_flag(CLICKABLE)`、
> `add_flag(EVENT_BUBBLE)` 和结束后的 `park_veil()`。两边同时做才是真机验证过的组合。

### dim_aod_assets.py

- 默认 `factor=0.62`，配对 `START_OPA = 255 × (1 − factor) = 97`。
- **幂等**：首次运行自动在工程内建立 `AOD/images_original/` 原始副本，
  之后每次都从它重新生成，不会越压越暗；也可用 `--source <目录>` 指向自己的
  原始素材（`--prefix` 控制文件名前缀，默认 `aod_`）。
- `--sync` 同步 `app/_lua/*.lua` 里的 `START_OPA`；`--factor 1.0 --sync` 完整还原。
- `--check` 只报告；`--compare` / `--compare-only` 生成亮度衔接曲线图。
- 只改 RGB，**alpha 与尺寸保持不变**；`--factor 1.0` 可逐像素还原。

> 改了 AOD 素材必须两个主题都重编译，否则压暗不会进入 `.face`。

### verify_project.py

```bash
python verify_project.py <工程>                          # 工程内有 AOD/images_original/ 时
python verify_project.py <工程> --source <原始素材目录>   # 原始素材在外部时（默认前缀 aod_）
python verify_project.py <工程> --strict                 # 有警告也返回非 0
```

输出 7 组检查结果，有问题时退出码非 0（`--strict` 下警告也算失败）：

1. 工程内文件名/目录名是否全 ASCII
2–3. 两个 `.fprj` 的 XML 解析、`Bitmap`/`BitmapList` 空项与缺图
4. `btn_*` 热区是否全部排在 Lua 容器之上
5. Lua 是否含点击修复三要素，并报告 `START_OPA/FRAMES/MIN_OPA/PERIOD`
6. 从 `AOD/images_original/`（或 `--source`）反推压暗系数，检查与 `START_OPA` 是否配对。
   AOD 主题没有 Lua 容器属正常，不会误报；`string.*` 检测会剥离注释，只看真实代码
7. 全部 PNG 是否可完整解码

---

返回 [README](../README.md) · 原理见 [02 · 渐亮脚本原理](../references/02-fade-principle.md)

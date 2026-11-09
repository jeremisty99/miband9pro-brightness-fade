# 05 · 致谢与出处

> 本项目的所有思路都建立在社区开源与教程之上。这一页列出**全部**参考脚本、文档、教程的原作者、链接、许可证与具体用途。许可证信息于 2026-11-09 通过 GitHub API 核实。

## A. 核心脚本：渐亮效果的来源

### NineBomb · [SmoothlyLight-9](https://github.com/NineBomb/SmoothlyLight-9)

| 项 | 内容 |
| --- | --- |
| 作者 | **NineBomb** |
| 许可证 | **AGPL-3.0** |
| 关键文件 | `SmoothlyLight.lua`（789 字节）、`README.md` |
| 仓库简介 | *Slowly light lua for Mi Band9* |

**本项目从它得到什么**：

- 整个缓慢亮屏的实现原型：全屏黑色 `lvgl.Object` + `lvgl.Timer` 每 17ms 递减 `bg_opa` + `ScreenStateChangedCB` 触发。
- README 的两条关键说明：
  - 「请把 lua 图层放在最顶层，并 lua 文件置于文件夹内」→ 确立了 `Shape=34` 容器放 `<Screen>` 末尾的做法；
  - 「**2.0 版本暂时不支持下属表盘的点击事件**，且未发布 1.0 版本」→ 这就是本项目实测「点击跳转全部失效」的官方印证，也是修复三的出发点。
- README 注明适用小米手环 8 / 9 / 8 Pro / 9 Pro。

> 本项目引用的原版代码片段见 [02 · 渐亮脚本原理](02-fade-principle.md)。基于该脚本修改得到的 Lua 文件属于 **AGPL-3.0 衍生作品**，见文末合规说明。

## B. 状态字符串与交互修复的实证来源

### NineBomb · [EXMars](https://github.com/NineBomb/EXMars)

| 项 | 内容 |
| --- | --- |
| 作者 | **NineBomb** |
| 许可证 | **AGPL-3.0**（README 明确「基于 AGPL3.0 协议开源」「请严格遵守 AGPL3.0 协议进行二次开发」） |
| 关键文件 | `resources/_lua/SmoothlyLighttop/SmoothlyLight.lua`、`resources/_lua/SmoothlyLightmiddle/SmoothlyLight.lua`、`resources/_lua/mars3/smash.lua` |

**用途**：状态字符串没有官方文档，这三个文件是社区里最直接的实证：

- `SmoothlyLighttop`：`if pre == "OFF" and now == "ON"` → `OFF` 是屏幕全黑；
- `SmoothlyLightmiddle`：`if pre == "IDLE" and now == "ON"`，并且用了 `s:add_flag(lvgl.FLAG.EVENT_BUBBLE)` → `IDLE` 是息屏显示，也印证了事件冒泡做法；
- `mars3/smash.lua`：`if now == "IDLE" then ...` 暂停动画 → 说明 IDLE 时屏幕仍亮着。

本项目 v4 曾照此做状态分流，结论是「会砍掉动画」，复盘见 [03](03-fixes.md)。

### sigmayl · [MiBandBLE](https://github.com/sigmayl/MiBandBLE)

- 作者 **sigmayl**；关键文件 `tests/display.lua`。
- 生命周期测试直接以 `('ON','OFF')` → `('OFF','AOD')` → `('AOD','ON')` 驱动 `ScreenStateChangedCB`，交叉验证了 `AOD` 是独立状态。

### LeeKLong · [Lua_MiBand9Pro](https://github.com/LeeKLong/Lua_MiBand9Pro)

| 项 | 内容 |
| --- | --- |
| 作者 | **LeeKLong** |
| 许可证 | **AGPL-3.0** |
| 关键文件 | `src/fade-bright/main.lua` |
| 仓库简介 | 小米手环 9 Pro Lua 表盘插件示例（含 G-Sensor、渐变壁纸、待机动画、亮屏渐显） |

**用途**：`fade-bright` 模块给出了三个可直接复用的成熟做法 ——

1. `clear_flag(lvgl.FLAG.CLICKABLE)` + `add_flag(lvgl.FLAG.EVENT_BUBBLE)` 防止遮罩干扰点击（本项目修复三的 Lua 侧）；
2. `lvgl.Anim` + `path = "ease_out"` 缓动渐隐；
3. 熄屏时 `ui.mask:set({bg_opa = 255})` **预置遮罩**；还用 `activity.isShown()` 排除表盘编辑态。

它的 README 还给出了 [EasyFace](https://github.com/m0tral/EasyFace) 与 [LVGL 在线图片转换工具](https://lvgl.io/tools/imageconverter) 的链接。

### sf-yuzifu · [Monika](https://github.com/sf-yuzifu/Monika)

- 作者 **sf-yuzifu**，许可证 **GPL-3.0**（含中文补充条款）。
- 关键文件 `src/runtime.lua`（亮熄屏生命周期与事件调度）。
- 用于理解 9 Pro（336×480）多设备 Lua 工程的组织方式；README 也指向 `m0tral/EasyFace`。

## C. 官方文档与教程

| 名称 | 作者 / 维护者 | 链接 | 本项目用途 |
| --- | --- | --- | --- |
| **VelaOS 应用开发文档** | **FangAiden** | [FangAiden/Vela_Application_Documentation](https://github.com/FangAiden/Vela_Application_Documentation) | Lua / LVGL API 的权威速查 |
| ↳ `docs-lua/screen/overview.md` | 同上 | 同上 | 明确写「设备验证结果：空表，无可用方法」→ 证实 **`screen` 模块没有亮度接口** |
| ↳ `docs-lua/lvgl/modules/disp.md` | 同上 | 同上 | `lvgl.disp` 只有 `set_bg_opa` / `set_bg_color` / `load_scr` 等 → 证实**没有背光 API**；`load_scr(anim="fade_on")` 的适用边界 |
| ↳ `docs-lua/lvgl/globals/functions/Timer.md` / `Anim.md` | 同上 | 同上 | 定时器与动画接口 |
| **LuaDevTemplate** | **FangAiden** | [FangAiden/LuaDevTemplate](https://github.com/FangAiden/LuaDevTemplate) | 理解**纯 Lua 表盘**（`app/lua/main.lua`）与本项目 `app/_lua/` 图层的区别；README 说明 8 Pro / 9 Pro 只支持 lvgl v8 |
| **VelaDocs** | **CheongSzesuen** | [CheongSzesuen/VelaDocs](https://github.com/CheongSzesuen/VelaDocs) | Vela QuickApp 文档的爬取源（Vela 文档 README 中致谢），GPL-3.0 |
| **米环9缓亮教程** | **Aiyong** | [米坛社区 BandBBS · threads/23158](https://www.bandbbs.cn/threads/23158)（2025-11-22） | 中文实操教程：在 EasyFace 工程建 `app/_lua` 文件夹、建覆盖全屏的基础容器、容器名写 `app__lua%2F<lua文件名>`、放最顶图层、改代码第 12 行调速度。是本项目 `Shape=34` 注入写法的直接来源，教程本身也指向 NineBomb 的脚本 |
| **Mi-Create 官方文档** | **ooflet** | [ooflet.github.io/docs](https://ooflet.github.io/docs) | `.fprj` 工程规范 |

## D. 工具链

| 工具 | 作者 / 组织 | 链接 | 许可证 | 说明 |
| --- | --- | --- | --- | --- |
| **EasyFace** | **m0tral** | [m0tral/EasyFace](https://github.com/m0tral/EasyFace) | 见仓库 | 主流表盘编辑器，本项目的 Gen2 编译器（V4.23）来自它；768 stars |
| **Mi-Create** | **ooflet** | [ooflet/Mi-Create](https://github.com/ooflet/Mi-Create) | **GPL-3.0** | `.fprj` 编辑器，支持 AOD 快速创建与实时预览；README 注明「编译器由第三方提供且不开源」 |
| **LVGL 在线图片转换工具** | LVGL 官方 | [lvgl.io/tools/imageconverter](https://lvgl.io/tools/imageconverter) | — | PNG → `.bin` 资源转换（Lua 表盘路线用） |

> 补充：本地拿到的 Mi-Create 源码副本来自 GitCode 镜像 `https://gitcode.com/gh_mirrors/mi/Mi-Create.git`，上游仍是 `ooflet/Mi-Create`。EasyFace Gen2 的 `Compiler.exe` 内嵌 Magick.NET，项目里的 `images\` 报错即来自它。

## E. 工程范例与背景资料

> 以下仅为**出处标注**：解包 / 容器逆向属于另一条工作流，本仓库既不展开也不提供相关工具。

| 资料 | 作者 | 链接 | 用途 |
| --- | --- | --- | --- |
| 表盘 bin 容器格式笔记（gist） | **basenc** | `https://gist.github.com/basenc/c0356f47c851f821f437375de45cfa70` | 早期调研容器结构时记录；本次复核时该链接超时，请以作者 gist 主页为准 |
| `Xiaomi-Smart-Band-9Pro-Lua-Watchface-CPUload` | **Ziyimiao5054** | [GitHub](https://github.com/Ziyimiao5054/Xiaomi-Smart-Band-9Pro-Lua-Watchface-CPUload) | GPL-3.0；其 `monika.fprj` 提供了 `Shape="34"` Lua 容器的真实写法范例（`app__lua%2Fmonika%2Fmonika.lua`），是本项目注入写法的交叉验证 |

## F. 合规说明

| 内容 | 归属 | 许可证 |
| --- | --- | --- |
| 渐亮 Lua 原脚本 | NineBomb | **AGPL-3.0** |
| EXMars 状态分流脚本 | NineBomb | **AGPL-3.0** |
| `fade-bright` 模块 | LeeKLong | **AGPL-3.0** |
| 本仓库的 Markdown 文档、SVG 图解、Python 工具 | 本项目原创 | **MIT**（见 [LICENSE](../LICENSE)） |

- 本仓库**不分发完整 Lua 文件**，仅引用少量片段用于教学讲解，片段版权归各自作者。
- 任何基于 `SmoothlyLight.lua` 修改得到的 Lua 脚本都是 **AGPL-3.0 衍生作品**，须继续遵循该协议，不得改用 MIT 等宽松许可证；需要完整脚本请到 [NineBomb/SmoothlyLight-9](https://github.com/NineBomb/SmoothlyLight-9) 获取。
- 引用、转载本仓库文档时，请保留本节出处列表。

---

如果这份笔记帮到了你，请给上述原项目点 star —— 没有他们的开源与教程，就没有这套方案。

上一篇：[04 · 参数调优与排错](04-tuning.md) · 下一篇：[06 · 表盘生态速查](06-ecosystem.md)

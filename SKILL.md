---
name: miband9pro-perfect-brightness-fade
description: 在小米手环 8 Pro / 9 Pro 的资源型 .fprj 表盘上实现无亮度跳变的缓慢亮屏（渐显），并同时保留原生跳转点击。当任务涉及 AOD 点亮闪黑、先亮后暗的亮度下凹、渐显失效或完全没有动画、叠加 Lua 图层后跳转按钮全部失效、START_OPA 与 AOD 素材亮度配对、FRAMES/MIN_OPA 调参、Shape=34 Lua 容器注入、以及 EasyFace / Mi-Create 编译 .fprj 报错时，应加载本技能。This skill should be used when diagnosing or implementing a smooth wake-up brightness fade on Xiaomi Band Pro watchfaces.
agent_created: true
---

# 小米手环 9 Pro 表盘 · 完美亮度渐显

## 目的

把「资源型 `.fprj` 表盘 + Lua 黑色遮罩」这条路线做到抬腕点亮时亮度单调上升、无黑闪、无下凹，同时不破坏表盘原有的 `btn_*` 跳转热区。技能内含完整的原理讲解、图解、可复用脚本和社区出处。

## 何时使用

- 需要在已有资源型表盘上叠加缓慢亮屏 / 渐显效果。
- 已叠加 Lua 后出现：点击跳转全失效、点亮先闪黑、先闪一下最亮再变暗、短暂突变暗、动画完全消失。
- 需要调整渐显的起点、帧数、收尾阈值，或判断某个参数是否安全。
- 需要排查 EasyFace / Mi-Create 对 `.fprj` 的编译错误。

## 三条不可违背的不变量

处理任何相关任务前先确认这三条，绝大多数返工都源于违反其一：

1. **Lua 只能让画面变暗，不能提亮。** Vela 没有背光 / 亮度调节接口（`screen` 模块经设备验证为空表；`lvgl.disp` 只有 `set_bg_opa` 等背景属性）。所谓「渐亮」是盖一层全屏黑矩形、把 `bg_opa` 逐帧降到 0 的视觉把戏。
2. **点亮的第一帧不是 Lua 画的。** AOD 与主表盘是两套独立主题，引擎先用正常背光重绘 AOD 最后一帧，再切主表盘。Lua 遮罩只作用于主表盘，盖不住那一帧。只要 AOD 素材比主表盘首帧亮，就必然出现「亮 → 暗 → 渐亮」的亮度下凹，调任何 Lua 参数都消不掉。
3. **`START_OPA` 与 AOD 素材亮度系数必须严格配对**：`START_OPA = 255 × (1 − factor)`。默认 `factor = 0.62 ↔ START_OPA = 97`。改任一个都必须同步改另一个，且**两个主题都要重新编译**。

## 工作流程

### 阶段一：判断路线

读 `references/06-ecosystem.md`，确认目标是「保留资源型控件」还是「纯 Lua 表盘」。前者用 `.fprj` + `Shape="34"` Lua 容器（本技能覆盖）；后者用 `FangAiden/LuaDevTemplate`，不在本技能范围。

### 阶段二：理解原理

按需加载：

- `references/01-lua-basics.md` —— Lua 在表盘中的运行机制、状态字符串、API 边界。
- `references/02-fade-principle.md` —— 原版渐亮脚本逐行解读、黑遮罩原理、点亮时序。
- `assets/diagrams/` 下 5 张 SVG 图解，用于讲解与答疑。

### 阶段三：实施

1. 用 `scripts/add_lua_layer.py` 把 Lua 图层注入 `.fprj`（幂等，保持编码/BOM/属性顺序）。
2. 用 `scripts/fix_click_after_lua.py` 把 `btn_*` 热区移到 Lua 容器之上；同时确认 Lua 侧有 `clear_flag(CLICKABLE)`、`add_flag(EVENT_BUBBLE)` 与结束后的 `park_veil()`。**两边必须同时做**，详见 `references/03-fixes.md`。
3. 用 `scripts/dim_aod_assets.py <工程> --factor 0.62 --sync` 压暗 AOD 素材并同步 `START_OPA`。
4. 用 EasyFace / Mi-Create 重新编译 **AOD 与主表盘两个主题**；改动 Lua 后必须关闭并重开工程再编译，避免 GUI 内存里的旧内容回写覆盖。
5. 用 `scripts/verify_project.py <工程>` 做静态自检。

### 阶段四：调优与排错

- `references/04-tuning.md` —— 参数档位表、配对公式、症状→原因→处理清单。
- `references/03-fixes.md` —— 完整版本演进与失败方案复盘（v4 砍掉动画、v5 让动画看不见），避免重复踩坑。
- 只剩「短暂突变暗」时，优先检查 `MIN_OPA`（收尾 `7→0` 跳变）和 `FRAMES`（台阶大小），不要再去动 `START_OPA`。

## 范围说明

本技能只覆盖**亮屏逻辑、优化点与配套修复**。解包 / `bin`→`.fprj` 转换 / 预览渲染工具属于另一条工作流，不在本仓库内；前置是一份已经能被 EasyFace 或 Mi-Create 编译的 `.fprj` 工程。

## 资源索引

| 路径 | 内容 |
| --- | --- |
| `references/01-lua-basics.md` | Lua 与表盘运行原理、API 边界、状态字符串 |
| `references/02-fade-principle.md` | 渐亮脚本原理与原版逐行解读 |
| `references/03-fixes.md` | 四类修复的完整复盘与失败方案 |
| `references/04-tuning.md` | 参数、调优档位、排错清单 |
| `references/05-sources.md` | 原作者、教程出处与许可证合规说明 |
| `references/06-ecosystem.md` | 亮屏所需的最小背景：分层、路线、AOD 独立主题、重编译规则 |
| `assets/diagrams/*.svg` | 5 张原理图解，可直接引用 |
| `scripts/*.py` | 亮屏链路 4 个工具：Lua 注入、层序修复、AOD 压暗、工程自检 |

## 引用与许可证提醒

讲解或二次分发时，必须标注原脚本作者 **NineBomb**（`SmoothlyLight-9`，AGPL-3.0）及 `references/05-sources.md` 列出的其他出处。基于该脚本修改得到的 Lua 属于 AGPL-3.0 衍生作品，不可擅自改为宽松许可证；本仓库的原创文档、图解与 Python 工具使用 MIT。完整 Lua 文件不随本仓库分发，需从原仓库获取。

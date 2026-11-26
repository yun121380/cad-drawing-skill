---
name: cad-drawing
description: 出国标二维工程图（零件图/剖视/尺寸/粗糙度/形位公差/标题栏，出 DWG+PDF）和 SolidWorks 2025 建 3D 零件。做法：SolidWorks 只出投影→导 DWG→AutoCAD 2024 里纯 COM 整理标注，不碰键鼠。用户提到 AutoCAD、CAD 画图、零件图、工程图、图纸、出图、SolidWorks、SW 建模、三维模型、毕设图纸、装配图、标准件时使用。
---

# 国标工程图：SolidWorks 投影 + AutoCAD 整理

> 许可：CC BY-NC-SA 4.0，**禁止商业化使用**。作者 yun121380，https://github.com/yun121380/cad-drawing-skill

目录 `$K` = 本 skill 的安装目录（如 `%USERPROFILE%\.claude\skills\cad-drawing`，bash 里写 `~/.claude/skills/cad-drawing`）。范例脚本按相对路径找 `scripts/`，模型和输出放在脚本旁边的 `models/`、`out/`（没有就先建）。

```
cad-drawing/
├── SKILL.md
├── scripts/
│   ├── sw_views.py     SW 出视图（第 1 步）
│   ├── sw2acad.py      AutoCAD COM 整理标注（第 2 步）
│   ├── acad_common.py  AutoCAD 公共部分：COM 重试、图层/图幅、标注样式、PDF 打印配置
│   ├── sw_part.py      SW 建模（COM 直接调用）
│   ├── sw_std.py       标准件：Toolbox GB 基础零件生成指定规格 + 放进装配（§3.1）
│   ├── toolbox_db.py   直接读 Toolbox 尺寸库 swbrowser.sldedb（SQLite），sw_std.make_any 用它生成任意 GB 件
│   ├── gbtol.py        GB/T 1800 公差查表（k6/H7/N9… → 极限偏差）、GB/T 1095 键槽、GB/T 1804 一般公差（§2.6）
│   ├── gb_hatch.py     装配图剖面线（GB/T 4457.5）：相邻零件错开、按材料换剖面符号、找窄剖面（挂在 Sheet 上，§2.4）
│   ├── conv.py         规定画法：外螺纹、花键、弹簧、锥齿轮、蜗杆蜗轮（挂在 Sheet 上，§2.4）
│   ├── placer.py       粗糙度/形位公差/基准/零件序号自动放置（挂在 Sheet 上，§2.7）
│   ├── audit.py        尺寸完整性审查：拿模型特征核对“标全没有、有没有封闭链”（§2.8）
│   ├── sw_mem.py       SolidWorks 内存守护：超过上限自动退出重开（§4.3）
│   ├── env_check.py    换电脑/重装后先跑：逐项检查软件路径、模板、Toolbox、字体、Python 包
│   ├── config.json     标题栏默认值 + 软件路径 + SW 内存上限 —— 换环境只改这里
│   └── com_filter.py   COM 消息过滤器（忙时自动重试）
└── examples/
    ├── reducer/  build_parts → build_asm → views → reducer_gb（装配图，模型坐标 + 自动序号）；
    │             零件图/ 输出轴、输出轴_auto（自动放符号 + 审查）、大齿轮、箱座、箱盖   成套图纸（§2.5）
    ├── conv_demo.py                      规定画法样张（外螺纹、花键、弹簧、锥齿轮、蜗杆蜗轮），空白图上画
    ├── std_demo.py                       新标准件生成测试（螺钉、弹簧垫圈、圆锥滚子轴承、O 形圈、毡圈）
    ├── hub_flange.py                     回转体，A3 1:1，单文件
    ├── plate_views.py + side_plate.py    板件，A3 1:2
    ├── bracket_views.py + bracket_seat.py 铸件支架，A3 1:1
    ├── asm_views.py + wheel_assembly.py  装配图，A3 1:2
    ├── bush_half_views.py + bush_half.py 半剖 + 局部剖，A3 1:1（含建模）
    ├── zcz/  params.py + build.py + views.py + drawing.py   复杂铸件轴承座，参数化全流程（最全，先看它）
    └── rot_oblique/  build.py + views.py + drawing.py       旋转剖（拼接法）+ 局部斜视图转正，A3 1:1
                      build_solid / views_solid / drawing_solid  实心轮毂的旋转剖（剖面线按轴线裁）
```

## 0. 环境（2026-11-07 实测）

**换电脑 / 重装软件后先跑 `python $K/scripts/env_check.py`**：逐项查 AutoCAD、SW、国标模板、Toolbox 基础零件、gbenor 字体、
PDF 打印机、Python 包、公差表自测，缺什么打印改 config.json 的哪一项（`acad_exe` / `sw_exe` / `sw_templates` / `toolbox_gb`）。
脚本里不再写死路径，都从 config.json 读。**这套流程只在作者的一台电脑上实测过**——别的版本（AutoCAD 2018~2023、SW 2022~2024）
COM 接口大体相同但没验证，第一次用先跑 env_check 和 examples/conv_demo.py。

- **AutoCAD 2024**：`C:\Program Files\Autodesk\AutoCAD 2024\acad.exe`，COM 名 `AutoCAD.Application(.24)`，有 `gbenor.shx` / `gbcbig.shx`。
- **SolidWorks 2025**：`C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe`（装在别处改 config.json），COM 名 `SldWorks.Application`（rev 33）。国标模板在 `C:\ProgramData\SolidWorks\SOLIDWORKS 2025\templates\gb_*.prtdot / drwdot`。基准面名称是中文（前视基准面…）。
- **Python 3.12** + pywin32 + PyMuPDF（fitz）+ ezdxf + shapely装在**用户目录 site-packages**。**不要用 `python -I`**，否则 import 失败。
- 写 JSON 时 Windows 下 `open(..., "w")` 默认是 GBK，要写 `encoding="utf-8"`。
- 截屏或 numpy 报 *OpenBLAS Memory allocation failed* 时，设环境变量 `OPENBLAS_NUM_THREADS=1`。

## 1. 选型

| 需求 | 做法 |
|---|---|
| 2D 零件图、装配图 | **sw_views + sw2acad**。SW 只出投影，AutoCAD 里纯 COM 整理标注。见 §2 |
| 3D 零件、装配、干涉检查 | **SolidWorks MCP**（`solidworks_*` 工具，需另装），或 `sw_part.py`。见 §3 |
| SolidWorks 自动标尺寸（AutoDimension）、SW 工程图直接交 | **不用**。用户看过说"好乱"：尺寸引线跑出图框、轴测图失控、标题栏空白。SW 只用来出视图 |

这样做的好处：投影、剖切面后的可见线（孔口端面线、倒角线）、剖面线、剖切符号、中心符号都由 SW 计算，不会漏线；不受输入法和焦点干扰，用户可以照常用电脑；改尺寸只需改脚本里的一行重跑，约 1 分钟。

## 2. 出图：SW 投影 → DWG → AutoCAD 整理

### 2.1 找范例

四类图都已实测出图（2026-11-07）。`*_views.py` 用来出视图，`*.py` 用来整理标注。找最接近的复制一份改：

| 范例 | 类型 | 演示的要点 |
|---|---|---|
| `hub_flange.py`（单文件，SW 和 AutoCAD 都在里面） | 回转体零件，A3 1:1 | A-A 全剖 + 圆视图，键槽、均布孔、R 圆角，粗糙度、基准、平行度；用 SW 模板图框（`own_frame=False` 的老写法） |
| `plate_views.py` + `side_plate.py` | 板件，A3 **1:2** | 主视图 + 俯视图，链式和基准尺寸、`4×100(=400)`、长槽、窗口，自画图框和标题栏 |
| `bracket_views.py` + `bracket_seat.py` | 铸件支架，A3 1:1 | 三视图：主视图是从左视图剖出来的 A-A，左视图带**虚线**；垂直度公差、基准、`move_label` 挪视图名 |
| `asm_views.py` + `wheel_assembly.py` | **装配图**，A3 1:2 | 剖视里的实心件（轴）不画剖面线（`unhatch`），零件序号排成一排，**明细栏**，配合尺寸 `%%C30H7/k6`，安装尺寸 |
| `zcz/`（2026-11-08，**最全，复杂零件先看它**；整个文件夹复制到工作目录再跑：build → views → drawing） | 铸件轴承座，A3 1:1，**参数化** | 所有尺寸在 `params.py`，标注坐标由参数 + `layout.json` 推出（不手抄），实测改 4 个参数重跑三步、零手改出图干净（§2.3）。主视图右半剖 + 安装孔局部剖，左视图 A-A 全剖（省略标注），俯视图（过渡线），**局部放大图 4:1**；螺纹规定画法、锪平孔旁注、极限偏差、半剖直径 `half_dia`、基准 A/B、平行度垂直度、全部表面符号 + GB/T 131-2006 统一要求、**GB/T 10609.1 标准标题栏**、`check()` 自动查压线 |
| `rot_oblique/`（2026-11-08） | 摇臂 + 弯板，A3 1:1 | **旋转剖**（拼接法，斜臂真长 60）+ 折线剖切符号；**局部斜视图**（裁剪 + 波浪线 + 转正 + 旋转符号）；角度尺寸 `AddDimAngular`；`model_to_sheet` 取点 |
| `bush_half_views.py` + `bush_half.py`（2026-11-08） | 凸缘套筒，A3 1:1 | 主视图**右半剖**（`half_section`）+ 左半外形上**局部剖**一个径向孔（`broken_out`，波浪线）；分界线改点画线（`to_center`）；半剖里的对称尺寸只画一半箭头（`DimLine1Suppress`）；均布孔 `4×%%C12` + 分布圆 |

### 2.2 步骤

1. **建零件和装配**：用 SolidWorks MCP 或 `sw_part.py`，存成 `.SLDPRT` 或 `.SLDASM`。
   - 材料要赋上，用中文名（如 `普通碳钢`；写"1045 钢"它不认），标题栏里的重量才对。
   - 装配推荐用基准面配合（`plane` 加 `component`），最稳。距离配合方向反了就传 `flip: true`，或者事后改 `FlipDimension`。
   - 装完一定要跑一次 `check_interference`。
2. **出视图**（`scripts/sw_views.py`）：
   - `new_drawing(sw, "A3", scale=(1,2))`：用国标模板，第一角画法，自动加中心线和中心符号。
   - `model_view(drw, part, "*前视", (x, y))`：可选视图 `*前视 *后视 *左视 *右视 *上视 *下视 *等轴测`；位置是图纸 mm。
   - `section(drw, 父视图, p1, p2, at, surface_only=False, aligned=True)`：剖切线 p1/p2 用父视图的**视图坐标**（原点 = 视图中心 = 零件外框中心，单位模型 mm），线必须**贯穿整个零件**。**会自动调点序，让剖切箭头指向 at 那一侧**（SW 的箭头总在 p1→p2 走向的右侧；箭头指错边时视图会上下/左右翻转——以前"从俯视图往上剖主视图倒过来"就是这个原因，2026-11-08 查清并修好）。`surface_only=True` 只画剖面 = **移出断面图**；`aligned=False` 不对齐、可以随便放。移出断面放在剖切线**延长线上**时 at 正好在线上、分不出左右，用 `look=(x,y)` 指定箭头朝哪边（范例 `examples/reducer/零件图/输出轴_views.py`）；这时父视图框要在剖切符号那一侧多留 ~16 mm，否则粗短画和箭头被当模板删掉。
   - `step_section(drw, 父视图, [折线各点], at)`：**阶梯剖**，剖切段和转折段交替、互相垂直；剖视图要放在剖切段的**垂直方向**上（剖切段水平就放上/下）。
   - **旋转剖（两段相交、夹角不是 90°）SW 的 API 出不了国标的**：两段相交的剖切线（选项 0）SW 给的是"投影的阶梯剖"，倾斜那段被投影缩短，不是转到投影面上的真长（实测摇臂斜臂孔心距 52，真长 60；`IsAligned` 返回 False）。**用拼接法（2026-11-08 实测成功，范例 `examples/rot_oblique/`）**：
     1. S1：沿不转的那段剖切面做普通全剖（`section`），放在正常位置；
     2. 另建一个同方向的父视图放在**图纸外**（如 x=560），沿倾斜那段剖切面再做一个全剖 S2（`aligned=False`，也放图纸外）；
     3. 用 `model_to_sheet` 算三对对应点：S2 里的 回转轴下端/上端/斜臂上一点 → S1 里 把这些点绕回转轴转到投影面后的位置，写进 layout.json；
     4. AutoCAD 里 `s.splice_aligned(...)`：S1 只留不转的那半，S2 斜臂那半按三对点的仿射变换搬过去（剖面线方向/间距自动改成和 S1 一致，轴线上的接缝线删掉），S2 剩下的删掉；
     5. 俯视图上删掉 S1 的直剖切线，用 `s.cut_path([端点1, 回转中心, 端点2])` 画折线剖切线（细点画线 + 转折处粗短画），`s.cut_end(...)` 画两端的粗短画、箭头、字母。
     **实心轮毂（中心没孔）也行**（2026-11-08，`examples/rot_oblique/*_solid.py`）：剖面线跨过轴线时 `splice_aligned` 自动调 `clip_hatch` 按轴线裁成一半（边界从同名 DXF 读、shapely 求交、重建剖面线，图案/比例/角度不变），两半拼上后剖面线照样连续。试过"两个视图各做半边局部剖"：主视图行，**斜视图上 `CreateBreakOutSection` 返回成功却不出剖面线**，放弃。
   - **斜视图** `auxiliary(drw, 父视图, 边的方向, at, "B", pick=(x,y,z))`：按方向（模型坐标）在父视图可见边里挑那条直线边，沿垂直于它的方向投影。默认 `aligned=False`（对齐放置时 SW 只让它待在投射方向上，常常压在主视图上）。
   - **局部视图 / 局部斜视图** `crop(drw, 视图, 闭合点列)`：裁剪视图，边界是细实线样条 = 波浪线。点列用 `sheet_to_view(视图, model_to_sheet(视图, 模型点))` 从模型坐标算，旋转、斜视图都对得上。
   - **转正配置**：`view.Angle = math.radians(-45)` 把斜视图转正；AutoCAD 里 `s.erase_text(r"视图\s*[A-Z].*", regex=True)` 删掉 SW 的"视图 B ⌒45°"，用 `s.rot_label(p, "B", ccw=...)` 写国标的"字母 + 旋转符号"，孔的中心线用 `s.center_cross(c, r)` 摆正。
   - `model_to_sheet(视图, (x,y,z))`：模型点 → 图纸坐标（ModelToViewTransform，行向量乘，实测孔心与 DXF 圆心一致）。尺寸点、引线点都可以这样算，斜视图、旋转视图、剖视图都适用。
   - **`view_affine(视图)` → layout.json，AutoCAD 那边 `M = sw2acad.mapper(aff)`**，之后所有标注点都写 `M(x, y, z)`（模型坐标），不用再推"视图中心 + 模型坐标 − 外框中心"。新写的零件图都按这个来（`examples/reducer/零件图/`）。
   - **肋板纵剖不画剖面线**：建模时把肋板做成**单独实体**（拉伸时 Merge=False），剖视里它就是单独一块剖面线、和主体之间有分界线，AutoCAD 里 `s.unhatch(肋板内一点)` 删掉即可。
   - 装配图上 `broken_out` 局部剖也能用（实测减速器主视图在输入轴端盖处挖开能看到轴承）。
   - `projected(drw, parent, at)`：投影视图。
   - `hidden_lines(view, True)`：显示虚线。要在**建完剖视以后**再开，否则剖视图也会跟着显示虚线。
   - `finish(drw, views)`：让比例生效、去掉切边，并打印各视图外框。
   - `export(drw, base)`：导出 DWG、DXF、PDF。导出时会临时把 SW 的"按图纸尺寸输出"打开，非 1:1 的图也不会被放大。
   - **三视图怎么摆**：主视图要全剖时，先建左视图，再从左视图沿对称面剖出主视图（剖视图放在左视图左边），俯视图用 `*上视` 或 `projected` 建在主视图下方。左视图要全剖时，从主视图竖直剖、放右边（`section` 自动让箭头朝右）。SW 的 `*左视` 就是国标左视图（物体前面在右侧）。
   - **半剖** `half_section(drw, view, depth, side="right", axis=0)`：直接在原视图上做一个矩形局部剖，矩形一边压在对称线上、另三边伸出零件外，剖到对称面。不生成新视图、不出 A-A（国标：剖切面是对称面且按投影关系配置时不标注）。`depth` = 这个视图里零件**最前面**到对称面的距离（零件 Z -50..50、前视图 → 50）。`side`：对称线竖直时 `right`/`left`，水平时 `top`/`bottom`，`axis` 是对称线的视图坐标（零件关于外框中心对称时就是 0）。AutoCAD 里再 `s.to_center(p1, p2)` 把压在对称线上的细实线改成点画线。
   - **局部剖** `broken_out(drw, view, [(x,y),...], depth)`：点列是闭合边界（视图坐标），画成闭合样条，导出后是细实线 SPLINE，就是国标的波浪线，而且只画在实体范围内，边界可以伸出轮廓。`depth` 含义同上，剖到要表达的孔/槽的轴线。一个视图可以做多处，和半剖并存也行。
   - 半剖、局部剖用的都是 SW 的 `CreateBreakOutSection(深度)`，先选中闭合草图再调。SW 自带的 L 形剖切线半剖试过不好用，见 §4.1。
   - **局部放大图** `detail(drw, 父视图, 圆心, 半径, at, scale=(4,1), label="I")`：圆心/半径是父视图的视图坐标。SW 的标签（`SW_NOTE` 块）在 AutoCAD 里会被当模板删掉，自己用 `s._text` 写罗马数字 + 细横线 + 比例。放大图里标尺寸记得 `k=`。
   - 剖切面过对称面、视图按投影关系摆放时，国标允许不标剖切符号和 "A-A"：AutoCAD 里用 `s.erase_in(框)` 删掉。
   - 螺纹孔 SW 不出装饰螺纹线（零件是普通孔建的），在 AutoCAD 里用 `s.thread_hole(...)` / `s.thread_circle(...)` 补（大径细实线、终止线粗实线、圆视图 3/4 细圆）。
3. **取坐标**：复杂零件按 §2.3 参数化，坐标由参数推出；简单零件可以用 `dump_dxf(base + ".DXF", 视图框列表)` 打印每个视图的粗线 x/y 集合、圆和圆弧，抄进脚本开头的注释。
4. **整理和标注**（`scripts/sw2acad.py`）：写法是 `with Sheet(src_dwg, out_dwg, views=视图框, view_scale=2) as s:`。
   - 进入时：删掉 SW 模板自带的图框（`own_frame=True`，默认），图线分到国标图层（可见线、虚线、中心线、剖面线），换字体。
   - 先调 `s.frame()` 和 `s.title_block(...)` 画自己的图框和标题栏；装配图再调 `s.bom(...)`。
   - 退出时：打印每个尺寸的实测值（非 1:1 的图已换算成实际尺寸），然后存 DWG、出 PDF（文件名带时间戳）。
5. **核对**：
   - 把打印出的尺寸实测值和设计值逐个对一遍。
   - 用 fitz 把 PDF 渲染成 PNG：先看全图，再放大到每个视图（`clip=fitz.Rect(x0*s, (297-y1)*s, x1*s, (297-y0)*s)`，`s=72/25.4`）。
   - **先跑 `s.check()`**（放在 `with` 块最后）：自动找出"文字被线/剖面线穿过""几段文字挤在一起"，报坐标，按报告挪 `TextPosition`，直到 0 处。它查不了的再用眼睛看：引线有没有连上；尺寸界线有没有穿过孔；符号尖端是不是落在轮廓线上；尺寸之间是不是太挤（没重叠就不报）。用了参数化 + check 后一般 1~2 轮。
   - **新图的标准写法**（2026-11-08 起）：标注点全用模型坐标（`mapper(view_affine)`）；粗糙度/形位公差/基准/序号用 `auto_*`（§2.7）；
     偏差用 `s.fit`（§2.6）；`with` 块末尾依次 `break_center_under_text()` → `audit_dims(...)`（§2.8）→ `check()`，两个都 0 处再看渲染图。
     照抄 `examples/reducer/零件图/输出轴_auto.py`（回转体）或 `箱盖.py`（铸件）。

运行：

```bash
cd /tmp && OPENBLAS_NUM_THREADS=1 PYTHONIOENCODING=utf-8 timeout 590 python 脚本.py > run.log 2>&1
```

Bash timeout 设 600000。全程不碰键鼠，不用提醒用户别动电脑。

### 2.3 参数化（复杂零件推荐，范例 `examples/zcz/`）

- `params.py` 放全部设计尺寸；`build.py`、`views.py`、`drawing.py` 都 `from params import *`。
- `views.py` 用参数算视图位置（主视图的高度按"俯视图上边 + 中间尺寸行数"推，零件变高不会挤）和剖切线、局部剖边界、放大圆，写 `layout.json`（视图中心、视图框、放大图实际中心——从 DXF 里找半径 = r×倍数的圆弧，**取离放置点最近的那个**，主视图里可能有同半径的圆弧）。
- `drawing.py` 读 `layout.json`，定义映射 `F(X,Y)`、`A(Z,Y)`、`T(X,Z)`、`Dt(Z,Y)`（模型坐标 → 图纸坐标：视图中心 + 模型坐标 − 外框中心），所有尺寸点、引线点都写成 `F(-hb, 0)` 这种形式；重量从 `build.json` 取模型实算值。
- 改参数后依次重跑 `build → views → drawing`，看 `check()` 的报告和渲染图。实测（2026-11-08）底座 160→176、厚 16→18、中心高 70→75、孔距 128→144、凸台顶 122→128，一行不改出图，`check()` 0 处。
- 局限：尺寸放在哪一侧、文字挪多少还是写死的相对偏移；零件形状大变（比如加一个凸台）要改 drawing.py。

### 2.4 `Sheet` 方法（坐标均为图纸 mm）

| 方法 | 说明 |
|---|---|
| `frame()` → 内框 | 国标横放图框，图幅取 `Sheet(sheet="A3")`；顺带删掉内框外残留的 SW 分区字母 |
| `erase_in((x0,y0,x1,y1))` | 删掉完全落在框内的对象（中心线除外）。剖切面是对称面、按投影关系配置时，用它去掉 SW 的剖切符号和 "A-A"（国标可省略标注） |
| `note([箭头尖, 折点], "文字", w=)` | 指引线 + 水平线上的文字（MText），用于倒角 `C1.5`、孔的旁注 `2×%%C13 {\\Fgdt;v}%%C22{\\Fgdt;x}2`（⌴ 锪平/沉孔、↧ 深度、`w` 埋头）。文字太长会自动折成两行 |
| `title_block(图名, 图号, material, scale, weight, designer, date, school, cls)` → 左上角 | 180×40 的学生用标题栏，返回值传给 `bom(origin=)` |
| `bom([(代号, 名称, 数量, 材料, 重量, 备注), ...], origin)` | 明细栏，接在标题栏上方，序号自下而上 1、2、3…，列宽按 GB/T 10609.2 |
| `balloon(零件上一点, 文字位置, n)` | 零件序号：小黑点、细引线、水平短线上写数字。同一视图的序号要排成一排 |
| `unhatch(零件内一点)` | 删掉该零件的剖面线（装配图里轴、键、销、螺栓纵剖时不画剖面线） |
| `hatch_material(零件内一点, material="非金属", scale=1)` | **按材料换剖面符号**（GB/T 4457.5，2026-11-10）：`"金属"` ANSI31、`"非金属"` 交叉网格 ANSI37（橡胶、塑料、尼龙…）、`"涂黑"` SOLID，也可以直接给 AutoCAD 图案名。间距 = 原来的 × scale：图上只有两三毫米宽的窄条给 0.5，不然网格太疏看着像斜线。和 `unhatch` 一样取包含该点的最小一块 |
| `stagger_hatches(details=(), tol=1, same=(), axes=(), sw=None)` | **装配图相邻零件剖面线错开**（GB/T 4457.5，2026-11-10）：SW 导出的剖视里所有零件都是同角度、同间距的 ANSI31，相邻零件分不清。按同名 DXF 算出每块剖面区域，同一零件的几块并成一组：互为镜像的自动认；绕对称轴 `axes=[("x", 竖直轴的 x) 或 ("y", 水平轴的 y)]` 翻过去落在另一块里的；`same=[(点, 点…), …]` 指定的（轴承内外圈、被螺孔切成两块的端盖、两个视图剖到不同部位的同一零件）。区域间距 ≤ tol（图纸 mm）的组算相邻，在 45°/135° × 三种间距（1、0.55、1.6 倍）里取邻居都没用的第一种，所以多数零件还是 SW 原来的 45°。`details=[(c_parent, k, c_det, r_det)]` 是局部放大图（参数同 `SwDxf.detail_hatch_lines`）：放大图里 SW 画的剖面线是线段，换了样式的零件删掉重画，和父视图一致。只改 ANSI31，所以放在 `unhatch`、`hatch_material` 之后。返回 (各样式块数, 放大图删的线段数, 重画的线段数) |
| `narrow_hatches(w=2)` | 图上宽度 ≤ w 的 ANSI31 剖面（向内缩 w/2 就没了的），返回 [(区域内一点, 估算宽度)]。国标只是“允许”涂黑（相邻两块涂黑之间留 ≥0.7 mm），斜线看得清就不必改；要涂黑再 `hatch_material(点, "涂黑")` |
| `move_label("A-A", (x, y))` | 挪动 SW 的视图名，避免和尺寸重叠 |
| `dimlin(p1, p2, loc, ang=0, txt="", k=None)` | 线性尺寸。ang=0 水平、90 竖直。txt 覆盖文字：Φ 写 `%%C`，公差带直接写进去（`%%C30H7`），可以写 `4×100(=400)`；极限偏差叠写 `%%C52H7({\\H0.7x;\\S+0.030^0;})`。**局部放大图里标尺寸传 `k=1/放大倍数`**（4:1 → 0.25），数值才对。半剖里只画一半的对称尺寸：`d.DimLine1Suppress = d.ExtLine1Suppress = True` |
| `dimdia(c, r, ang, leader, txt)` / `dimrad(…)` | 直径、半径。ang 是引线方向；返回的对象可以改 `.TextPosition = P(x, y)` |
| `rough(tip, ra, ang=0, mode="remove")` / `rough_leader(表面点, 折点, ra)` | GB/T 131 粗糙度符号。`mode`：`remove` 去除材料（加工面）、`keep` 不去除材料（毛坯面，"其余"用 `rough(p, None, mode="keep")`）、`any` 基本符号。竖直面用 `ang=90`（符号在左侧，字从下往上读）；也可以直接标在尺寸线上（GB/T 131 允许）。`rough_leader` 的折点在表面点左边时，水平线向左伸、符号放左端，引线不穿过符号 |
| `datum(foot, "A", direction=(1,0))` | 基准符号，别压在孔上 |
| `gtol(sym, value, datum, frame_at, [折点..., 箭头点])` | 形位公差框格，引线从框格右端引出（第一个折点在框格左边时从左端引出）。sym 用 gdt 字体代号：`f` 平行度、`b` 垂直度、`c` 平面度、`r` 同轴度、`j` 位置度、`h` 圆跳动、`t` 全跳动。要标轴线的公差，箭头接在直径尺寸线的终端 |
| `line/circle(…, layer="中心线")` | 补中心线（分布圆、剖视图的轴线） |
| `to_center(p1, p2)` | 半剖分界线：删掉落在 p1-p2 上的细实线/中心线碎段，画一整条点画线（p1/p2 取到轮廓外 3~5 mm，穿过孔的地方也连上） |
| `title_block_gb(图名, 图号, material, scale, weight, company, designer, date)` → 左上角 | **GB/T 10609.1 标准标题栏 180×56**（更改区、签字区、材料标记、阶段标记/重量/比例、共张第张、单位/图名/图号），几何照抄 SW 的 gb 模板。零件图用它；`title_block` 是老的 180×40 简化版 |
| `transition(box)` | 过渡线：box 内 SW 画成粗实线的样条、斜短线、小圆弧（R≤5）改细实线，直线两端各缩 0.8 不碰轮廓。只框俯视图里圆角过渡处，别框到真实外形 |
| `thread_hole(x轴, y顶, 深, d, d1, side)` / `thread_circle(c, d)` | 内螺纹规定画法：非圆视图大径细实线 + 终止线粗实线（`side="right"` 半剖只画一半）；圆视图大径 3/4 细圆 |
| `half_dia(c, r, ang, "%%C56")` | 只画一半的直径尺寸（半剖、对称图形）：箭头在 ang 方向圆周上，线过圆心伸出 6，数字沿线 |
| `erase_text("I")` / `erase_text(r"视图\s*[A-Z].*", regex=True)` | 删掉内容等于某串（或匹配正则）的文字（SW 自动放的放大图标签、斜视图标签） |
| `splice_aligned(keep_box, axis_x, keep_side, src_box, src_axis, src_side, src_pts, dst_pts)` | 旋转剖拼接（见 §2.2）：主剖视图留一半，另一个剖视图的一半按三对点仿射搬过来 |
| `cut_path(折线点)` / `cut_end(端点, 朝里方向, 投射方向, "A")` | 剖切线：细点画线 + 转折处粗短画；端部粗短画 + 箭头 + 字母（GB/T 4458.6） |
| `rot_label(p, "B", ccw)` | 旋转配置视图的标注：字母 + 半圆弧旋转符号 |
| `center_cross(c, r)` | 重画水平/竖直的十字中心线（旋转过的视图里 SW 的中心符号是斜的） |
| **`check()`** | **自动查文字压线/重叠**：文字和尺寸数字临时改蓝色、彩色出一张校核 PDF、栅格化，字形 0.35 mm 内有别的墨迹就报，打印说明和图纸坐标。放在 `with` 块最后，报 0 处再交。**同时跑几何检查**（`check_geometry`）：平行尺寸线间距 < 5 mm、引线箭头悬空（离最近图线 > 0.6 mm，分度圆这类中心线圆也算图线）、同值同向尺寸出现多次（只是提示：两段 Φ35k6 轴颈这种是正常的） |
| `auto_dims(视图框, "below"/"above"/"left"/"right", [(p1, p2[, 文字]), ...])` | **尺寸自动分排**（GB/T 4458.4）：按跨度从小到大，逐个放进最里面一排不和已有尺寸（连文字）重叠的位置；第一排离轮廓 10、排距 7；首尾相接的链式尺寸同排。轴的轴向尺寸、齿轮左边一排直径都用它（`examples/reducer/零件图/`） |
| `view_label(名, at, scale=None, keep_near=None)` | **统一重画视图名**：先删掉 SW 的所有同名标签（"A-A"、"视图 B"、"B 2:1"、"详图 I 4:1"、带角度的），再按国标写；罗马数字 + scale 时写成"I / 细横线 / 4:1"。删 "I" 这种短名时传 `keep_near=放大图附近一点`，免得把父视图上的 "I" 也删了 |
| `break_center_under_text(margin=1, layers=("中心线",), only=None)` | 国标"尺寸数字不能被图线穿过，否则把图线断开"：把穿过尺寸文字的点画线断开（轴上的配合尺寸、圆视图中心线）。放在 `check()` 前。窄轴上的键槽轮廓实在躲不开时，对那几个尺寸 `only=[d], layers=("粗实线",)` 断开轮廓线——别全局对粗实线用 |
| `clip_hatch(剖面线, a0, a1, keep)` | 把一块剖面线沿直线 a0→a1 裁成一半（边界取同名 DXF，shapely 求交后重建），`splice_aligned` 自动调 |
| `balloon_group(零件上一点, at, [n1, n2, n3])` | 紧固件组公共指引线序号（螺母、垫圈、螺栓自下而上竖排） |
| `table(右上角, 列宽, 行)` | 通用表格：齿轮参数表（右上角）等。格里只能放普通文字（TEXT 不支持叠写偏差，写成 `50.07(-0.10/-0.16)`） |
| `gear_teeth(p0, u, 齿宽, ra, r, rf, sides, hidden)` / `gear_circles(c, ra, r, rf=None)` | **圆柱齿轮规定画法**（GB/T 4459.2）：非圆视图（剖开时轮齿按不剖）齿顶线、齿根线粗实线，分度线点画线伸出端面 3；`hidden` 那一侧齿顶线画虚线（啮合区）。圆视图齿顶圆粗、分度圆点画线。齿轮模型只建到齿根圆，SW 的剖面线天然停在齿根；模型外圆在圆视图里是粗实线，要改成细实线（齿根圆）——见 `大齿轮.py` |
| `gear_side(p0, u, 齿宽, ra, r, sides=(1,-1), mesh=(), model_r=None, k=1, ext=3)` | **装配图里不剖的齿轮**（非圆外形视图，2026-11-10）：装配模型里齿轮按**分度圆柱**建（两轮正好相切，干涉检查干净），SW 投出来的是分度圆柱的两条轮廓线。这里删掉 ±model_r·k 处、齿宽范围内的那两条线，改画齿顶线（粗实线）+ 分度线（点画线，两端伸出 ext；端面外紧挨着别的零件时停在第一条横穿它的粗实线前 0.3），端面线补到齿顶线；后面零件的线 SW 截在分度圆柱轮廓上，改截到齿顶线；`mesh` 里的那一侧是啮合区：不画齿顶线，分度线画粗实线（两轮各调一次，重合处只留一根）。p0 = 齿宽起始端面的中心（图纸坐标），u = 沿齿宽方向的单位向量，side = 1 是 u 逆时针转 90° 那一侧；齿宽、ra、r、model_r 是模型 mm，k = 1/视图比例 |
| `gear_arc(c, ra, r, model_r, k=1)` | 上面那种齿轮的**圆视图**（只露出一段也行）：找圆心 c、半径 model_r·k 的圆或圆弧，model_r = r 时改成点画线（分度圆），否则删掉；补齿顶圆（粗实线）。圆弧被别的零件挡住时，齿顶圆弧的端点沿挡住它的那条粗实线延伸到齿顶圆上；后面零件的线 SW 截在分度圆上，改截到齿顶圆 |
| `title({占位符: 值})` | 只在 `own_frame=False`（沿用 SW 模板图框）时用 |
| `notes([条目], p=(40,80))` | 技术要求 |
| `s.layer(名)`、`s.ms` | 直接用 AutoCAD COM 加别的东西，比如"其余"两个字 |

`half_dia(..., frac=0.55)`：字中点离圆心 frac×r，同心圆多时调它让字落在两圆之间；文字是普通 TEXT，写不了叠写偏差。
**frac 取负**（如 −1.25，同时 `over = r·1.25 + 11`）：字写到圆心另一侧的延长线上——箱座/箱盖的半圆轴承孔这样把 Φ62H7 挪到结合面外的空白处。

**2026-11-08 新增方法**（`conv.py` / `placer.py` / `audit.py`，import sw2acad 时自动挂到 Sheet 上；k = 视图比例，1:2 传 0.5）：

| 方法 | 说明 |
|---|---|
| `fit("%%C35k6")` / `fit("12N9", code=False)` | 查 GB/T 1800 表生成带叠写偏差的文字，**不再手写偏差**（§2.6） |
| `thread_shaft(p0, u, 长, d, P=None, sides, k)` / `thread_shaft_circle(c, d, k=)` | **外螺纹**（GB/T 4459.1）：非圆视图小径细实线 + 终止线粗实线；圆视图 3/4 小径细圆、自动删倒角圆。模型按大径建光轴 |
| `spline_shaft(p0, u, 长, D, d, sides, k)` / `spline_circle(c, D, d, N, B, k)` / `conv.spline_mark(N,d,D,B)` | **矩形花键**（GB/T 4459.3）：小径细实线、终止线细实线、30° 尾线；圆视图画全部齿形（删光轴整圆）；标记 `6×23f7×26a11×6d10 GB/T 1144-2001` |
| `spring(p0, u, H0, D2, d, n, n2=2, k, keep=2)` | **圆柱螺旋压缩弹簧**剖视规定画法（GB/T 4459.4）：簧丝断面（≥2 mm 画剖面线，否则涂黑）、后半圈公切线、端面磨平、n>4 时中间用簧丝中心点画线省略。不建模 |
| `bevel_teeth(apex, u, δ, R, b, m, sides, k)` / `bevel_circles(c, d, da, R, b, k)` | **直齿锥齿轮**：齿顶线/齿根线收敛于锥顶、背锥线、分度线；圆视图大小端齿顶圆 + 大端分度圆。毛坯建到齿根锥 |
| `worm_teeth(p0, u, 长, d1, m, sides, k)` / `worm_circles(c, d1, m)` | **蜗杆**：齿顶线粗、分度线点画线、齿根线可省 |
| `worm_wheel_section(c, u, a, d1, m, b2, de2, sides, k, root=False)` / `worm_wheel_circles(c, d2, de2)` | **蜗轮**过轴线剖视：以蜗杆轴线为圆心的喉部齿顶圆弧（到外圆 de2 为止）、分度圆弧、端面线；模型建到齿根喉圆 |
| `auto_rough(表面线段, ra, out=法向)` | 粗糙度**自动放置**（§2.7） |
| `auto_gtol(sym, 值, 基准, 箭头点, out=)` / `auto_datum(foot, "A", out=, slide=)` | 形位公差框格 / 基准符号自动放置 |
| `auto_balloons([(零件上一点, 序号), ...], box=视图框, sides=)` | 装配图序号自动排：按指引线穿过东西最少分到四周，排成一排、交叉就换位 |
| `audit_dims(features, [(仿射, 视图框), ...], ignore_r=)` | **尺寸完整性审查**（§2.8） |

### 2.5 成套图纸：装配图 + 零件图（范例 `examples/reducer/`，2026-11-08 一级圆柱齿轮减速器）

1. `build_parts.py`：零件都在**全局坐标**里建（输入轴 X=0、输出轴 X=100、结合面 Y=0、轴线沿 Z），装配时只平移/旋转不加配合。键槽：`shaft_keyway` / `hub_keyway`（草图画在过轴线的基准面上，`sw_part.cut_offset` 从槽底开始切，见 §3）。
2. `build_asm.py`：`sw_std.make` 生成标准件（3 个平键、4 组 M10×40 螺栓 + 垫圈 + 螺母），`sw_std.place` 按"零件轴线 → 装配方向 + 参考点 → 装配点"放好；大齿轮绕自身轴线转 −90° 让轮毂键槽对上轴上的键（变换矩阵行向量约定）。标准件信息（代号、规格、材料、质量）写 `std.json` 给明细栏。干涉检查（MCP `solidworks_check_interference`）只剩螺栓和螺母的螺纹重叠（每组约 193 mm³ = 大径与螺母小径之间那圈，正常）。
3. `views.py` + `reducer_gb.py`：装配图 A2 1:2。键在 A-A 里纵剖、`unhatch` 去剖面线并删 SW 在键圆头处加的中心符号；明细栏行 `std_row(...)` 从 std.json 生成（`GB/T 1096 键 12×8×32`…），总重 = 零件 + 标准件；螺栓组用 `balloon_group`；轴伸直径挪到左视图（A-A 里轴伸太窄、还有键挡着）。
4. `零件图/输出轴*.py`：主视图 `*右视`（键槽正对观察者），两个移出断面放在剖切线延长线上（不对称：画箭头、省略字母）；直径竖直标、文字压轴线的断开点画线；轴向尺寸 `auto_dims` 自动分排；基准 A/B 在两个轴颈、三角形和直径尺寸线对齐；圆跳动指向表面。
5. `零件图/大齿轮*.py`：主视图 = 过轴线全剖（对称面、按投影关系配置，剖切符号和 A-A 都不标）+ 圆视图；`gear_teeth` / `gear_circles`；左边一排直径 `auto_dims`；孔 Φ40H7 有键槽只能 `half_dia`、基准 A 三角形和它对齐；键槽宽 12JS9、槽深 43.3；参数表 `table`。
6. 每张图 `check()` 0 处再交。改零件尺寸时：`build_parts → build_asm → views + 各零件 *_views → 各 drawing`。

7. **装配图已改成模型坐标**（2026-11-08）：`views.py` 写 `reducer_layout.json`（三个视图的 `view_affine`），`reducer_gb.py` 里
   所有点写 `T(X, Y, Z)`（A-A）、`F(...)`（主视图）、`LV(...)`（左视图），序号 `auto_balloons` 自动排。改版时发现老脚本里左视图
   公式 `x = 343.75 − Z/2` 的方向是反的（SW 实际是 `346.25 + Z/2`）——手推坐标就是会出这种错。
8. **箱座、箱盖零件图**（`零件图/箱座*.py`、`箱盖*.py`，A2 1:2）：主视图（局部剖螺栓孔/地脚孔；箱盖开虚线表达内腔）+ 俯视图 +
   A-A（过输出轴承孔轴线，放左视图位置）。对称于 X=75 的长度尺寸都在俯视图下方 `auto_dims`；半圆轴承孔 `half_dia(frac<0)`；
   粗糙度、平面度 `auto_*`；`audit_dims` 0 处（箱盖第一版漏了凸缘到轴线的 68，就是 audit 报出来的）。
   开虚线注意：`hidden_lines(front, True)` 后**投影视图和剖视也跟着显示虚线**（实测），要对它们再 `hidden_lines(v, False)`。

还没做的：齿轮轴、套筒、四个端盖的零件图（同样的路子，照 输出轴_auto.py / 箱盖.py 抄）。

### 2.6 公差查表（`scripts/gbtol.py`，2026-11-08）

偏差值不要再手写：`s.dimlin(..., txt=s.fit("%%C35k6"))` → `%%C35k6(+0.018/+0.002 叠写)`。范围 0~500 mm，轴 a~u（含 cd ef fg js j k），
孔同字母大写（J 只有 6/7/8 级），K/M/N/P~U 孔的 Δ 修正都在。`python gbtol.py` 自测 40 个手册值全对。
- `gbtol.limits("H7", 62)` → `(0.030, 0.0)`；`tol_text("12N9", code=False)`；`tol_text("%%C40js6")` → `±0.008`（新标准 ±IT/2，JS9 b=12 是 ±0.0215）
- `gbtol.keyway(40)` → GB/T 1095 键槽：b=12、t1=5、t2=3.3，轴上标 `depth_text(kw["shaft_depth"])` = 35(0/−0.2)，毂上 43.3(+0.2/0)
- `gbtol.general("m", 120)` → GB/T 1804 一般公差 ±0.3
- **`check()` 里自动核对**：图上所有“代号 + 手写偏差”的尺寸（`%%C35k6({\H0.7x;\S+0.018^+0.002;})`、`(%%P0.008)`）都按表验一遍，
  对不上报“公差：k6 Φ35 应为 +0.018/+0.002，图上写了 …”。`H7/r6` 这种配合代号不查。

### 2.7 符号自动放置（`scripts/placer.py`，2026-11-08）

只给“标在哪个要素上”，位置自动挑——不用再算坐标、看 2~4 轮渲染图：
```python
s.auto_rough((M(-50, 17.5), M(-18, 17.5)), "0.8", out=(0, 1))   # 表面 = 视图里那条轮廓线（两端点），out = 指向材料外
s.auto_gtol("h", "0.015", "A-B", M(16, 20), out=(0, 1))         # 箭头落点 + 箭头来的方向（垂直于表面）
s.auto_datum(M(42, 17.5), "A", out=(0, 1))                      # 标轴线的基准别给 slide（要和尺寸线对齐）
s.auto_balloons([(T(-85, 0, 17.5), 1), ...], box=视图框, sides=("left", "top", "right", "bottom"))
```
做法：从当前图收集障碍（文字、尺寸数字、尺寸线、已放符号 = 硬障碍；轮廓线、剖面线区域（从 DXF 取真实边界）、中心线 = 软障碍），
shapely STRtree；每个符号枚举几十个候选——粗糙度：直接标在线上 / 标在延长线上 / 指引线引出（各种长度、±30°、左右）；
形位公差：折点距离 8~40、框格左右；序号：每个零件先按“指引线穿过的东西最少”分到一侧，整排离视图 −30（排在外框里的空白处）~ +70 都试，
相邻指引线交叉就交换。按“压字 ≫ 压剖面线 > 压轮廓线 > 离要素远”打分取最低。**GB/T 131 读向**：只有朝上、朝左的面能直接标，
朝下/朝右只能引出——候选里已保证。每个符号打印代价，≥100 带“← 看一眼”。

实测：输出轴（基准 2、跳动 2、粗糙度 4）、箱座、箱盖第一次就 `check()` 0 处；减速器装配图 18 个序号 3 轮调参后 0 处。
**仍然要看渲染图**：算法只知道“别压东西”，不懂“这个符号放这儿习不习惯”（比如序号排在视图外框里面的空白处、半径尺寸挤在一起）。

### 2.8 尺寸完整性审查（`scripts/audit.py` + `sw_views.part_features`，2026-11-08）

`check()` 只查排版。`audit_dims` 拿模型核对“尺寸标全了没有”：
1. views 步骤：`V.part_features(sw, 零件, "xx_features.json")` 读零件的平面（垂直 X/Y/Z 的位置）和圆柱面（轴线、半径；R≤3 且不满半圈的当圆角跳过）；
2. AutoCAD 步骤最后：`s.audit_dims(FEAT, [(L["front"], 视图框), ...], ignore_r=[齿根圆半径])`。

每个线性尺寸两端按视图仿射换回模型坐标，按 X/Y/Z 各建一张图：节点 = 平面、孔/轴轴线、圆柱两条轮廓线；边 = 尺寸（对称尺寸还连到中点，
齿宽 40、腹板 12 这种对称于中面的靠它连通）、圆柱轮廓 ↔ 轴线（隐含）；分布圆上的孔按“孔心到某轴线距离 = 图上某 Φ/2”算已定位。报告：
- `Z 向缺定位尺寸：Z=-50, -18, 20 … 这一组和其余要素之间没有尺寸连起来` —— 实测去掉输出轴一个 13 就报这一条；
- `可能是封闭尺寸链` —— 一个尺寸两端已经被别的尺寸连通（直径尺寸、重复的同一对点不算）；
- `Φ143.75 的圆柱面在图上没有直径/半径尺寸`（Φ、R、M 螺纹小径、槽宽都算数；齿轮齿根圆这种按规定不注的用 ignore_r）；
- `视图有 N 段虚线，内部结构是不是该剖开`——只是提示。

**它查不了的**：该不该剖、视图选得好不好、尺寸基准选得合不合理（只查连通，不查从哪儿标）、斜视图里的尺寸、工艺上该不该标。
这些还是要人（老师/审图人）看——这套流程出的图**没经过老师或审图人审过**。

## 3. SolidWorks 建模（`scripts/sw_part.py`；优先用 SolidWorks MCP）

```python
import sys, os; sys.path.insert(0, os.path.expanduser(r"~\.claude\skills\cad-drawing\scripts"))
import sw_part as S
sw = S.connect(); p = S.new_part(sw)
sk = S.sketch_on(p, "front")                 # 单位是米：用 S.mm
sk.CreateCornerRectangle(0, 0, 0, 400*S.mm, 120*S.mm, 0)
sk.CreateCircleByRadius(60*S.mm, 90*S.mm, 0, 6*S.mm)   # 同一草图里的内环直接拉成孔
S.extrude(p, 4)                               # 深度单位 mm
sk = S.sketch_on(p, "front"); ...; S.cut_through(p)   # 自动试两个方向（... 为省略的草图绘制）
S.set_material(p)                             # 默认"普通碳钢"
print(S.mass_kg(p)); S.save(p, r"...\零件.SLDPRT"); S.snapshot(p, r"...\零件.png")
```

建完零件要用 `dump_dxf` 核对每个圆的半径，并用 `get_mass_properties` 核对体积。

**偏移起点切除（键槽、轮毂槽）**：`S.cut_offset(p, 起点mm, 深mm, check, max_removed=)`——草图画在过轴线的基准面上，从"基准面平移到槽底"开始往外切；四种方向组合逐个试，`check`（如 `lambda q: S.has_plane_face(q, 0, 115)`：X=115 处有平面 = 槽底）和 `max_removed`（切掉的体积上限，槽面积 × 槽深 × 1.3）都满足才留下，否则 `EditUndo2` 撤销再试。只查槽底面不够：切反了（从槽底往轴心切）在同一位置也留下一个平面，实测输出轴被多切掉 15000 mm³。范例 `examples/reducer/build_parts.py` 的 `shaft_keyway` / `hub_keyway`。

**标准件**（`scripts/sw_std.py`）：Toolbox 没有"按规格生成"的 COM 接口，做法是只读打开 `C:\SOLIDWORKS Data\browser\GB\...` 的基础零件、删设计表、按 GB 尺寸表改驱动尺寸、压缩螺纹纹理、去 Toolbox 标记、写自定义属性后另存。

```python
import sw_std
path, info = sw_std.make(sw, "bolt", "M10x40", out_dir)   # 也有 nut "M10"、washer "10"、key "12x8x32"、pin "6x30"、bearing "6206"
# info：代号 GB/T 5782-2016、名称、规格 M10×40、材料 8.8 级、标记、质量kg、外框 —— 明细栏直接用
sw_std.place(asm, sw, path, "bolt", (x, 12, z), (0, -1, 0), ref=(外框xmax - 40, 0, 0), up=(1, 0, 0))
```

`place`：零件自身轴线（螺栓/键/销/轴承 +X，螺母/垫圈 +Z）转到 axis，零件上的参考点 ref 放到 origin，`up` 定第二个方向（零件 +Y 转去哪：螺栓头对边、键宽）。各标准件生成后的自身坐标约定写在 sw_std.py 的 `LOCAL`/`AXIS` 注释里。零件要先在 SW 里打开才能插入。

### 3.1 更多标准件：直接读 Toolbox 尺寸库（2026-11-08）

`C:\SOLIDWORKS Data\lang\english\swbrowser.sldedb` 就是 SQLite：`GB_TYPE_*` 每种件一行（类型名、基础零件、配置表、数据表），
`GB_CFG_*` 写着每个驱动尺寸名（`d@Sketch2`）取哪张表哪一列、按什么条件过滤，`GB_DATA_*` 是尺寸表。`toolbox_db.py` 把这套规则解释一遍，
**尺寸全部来自 SW 官方库，不是手抄**。Toolbox GB 里有的件都能生成（几百种）：
```python
path, info = sw_std.make_tb(sw, "screw", "M8x25", out)          # GB/T 70.1 内六角圆柱头螺钉
sw_std.make_tb(sw, "screw_hex", "M8x25", out)                    # GB/T 5783 六角头螺栓全螺纹（端盖螺钉）
sw_std.make_tb(sw, "screw_pan", "M5x12", out)                    # GB/T 67 开槽盘头螺钉
sw_std.make_tb(sw, "spring_washer", "10", out)                   # GB/T 93 弹簧垫圈
sw_std.make_tb(sw, "taper_bearing", "30206", out)                # GB/T 297 圆锥滚子轴承
sw_std.make_tb(sw, "oring", "30x3.55", out)                      # GB/T 3452.1 O 形圈
sw_std.make_any(sw, "GB/T 893", {"Size": "..."}, out)            # 其他任意件：类型名一部分 + 选项（toolbox_db.DB().choices 列可选值）
sw_std.make_felt(sw, 30, out)                                    # 毡圈 JB/ZQ 4606（Toolbox 没有，自建；info["槽"] 给端盖槽尺寸）
```
规格不在表里直接报错并列出可选值。实测（std_demo.py）：M8×25 内六角 外框 X 0..33、头 Φ13；30206 T=17.25 D=62；弹簧垫圈 10：d 10.9 s=b=2.6。
- Toolbox 的 5783 表里 s、k 存的是极限值（M8：12.73、5.45），`make_tb` 已改成公称值（13、5.3）。别的件第一次用也看一眼外框。
- 毡圈表是按《机械设计课程设计手册》**手录**的（Toolbox 没有），第一次用对一遍手册。
- 角度尺寸（锥轴承的接触角）库里是度：`Parameter.GetType` = 1 时按角度设（实测）。
- 库里登记的路径有时和实际目录对不上（O 形圈），`make_any` 会按文件名在库目录里找。

## 4. 踩过的坑

### 4.1 SW 出视图与导出

| 症状 | 原因 / 解决 |
|---|---|
| 剖视图是空的，只有 "A-A" 两个字 | 剖切线用了图纸坐标。要用父视图的视图坐标（模型原点为 0,0），`section()` 已按这个约定 |
| 剖视图没有剖面线，剖切符号只出现一端（2026-11-07 轴承座） | 视图坐标原点实测是**视图中心**，不是模型原点。零件在模型里 Y 0..113 时，视图中心对应 Y=56.5，剖切线要写 (0,66)/(0,-66)。先算出视图中心对应的模型坐标再给线 |
| 剖视图只剖到一部分 | 剖切线没有贯穿零件。视图坐标的原点是**视图中心对应的模型原点**，线要两头都伸出轮廓 |
| 剖视图的剖切方向或位置不对，主视图上下颠倒 | 根因（2026-11-08 查清）：SW 的剖切箭头总在剖切线 p1→p2 走向的**右侧**，视图按箭头方向投影；剖视图放在箭头背后一侧时就翻了。`section()` / `step_section()` 现在按 at 的方位自动反转点序，让箭头指向剖视图 |
| 放大图的 `GetOutline` 外框时大时小（一次 75×79，一次 27×29） | 不能拿它当 Sheet 的视图框，否则框外的放大图图线会被当模板删掉。用放大圆（中心 ± r×倍数 + 4）当视图框 |
| SW 自动放的放大图标签 "I" 位置每次不同（一次跑进了轴孔里） | `s.erase_text("I")` 删掉，自己画指引线 + 罗马数字 |
| SW 有时不给轴孔出中心符号（同一模型、同样的设置，两次结果不同） | 关键中心线不要指望 SW：AutoCAD 里自己 `s.line(...)` 补上 |
| `view.GetVisibleEntities2(None, 1)` 报类型不匹配 | 组件参数要传 `VARIANT(VT_DISPATCH, None)`（`_none()`） |
| 旋转、裁剪过的视图 `GetOutline` 是整个视图（裁剪前）的外框，大得多 | 当 Sheet 的视图框会把标题栏圈进去（模板线删不掉）。用裁剪边界点经 `model_to_sheet` 算框 |
| 斜视图的投射箭头和字母被删了 | 它们画在父视图外框外面。父视图框在箭头那一侧多留 25 mm |
| 斜视图父视图上的字母 SW 导出了两份，还压在箭头上 | 留一份、挪开（`examples/rot_oblique/drawing.py`） |
| 剖视图也显示了虚线 | 父视图先开了虚线，剖视图会继承。先建剖视，再对需要的视图开 `hidden_lines` |
| 视图被缩成 1:2 | 国标模板会自动缩放。`SetProperties2` 设 1:1 要在建完视图后**再设一次**才生效，`finish()` 已处理 |
| 圆角处多一圈线 | 切边。国标不画，`finish()` 里用 `SetDisplayTangentEdges2(0)` 关掉 |
| 1:2 的图导出 DWG 后被放大成 1:1，图框也变大了 | SW 选项 swDxfOutputNoScale(136)=1 时按模型尺寸输出。`export()` 会临时设为 0 |
| SW 导出 DWG 时 SaveAs 返回 False，错误码 1 | 同名 DWG 被占用，或 SW 里同名工程图还开着。`new_drawing` 会先关掉旧工程图，`export` 会先删旧文件 |
| SW 导出的 SAT 在 AutoCAD 里报 *Error reading in ACIS file* | SW 2025 默认导出 ACIS 33，版本太新。要导 SAT 就设 `SetUserPreferenceIntegerValue(5, 8)`（ACIS 7.0），用完改回去。A 路线不需要导 SAT |
| `CreateSectionViewAt5` 的 ExcludedComponents（装配图里不剖某个零件）不生效 | 传了组件数组，返回的视图照样有剖面线。改在 AutoCAD 里用 `unhatch` 删掉那块剖面线 |
| 老的 `half_section`（L 形剖切线 + `CreateSectionViewAt5` 选项 2）出来是全剖 | 选项 2 是阶梯剖，L 形线被当成阶梯剖。已改用局部剖做半剖（§2.2） |
| SW 原生半剖（两段相连的垂直剖切线、选项 0）方向不受控（2026-11-08 试了 12 种画法） | 它总以**竖直**那段为剖切面、剖视图水平摆在父视图左右。只有"父视图是侧视图、竖段从上方外面画到中心、再横着向右"一种得到正立的上半剖；其余是残缺的 1/4、镜像，或叠在父视图上；在俯视图上画永远得到躺倒的侧视图；`view.Angle` 转父视图也不行。一律用 `half_section`（局部剖做法） |
| 局部剖/半剖后外形半边多出一条贴近轴线的竖线 | 不是 SW 的毛病：凸缘孔离筒体太近，贯穿切除在筒体外圆上切出了浅槽（Φ12 孔在 R35 上，筒体 R30）。建模时孔边要离开筒体 |
| 半剖分界线是细实线，而且被零件轮廓断成好几段、点画线节奏对不上看着像实线，穿过孔的地方还没线 | `Sheet.to_center(p1, p2)` 现在删掉碎段、画一整条点画线 |
| 每个铸造圆角的圆心都有一个中心符号十字 | SW 默认给圆角加中心符号（选项 309/448）。`new_drawing` 已关掉 |
| 局部放大图的剖面线在 AutoCAD 里变成点画线 | 放大图的剖面线导出为块 `SW_HATCH_n`，老的 `_relayer` 把所有块都当中心符号炸开放中心线层。已改为只有 `*CENTERMARK*` 块进中心线层，其余块炸开后按类型分层 |
| 图框左右两边外面有 A B C D 字母 | SW 模板的分区字母像视图标注，被 `_relayer` 留下来了。`frame()` 现在会删掉内框外的文字 |

### 4.2 AutoCAD COM 整理

| 症状 | 原因 / 解决 |
|---|---|
| **AutoCAD 弹 FATAL ERROR: Unhandled Access Violation 崩溃** | 两个原因，都已修好：① 原来用 `retry(lambda: Documents.Open(...))`，Open 其实已经成功了却抛异常，重试就把同一个文件反复打开。现在 Open/Add/Close 都只调一次，再轮询核对结果（`Sheet._once`）。② **刚启动的 AutoCAD 上 `SetVariable("SDI", 0)` 后再 Open 必崩**（复现了两次）。现在 `Sheet` 不改 SDI：SDI=1 时 Open 会直接替换当前文档，正好不用再关旧文档。**以后写 COM 代码，有副作用的调用都不要整个包进 retry，也不要去碰 SDI** |
| AutoCAD 关掉最后一个文档时整个程序退出 | SDI=1 时会这样。所以 `Sheet` 不去关文档，直接 Open 替换当前文档（不要改成 SDI=0，见上面"崩溃"那条） |
| COM 报 *被呼叫方拒绝接收呼叫* | AutoCAD 刚打开文档，还在后台重生成。`Sheet` 会先等 `GetAcadState().IsQuiescent`，每个对象的 COM 调用都包了 `retry` |
| 其他 COM 调用也偶发"拒绝接收" | 已用 `com_filter.install()` 注册 COM 消息过滤器（comtypes 加 ole32.CoRegisterMessageFilter），忙时自动等 150 ms 重试，最多 120 s。sw2acad 导入时就会装上 |
| SW 导出 DWG 时报 WinError 32（文件被占用） | 上一轮 sw2acad 把同名 DWG 开在 AutoCAD 里了。`export()` 会先在 AutoCAD 里释放它：多文档时直接 Close，SDI=1 时发 `_.NEW` 新建一张图把它顶掉 |
| 1:2 图里尺寸数字是图纸上的长度 | `Sheet(view_scale=2)` 会给每个尺寸设 `LinearScaleFactor=2`。`Measurement` 返回的已经是换算后的值，不要再乘一次 |
| COM 报 *RPC 服务器不可用* | ROT 里留着已经退出的 AutoCAD。`live_acad()` 会自动重新启动 |
| `Documents` 不能 `for` 遍历 | 晚绑定问题，改用 `Item(i)` 加 `Count` |
| `AutoCAD IMPORT` STEP 后模型空间一直是空的 | 转换在后台排队，要等右下角弹出"Import File Processing Complete"后再点击才导入。别走这条路 |
| 形位公差的引线画成弧线 | `AddLeader` 的类型 1 是样条线，要用 **2**（直线带箭头） |
| 标题栏占位符替换不掉 | 模板里用的是中文引号 `“图样名称”`；"共  张"中间本来就带空格，页码模板会自动填，不要再写 |
| 新打印的 PDF 没有覆盖旧的 | WPS 锁住了旧 PDF。`Sheet` 每次都带时间戳另存 |
| 中文字体显示成问号 | SW 用的长仿宋 TTF 本机没有。`Sheet` 已把所有文字样式换成 gbenor+gbcbig |
| 尺寸、剖面线、公差框格 `Explode` 报 AttributeError | 这些 COM 对象没有 Explode 方法（复制出来的也没有）。只有块参照、多段线能炸 |
| **用 `SendCommand('(command "_.EXPLODE" ...)')` 后 AutoCAD 的 COM 整个卡死**，所有调用都超时 | 2026-11-08 实测，只能 `taskkill /IM acad.exe /F`。**脚本里不要用 SendCommand 干活**；`check()` 改成彩色出图 + 栅格化 |
| 改 "文字" 图层颜色，出图里文字颜色不变 | 文字对象颜色要逐个设 `e.TrueColor`（AcCmColor），恢复时设 ColorIndex=256（随层）；尺寸数字用 `d.TextColor` |
| 用 Alignment + TextAlignmentPoint 再设 Rotation 的文字跑到别处 | 旋转文字改用左对齐，按估算字宽算 InsertionPoint（`half_dia` 已这样做） |
| 过渡线小圆弧缩短后变成大半个圆 | 圆弧只有十几度，两端各缩 0.8/R 弧度就反过来了。`transition()` 限制每端最多缩掉 20% |
| `check()` 报的位置整体偏了一百多 mm | 校核图按"范围"打印，图框外刚删掉/搬走的对象（拼接用的辅助视图）还留在范围里，整张图被居中偏移。`check()` 现在先 `ZoomExtents` |
| 拼接时紧贴斜轴线的剖面线被当成"跨轴线"丢掉 | 不能用外框四角判断在轴线哪侧（斜着放的视图外框角会跨过去）。改用直线端点、圆弧采样点、剖面线外框中心 |
| 搬过来的剖面线方向跟着转了 30° | `TransformBy` 会转剖面线图案。搬完把 PatternAngle/PatternScale 设成主视图那半边的 |
| 剖开的孔中间多一条竖线 | 孔的圆柱面被切成两半，背面接缝线正好在轴线上。拼接后删掉轴线上的粗实线、另画点画线 |
| `check()` 把标题栏每个字都报成压线 | 蓝字边缘的抗锯齿像素是暗蓝色，被当成别的墨迹。判据改成"够暗而且不偏蓝"（B − max(R,G) < 40） |
| `check()` 报 *Null extents* 崩掉 | 明细栏空格写了空字符串，没有外框。已跳过 |
| `AddDimRotated(…, 90°)` 建的竖直尺寸，`Rotation` 读回来是 0 | 实测如此。要判断尺寸方向用 `dimlin` 记在 `self._dims` 里的角度（`break_center_under_text` 已这样做） |
| 配合尺寸文字挪到轴线旁边（改 TextPosition）后，尺寸线拖出一长截，字压到轴承上 | 窄的轴段上别挪字：字留在中间，用 `break_center_under_text` 把点画线断开（国标做法） |
| `check()` 出校核图时 `lay.ConfigName = …` 连续报 *Invalid input*（两个 pc3 都不行），随后 AutoCAD 进程消失；下一轮 Open 报“远程过程调用失败” | 2026-11-08 装配图连跑多轮后出现一次。`Sheet.__enter__` 现在 Open 失败时查 acad.exe 还在不在，不在就 `live_acad()` 重启再开一次 |
| `check()` 出完校核 PDF 紧接着 `check_geometry` 读对象报“被呼叫方拒绝接收呼叫”（消息过滤器也没挡住） | AutoCAD 打印后还在后台忙。`check()` 现在先 `_idle(120)` 再跑，整段再包一层 retry |
| 旧时间戳 PDF 越积越多、删不掉 | 原因是 AutoCAD 打印完自动用 WPS 打开、锁住文件。现在用 `DWG To PDF NoView.pc3`（`acad_common.ensure_pdf_pc3()` 复制 DWG To PDF.pc3、只把 View_New_File 改成 FALSE、按 adler32 重写文件头），打印完不再打开；`Sheet` 退出时删掉同名的旧时间戳 PDF（留最新的出图和校核图）。新生成的 pc3 要先 `RefreshPlotDeviceInfo` 再设，否则 Invalid input |
| 装配图剖视里所有零件的剖面线同一个方向、同样疏密，相邻零件分不开（2026-11-10 末端执行器、机械臂部装图） | SW 导出就是统一的 ANSI31。出图后调 `s.stagger_hatches()` 重新分配（§2.4） |
| 错开以后同一零件的几块剖面线方向不一样 | SW 每个封闭区域导成一块 HATCH，被孔、轴隔开的几块在邻接关系里互不相干。镜像对称的会自动并组；不完全对称的给 `axes`（要用真正的对称轴，如关节轴线；偶然配上对的镜像轴会把小零件翻进别的零件里）；镜像也认不出来的用 `same` 指定 |
| 局部放大图里的剖面线没跟着父视图改 | 放大图的剖面线导出为 `SW_HATCH_n` 块里的线段，不是 HATCH。给 `stagger_hatches(details=…)`：按同名 DXF 找出这些线段，删掉后按新样式重画 |
| 橡胶、尼龙件被剖到，画成了金属的 45° 斜线 | SW 不分材料。`s.hatch_material(点, "非金属", 0.5)` 换交叉网格，要在 `stagger_hatches` 之前调 |
| 装配图里的齿轮只是一个圆柱的矩形轮廓，没有齿顶线和分度线 | 装配模型里齿轮只能按分度圆柱建（按齿顶圆建两轮会干涉）。出图后非圆视图用 `gear_side`、圆视图用 `gear_arc` 改成规定画法；圆视图里只露出一段圆弧的也能处理 |
| 改成规定画法后，后面零件的线戳进齿顶圆和分度圆之间；分度线伸出端面 3 mm 穿进了紧挨着的零件（2026-11-10 末端执行器俯视图、A-A） | SW 只按分度圆柱遮挡，轮齿那一圈它不知道。`gear_side` / `gear_arc` 已把截在分度圆柱轮廓上的线改截到齿顶；分度线碰到第一条横穿它的粗实线就停 |

### 4.3 SolidWorks 建模 / 装配 / MCP

| 症状 | 原因 / 解决 |
|---|---|
| 圆角倒到了别的边上（实测：本想倒支承板和圆筒的交线，结果圆筒前端面的圆边被倒圆，体积反而变小） | `SelectByID2(.., "EDGE", x,y,z)` 是沿当前视向打射线，会选到挡在前面的边。改为遍历 `body.GetEdges()`，用 `edge.GetClosestPointOn(x,y,z)` 取离点最近的边再 `Select4`（见 `examples/zcz_build.py` 的 `fillet`）。做完看体积：凹边倒圆体积应该**变大** |
| 右视基准面上的草图坐标 | 实测：草图 x = 模型 −Z，草图 y = 模型 Y（上视基准面：草图 x = X，草图 y = −Z）。前后对称的轮廓不受影响；不对称时先用小矩形探测一下 |
| 装配不想加配合，零件按全局坐标建好直接放 | `AddComponent5(路径, 0, "", False, "", 0,0,0)` 后设 `comp.Transform2`。`sw.GetMathUtility.CreateTransform(...)` 晚绑定报"找不到成员"，要按 DISPID 直接调：`mu._oleobj_.Invoke(mu._oleobj_.GetIDsOfNames("CreateTransform"), 0, pythoncom.DISPATCH_METHOD, True, VARIANT(0x2005, [1,0,0,0,1,0,0,0,1,tx,ty,tz,1,0,0,0]))`，再 `wc.Dispatch(...)`。范例：`examples/reducer/build_asm.py`（2026-11-08 一级齿轮减速器） |
| `asm.EditRebuild3()` 报 *'bool' object is not callable*；`InterferenceDetectionManager` 拿到 None | 晚绑定把无参方法当属性：写 `asm.EditRebuild3` 不带括号。干涉检查改用 MCP 的 `solidworks_check_interference` |
| 距离配合方向反了，零件互相嵌进去，干涉检查报出来 | 加 `flip: true`；已有的配合改 `GetDefinition().FlipDimension=True` 后调 `ModifyDefinition(md, doc, VARIANT(VT_DISPATCH, None))`，第三个参数传 None 会报类型不匹配 |
| SolidWorks MCP 画的小孔半径不对（R2.5 变成了 R2.958） | 草图自动吸附到了旁边的大圆。已在 MCP 里打补丁，画草图时开 AddToDB。**建完零件要用 dump_dxf 核对每个圆的半径** |
| SolidWorks MCP 的倒角报"成功"但体积没变 | swChamferType 0 和 16 在 SW 2025 上都是零尺寸倒角。MCP 已打补丁改用角度-距离 45°。做完倒角要用 get_mass_properties 核对体积变了没有 |
| SW 导出新的同名 SLDPRT 时报 Save failed | 旧的工程图或装配体还引用着这个零件。先 `sw.CloseAllDocuments(True)` |
| `Explode`/`Move` 等方法报参数错误 | 点参数必须是 `VARIANT(0x2005, [x, y, z])`，不能直接传 COM 返回的 tuple |
| SW `SelectByID2` 失败 | Callout 参数要传 `VARIANT(VT_DISPATCH, None)`；基准面要用中文名 |
| SW `RevisionNumber()` 报 *'str' object is not callable* | 它是属性，不是方法 |
| SW `CreateMassProperty` 找不到成员；`GetMaterialPropertyName2` 类型不匹配 | byref 参数要传 `VARIANT(VT_BYREF\|…)`；质量用 `GetMassProperties(1, st)[5]` |
| `GetMassProperties` 返回 None | 还在草图编辑状态。先 `InsertSketch(True)` 退出草图、`EditRebuild3` 再算 |
| `body.GetFaces` / `face.GetBox` 一会儿是属性一会儿是方法（报 *'method' object is not iterable*） | 晚绑定不稳定：`x = b.GetFaces; x = x() if callable(x) else x` |
| **SolidWorks 进程私有内存涨到 15 GB**，接着 AutoCAD 打开文档失败、OpenBLAS 报内存不够（2026-11-08，连续建零件/装配/出 6 张工程图之后） | SW 关了文档也不怎么释放。**现在自动处理**（`sw_mem.py`）：`sw_views.connect()` / `sw_part.connect()` 之前、`export()` 之后、`Sheet` 进 AutoCAD 之前各查一次私有内存，超过 config.json 的 `sw_mem_limit_gb`（默认 6）就关闭全部文档、`ExitApp`，60 s 不退就 taskkill；下次 connect 自动重开。**有未保存的文档时不退**，只打印警告。实测 5.2 GB → 9.5 s 退干净。手动看：`python sw_mem.py` |
| 晚绑定：`face.GetSurface` 用 `callable()` 判断后调用，报“找不到成员” | 属性返回的 COM 对象本身也 callable（`__call__` 调默认成员）。判断“是不是没带括号的方法”要用 `inspect.ismethod(x)`（`part_features` 的 `V()`）。老代码里 `x() if callable(x) else x` 对返回 COM 对象的属性会出错 |
| 投影视图、剖视图也显示了虚线（开虚线在建完剖视之后也一样） | 父视图 `hidden_lines(front, True)` 后，`projected` 出来的俯视图和剖视图跟着变（2026-11-08 箱盖实测）。对它们再 `hidden_lines(v, False)` |
| 零件特征里有一大堆 R≤3 的圆柱面 | 铸造圆角。`part_features(fillet_r=3)` 默认跳过“半径 ≤3 且不满半圈”的 |
| 斜视图上做局部剖：`CreateBreakOutSection` 返回成功，可视图里什么都没变 | 实测（整个视图框都圈上也一样）。斜视图上别用局部剖；要"半边剖开"就做全剖再 `clip_hatch` |
| 装配干涉检查报螺栓和螺母各重叠约 193 mm³ | 螺栓按大径建、螺母按小径建，旋合段的那一圈。正常，不用改 |

### 4.4 改 skill 本身

| 症状 | 原因 / 解决 |
|---|---|
| 按原文替换改 `scripts/*.py`、SKILL.md 时提示找不到原文 | 这些文件是 CRLF 换行。用 Python 读写时加 `newline=""`，补丁里的换行先换成 `\r\n` |
| 改坏了要回退 | 改之前把原文件复制成 `原名.bakMMDDHHMM`（月日时分），`scripts/` 里留着历次的备份 |

## 5. 画法规范（国标要点）

- **第一角画法**：俯视图在主视图下方，左视图在主视图右侧。
- 孔要画十字中心线（超出圆约 5）；看不见的轮廓用虚线层；剖视图用 ANSI31 剖面线。
- **剖视图 = 被剖到的实体（加剖面线）+ 剖切面后所有看得见的轮廓线。** 最常漏的是孔或槽两端在剖视图上的端面竖线：空心件全剖时，上下两块实体之间必须用端面线连起来，否则看起来像两块分开的板。画完后自问："这根孔/槽的两头，在这个视图里看得见边线吗？"
- 端视图上，外倒角会多出一个圆（例如 C1 时是 Φ(D−2)）。
- 回转体的直径（Φ）标在非圆视图上；倒角用 `leader` 注 C1，同样的有几处就写 n×C1。
- **尺寸**：链式或基线式，不要重复标注，也不要标成封闭尺寸链；同一方向的尺寸排在同一侧，小尺寸在里、大尺寸在外。
- 标题栏写图名、图号、比例、材料、设计人和日期；技术要求放在图面左下方的空白处。
- **装配图剖面线**（GB/T 4457.5、GB/T 4459.7）：相邻零件方向相反，或方向一致而间距不同；同一零件在各视图（含局部放大图）方向、间距一致。金属用 45° 细实线（ANSI31），非金属用交叉网格（ANSI37）；图上宽 ≤2 mm 的剖面允许涂黑，相邻两块涂黑之间留 ≥0.7 mm。实心件（轴、键、销、螺栓、连杆）纵剖和外购件不画剖面线；滚动轴承内外圈剖面线可以一致，滚动体不画。做法：`unhatch` → `hatch_material` → `stagger_hatches`（§2.4）。
- **装配图里的齿轮**（GB/T 4459.2）：非圆外形视图齿顶线粗实线、分度线点画线、齿根线不画；啮合区两轮的齿顶线都不画，分度线画一根粗实线。过轴线剖开时轮齿按不剖，啮合区一个齿轮的齿顶线画粗实线，另一个被挡住的画虚线或不画（`gear_teeth` 的 `hidden`）。圆视图齿顶圆粗实线、分度圆点画线（两轮相切）、齿根圆不画。装配模型按分度圆柱建，出图后用 `gear_side` / `gear_arc` 改（§2.4）。

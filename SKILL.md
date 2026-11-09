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
│   ├── sw_std.py       标准件：从 Toolbox GB 基础零件生成指定规格（螺栓/螺母/垫圈/键/销/轴承）+ 放进装配
│   ├── config.json     标题栏默认值（学校、班级、设计人）—— 换环境只改这里
│   └── com_filter.py   COM 消息过滤器（忙时自动重试）
└── examples/
    ├── reducer/  build_parts → build_asm → views → reducer_gb；零件图/ 输出轴、大齿轮   成套图纸（§2.5）
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

- **AutoCAD 2024**：`C:\Program Files\Autodesk\AutoCAD 2024\acad.exe`，COM 名 `AutoCAD.Application(.24)`，有 `gbenor.shx` / `gbcbig.shx`。
- **SolidWorks 2025**：默认 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe`（装在别处设环境变量 `SW_EXE`，AutoCAD 同理 `ACAD_EXE`），COM 名 `SldWorks.Application`（rev 33）。国标模板在 `C:\ProgramData\SolidWorks\SOLIDWORKS 2025\templates\gb_*.prtdot / drwdot`。基准面名称是中文（前视基准面…）。
- **Python 3.12** + pywin32 + PyMuPDF（fitz）+ ezdxf + shapely装在**用户目录 site-packages**。**不要用 `python -I`**，否则 import 失败。
- 写 JSON 时 Windows 下 `open(..., "w")` 默认是 GBK，要写 `encoding="utf-8"`。
- 截屏或 numpy 报 *OpenBLAS Memory allocation failed* 时，设环境变量 `OPENBLAS_NUM_THREADS=1`。

## 1. 选型

| 需求 | 做法 |
|---|---|
| 2D 零件图、装配图 | **sw_views + sw2acad**。SW 只出投影，AutoCAD 里纯 COM 整理标注。见 §2 |
| 3D 零件、装配、干涉检查 | **SolidWorks MCP**（`solidworks_*` 工具，见记忆 solidworks-mcp），或 `sw_part.py`。见 §3 |
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
| `title({占位符: 值})` | 只在 `own_frame=False`（沿用 SW 模板图框）时用 |
| `notes([条目], p=(40,80))` | 技术要求 |
| `s.layer(名)`、`s.ms` | 直接用 AutoCAD COM 加别的东西，比如"其余"两个字 |

`half_dia(..., frac=0.55)`：字中点离圆心 frac×r，同心圆多时调它让字落在两圆之间；文字是普通 TEXT，写不了叠写偏差。

### 2.5 成套图纸：装配图 + 零件图（范例 `examples/reducer/`，2026-11-08 一级圆柱齿轮减速器）

1. `build_parts.py`：零件都在**全局坐标**里建（输入轴 X=0、输出轴 X=100、结合面 Y=0、轴线沿 Z），装配时只平移/旋转不加配合。键槽：`shaft_keyway` / `hub_keyway`（草图画在过轴线的基准面上，`sw_part.cut_offset` 从槽底开始切，见 §3）。
2. `build_asm.py`：`sw_std.make` 生成标准件（3 个平键、4 组 M10×40 螺栓 + 垫圈 + 螺母），`sw_std.place` 按"零件轴线 → 装配方向 + 参考点 → 装配点"放好；大齿轮绕自身轴线转 −90° 让轮毂键槽对上轴上的键（变换矩阵行向量约定）。标准件信息（代号、规格、材料、质量）写 `std.json` 给明细栏。干涉检查（MCP `solidworks_check_interference`）只剩螺栓和螺母的螺纹重叠（每组约 193 mm³ = 大径与螺母小径之间那圈，正常）。
3. `views.py` + `reducer_gb.py`：装配图 A2 1:2。键在 A-A 里纵剖、`unhatch` 去剖面线并删 SW 在键圆头处加的中心符号；明细栏行 `std_row(...)` 从 std.json 生成（`GB/T 1096 键 12×8×32`…），总重 = 零件 + 标准件；螺栓组用 `balloon_group`；轴伸直径挪到左视图（A-A 里轴伸太窄、还有键挡着）。
4. `零件图/输出轴*.py`：主视图 `*右视`（键槽正对观察者），两个移出断面放在剖切线延长线上（不对称：画箭头、省略字母）；直径竖直标、文字压轴线的断开点画线；轴向尺寸 `auto_dims` 自动分排；基准 A/B 在两个轴颈、三角形和直径尺寸线对齐；圆跳动指向表面。
5. `零件图/大齿轮*.py`：主视图 = 过轴线全剖（对称面、按投影关系配置，剖切符号和 A-A 都不标）+ 圆视图；`gear_teeth` / `gear_circles`；左边一排直径 `auto_dims`；孔 Φ40H7 有键槽只能 `half_dia`、基准 A 三角形和它对齐；键槽宽 12JS9、槽深 43.3；参数表 `table`。
6. 每张图 `check()` 0 处再交。改零件尺寸时：`build_parts → build_asm → views + 各零件 *_views → 各 drawing`。

还没做的：箱座、箱盖、齿轮轴、套筒、端盖的零件图（同样的路子）；装配图的标注坐标还是 `sx()/sy()` 手推的，没改成 `view_affine`。

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
| 旧时间戳 PDF 越积越多、删不掉 | 原因是 AutoCAD 打印完自动用 WPS 打开、锁住文件。现在用 `DWG To PDF NoView.pc3`（`acad_common.ensure_pdf_pc3()` 复制 DWG To PDF.pc3、只把 View_New_File 改成 FALSE、按 adler32 重写文件头），打印完不再打开；`Sheet` 退出时删掉同名的旧时间戳 PDF（留最新的出图和校核图）。新生成的 pc3 要先 `RefreshPlotDeviceInfo` 再设，否则 Invalid input |

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
| **SolidWorks 进程私有内存涨到 15 GB**，接着 AutoCAD 打开文档失败、OpenBLAS 报内存不够（2026-11-08，连续建零件/装配/出 6 张工程图之后） | SW 关了文档也不怎么释放。一批 SW 工作做完、转去 AutoCAD 前：`sw.CloseAllDocuments(True); sw.ExitApp()`，下次 `connect()` 自动重开。跑之前可以看一眼 `Get-Process SLDWORKS` 的 PrivateMemorySize |
| 斜视图上做局部剖：`CreateBreakOutSection` 返回成功，可视图里什么都没变 | 实测（整个视图框都圈上也一样）。斜视图上别用局部剖；要"半边剖开"就做全剖再 `clip_hatch` |
| 装配干涉检查报螺栓和螺母各重叠约 193 mm³ | 螺栓按大径建、螺母按小径建，旋合段的那一圈。正常，不用改 |

## 5. 画法规范（国标要点）

- **第一角画法**：俯视图在主视图下方，左视图在主视图右侧。
- 孔要画十字中心线（超出圆约 5）；看不见的轮廓用虚线层；剖视图用 ANSI31 剖面线。
- **剖视图 = 被剖到的实体（加剖面线）+ 剖切面后所有看得见的轮廓线。** 最常漏的是孔或槽两端在剖视图上的端面竖线：空心件全剖时，上下两块实体之间必须用端面线连起来，否则看起来像两块分开的板。画完后自问："这根孔/槽的两头，在这个视图里看得见边线吗？"
- 端视图上，外倒角会多出一个圆（例如 C1 时是 Φ(D−2)）。
- 回转体的直径（Φ）标在非圆视图上；倒角用 `leader` 注 C1，同样的有几处就写 n×C1。
- **尺寸**：链式或基线式，不要重复标注，也不要标成封闭尺寸链；同一方向的尺寸排在同一侧，小尺寸在里、大尺寸在外。
- 标题栏写图名、图号、比例、材料、设计人和日期；技术要求放在图面左下方的空白处。

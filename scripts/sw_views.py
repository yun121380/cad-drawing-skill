"""sw_views —— 让 SolidWorks 只负责投影：国标模板、1:1、开自动中心线，不标任何尺寸，导出 DWG/DXF/PDF。

后续在 AutoCAD 里用 sw2acad.Sheet 整理和标注。坐标单位：本模块对外一律用 mm（图纸坐标）。

    import sw_views as V
    sw = V.connect()
    drw = V.new_drawing(sw, "A3")
    v1 = V.model_view(drw, part, "*前视", (300, 175))          # 圆视图/主视图
    sv = V.section(drw, v1, (0, 75), (0, -75), (140, 175))      # 剖切线在 v1 的视图坐标里（模型原点为 0,0）
    V.finish(drw, [v1, sv])                                      # 1:1 生效 + 去切边 + 打印各视图外框
    V.export(drw, r"...\name")                                   # name.SLDDRW/.DWG/.DXF/.PDF
    V.dump_dxf(r"...\name.DXF", views)                           # 列出视图区内的粗线坐标、圆、圆弧，供标注取点
"""
import os
import pythoncom
import win32com.client as wc

TPL = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2025\templates\gb_%s.drwdot"
SW_EXE = os.environ.get("SW_EXE", r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe")   # 装在别处就设环境变量 SW_EXE


def _none():
    return wc.VARIANT(pythoncom.VT_DISPATCH, None)


def _ref_i4():
    return wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def connect():
    import time
    try:
        return wc.GetActiveObject("SldWorks.Application")
    except Exception:
        os.startfile(SW_EXE)
        for _ in range(60):
            time.sleep(3)
            try:
                return wc.GetActiveObject("SldWorks.Application")
            except Exception:
                pass
    raise RuntimeError("SolidWorks 启动超时")


def close_drawings(sw):
    d = sw.GetFirstDocument; docs = []
    while d:
        docs.append(d); d = d.GetNext
    for d in docs:
        if d.GetType == 3:           # swDocDRAWING
            sw.CloseDoc(d.GetTitle)


_SCALE = {}


def _sheet_scale(drw, scale=None):
    """scale=(1,2) 表示 1:2。记在 _SCALE 里，finish() 再设一次时沿用。"""
    key = drw.GetTitle
    scale = scale or _SCALE.get(key, (1, 1)); _SCALE[key] = scale
    sh = drw.GetCurrentSheet; pr = list(sh.GetProperties2)
    # [纸张, 模板, 比例分子, 比例分母, 第一角, 宽, 高, 同自定义]
    sh.SetProperties2(int(pr[0]), int(pr[1]), float(scale[0]), float(scale[1]), True, pr[5], pr[6], bool(pr[7]))


def new_drawing(sw, size="A3", scale=(1, 1)):
    """关掉旧工程图，按国标模板新建，开自动中心符号/中心线，第一角。scale=(1,2) 即 1:2。
    非 1:1 时 sw2acad.Sheet 要传 view_scale=2，尺寸才会按实际大小显示。"""
    close_drawings(sw)
    drw = sw.NewDocument(TPL % size.lower(), 0, 0, 0)
    for t in (189, 190, 308):        # 自动中心符号 / 自动中心线 / 孔中心符号
        drw.Extension.SetUserPreferenceToggle(t, 0, True)
    for t in (309, 448):             # 圆角不加中心符号（国标不画；不关的话每个铸造圆角圆心都有个十字）
        drw.Extension.SetUserPreferenceToggle(t, 0, False)
    _sheet_scale(drw, scale)
    return drw


def model_view(drw, part_path, view="*前视", at=(300, 175)):
    """命名视图：*前视 *后视 *左视 *右视 *上视 *下视 *等轴测。at 为视图中心（图纸 mm）。"""
    v = drw.CreateDrawViewFromModelView3(part_path, view, at[0] / 1000, at[1] / 1000, 0)
    if v is None:
        raise RuntimeError(f"建视图失败：{part_path} {view}")
    return v


def projected(drw, parent, at):
    """从 parent 投影一个视图（第一角：放右边=左视图，放下面=俯视图）。"""
    drw.ClearSelection2(True)
    drw.Extension.SelectByID2(parent.Name, "DRAWINGVIEW", 0, 0, 0, False, 0, _none(), 0)
    v = drw.CreateUnfoldedViewAt3(at[0] / 1000, at[1] / 1000, 0, False)
    if v is None:
        raise RuntimeError("投影视图失败")
    return v


def _orient(parent, pts, at):
    """SW 的剖切箭头实测总在剖切线走向（p1→p2）的右侧，箭头指向哪边就从哪边看过去。第一角画法里
    剖视图应放在箭头所指的那一侧，否则视图上下/左右翻转（“从俯视图往上剖主视图倒过来”就是这个原因）。
    这里按 at 相对父视图中心的方向，必要时把点序反过来，让箭头指向 at。"""
    ol = parent.GetOutline
    cx, cy = (ol[0] + ol[2]) / 2 * 1000, (ol[1] + ol[3]) / 2 * 1000
    vx, vy = at[0] - cx, at[1] - cy
    dx, dy = pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]
    if len(pts) > 2:                                  # 阶梯剖：用第一段剖切段的走向
        dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
    return list(reversed(pts)) if dy * vx - dx * vy < 0 else list(pts)


def section(drw, parent, p1, p2, at, label="A", surface_only=False, aligned=True, look=None):
    """全剖（2026-11-08 起自动定向：箭头指向剖视图所在一侧，第一角画法不会再翻转）。
    surface_only=True：只画剖面 = 断面图（移出断面，选项 32）；aligned=False：不和父视图对齐，可以随便放（选项 1）。
    look=(x,y)（图纸坐标）：箭头朝它那一侧，不给就朝 at。移出断面放在剖切线延长线上时 at 正好在线上、分不出左右，
    要用 look 指定投射方向。"""
    p1, p2 = _orient(parent, [p1, p2], look or at)
    opt = (32 if surface_only else 0) | (0 if aligned else 1)
    drw.ActivateView(parent.Name)
    ln = drw.SketchManager.CreateLine(p1[0] / 1000, p1[1] / 1000, 0, p2[0] / 1000, p2[1] / 1000, 0)
    ln.Select4(False, _none())
    v = drw.CreateSectionViewAt5(at[0] / 1000, at[1] / 1000, 0, label, opt, _none(), 0)
    if v is None:
        raise RuntimeError("剖视图失败（剖切线是否穿过零件？坐标是视图坐标不是图纸坐标）")
    return v


def step_section(drw, parent, pts, at, label="A"):
    """阶梯剖（2026-11-08 实测可用）：pts 是折线各点（视图坐标），剖切段和转折段交替、互相垂直，
    如 [(-75,20),(0,20),(0,-20),(75,-20)]。箭头自动指向 at 一侧。转折处国标不画线，SW 也不画。"""
    pts = _orient(parent, pts, at)
    drw.ClearSelection2(True); drw.ActivateView(parent.Name)
    segs = [drw.SketchManager.CreateLine(a[0] / 1000, a[1] / 1000, 0, b[0] / 1000, b[1] / 1000, 0)
            for a, b in zip(pts, pts[1:])]
    drw.ClearSelection2(True)
    for i, s in enumerate(segs):
        s.Select4(i > 0, _none())
    v = drw.CreateSectionViewAt5(at[0] / 1000, at[1] / 1000, 0, label, 2, _none(), 0)
    if v is None:
        raise RuntimeError("阶梯剖失败")
    return v


def aligned_section(drw, parent, end_main, center, end_rot, at, label="A"):
    """【不是国标旋转剖，别直接交】两段相交剖切线（选项 0）SW 出的其实是“投影的阶梯剖”：两段剖切面上的
    剖面都画出来了，但倾斜那段没有转到投影面上，而是被投影缩短（实测摇臂斜臂孔心在 X=-52，真长应是 60；
    IDrSection.IsAligned 也返回 False）。国标旋转剖要用拼接法：见 SKILL.md §2.2 和 examples/rot_oblique/。
    这个函数留着做对照：按 end_main→center 走向判断箭头，不指向 at 时加选项 4 翻过来，否则视图上下颠倒。"""
    ol = parent.GetOutline
    cx, cy = (ol[0] + ol[2]) / 2 * 1000, (ol[1] + ol[3]) / 2 * 1000
    dx, dy = center[0] - end_main[0], center[1] - end_main[1]
    flip = (dy * (at[0] - cx) - dx * (at[1] - cy)) < 0
    drw.ClearSelection2(True); drw.ActivateView(parent.Name)
    sm = drw.SketchManager
    s1 = sm.CreateLine(end_main[0] / 1000, end_main[1] / 1000, 0, center[0] / 1000, center[1] / 1000, 0)
    s2 = sm.CreateLine(center[0] / 1000, center[1] / 1000, 0, end_rot[0] / 1000, end_rot[1] / 1000, 0)
    drw.ClearSelection2(True)
    s1.Select4(False, _none()); s2.Select4(True, _none())
    v = drw.CreateSectionViewAt5(at[0] / 1000, at[1] / 1000, 0, label, 4 if flip else 0, _none(), 0)
    if v is None:
        raise RuntimeError("旋转剖失败（两段剖切线都要穿过实体，交点一般取回转中心）")
    return v


def auxiliary(drw, parent, direction, at, label="A", pick=None, flip=False, aligned=False):
    """斜视图（向视图）：沿垂直于父视图里某条直线边的方向投影。direction=(dx,dy,dz) 是那条模型边的方向
    （模型坐标），pick=(x,y,z) 可选，用来在多条同向边里挑离它最近的。
    aligned=True 时 SW 只让它待在投影方向上（箭头所指一侧，常常压在主视图上，实测）；默认 aligned=False，
    放在 at，国标叫“移位配置”，父视图上的箭头 + 字母、斜视图上方的“X”标注都要有（SW 会出，标签在 AutoCAD 里改成单个字母）。"""
    import math
    edges = parent.GetVisibleEntities2(_none(), 1) or []         # 零件视图组件参数传空 VARIANT，传 None 报类型不匹配
    dn = math.sqrt(sum(c * c for c in direction)); d = [c / dn for c in direction]
    best, score = None, None
    for e in edges:
        try:
            a = e.GetStartVertex.GetPoint; b = e.GetEndVertex.GetPoint
        except Exception:
            continue
        v = [b[i] - a[i] for i in range(3)]; L = math.sqrt(sum(c * c for c in v))
        if L < 1e-6 or abs(sum(v[i] / L * d[i] for i in range(3))) < 0.999:
            continue
        sc = 0 if pick is None else min(math.dist([p * 1000 for p in a], pick), math.dist([p * 1000 for p in b], pick))
        if score is None or sc < score:
            best, score = e, sc
    if best is None:
        raise RuntimeError("父视图里没找到这个方向的直线边")
    drw.ClearSelection2(True)
    drw.ActivateView(parent.Name)
    parent.SelectEntity(best, False)
    v = drw.CreateAuxiliaryViewAt2(at[0] / 1000, at[1] / 1000, 0, not aligned, label, True, flip)
    if v is None:
        raise RuntimeError("斜视图失败")
    return v


def broken_out_poly(drw, view, pts, depth):
    """局部剖，边界是直线多边形（不是样条）：做“半边剖开”用，比如旋转剖拼接里实心轮毂的两半——
    矩形一条边压在回转轴线上，剖面线就止于轴线，拼接时不用裁剖面线。pts 为视图坐标。"""
    drw.ClearSelection2(True)
    drw.ActivateView(view.Name)
    sm = drw.SketchManager
    segs = [sm.CreateLine(a[0] / 1000, a[1] / 1000, 0, b[0] / 1000, b[1] / 1000, 0)
            for a, b in zip(pts, list(pts[1:]) + [pts[0]])]
    drw.ClearSelection2(True)
    for i, s in enumerate(segs):
        s.Select4(i > 0, _none())
    if not drw.CreateBreakOutSection(depth / 1000):
        raise RuntimeError("局部剖失败")


def view_depth(view, part_doc, p_plane):
    """该视图里，零件最靠近观察者的点到“过 p_plane、平行于图面”的平面的距离（mm）= 局部剖要给的深度。
    用 ModelToViewTransform 的第三列当视线方向，Body2.GetExtremePoint 求零件在这个方向上的极点。"""
    import numpy as np
    a = view.ModelToViewTransform.ArrayData
    w = np.array([a[2], a[5], a[8]])                 # 模型方向 → 视图 z（朝观察者）
    best = None
    for b in part_doc.GetBodies2(0, True):
        for sgn in (1, -1):
            r = b.GetExtremePoint(*[float(c) for c in sgn * w])     # 返回 (True, x, y, z)，第一个是成功标志（实测）
            z = np.dot(np.array(r[-3:]) * 1000, w)
            best = z if best is None else max(best, z)
    return best - np.dot(np.array(p_plane, float), w)


def view_affine(view):
    """视图的“模型 mm → 图纸 mm”仿射：{"o": 模型原点的图纸坐标, "ex"/"ey"/"ez": 模型 +1 mm 在图纸上的位移}。
    写进 layout.json，AutoCAD 那边用 sw2acad.mapper(aff) 变回函数 M(x, y, z)，标注点全按模型坐标写。"""
    o = model_to_sheet(view, (0, 0, 0))
    d = lambda p: [a - b for a, b in zip(model_to_sheet(view, p), o)]
    return {"o": list(o), "ex": d((1, 0, 0)), "ey": d((0, 1, 0)), "ez": d((0, 0, 1))}


def model_to_sheet(view, p):
    """模型坐标 (mm) → 图纸坐标 (mm)。用 view.ModelToViewTransform：[x y z]·R·scale + T（实测按行向量乘，
    斜视图里孔中心算出来和 DXF 里的圆心对上，2026-11-08）。斜视图、旋转过的视图都能用。"""
    a = view.ModelToViewTransform.ArrayData
    x, y, z = (c / 1000 for c in p)
    k = a[12]
    sx = (x * a[0] + y * a[3] + z * a[6]) * k + a[9]
    sy = (x * a[1] + y * a[4] + z * a[7]) * k + a[10]
    return sx * 1000, sy * 1000


def sheet_to_view(view, q):
    """图纸坐标 → 该视图的草图坐标（在视图里画剖切线、局部剖边界、裁剪边界用）：以 view.Position 为原点、除以视图比例。"""
    px, py = view.Position
    s = view.ScaleDecimal
    return (q[0] - px * 1000) / s, (q[1] - py * 1000) / s


def crop(drw, view, pts):
    """把视图裁成局部视图（局部斜视图/局部视图）：pts 为闭合边界（视图坐标），画成闭合样条后 Crop。
    边界在 AutoCAD 里是细实线样条 = 波浪线；如果局部结构本身外形封闭，可以在 AutoCAD 里把波浪线删掉。"""
    drw.ClearSelection2(True)
    drw.ActivateView(view.Name)
    arr = []
    for x, y in list(pts) + [pts[0]]:
        arr += [x / 1000, y / 1000, 0.0]
    spl = drw.SketchManager.CreateSpline2(wc.VARIANT(0x2005, arr), True)
    drw.ClearSelection2(True)
    spl.Select4(False, _none())
    r = view.Crop2(False, False, 0)
    return r


def detail(drw, parent, center, r, at, scale=(2, 1), label="I"):
    """局部放大图。center/r 是 parent 视图坐标里的圆（模型 mm，原点=视图中心），at 是放大图位置（图纸 mm）。
    CreateDetailViewAt4(X,Y,Z, Style=0 标准, Scale1, Scale2, Label, Showtype=1 圆, FullOutline, Jagged, NoOutline, Intensity)。"""
    drw.ClearSelection2(True)
    drw.ActivateView(parent.Name)
    c = drw.SketchManager.CreateCircleByRadius(center[0] / 1000, center[1] / 1000, 0, r / 1000)
    drw.ClearSelection2(True)
    c.Select4(False, _none())
    v = drw.CreateDetailViewAt4(at[0] / 1000, at[1] / 1000, 0, 0, float(scale[0]), float(scale[1]), label, 1,
                                False, False, False, 0)
    if v is None:
        raise RuntimeError("局部放大图失败")
    return v


def view_half_extent(view):
    """视图里零件的半宽、半高（模型 mm，即视图坐标）。视图坐标原点 = 视图中心 = 零件外框中心。"""
    ol = view.GetOutline
    k = 1000.0 / view.ScaleDecimal
    return (ol[2] - ol[0]) / 2 * k, (ol[3] - ol[1]) / 2 * k


def broken_out(drw, view, pts, depth):
    """局部剖（2026-11-08 实测可用）。pts：闭合边界的点（view 的视图坐标，模型 mm，原点=视图中心），
    不用首尾重复，画成闭合样条 —— 导出后是细实线 SPLINE，正好是国标的波浪线（只画在零件实体内）。
    depth：从这个视图里零件**最前面**往里剖多深（mm）。例：零件 Z -50..50、前视图要剖到 Z=0，就是 50。
    边界里被剖到的实体自动打剖面线，孔/槽自动露出来；同一个视图可以做多处。"""
    drw.ClearSelection2(True)
    drw.ActivateView(view.Name)
    arr = []
    for x, y in list(pts) + [pts[0]]:
        arr += [x / 1000, y / 1000, 0.0]
    spl = drw.SketchManager.CreateSpline2(wc.VARIANT(0x2005, arr), True)
    drw.ClearSelection2(True)
    spl.Select4(False, _none())
    if not drw.CreateBreakOutSection(depth / 1000):
        raise RuntimeError("局部剖失败（边界要闭合、要落在零件上；depth 不能超出零件厚度）")


def half_section(drw, view, depth, side="right", axis=0.0, margin=15):
    """半剖（2026-11-08 实测可用）：在**原视图上**做一个矩形局部剖 —— 一条边压在对称线上，另三边伸出零件外，
    深度剖到对称面。所以不生成新视图、不出剖切符号和 "A-A"（国标：剖切面是对称面且视图按投影关系配置时不标注）。
    side：right/left（对称线竖直，axis 是对称线的视图 x）或 top/bottom（对称线水平，axis 是视图 y）。
    国标习惯：对称线竖直时剖右半，水平时剖下半（或上半）。depth 同 broken_out：零件最前面到对称面的距离。
    矩形压在对称线上的那条边导出为细实线，要在 AutoCAD 里用 Sheet.to_center(p1, p2) 改成中心线。

    SW 自带的 L 形剖切线半剖（两段相连的垂直线、Options=0）也试过：它总以**竖直**那段为剖切面、剖视图水平摆放，
    只有“父视图是侧视图、竖段从上方外面画到中心、再横着向右”这一种画法得到正立的上半剖，其他画法出来是
    残缺的 1/4、镜像或叠在父视图上；Options=2（阶梯剖）出来是全剖。所以统一用这里的局部剖做法。"""
    hw, hh = view_half_extent(view)
    hw += margin; hh += margin
    if side == "right":
        x0, y0, x1, y1 = axis, -hh, hw, hh
    elif side == "left":
        x0, y0, x1, y1 = -hw, -hh, axis, hh
    elif side == "top":
        x0, y0, x1, y1 = -hw, axis, hw, hh
    elif side == "bottom":
        x0, y0, x1, y1 = -hw, -hh, hw, axis
    else:
        raise ValueError(side)
    drw.ClearSelection2(True)
    drw.ActivateView(view.Name)
    sm = drw.SketchManager
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    segs = [sm.CreateLine(a[0] / 1000, a[1] / 1000, 0, b[0] / 1000, b[1] / 1000, 0)
            for a, b in zip(corners, corners[1:] + corners[:1])]
    drw.ClearSelection2(True)
    for i, s in enumerate(segs):
        s.Select4(i > 0, _none())
    if not drw.CreateBreakOutSection(depth / 1000):
        raise RuntimeError("半剖失败（depth 是否超出零件？）")


def hidden_lines(view, on=True):
    """视图显示不可见轮廓（虚线）。国标里只在表达不清时才画虚线，按需开。"""
    view.SetDisplayMode3(False, 1 if on else 2, False, True)   # swHIDDEN_GREYED / swHIDDEN


def finish(drw, views):
    """比例要在建完视图后再设一次才生效；国标不画圆角切边。返回各视图外框（图纸 mm）。"""
    _sheet_scale(drw)
    for v in views:
        v.SetDisplayTangentEdges2(0)
    drw.ForceRebuild3(False)
    boxes = {}
    for v in views:
        ol = [round(x * 1000, 2) for x in v.GetOutline]
        boxes[v.Name] = ol
        print(v.Name, "外框 mm", ol)
    return boxes


def _release_in_autocad(path):
    """上一轮 sw2acad 把同名 DWG 开在 AutoCAD 里，SW 就覆盖不了（WinError 32）。
    SDI=1 下不能关唯一的文档，用 New 一个空白图把它顶掉；多文档时直接 Close。"""
    try:
        a = wc.GetActiveObject("AutoCAD.Application")
        a.Documents.Count                       # ROT 里可能是已退出/还在启动的 AutoCAD（实测 AttributeError）
    except Exception:
        return
    import time
    for i in range(a.Documents.Count):
        d = a.Documents.Item(i)
        if d.FullName.lower() == os.path.abspath(path).lower():
            if a.Documents.Count > 1:
                d.Close(False)
            else:
                try:
                    d.SendCommand("(command \"_.NEW\" \".\")\n")    # SDI=1 下也安全：新图替换当前图（不保存）
                except Exception:
                    pass
            for _ in range(30):
                time.sleep(0.5)
                try:
                    open(path, "ab").close(); return
                except OSError:
                    pass
            return


def export(drw, out_noext, exts=("SLDDRW", "DWG", "DXF", "PDF")):
    """导出。旧文件先删掉：同名 DWG 被别的进程占着时 SaveAs 会返回 False（错误码 1）。
    DWG/DXF 一律按图纸尺寸输出（swDxfOutputNoScale=0），否则非 1:1 的图会被放大回模型尺寸、图框也跟着放大。"""
    sw = wc.GetActiveObject("SldWorks.Application")
    old = sw.GetUserPreferenceIntegerValue(136)
    sw.SetUserPreferenceIntegerValue(136, 0)
    try:
        for e_ in exts:
            p = out_noext + "." + e_
            if e_.upper() == "DWG":
                _release_in_autocad(p)
            if os.path.exists(p):
                os.remove(p)
            e, w = _ref_i4(), _ref_i4()
            ok = drw.Extension.SaveAs(p, 0, 1, _none(), e, w)
            if not ok:
                raise RuntimeError(f"导出 {p} 失败，错误码 {e.value}")
    finally:
        sw.SetUserPreferenceIntegerValue(136, old)
    print("导出", out_noext, exts, "| swDxfOutputNoScale 原值", old)


def dump_dxf(dxf_path, views):
    """列出每个视图框内的粗实线端点 x/y 集合、圆、圆弧，作为 AutoCAD 里标注取点的依据。"""
    import ezdxf
    msp = ezdxf.readfile(dxf_path).modelspace()
    inside = lambda x, y, b: b[0] <= x <= b[2] and b[1] <= y <= b[3]
    for b in views:
        xs, ys = set(), set()
        print(f"== 视图框 {b}")
        for e in msp:
            t = e.dxftype()
            if t == "LINE" and e.dxf.get("lineweight") == 25:
                s, f = e.dxf.start, e.dxf.end
                if inside(s.x, s.y, b) and inside(f.x, f.y, b):
                    xs.update([round(s.x, 2), round(f.x, 2)]); ys.update([round(s.y, 2), round(f.y, 2)])
            elif t in ("CIRCLE", "ARC") and inside(e.dxf.center.x, e.dxf.center.y, b):
                extra = f" {e.dxf.start_angle:.1f}→{e.dxf.end_angle:.1f}°" if t == "ARC" else ""
                print(f"  {t} 圆心 ({e.dxf.center.x:.2f}, {e.dxf.center.y:.2f}) R{e.dxf.radius:.3f}{extra}")
        print("  粗线 x:", sorted(xs)); print("  粗线 y:", sorted(ys))

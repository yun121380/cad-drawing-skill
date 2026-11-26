"""一级圆柱齿轮减速器装配图（A2 1:2）：主视图 + A-A（沿结合面剖切，拆去箱盖）+ 左视图，明细栏、序号、配合尺寸。
2026-11-08 改版：所有标注点都按**模型坐标**写（全局坐标：X 沿两轴连线，输入轴 X=0、输出轴 X=100；Y 向上，结合面 Y=0；
Z 沿轴线，输入轴伸出端 +Z），经 views.py 写的 reducer_layout.json（各视图仿射）换算到图纸——改零件尺寸、挪视图都不用改这里。
零件序号用 auto_balloons 自动排。旧的手算坐标版留在 reducer_gb_old.py.bak。
齿轮 m=2.5：小齿轮 da 55 df 43.75 d 50；大齿轮 da 155 df 143.75 d 150；齿宽 45 / 40。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from sw2acad import Sheet, P, retry, mapper

D = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(D, "reducer_layout.json"), encoding="utf-8"))
F, T, LV = mapper(L["front"]), mapper(L["top"]), mapper(L["left"])      # 主视图 / A-A / 左视图：模型 (X,Y,Z) → 图纸
BF, BT, BL = L["boxes"]["front"], L["boxes"]["top"], L["boxes"]["left"]
VIEWS = [tuple(v) for v in L["VIEWS"]]
VIEWS = [(BF[0] - 20, BF[1] - 3, BF[2] + 3, BF[3] + 3), (BT[0] - 20, BT[1] - 3, BT[2] + 3, BT[3] + 3),
         (BL[0] - 3, BL[1] - 3, BL[2] + 3, BL[3] + 3)]
STD = json.load(open(os.path.join(D, "models", "std.json"), encoding="utf-8"))   # build_asm.py 写的标准件信息


def std_row(k, qty):
    v = STD[k]
    name = {"key": "键", "bolt": "螺栓", "washer": "垫圈", "nut": "螺母"}[v["kind"]] + " " + v["规格"]
    return (v["代号"].split("-")[0], name, qty, v["材料"], f"{v['质量kg'] * qty:.3f}".rstrip("0"), "")


PARTS_KG = [11.02, 4.41, 1.17, 2.77, 1.29, 0.06, 0.19 * 2, 0.28 * 2, 0.53, 0.46, 0.65, 0.56]
sx = lambda X: T(X, 0, 0)[0]              # A-A 里的横坐标 / 纵坐标（轮齿规定画法用）
sy = lambda Z: T(0, 0, Z)[1]

with Sheet(D + r"\reducer_sw.DWG", D + r"\减速器装配图.dwg", views=VIEWS, sheet="A2", view_scale=2) as s:
    s.frame()
    total = sum(PARTS_KG) + sum(STD[k]["质量kg"] * q for k, q in
                                (("key_out", 1), ("key_ext", 1), ("key_in", 1), ("bolt", 4), ("washer", 4), ("nut", 4)))
    top = s.title_block("一级圆柱齿轮减速器", "JSQ-00", scale="1:2", weight=f"{total:.1f}",
                        designer="", date="2026.11")
    s.bom([("JSQ-01", "箱座", 1, "HT200", "11.02", ""),
           ("JSQ-02", "箱盖", 1, "HT200", "4.41", ""),
           ("JSQ-03", "齿轮轴", 1, "45", "1.17", "z=20"),
           ("JSQ-04", "大齿轮", 1, "45", "2.77", "z=60"),
           ("JSQ-05", "输出轴", 1, "45", "1.29", ""),
           ("JSQ-06", "套筒", 1, "Q235A", "0.06", ""),
           ("GB/T 276", "滚动轴承 6206", 2, "", "0.19", ""),
           ("GB/T 276", "滚动轴承 6207", 2, "", "0.28", ""),
           ("JSQ-07", "输入轴闷盖", 1, "HT150", "0.53", ""),
           ("JSQ-08", "输入轴透盖", 1, "HT150", "0.46", ""),
           ("JSQ-09", "输出轴闷盖", 1, "HT150", "0.65", ""),
           ("JSQ-10", "输出轴透盖", 1, "HT150", "0.56", ""),
           std_row("key_out", 1), std_row("key_ext", 1), std_row("key_in", 1),
           std_row("bolt", 4), std_row("washer", 4), std_row("nut", 4)], origin=top)

    # ---- 视图名；模板分区字母
    s.move_label("A-A", (BT[0] + 30, BT[3] + 8))
    for e in s._items():
        if e.ObjectName in ("AcDbMText", "AcDbText") and retry(lambda: e.InsertionPoint)[0] < 25:
            e.Delete()

    # ---- 剖面线：实心轴纵剖不画；钢球不画；相邻零件剖面线方向/间距错开
    s.unhatch(T(0, 0, 101.5))                 # 齿轮轴伸出段
    s.unhatch(T(100, 0, -108.5))              # 输出轴伸出段
    for X, rc, Z in ((0, 23, 41), (0, 23, -41), (100, 26.75, 41.5), (100, 26.75, -41.5)):   # 轴承钢球
        for sg in (1, -1):
            s.unhatch(T(X + sg * rc, 0, Z))
    g_lo, g_hi = sy(20), sy(-20)              # 大齿轮剖面线的上下边（齿宽 Z ±20）
    for e in s._items():
        if e.ObjectName != "AcDbHatch":
            continue
        mn, mx = retry(lambda: e.GetBoundingBox())
        w, h = mx[0] - mn[0], mx[1] - mn[1]
        if w < 2.2 and h > 7:                         # 轴承内外圈、套筒
            e.PatternScale = e.PatternScale * 0.5
            if h > 7.5: e.PatternAngle = 1.5708
            e.Evaluate()
        elif abs(mn[1] - g_lo) < 0.1 and abs(mx[1] - g_hi) < 0.1:
            e.PatternAngle = 1.5708; e.Evaluate()

    # ---- 轮齿规定画法（A-A）：齿顶线粗实线、分度线点画线；啮合区小齿轮齿顶线可见、大齿轮齿顶线画虚线
    zp, zg = 22.5, 20
    s.line((sx(-27.5), sy(zp)), (sx(-27.5), sy(-zp)), "粗实线")
    s.line((sx(27.5), sy(zp)), (sx(27.5), sy(-zp)), "粗实线")
    for z in (zp, -zp):
        s.line((sx(-27.5), sy(z)), (sx(-21.875), sy(z)), "粗实线")
        s.line((sx(21.875), sy(z)), (sx(27.5), sy(z)), "粗实线")
    s.line((sx(22.5), sy(zg)), (sx(22.5), sy(-zg)), "虚线")
    s.line((sx(177.5), sy(zg)), (sx(177.5), sy(-zg)), "粗实线")
    for z in (zg, -zg):
        s.line((sx(22.5), sy(z)), (sx(28.125), sy(z)), "虚线")
        s.line((sx(171.875), sy(z)), (sx(177.5), sy(z)), "粗实线")
    for X in (-25, 25, 175):
        s.line((sx(X), sy(zp) - 3), (sx(X), sy(-zp) + 3))
    # 主视图、左视图里的轴线（SW 中心符号只有短十字）
    for X in (0, 100):
        s.line(F(X, -53.5, 0), F(X, 52.5, 0))
    s.line(LV(0, 0, -140.5), LV(0, 0, 135.5))

    # ---- 键：纵剖按不剖画，删掉剖面线；删掉 SW 在圆头处加的中心符号
    for (X, Z), half in (((119, 1), (3, 9)), ((113.5, -102.5), (3, 12.5)), ((11.5, 100), (3, 11))):
        kc = T(X, 0, Z)
        s.unhatch(kc)
        for e in s._items():
            if e.Layer == "中心线" and e.ObjectName == "AcDbLine":
                a_, b_ = e.StartPoint, e.EndPoint
                if all(abs(q[0] - kc[0]) <= half[0] + 3 and abs(q[1] - kc[1]) <= half[1] + 3 for q in (a_, b_)):
                    e.Delete()

    # ---- 尺寸（A-A）
    s.dimlin(T(0, 0, 125), T(100, 0, 75), T(50, 0, 137.5), 0, "100%%P0.027")      # 中心距
    s.dimlin(T(-80, 0, 58), T(230, 0, 58), T(75, 0, 157.5))                        # 地脚孔距 310
    s.dimlin(T(-98, 0, 75), T(248, 0, 75), T(75, 0, 175.5))                        # 总长 346
    s.dimlin(T(230, 0, 58), T(230, 0, -58), T(263, 0, 0), 90)                      # 116
    s.dimlin(T(248, 0, 75), T(248, 0, -75), T(281, 0, 0), 90)                      # 150
    d = s.dimdia(T(-80, 0, 58), 9 * 0.5, 225, 0, "4×%%C18")                        # 地脚孔
    d.TextPosition = P(*T(-115, 0, 93.5))
    for X, r, Z, txt in ((0, 31, 34.3, "%%C62H7"), (0, 15, -34.7, "%%C30k6"), (100, 36, 34.3, "%%C72H7"),
                         (100, 17.5, -37.5, "%%C35k6")):
        s.dimlin(T(X - r, 0, Z), T(X + r, 0, Z), T(X, 0, Z), 0, txt)
    d40 = s.dimlin(T(80, 0, -8.5), T(120, 0, -8.5), T(100, 0, -8.5), 0, "%%C40H7/r6")
    # 两个轴伸直径标在左视图上（A-A 里轴伸太窄，还有键挡着）
    s.dimlin(LV(0, -12, 107.5), LV(0, 12, 107.5), LV(0, 0, 107.5), 90, "%%C24k6")
    s.dimlin(LV(0, -14, -108.5), LV(0, 14, -108.5), LV(0, 0, -108.5), 90, "%%C28k6")
    # 左视图：中心高、总高（右侧，输入轴伸出端一侧）；下方：两轴伸端总长
    s.dimlin(LV(0, -125, 75), LV(0, 0, 125), LV(0, -62.5, 156.5), 90)            # 中心高 125
    s.dimlin(LV(0, -125, 75), LV(0, 98, 0), LV(0, -13.5, 176.5), 90)             # 总高 223
    s.dimlin(LV(0, 0, 125), LV(0, 0, -130), LV(0, -141.5, 0))                     # 255

    # ---- 零件序号：给零件上一点（模型坐标），位置自动排（分到视图四周、排成一排、指引线不交叉）
    s.auto_balloons([(T(-85, 0, 17.5), 1), (T(-9, 0, -8.5), 3), (T(-35, 0, 65.5), 10), (T(-35, 0, -64.5), 9),
                     (T(-29, 0, -36.5), 7), (T(95, 0, -84.5), 5), (T(119.8, 0, -26.5), 6), (T(139, 0, -64.5), 12),
                     (T(134, 0, -36.5), 8), (T(139, 0, 65.5), 11), (T(147, 0, 0), 4),
                     (T(119, 0, -7), 13), (T(113.5, 0, -120.5), 14), (T(11.5, 0, 112), 15)],
                    box=BT, sides=("left", "top", "right", "bottom"))
    s.auto_balloons([(F(135, 46.5, 0), 2)], box=BF, sides=("top", "right"))
    s.balloon_group(F(-66, 15.1, 0), F(-101, 26.5, 0), [16, 17, 18][::-1])     # 自下而上：螺母、垫圈、螺栓

    s.notes(["技术特性：i=3，m=2.5，z1=20，z2=60，a=100。",
             "1. 装配前零件清洗干净，箱体内壁涂耐油油漆。",
             "2. 齿面接触斑点沿齿高不少于40%，沿齿长",
             "   不少于50%；齿侧间隙不小于0.10。",
             "3. 轴承轴向游隙0.05~0.10，用端盖调整。",
             "4. 结合面涂密封胶，不允许漏油；箱内加",
             "   L-CKC150 齿轮油至规定油面高度。",
             "5. 端盖螺钉图中从略。"], p=(BL[0], BT[3] + 3))
    print("断开轴线", s.break_center_under_text())
    print("断开键轮廓", s.break_center_under_text(layers=("中心线", "粗实线"), only=[d40]))
    s.check()

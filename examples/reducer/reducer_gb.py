"""一级圆柱齿轮减速器装配图（A2 1:2）：主视图 + A-A（沿结合面剖切，拆去箱盖）+ 左视图，明细栏、序号、配合尺寸。
坐标取自 reducer_sw.DXF（图纸 mm）：
  主视图：x = 112.5 + X/2，y = 326.75 + Y/2（底面 y 264.25，盖顶 375.75，结合面凸缘左端 x 78.5）
  A-A  ：x = 112.5 + X/2，y = 158.75 - Z/2（底座凸缘 x 63.5..236.5、y 121.25..196.25；输入轴伸 y 96.25，输出轴伸 y 223.75）
  左视图：x = 343.75 - Z/2，y = 326.75 + Y/2（轴伸端 x 281.25 / 408.75，底座凸缘 x 306.25..381.25）
齿轮 m=2.5：小齿轮 da 55 df 43.75 d 50；大齿轮 da 155 df 143.75 d 150；齿宽 45 / 40。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from sw2acad import Sheet, P, retry

D = os.path.dirname(os.path.abspath(__file__))
VIEWS = [(38, 253, 264, 387), (52, 85, 248, 235), (270, 253, 420, 387)]
STD = json.load(open(os.path.join(D, "models", "std.json"), encoding="utf-8"))   # build_asm.py 写的标准件信息


def std_row(k, qty):
    v = STD[k]
    name = {"key": "键", "bolt": "螺栓", "washer": "垫圈", "nut": "螺母"}[v["kind"]] + " " + v["规格"]
    return (v["代号"].split("-")[0], name, qty, v["材料"], f"{v['质量kg'] * qty:.3f}".rstrip("0"), "")


PARTS_KG = [11.02, 4.41, 1.17, 2.77, 1.29, 0.06, 0.19 * 2, 0.28 * 2, 0.53, 0.46, 0.65, 0.56]


def sx(X): return 112.5 + X / 2
def sy(Z): return 158.75 - Z / 2


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

    # ---- 剖面线：实心轴纵剖不画；钢球不画；相邻零件剖面线方向/间距错开
    s.move_label("A-A", (145, 244))
    for e in s._items():                # SW 模板分区字母 A~D 留在图框左边外，删掉
        if e.ObjectName in ("AcDbMText", "AcDbText") and retry(lambda: e.InsertionPoint)[0] < 25:
            e.Delete()
    s.unhatch((112.5, 108))            # 齿轮轴
    s.unhatch((162.5, 213))            # 输出轴
    for c in [(101, 138.25), (124, 138.25), (101, 179.25), (124, 179.25),
              (149.125, 138), (175.875, 138), (149.125, 179.5), (175.875, 179.5)]:
        s.unhatch(c)
    for e in s._items():
        if e.ObjectName != "AcDbHatch":
            continue
        mn, mx = retry(lambda: e.GetBoundingBox())
        w, h = mx[0] - mn[0], mx[1] - mn[1]
        if w < 2.2 and h > 7:                         # 轴承内外圈、套筒
            e.PatternScale = e.PatternScale * 0.5
            if h > 7.5: e.PatternAngle = 1.5708      # 轴承圈反向
            e.Evaluate()
        elif abs(mn[1] - 148.75) < 0.1 and abs(mx[1] - 168.75) < 0.1:   # 大齿轮
            e.PatternAngle = 1.5708; e.Evaluate()

    # ---- 轮齿规定画法（A-A）：齿顶线粗实线，分度线点画线；啮合区小齿轮齿顶线可见、大齿轮齿顶线画虚线
    zp, zg = 22.5, 20
    s.line((sx(-27.5), sy(zp)), (sx(-27.5), sy(-zp)), "粗实线")               # 小齿轮左齿顶线
    s.line((sx(27.5), sy(zp)), (sx(27.5), sy(-zp)), "粗实线")                 # 小齿轮右齿顶线（啮合区，可见）
    for z in (zp, -zp):
        s.line((sx(-27.5), sy(z)), (sx(-21.875), sy(z)), "粗实线")
        s.line((sx(21.875), sy(z)), (sx(27.5), sy(z)), "粗实线")
    s.line((sx(22.5), sy(zg)), (sx(22.5), sy(-zg)), "虚线")                   # 大齿轮齿顶线（被小齿轮挡住）
    s.line((sx(177.5), sy(zg)), (sx(177.5), sy(-zg)), "粗实线")
    for z in (zg, -zg):
        s.line((sx(22.5), sy(z)), (sx(28.125), sy(z)), "虚线")
        s.line((sx(171.875), sy(z)), (sx(177.5), sy(z)), "粗实线")
    for X in (-25, 25, 175):                                                  # 分度线
        s.line((sx(X), sy(zp) - 3), (sx(X), sy(-zp) + 3))
    # 主视图、左视图里轴线（SW 中心符号只有短十字）
    s.line((sx(0), 300), (sx(0), 353)); s.line((sx(100), 300), (sx(100), 353))
    s.line((276, 326.75), (414, 326.75))

    # ---- 键：纵剖按不剖画，删掉剖面线；删掉 SW 在圆头处加的中心符号
    for kc in ((sx(119), sy(1)), (sx(113.5), sy(-102.5)), (sx(11.5), sy(100))):
        s.unhatch(kc)
    for kc, half in (((sx(119), sy(1)), (3, 9)), ((sx(113.5), sy(-102.5)), (3, 12.5)), ((sx(11.5), sy(100)), (3, 11))):
        for e in s._items():
            if e.Layer == "中心线" and e.ObjectName == "AcDbLine":
                a_, b_ = e.StartPoint, e.EndPoint
                if all(abs(q[0] - kc[0]) <= half[0] + 3 and abs(q[1] - kc[1]) <= half[1] + 3 for q in (a_, b_)):
                    e.Delete()

    # ---- 尺寸
    def fill(d):          # 轴上的配合尺寸文字骑在轴线上：最后用 break_center_under_text 把点画线断开（国标做法）
        return d

    s.dimlin((sx(0), 96.25), (sx(100), 121.25), (137.5, 90), 0, "100%%P0.027")   # 中心距
    s.dimlin((72.5, 129.75), (227.5, 129.75), (150, 80))                         # 地脚孔距 310
    s.dimlin((63.5, 121.25), (236.5, 121.25), (150, 71))                          # 总长 346
    s.dimlin((227.5, 129.75), (227.5, 187.75), (244, 158.75), 90)                 # 116
    s.dimlin((236.5, 121.25), (236.5, 196.25), (253, 158.75), 90)                 # 150
    d = s.dimdia((72.5, 129.75), 4.5, 225, 0, "4×%%C18")                         # 地脚孔
    d.TextPosition = P(55, 112)
    # 两个轴伸直径标在左视图上（A-A 里轴伸太窄，还有键挡着）：左视图 x = 343.75 - Z/2，y = 326.75 + Y/2
    s.dimlin((290, 326.75 - 6), (290, 326.75 + 6), (290, 326.75), 90, "%%C24k6")
    s.dimlin((398, 326.75 - 7), (398, 326.75 + 7), (398, 326.75), 90, "%%C28k6")
    fill(s.dimlin((sx(-31), 141.6), (sx(31), 141.6), (sx(0), 141.6), 0, "%%C62H7"))
    fill(s.dimlin((sx(-15), 176.1), (sx(15), 176.1), (sx(0), 176.1), 0, "%%C30k6"))
    fill(s.dimlin((sx(64), 141.6), (sx(136), 141.6), (sx(100), 141.6), 0, "%%C72H7"))
    fill(s.dimlin((sx(82.5), 177.5), (sx(117.5), 177.5), (sx(100), 177.5), 0, "%%C35k6"))
    d40 = fill(s.dimlin((sx(80), 163), (sx(120), 163), (sx(100), 163), 0, "%%C40H7/r6"))
    # 左视图右侧：中心高、总高；下方：两轴伸端总长
    s.dimlin((381.25, 264.25), (408.75, 326.75), (422, 295.5), 90)                 # 中心高 125
    s.dimlin((381.25, 264.25), (343.75, 375.75), (432, 320), 90)                   # 总高 223
    s.dimlin((281.25, 326.75), (408.75, 326.75), (345, 256))                       # 255

    # ---- 零件序号
    s.balloon((70, 150), (48, 150), 1)
    s.balloon((108, 163), (48, 172), 3)
    s.balloon((95, 126), (48, 128), 10)
    s.balloon((95, 191), (86, 230), 9)
    s.balloon((98, 177), (100, 230), 7)
    s.balloon((160, 201), (150, 230), 5)
    s.balloon((172.4, 172), (188, 230), 6)
    s.balloon((182, 191), (200, 230), 12)
    s.balloon((179.5, 177), (214, 230), 8)
    s.balloon((182, 126), (200, 110), 11)
    s.balloon((186, 158.75), (218, 110), 4)
    s.balloon((180, 350), (225, 372), 2)
    # 标准件序号：键在 A-A 里；螺栓组在主视图左端（螺栓、垫圈、螺母一组，序号竖排）
    s.balloon((sx(119), sy(1) + 4), (226, 230), 13)
    s.balloon((sx(113.5), sy(-102.5) + 9), (176, 230), 14)
    s.balloon((sx(11.5), sy(100) - 6), (92, 100), 15)
    s.balloon_group((sx(-58) - 4, 334.3), (62, 340), [16, 17, 18][::-1])   # 自下而上：螺母、垫圈、螺栓

    s.notes(["技术特性：i=3，m=2.5，z1=20，z2=60，a=100。",
             "1. 装配前零件清洗干净，箱体内壁涂耐油油漆。",
             "2. 齿面接触斑点沿齿高不少于40%，沿齿长",
             "   不少于50%；齿侧间隙不小于0.10。",
             "3. 轴承轴向游隙0.05~0.10，用端盖调整。",
             "4. 结合面涂密封胶，不允许漏油；箱内加",
             "   L-CKC150 齿轮油至规定油面高度。",
             "5. 端盖螺钉图中从略。"], p=(272, 238))
    print("断开轴线", s.break_center_under_text())
    print("断开键轮廓", s.break_center_under_text(layers=("中心线", "粗实线"), only=[d40]))   # 窄轴上躲不开键
    s.check()

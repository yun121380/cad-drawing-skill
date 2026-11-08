"""大齿轮零件图（A3 1:1）。m=2.5 z=60：da 155，d 150，df 143.75；齿宽 40；轮毂 Φ64、孔 Φ40H7、键槽 12JS9 / 43.3；
腹板厚 12、轮缘内径 Φ120，腹板上 4×Φ20 减重孔（分布圆 Φ92）。标注点全按模型坐标写（轴线 X=100、Y=0，沿 Z）。"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
from sw2acad import Sheet, P, mapper

D = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(D, "大齿轮_layout.json"), encoding="utf-8"))
SC0, CC0 = mapper(L["sec"]), mapper(L["circ"])
SC = lambda Y, Z: SC0(100, Y, Z)                 # 剖视图：sheet x = 105 - Z
CC = lambda X, Y: CC0(100 + X, Y, 0)             # 圆视图：以齿轮中心为原点
ZL, ZR = (20, -20) if SC(0, 20)[0] < SC(0, -20)[0] else (-20, 20)     # 图上左/右端面
m, z = 2.5, 60
ra, r, rf = m * (z + 2) / 2, m * z / 2, m * (z - 2.5) / 2
TOL = "({\\H0.7x;\\S%s^%s;})"

with Sheet(D + r"\大齿轮_sw.DWG", D + r"\大齿轮.dwg", views=L["VIEWS"]) as s:
    s.frame()
    s.title_block_gb("大齿轮", "JSQ-04", material="45", scale="1:1", weight="2.77", date="2026.11")
    s.erase_text("A-A"); s.erase_text("A")       # 剖切面是对称面、按投影关系配置：剖切符号和字母都不标

    # ---- 轮齿规定画法：剖视里齿顶线、齿根线粗实线，分度线点画线；圆视图齿顶圆粗实线、分度圆点画线、齿根圆细实线
    p0 = SC(0, ZL); p1 = SC(0, ZR)
    s.gear_teeth(p0, (p1[0] - p0[0], p1[1] - p0[1]), 40, ra, r, rf)
    c = CC(0, 0)
    s.gear_circles(c, ra, r)
    for e in s._items():                         # SW 把模型外圆（= 齿根圆）画成粗实线：改细实线
        if e.ObjectName == "AcDbCircle" and abs(e.Radius - rf) < 0.05 and math.dist(e.Center[:2], c) < 0.1:
            e.Layer = "细实线"
    s.circle(c, 46, "中心线")                     # 减重孔分布圆

    # ---- 剖视图尺寸：左边一排直径（自动分排）、下面齿宽
    bs = L["box_sec"]
    s.auto_dims((SC(0, ZL)[0], bs[1], SC(0, ZR)[0], bs[3]), "left",
                [(SC(-ra, ZL), SC(ra, ZL), "%%C155h11" + TOL % ("0", "-0.25")),
                 (SC(-r, ZL), SC(r, ZL), "%%C150"),
                 (SC(-60, ZL), SC(60, ZL), "%%C120"),
                 (SC(-32, ZL), SC(32, ZL), "%%C64")])
    s.auto_dims((SC(0, ZL)[0], SC(-ra, 0)[1], SC(0, ZR)[0], SC(ra, 0)[1]), "below", [(SC(-ra, ZL), SC(-ra, ZR))])
    d12 = s.dimlin(SC(-46, 6), SC(-46, -6), SC(-46, 0), 0)      # 腹板厚：数字挪到旁边的空腔里
    tp = d12.TextPosition; d12.TextPosition = P(SC(-46, -13)[0], tp[1])

    # ---- 圆视图：孔、键槽、减重孔
    dk = s.dimlin(CC(-6, 23.3), CC(6, 23.3), CC(0, 48), 0, "12JS9")      # 键槽宽：字放到右边（两孔之间）
    tp = dk.TextPosition; dk.TextPosition = P(c[0] + 17, tp[1])
    s.dimlin(CC(0, -20), CC(6, 23.3), CC(26.5, 0), 90, "43.3" + TOL % ("+0.2", "0"))
    a45 = math.radians(45)
    dh = s.dimdia(CC(46 * math.cos(a45), 46 * math.sin(a45)), 10, 45, 30, "4×%%C20")
    s.half_dia(c, 46, 200, "%%C92", frac=0.85)       # 分布圆：半个直径尺寸，字落在轮毂圆和减重孔之间
    # 孔 Φ40H7：圆视图里半个直径尺寸（上边是键槽），基准 A（孔轴线）的三角形和这条尺寸线对齐、贴在孔壁外
    a160 = math.radians(160)                     # 160°：字在线的上方，不压水平中心线；基准框落在两孔之间
    s.half_dia(c, 20, 160, "%%C40H7")
    s.datum(CC(20 * math.cos(a160), 20 * math.sin(a160)), "A", direction=(math.cos(a160), math.sin(a160)), gap=16)

    # ---- 形位公差：齿顶圆径向圆跳动、端面圆跳动，基准 A（孔轴线）
    top = SC(ra, 0)
    s.gtol("h", "0.022", "A", (top[0] - 38, top[1] + 16), [(top[0], top[1] + 16), top])
    face = SC(66, ZR)
    s.gtol("h", "0.018", "A", (face[0] + 22, face[1] + 30), [(face[0] + 16, face[1] + 30), (face[0] + 16, face[1]), face])

    # ---- 粗糙度：齿面标在分度线上；孔 Ra 1.6；端面 Ra 3.2；其余 Ra 6.3
    pc = CC(r * math.cos(math.radians(112)), r * math.sin(math.radians(112)))   # 齿面：指引线落在圆视图的分度圆上
    s.rough_leader(pc, (pc[0] - 14, pc[1] + 18), "1.6")
    s.rough(SC(-20, 10), "1.6")                      # 孔表面：符号在孔里（无材料一侧），开口朝上

    s.rough_leader(SC(-66, ZR), (SC(-66, ZR)[0] + 10, SC(-66, ZR)[1] - 14), "3.2")
    x1, y1 = s.inner[2], s.inner[3]
    s._text((x1 - 46, y1 - 10), 5, "其余")
    s.rough((x1 - 34, y1 - 14), "6.3")

    # ---- 参数表（右上角）
    s.table((x1, y1 - 22), (28, 12, 44),
            [("模数", "m", "2.5"), ("齿数", "z", "60"), ("压力角", "α", "20°"), ("齿顶高系数", "ha*", "1"),
             ("精度等级", "", "7 GB/T 10095.1"), ("公法线长度", "W", "50.07(-0.10/-0.16)"),
             ("跨齿数", "k", "7"), ("配对齿轮", "图号", "JSQ-03"), ("", "齿数", "20")])

    s.notes(["1. 调质处理 217~255HBW。",
             "2. 未注倒角 C1.5，未注圆角 R3。",
             "3. 未注尺寸公差按 GB/T 1804-m。"], p=(30, 62))
    print("断开中心线", s.break_center_under_text())
    s.check()

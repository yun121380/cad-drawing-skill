"""复杂轴承座零件图（A3 1:1）—— AutoCAD 整理标注。
所有坐标由 params.py（设计尺寸）+ layout.json（views.py 写的视图摆放）算出，不再从 DXF 手抄：
  主视图 F(X, Y)、A-A A(Z, Y)、俯视图 T(X, Z)、放大图 Dt(Z, Y)。改了 params.py 依次重跑 build → views → drawing 即可。"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sw2acad import Sheet, P
from params import *

D = os.path.dirname(os.path.abspath(__file__))
lay = json.load(open(os.path.join(D, "layout.json"), encoding="utf-8"))
FC, AC, TC, VIEWS, DET = lay["FC"], lay["AC"], lay["TC"], lay["VIEWS"], lay["DET"]
H = H_TOTAL
F = lambda X, Y: (FC[0] + X, FC[1] - H / 2 + Y)
A = lambda Z, Y: (AC[0] + Z, AC[1] - H / 2 + Y)
T = lambda X, Z: (TC[0] + X, TC[1] + Z)
K, DC, SRC = DET["k"], DET["center"], DET["src"]
Dt = lambda Z, Y: (DC[0] + K * (A(Z, Y)[0] - SRC[0]), DC[1] + K * (A(Z, Y)[1] - SRC[1]))
hb, hl, hw, R, r0, rs, ro = BASE_L / 2, L / 2, WEB_FOOT / 2, BOSS_D / 2, BORE_D / 2, SEAL_D / 2, OILG_D / 2
z1, z2 = hl - SEAL_E, hl - SEAL_E - SEAL_W
yc = AXIS_H
off = lambda p, dx=0, dy=0: (p[0] + dx, p[1] + dy)
TOL52 = "%%%%C%dH7({\\H0.7x;\\S%s^%s;})" % (BORE_D, *BORE_TOL)
TOL52 = TOL52.replace("%%%%", "%%")

with Sheet(D + r"\zcz_sw.DWG", D + r"\轴承座.dwg", views=VIEWS) as s:
    s.frame()
    mass = json.load(open(os.path.join(D, "build.json"), encoding="utf-8"))["mass_kg"]   # 重量取模型实算值
    s.title_block_gb("轴承座", "ZCZ-01", material="HT200", scale="1:1", weight=f"{mass:.2f}",
                     designer="", date="2026.11")

    # ---- 清理：剖切面过对称面且按投影关系配置 → A-A 标注省略；SW 的放大图圆圈旁的 "I" 换成带指引线的
    x0 = FC[0]
    n = (s.erase_in((x0 - 17, F(0, 0)[1] - 18, x0 + 17, F(0, 0)[1] - 1)) +
         s.erase_in((x0 - 17, F(0, H)[1] + 1, x0 + 17, 292)) +
         s.erase_in((AC[0] - 13, F(0, H)[1] + 10, AC[0] + 17, 292)) +
         s.erase_in((SRC[0] + 5, SRC[1] - 3, SRC[0] + 12, SRC[1] + 8)))
    n += s.erase_text("I")                              # SW 自动放的 "I"，位置不可控（实测这次跑进了轴孔里）
    print("删剖切符号/标注", n)
    s.to_center(F(0, -3), F(0, H + 4))                 # 半剖分界线 -> 一整条点画线（也穿过轴孔、油孔）
    s.line(F(-R - 5, yc), F(R + 5, yc))                # 轴孔水平中心线（SW 这次没出中心符号）
    a = math.radians(-40)
    s.line(off(SRC, DET["r"] * math.cos(a), DET["r"] * math.sin(a)), off(SRC, 12, -10), "细实线")
    s._text(off(SRC, 14.5, -10), 5, "I")

    # ---- 过渡线（俯视图里支承板与底座的圆角处；主视图油杯凸台与圆筒的相贯处）
    for sg in (-1, 1):
        x = T(sg * hw, 0)[0]
        s.transition((min(x - 7 * sg, x + 9 * sg), TC[1] - 19, max(x - 7 * sg, x + 9 * sg), TC[1] + 19))
    yob = AXIS_H + math.sqrt(R * R - (OIL_D / 2) ** 2)
    s.transition((F(-OIL_D / 2 - 5, 0)[0], F(0, yob - 4)[1], F(OIL_D / 2 + 5, 0)[0], F(0, yob + 4)[1]), kinds=("spline",))

    # ---- 螺纹孔 M10：A-A 全剖两侧画，主视图半剖只画右半，俯视图画 3/4 细圆
    s.thread_hole(A(0, 0)[0], A(0, OIL_TOP)[1], THREAD_L, THREAD[1], TAP_D)
    s.thread_hole(F(0, 0)[0], F(0, OIL_TOP)[1], THREAD_L, THREAD[1], TAP_D, side="right")
    s.thread_circle(T(0, 0), THREAD[1])

    # ---- 放大图标签（罗马数字在上、比例在下）
    top_d = DC[1] + K * DET["r"]
    s.view_label("I", (DC[0], top_d + 9.5), scale=f"{K}:1", keep_near=(DC[0], top_d))

    # ---- 主视图
    fy0 = F(0, 0)[1]
    s.dimlin(F(-hb, 0), F(hb, 0), (x0, fy0 - 16))
    s.dimlin(F(-RECESS_W / 2, 0), F(RECESS_W / 2, 0), (x0, fy0 - 8))
    s.dimlin(F(-hb, 0), F(-R, yc), (F(-hb, 0)[0] - 5, F(0, yc / 2)[1]), 90, f"{AXIS_H}%%P0.03")
    s.dimlin(F(-hb, 0), F(-OIL_D / 2, OIL_TOP), (F(-hb, 0)[0] - 14, F(0, OIL_TOP / 2 + 22)[1]), 90)
    s.dimlin(F(-OIL_D / 2, OIL_TOP), F(OIL_D / 2, OIL_TOP), (x0, F(0, OIL_TOP)[1] + 8), 0, f"%%C{OIL_D}")
    s.half_dia(F(0, yc), ro, -45, f"%%C{OILG_D}")                       # 油槽：半剖里只画一半
    s.rough_leader(off(F(0, yc), ro * math.cos(math.radians(20)), ro * math.sin(math.radians(20))),
                   off(F(0, yc), 13, 12), "6.3")                         # 油槽面
    s.rough_leader(F(HOLE_X - HOLE_D / 2, BASE_H / 2 - 2), off(F(hb, 0), 6, 9), "12.5")   # 安装孔

    # ---- A-A
    ay_top = A(0, yc + R)[1]
    s.dimlin(A(-hl, yc + R), A(hl, yc + R), (AC[0], ay_top + 22))                        # 60
    xb = A(-hl, 0)[0] - 13                                                              # Φ52 尺寸线位置
    d = s.dimlin(A(-hl + CH, yc - r0), A(-hl + CH, yc + r0), (xb, A(0, yc)[1]), 90, TOL52)
    d.TextPosition = P(xb - 2.5, A(0, yc)[1] - 10)
    s.rough((xb, A(0, yc)[1] + 13), "1.6", ang=90)                       # 轴孔：标在尺寸线上
    gy = A(0, (BASE_H + yc - R) / 2)[1]
    d = s.dimlin(A(-WEB_T / 2, 0), A(WEB_T / 2, 0), (AC[0], gy))                          # 支承板厚
    d.TextPosition = P(A(hl, 0)[0] - 7, gy - 1.3)
    s.dimlin(A(hl, 0), A(hl, RECESS_H), (A(hl, 0)[0] + 8, A(0, 1.5)[1]), 90)
    s.dimlin(A(hl, 0), A(hl, BASE_H), (A(hl, 0)[0] + 17, A(0, BASE_H / 2)[1]), 90)
    s.dimlin(A(-OILG_W / 2, yc - ro), A(OILG_W / 2, yc - ro), (AC[0], A(0, yc - ro)[1] + 7))
    s.dimlin(A(-THREAD[1] / 2, OIL_TOP), A(THREAD[1] / 2, OIL_TOP), (AC[0], A(0, OIL_TOP)[1] + 6), 0,
             THREAD[0] + "{\\Fgdt;x}%d" % THREAD_L)
    s.datum(A(hl - 13, 0), "A", direction=(0, -1))
    s.datum((xb, A(0, yc - r0)[1] - 1), "B", direction=(0, -1))
    s.gtol("f", "0.03", "A", (xb - 40, ay_top + 3), [(xb, ay_top + 3), (xb, A(0, yc + r0)[1])])
    py = A(0, yc - R + 7)[1]
    s.gtol("b", "0.03", "B", (A(hl, 0)[0] + 13, py), [(A(hl, 0)[0], py)])
    s.rough((A(-hl, 0)[0], ay_top + 7), "3.2", ang=90)
    s.rough_leader(A(hl, yc + R - 4), (A(hl, 0)[0] + 11, ay_top + 3), "3.2")
    s.rough_leader(A(-hl + 7, 0), (A(-hl, 0)[0] - 7, A(0, 0)[1] - 13), "6.3")

    # ---- 俯视图
    s.dimlin(T(-HOLE_X, 0), T(HOLE_X, 0), (TC[0], T(0, -hl)[1] - 10))
    d = s.dimlin(T(-hw, WEB_T / 2), T(hw, WEB_T / 2), (TC[0], T(0, WEB_T / 2)[1] + 11))
    d.TextPosition = P(TC[0] + 18, T(0, WEB_T / 2)[1] + 12.8)       # 别压在竖直中心线上（check 报出来的）
    s.dimlin(T(-R, hl), T(R, hl), (TC[0], T(0, hl)[1] + 5.5), 0, f"%%C{BOSS_D}")
    c45 = HOLE_D / 2 * math.cos(math.radians(45))
    s.note([T(HOLE_X + c45, c45), T(HOLE_X + 19, 19)],
           f"2×%%C{HOLE_D} {{\\Fgdt;v}}%%C{CB_D}{{\\Fgdt;x}}{CB_H}", w=27)

    # ---- 放大图（k = 1/放大倍数）
    yb = Dt(0, yc + r0)[1] - 7
    s.dimlin(Dt(z2, yc + r0), Dt(z1, yc + r0), (Dt((z1 + z2) / 2, 0)[0], yb), k=1 / K)
    s.dimlin(Dt(z1, yc + r0), Dt(hl, yc + r0), (Dt((z1 + hl) / 2, 0)[0], yb), k=1 / K)
    zm = (z1 + z2) / 2
    s.dimlin(Dt(zm, yc + r0), Dt(zm, yc + rs), Dt(zm, (r0 + rs) / 2 + yc), 90, k=1 / K)
    s.note([Dt(hl - CH / 2, yc + r0 + CH / 2), off(Dt(hl, yc + r0), 4, -6)], f"C{CH}")
    s.rough_leader(off(Dt(z2, yc + rs), 4, 0), off(DC, -28, -22), "6.3")   # 密封槽面

    # ---- 表面结构的统一要求（GB/T 131-2006：毛坯面符号 + 括号里基本符号）、技术要求
    s.rough((372, 277), None, mode="keep", h=5)
    s._text((383, 281.5), 5, "("); s.rough((388, 278.5), None, mode="any"); s._text((396, 281.5), 5, ")")
    s.notes(["1. 铸件不得有砂眼、气孔、裂纹。",
             "2. 铸件人工时效处理。",
             "3. 未注铸造圆角 R3~R5。",
             "4. 未注加工面 Ra12.5。",
             "5. 两端密封槽及倒角相同。"], p=(248, 112))
    s.check()

"""输出轴零件图（A3 1:1）。所有标注点按模型坐标 (X, Y, Z) 写，经 输出轴_layout.json 里的视图仿射换算到图纸。
模型：轴线 X=100、Y=0，沿 Z；轴段 (Z 范围, 半径)：51..33 R17.5 | 33..20 R21 | 20..-18 R20 | -18..-50 R17.5 |
-50..-75 R16 | -75..-130 R14。键槽在 +X 一侧：12×5 深（Z -15..17），8×4 深（Z -125..-80）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
from sw2acad import Sheet, P, mapper

D = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(D, "输出轴_layout.json"), encoding="utf-8"))
M0 = mapper(L["main"]); M = lambda r, Z: M0(100, r, Z)          # 主视图：r>0 上轮廓，r<0 下轮廓，r=0 轴线
SA, SB = mapper(L["secs"]["A"]["aff"]), mapper(L["secs"]["B"]["aff"])
bm = L["box_main"]
SEG = [(51, 33, 17.5), (33, 20, 21), (20, -18, 20), (-18, -50, 17.5), (-50, -75, 16), (-75, -130, 14)]
TOL = "({\\H0.7x;\\S%s^%s;})"

with Sheet(D + r"\输出轴_sw.DWG", D + r"\输出轴.dwg", views=L["VIEWS"]) as s:
    s.frame()
    s.title_block_gb("输出轴", "JSQ-05", material="45", scale="1:1", weight="1.29", date="2026.11")
    # 移出断面配在剖切线延长线上：不对称，画箭头，字母省略（GB/T 17452）
    for t in ("A", "B"):
        s.erase_text(t); s.erase_text(f"{t}-{t}")

    # ---- 直径（竖直尺寸，文字压在轴线上的由 break_center_under_text 断开点画线）
    def dia(Z, r, txt, above=False):
        d = s.dimlin(M(-r, Z), M(r, Z), M(0, Z), 90, txt)
        if above:                                    # 键槽挡着：文字移到轴外上方，尺寸线跟着延长
            tp = d.TextPosition
            import re
            n = len(re.sub(r"\(.*\)", "", txt).replace("%%C", "C")) + 2.5     # 叠写偏差约占 2.5 个字宽
            d.TextPosition = P(tp[0], M(r, Z)[1] + 2 + n * 3.5 * 0.7 / 2)
        return d
    dia(42, 17.5, "%%C35k6" + TOL % ("+0.018", "+0.002"))
    dia(26.5, 21, "%%C42")
    d40 = dia(4, 20, "%%C40r6" + TOL % ("+0.050", "+0.034"))          # 压在键槽上：键槽轮廓在文字处断开
    dia(-34, 17.5, "%%C35k6" + TOL % ("+0.018", "+0.002"))
    dia(-62.5, 16, "%%C32")
    d28 = dia(-92, 14, "%%C28k6" + TOL % ("+0.015", "+0.002"))

    # ---- 轴向尺寸（下方，自动分排）：链式少一环（密封段 25 不注），再加总长；键槽定位和长度
    zb = lambda Z, r: M(-r, Z)
    items = [(zb(51, 17.5), zb(33, 17.5)), (zb(33, 21), zb(20, 21)), (zb(20, 20), zb(-18, 20)),
             (zb(-18, 17.5), zb(-50, 17.5)), (zb(-75, 14), zb(-130, 14)), (zb(51, 17.5), zb(-130, 14)),
             (zb(20, 20), M(0, 17)), (M(0, 17), M(0, -15)), (M(0, -80), M(0, -125)), (M(0, -125), zb(-130, 14))]
    s.auto_dims(bm, "below", items)

    # ---- 断面：键槽宽（N9）、槽底到对面的尺寸（负偏差）
    for S_, zc, r, b, t, wtol in ((SA, 1, 20, 12, 5, ("0", "-0.043")), (SB, -102.5, 14, 8, 4, ("0", "-0.036"))):
        xb = 100 + r - t
        far = S_(100 - r, 0, zc); bot = S_(xb, 0, zc)
        c = S_(100, 0, zc)
        right = bot[0] > c[0]                         # 键槽在断面哪一边
        w1, w2 = S_(100 + r, -b / 2, zc), S_(100 + r, b / 2, zc)
        s.dimlin(w1, w2, (max(w1[0], w2[0]) + 9 if right else min(w1[0], w2[0]) - 9, c[1]), 90,
                 f"{b}N9" + TOL % wtol)
        s.dimlin(far, bot, ((far[0] + bot[0]) / 2, c[1] - r - 9), 0, f"{2 * r - t}" + TOL % ("0", "-0.2"))

    # ---- 基准、跳动、粗糙度（上方）
    yt = lambda Z, r: M(r, Z)
    s.datum(yt(42, 17.5), "A", direction=(0, 1))                 # 轴线基准：三角形和直径尺寸线对齐
    s.datum(yt(-34, 17.5), "B", direction=(0, 1))
    for Zp, r in ((16, 20), (-78, 14)):                           # 圆跳动：箭头垂直指向表面，框格在左上
        tip = yt(Zp, r)
        s.gtol("h", "0.015", "A-B", (tip[0] - 38, tip[1] + 26), [(tip[0], tip[1] + 26), tip])
    for Zp, r, ra in ((37, 17.5, "0.8"), (-42, 17.5, "0.8"), (-6, 20, "1.6"), (-110, 14, "1.6")):
        s.rough(yt(Zp, r), ra)
    x1, y1 = s.inner[2], s.inner[3]
    s._text((x1 - 46, y1 - 10), 5, "其余")
    s.rough((x1 - 34, y1 - 14), "6.3")

    s.notes(["1. 调质处理 220~250HBW。",
             "2. 未注倒角 C1，未注圆角 R1。",
             "3. 未注尺寸公差按 GB/T 1804-m。"], p=(30, 70))
    for S_, zc, r in ((SA, 1, 20), (SB, -102.5, 14)):              # 断面的十字中心线（SW 的中心符号只剩半截）
        s.center_cross(S_(100, 0, zc), r)
    print("断开轴线", s.break_center_under_text())
    print("断开键槽轮廓", s.break_center_under_text(margin=1.8, layers=("粗实线",), only=[d40, d28]))
    s.check()

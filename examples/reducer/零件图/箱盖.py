"""箱盖零件图（A2 1:2，HT200 铸件）。标注点全按模型坐标写（全局坐标同装配：输入轴 X=0、输出轴 X=100，结合面 Y=0，Y 向上），
经 箱盖_layout.json 的视图仿射换算到图纸；粗糙度、形位公差自动放；audit_dims 核对尺寸是否标全。
模型：外壳 R48（X=0）、R98（X=100）两圆弧加公切线，Z ±38；内腔 R40 / R90，Z ±30（主视图用虚线表达）；
结合面凸缘 X -68..218 × Y 0..12 × Z ±60；轴承座凸台 R44 / R49；轴承孔 Φ62 / Φ72；螺栓孔 4×Φ11（X -58/208，Z ±45）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
from sw2acad import Sheet, P, mapper

D = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(D, "箱盖_layout.json"), encoding="utf-8"))
FEAT = json.load(open(os.path.join(D, "箱盖_features.json"), encoding="utf-8"))
FV, TV, SV = mapper(L["front"]), mapper(L["top"]), mapper(L["sec"])
BF, BT, BS = L["boxes"]["front"], L["boxes"]["top"], L["boxes"]["sec"]
F = lambda X, Y: FV(X, Y, 0)
T = lambda X, Z: TV(X, 0, Z)
S = lambda Z, Y: SV(100, Y, Z)
k = 0.5

with Sheet(D + r"\箱盖_sw.DWG", D + r"\箱盖.dwg", views=L["VIEWS"], sheet="A2", view_scale=2) as s:
    s.frame()
    s.title_block_gb("箱盖", "JSQ-02", material="HT200", scale="1:2", weight="4.41", date="2026.11")

    for X, r in ((0, 44), (100, 49)):                          # 轴承孔中心线
        s.line(F(X, -4), F(X, r + 4)); s.line(F(X - r - 4, 0), F(X + r + 4, 0))
    s.line(S(0, -4), S(0, 102))

    # ---- 主视图：外壳、内腔、凸台的半径；轴承孔直径；中心距和凸缘定位（下方）；凸缘厚（左侧）
    s.dimrad(F(0, 0), 48 * k, 165, 8); s.dimrad(F(0, 0), 40 * k, 140, 4)
    s.dimrad(F(100, 0), 98 * k, 30, 8); s.dimrad(F(100, 0), 90 * k, 70, 4)
    s.dimrad(F(0, 0), 44 * k, 60, 4); s.dimrad(F(100, 0), 49 * k, 115, 4)
    s.half_dia(F(0, 0), 31 * k, 150, "%%C62H7", frac=-1.25, over=31 * k * 1.25 + 11)
    s.half_dia(F(100, 0), 36 * k, 30, "%%C72H7", frac=-1.1, over=36 * k * 1.1 + 11)
    s.auto_dims(BF, "below", [(F(-68, 0), F(0, 0), "68"), (F(0, 0), F(100, 0), "100%%P0.027")], first=24)   # 68：audit 查出来漏了
    s.auto_dims(BF, "left", [(F(-68, 0), F(-68, 12))])

    # ---- 俯视图：长度（下方，对称于 X=75）、螺栓孔前后距（右侧）
    s.auto_dims(BT, "below", [(T(-68, 60), T(218, 60)), (T(-58, 45), T(208, 45))])
    s.auto_dims(BT, "right", [(T(208, -45), T(208, 45))])
    s.note([T(-58 + 5.5 * 0.7, -45 + 5.5 * 0.7), (T(-58, -45)[0] + 12, BT[3] + 6)], "4×%%C11")

    # ---- A-A：前后方向宽度
    s.auto_dims(BS, "below", [(S(-60, 0), S(60, 0))])
    _, top_off = s.auto_dims(BS, "above", [(S(-38, 98), S(38, 98)), (S(-30, 90), S(30, 90))])
    s.view_label("A-A", ((BS[0] + BS[2]) / 2, BS[3] + top_off + 9))

    # ---- 粗糙度、形位公差
    s.auto_rough((F(-68, 0), F(218, 0)), "1.6", out=(0, -1))        # 结合面（朝下）
    s.auto_rough((S(30, 36), S(60, 36)), "1.6", out=(0, -1))         # 轴承孔（A-A 里孔顶母线）
    s.auto_gtol("c", "0.03", "", F(185, 0), out=(0, -1))             # 结合面平面度
    x1, y1 = s.inner[2], s.inner[3]
    s._text((x1 - 46, y1 - 10), 5, "其余")
    s.rough((x1 - 34, y1 - 14), None, mode="keep")

    s.notes(["1. 铸件不得有砂眼、缩孔等缺陷，铸后时效处理。",
             "2. 箱盖与箱座合箱后镗轴承孔，结合面配刮。",
             "3. 两轴承孔轴线的平行度公差 0.03。",
             "4. 未注铸造圆角 R3~R5，未注壁厚 8。",
             "5. 未注尺寸公差按 GB/T 1804-m。"], p=(BS[0] - 20, BT[3] - 8))
    s.break_center_under_text()
    s.audit_dims(FEAT, [(L["front"], L["VIEWS"][0]), (L["top"], L["VIEWS"][1]), (L["sec"], L["VIEWS"][2])])
    s.check()

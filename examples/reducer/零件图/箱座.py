"""箱座零件图（A2 1:2，HT200 铸件）。标注点全按模型坐标写（全局坐标：X 沿两轴连线，输入轴 X=0、输出轴 X=100；Y 向上，
结合面 Y=0；Z 前后），经 箱座_layout.json 的视图仿射换算到图纸。粗糙度、形位公差、基准用 auto_* 自动放；
最后 audit_dims 拿模型特征核对尺寸是否标全、check() 查压线。
模型：底座凸缘 X -98..248 × Z ±75 × Y -125..-107；箱壁 X -48..198 × Z ±38；结合面凸缘 X -68..218 × Z ±60 × Y -12..0；
内腔 X -40..190 × Z ±30 × Y -113..0；轴承座凸台 R44（X=0）/ R49（X=100）；轴承孔 Φ62 / Φ72；
结合面螺栓孔 4×Φ11（X -58/208，Z ±45）；地脚孔 4×Φ18（X -80/230，Z ±58）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
from sw2acad import Sheet, P, mapper

D = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(D, "箱座_layout.json"), encoding="utf-8"))
FEAT = json.load(open(os.path.join(D, "箱座_features.json"), encoding="utf-8"))
FV, TV, SV = mapper(L["front"]), mapper(L["top"]), mapper(L["sec"])
BF, BT, BS = L["boxes"]["front"], L["boxes"]["top"], L["boxes"]["sec"]
F = lambda X, Y: FV(X, Y, 0)                 # 主视图：X 向右、Y 向上
T = lambda X, Z: TV(X, 0, Z)                 # 俯视图：X 向右、Z 向下
S = lambda Z, Y: SV(100, Y, Z)               # A-A：Z 向右、Y 向上
k = 0.5

with Sheet(D + r"\箱座_sw.DWG", D + r"\箱座.dwg", views=L["VIEWS"], sheet="A2", view_scale=2) as s:
    s.frame()
    s.title_block_gb("箱座", "JSQ-01", material="HT200", scale="1:2", weight="11.02", date="2026.11")

    # ---- 中心线：轴承孔轴线（主视图竖直、俯视图竖直）、A-A 对称线
    for X, r in ((0, 44), (100, 49)):
        s.line(F(X, 4), F(X, -r - 4)); s.line(F(X - r - 4, 0), F(X + r + 4, 0))
    s.line(S(0, 4), S(0, -129))

    # ---- 主视图：高度方向（左侧）、轴承孔中心距和定位（上方）
    s.auto_dims(BF, "left", [(F(-68, 0), F(-68, -12)), (F(-98, -107), F(-98, -125)), (F(-68, 0), F(-98, -125))])
    s.auto_dims(BF, "above", [(F(-48, -12), F(0, 0), "48"), (F(0, 0), F(100, 0), "100%%P0.027")], first=22)
    s.dimrad(F(0, 0), 44 * k, 235, 8)                   # 凸台外圆
    s.dimrad(F(100, 0), 49 * k, 305, 8)
    # 半圆孔的直径：一个箭头落在孔壁，线过圆心伸到结合面上方的空白处，字写在那一段（不压轴线和凸台）
    s.half_dia(F(0, 0), 31 * k, -150, "%%C62H7", frac=-1.25, over=31 * k * 1.25 + 11)
    s.half_dia(F(100, 0), 36 * k, -30, "%%C72H7", frac=-1.1, over=36 * k * 1.1 + 11)

    # ---- 俯视图：长度方向（下方，全部对称于 X=75）、前后方向孔距（右侧）
    s.auto_dims(BT, "below", [(T(-98, 75), T(248, 75)), (T(-80, 58), T(230, 58)), (T(-68, 60), T(218, 60)),
                              (T(-58, 45), T(208, 45)), (T(-48, 38), T(198, 38)), (T(-40, 30), T(190, 30))])
    s.auto_dims(BT, "right", [(T(230, -58), T(230, 58)), (T(208, -45), T(208, 45))])
    s.note([T(-80 - 9 * 0.7, -58 - 9 * 0.7), (T(-80, -58)[0] - 14, BT[3] + 6)], "4×%%C18")
    s.note([T(-58 + 5.5 * 0.7, -45 + 5.5 * 0.7), (T(-58, -45)[0] + 12, BT[3] + 6)], "4×%%C11")

    # ---- A-A：前后方向的宽度（下方 / 上方）、内腔深（右侧）
    s.auto_dims(BS, "below", [(S(-75, -125), S(75, -125)), (S(-30, -113), S(30, -113))])
    _, top_off = s.auto_dims(BS, "above", [(S(-60, 0), S(60, 0)), (S(-38, -60), S(38, -60))])
    s.view_label("A-A", ((BS[0] + BS[2]) / 2, BS[3] + top_off + 9))         # 视图名放在上方尺寸外面
    s.auto_dims(BS, "right", [(S(60, 0), S(30, -113), "113")])

    # ---- 粗糙度、形位公差：只给要素，位置自动挑
    s.auto_rough((F(-68, 0), F(218, 0)), "1.6", out=(0, 1))                  # 结合面
    s.auto_rough((F(-98, -125), F(248, -125)), "12.5", out=(0, -1))          # 底面（朝下：只能引出）
    s.auto_rough((S(30, -36), S(60, -36)), "1.6", out=(0, 1))              # 轴承孔（A-A 里孔底母线）
    s.auto_gtol("c", "0.03", "", F(150, 0), out=(0, 1))                      # 结合面平面度
    x1, y1 = s.inner[2], s.inner[3]
    s._text((x1 - 46, y1 - 10), 5, "其余")
    s.rough((x1 - 34, y1 - 14), None, mode="keep")                           # 其余铸造表面不去除材料

    s.notes(["1. 铸件不得有砂眼、缩孔等缺陷，铸后时效处理。",
             "2. 箱座与箱盖合箱后镗轴承孔，结合面配刮，",
             "   0.05 塞尺塞入深度不大于结合面宽度的 1/3。",
             "3. 两轴承孔轴线的平行度公差 0.03。",
             "4. 未注铸造圆角 R3~R5，未注倒角 C2。",
             "5. 未注尺寸公差按 GB/T 1804-m。"], p=(BS[0] - 20, BT[3] - 8))
    s.break_center_under_text()
    s.audit_dims(FEAT, [(L["front"], L["VIEWS"][0]), (L["top"], L["VIEWS"][1]), (L["sec"], L["VIEWS"][2])])
    s.check()

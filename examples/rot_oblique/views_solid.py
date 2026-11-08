"""实心轮毂摇臂（中心没有孔）的旋转剖：和 views.py 一样做两个全剖 S1、S2 再拼接。
两个剖视里剖面线都跨过轮毂轴线，AutoCAD 里 splice_aligned 会按轴线把剖面线裁成一半（clip_hatch）。
（试过“半边局部剖”：主视图上能用，但斜视图上 CreateBreakOutSection 返回成功却不出剖面线，放弃。）"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import sw_views as V

D = os.path.dirname(os.path.abspath(__file__))
part = os.path.join(D, "rocker_solid.SLDPRT")
sw = V.connect()
drw = V.new_drawing(sw, "A3")

# 俯视图视图坐标 = (X - xc, -(Z - zc))，xc/zc 为零件外框中心（外框 X -65..83、Z -20..43）
xc, zc = 9, 11.5
top = V.model_view(drw, part, "*上视", (115, 80))
vw = lambda X, Z: (X - xc, -(Z - zc))
a = math.radians(150); d2 = (math.cos(a), math.sin(a))
L1 = (vw(-75, 0), vw(95, 0))
sec = V.section(drw, top, L1[0], L1[1], (115, 185), "A")
topx = V.model_view(drw, part, "*上视", (560, 80))
s2 = V.section(drw, topx, vw(85 * d2[0], 85 * d2[1]), vw(-85 * d2[0], -85 * d2[1]), (560, 200), "Z", aligned=False)
boxes = V.finish(drw, [top, sec, s2])
V.export(drw, os.path.join(D, "rs_sw"))

rotY = lambda X, Y, Z, f=math.radians(30): (X * math.cos(f) - Z * math.sin(f), Y, X * math.sin(f) + Z * math.cos(f))
boss2 = (60 * d2[0], 0, 60 * d2[1])
VB = {k: tuple(round(v) + dd for v, dd in zip(b, (-4, -4, 4, 4))) for k, b in boxes.items()}
lay = {"VIEWS": list(VB.values()),
       "splice": {"keep_box": boxes[sec.Name], "src_box": boxes[s2.Name],
                  "axis_x": V.model_to_sheet(sec, (0, 0, 0))[0],
                  "keep_side": 1 if V.model_to_sheet(sec, (70, 0, 0))[0] > V.model_to_sheet(sec, (0, 0, 0))[0] else -1,
                  "src_axis": [V.model_to_sheet(s2, (0, 0, 0)), V.model_to_sheet(s2, (0, 30, 0))],
                  "src_boss": V.model_to_sheet(s2, boss2),
                  "src_pts": [V.model_to_sheet(s2, p) for p in ((0, 0, 0), (0, 30, 0), boss2)],
                  "dst_pts": [V.model_to_sheet(sec, rotY(*p)) for p in ((0, 0, 0), (0, 30, 0), boss2)],
                  "s1_line": [[115 + L1[0][0], 80 + L1[0][1]], [115 + L1[1][0], 80 + L1[1][1]]]},
       "hub": V.model_to_sheet(top, (0, 30, 0)), "e1": V.model_to_sheet(top, (85, 30, 0)),
       "e2": V.model_to_sheet(top, (80 * d2[0], 30, 80 * d2[1]))}
json.dump(lay, open(os.path.join(D, "layout_solid.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(lay["splice"]))

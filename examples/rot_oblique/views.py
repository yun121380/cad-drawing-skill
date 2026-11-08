"""旋转剖 + 局部斜视图演示（A3 1:1）。
左：摇臂俯视图 + 上方 A-A 旋转剖（斜臂旋转到投影面上展开画）。
右：弯板主视图 + B 向局部斜视图（只画斜板，波浪线断开，转正配置）。
视图里要标注的点（剖切路径、孔心等）用 model_to_sheet 算好写进 layout.json。"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import sw_views as V

D = os.path.dirname(os.path.abspath(__file__))
rocker, bent = os.path.join(D, "rocker.SLDPRT"), os.path.join(D, "bent.SLDPRT")
sw = V.connect()
drw = V.new_drawing(sw, "A3")

# ---- 摇臂：俯视图视图坐标 = (X - 9, -(Z - 11.5))（外框中心 X 9、Z 11.5）
top = V.model_view(drw, rocker, "*上视", (115, 80))
vw = lambda X, Z: (X - 9, -(Z - 11.5))
a = math.radians(150)
E1, C0, E2 = (85, 0), (0, 0), (80 * math.cos(a), 80 * math.sin(a))
# SW 的“旋转剖”其实是投影的（斜臂被缩短，实测孔心在 X=-52 而不是 -60）。改为拼接：
#   S1：沿主剖切面（X 轴所在竖直面）全剖，放在俯视图上方；只留 +X 一半
#   S2：另做一个俯视图（放在图纸外），沿斜臂所在竖直面全剖（也放图纸外），取斜臂那一半，在 AutoCAD 里转到 S1 的另一半
L1 = (vw(-75, 0), vw(95, 0))
sec = V.section(drw, top, L1[0], L1[1], (115, 185), "A")
topx = V.model_view(drw, rocker, "*上视", (560, 80))
d2 = (math.cos(a), math.sin(a))
s2 = V.section(drw, topx, vw(85 * d2[0], 85 * d2[1]), vw(-85 * d2[0], -85 * d2[1]), (560, 200), "Z", aligned=False)
rotY = lambda X, Y, Z, f=math.radians(30): (X * math.cos(f) - Z * math.sin(f), Y, X * math.sin(f) + Z * math.cos(f))
boss2 = (60 * math.cos(a), 0, 60 * math.sin(a))

# ---- 弯板：主视图 + 斜视图（不对齐放在 at），按模型坐标裁成只剩斜板，再转正（逆时针 45°）
fr = V.model_view(drw, bent, "*前视", (300, 210))
c = math.cos(math.radians(45))
aux = V.auxiliary(drw, fr, (c, c, 0), (330, 110), "B", pick=(50, 10, 30))
A, u, n = (50, 0), (c, c), (-c, c)
Pm = lambda s, z: (A[0] + s * u[0] + 5 * n[0], A[1] + s * u[1] + 5 * n[1], z)
pts3 = [Pm(74, -34), Pm(74, 34)] + [Pm(10 + 1.8 * math.sin(k * math.pi / 2), 34 - 68 * k / 8) for k in range(9)]
V.crop(drw, aux, [V.sheet_to_view(aux, V.model_to_sheet(aux, p)) for p in pts3])
aux.Angle = math.radians(-45)                     # 转正：斜板长边水平
views = [top, sec, fr, aux, s2]
boxes = V.finish(drw, views)
V.export(drw, os.path.join(D, "rb_sw"))

hole = (A[0] + 40 * u[0], A[1] + 40 * u[1], 0)     # 斜板孔中心
# 斜视图 GetOutline 是整个（裁剪前、旋转后）视图的外框，比裁剪后大很多，会把标题栏圈进来：改用裁剪边界算
crop_pts = [V.model_to_sheet(aux, p) for p in pts3]
cb = (min(p[0] for p in crop_pts), min(p[1] for p in crop_pts), max(p[0] for p in crop_pts), max(p[1] for p in crop_pts))
boxes[aux.Name] = cb
TOPF = lambda s, z: V.model_to_sheet(aux, (A[0] + s * u[0] + 10 * n[0], A[1] + s * u[1] + 10 * n[1], z))   # 斜板上表面
FR = lambda x, y: V.model_to_sheet(fr, (x, y, 30))
lay = {
    # 主视图框往上多留 25：斜视图的投射箭头和字母画在视图外面，框小了会被当模板删掉（实测箭头没了）
    "VIEWS": [tuple(round(v) + d for v, d in zip(b, (-4, -4, 4, 29 if k == fr.Name else 4))) for k, b in boxes.items()],
    "aux_pts": {"end_lo": TOPF(70, -30), "end_hi": TOPF(70, 30), "hole": V.model_to_sheet(aux, hole)},
    "fr_pts": {"b0": FR(-50, 0), "b1": FR(50, 0), "t0": FR(-50, 10), "A": FR(50, 0),
               "A20": FR(70, 0), "U20": FR(50 + 20 * c, 20 * c), "Bout": FR(50 + 70 * c, 70 * c),
               "Bin": FR(50 + 70 * c - 10 * c, 70 * c + 10 * c)},
    "top_pts": {"hub": V.model_to_sheet(top, (0, 30, 0)), "b1": V.model_to_sheet(top, (70, 30, 0)),
                "b2": V.model_to_sheet(top, (60 * math.cos(a), 30, 60 * math.sin(a)))},
    "sec_pts": {},
    "splice": {
        "keep_box": boxes[sec.Name], "src_box": boxes[s2.Name],
        "axis_x": V.model_to_sheet(sec, (0, 0, 0))[0],
        "keep_side": 1 if V.model_to_sheet(sec, (70, 0, 0))[0] > V.model_to_sheet(sec, (0, 0, 0))[0] else -1,
        "src_axis": [V.model_to_sheet(s2, (0, 0, 0)), V.model_to_sheet(s2, (0, 30, 0))],
        "src_boss": V.model_to_sheet(s2, boss2),
        "src_pts": [V.model_to_sheet(s2, p) for p in ((0, 0, 0), (0, 30, 0), boss2)],
        "dst_pts": [V.model_to_sheet(sec, rotY(*p)) for p in ((0, 0, 0), (0, 30, 0), boss2)],
        "s1_line": [[115 + L1[0][0], 80 + L1[0][1]], [115 + L1[1][0], 80 + L1[1][1]]],
    },
    "cut": [V.model_to_sheet(top, (E1[0], 30, E1[1])), V.model_to_sheet(top, (0, 30, 0)), V.model_to_sheet(top, (E2[0], 30, E2[1]))],
    "aux_hole": V.model_to_sheet(aux, hole),
    "aux_top": max(boxes[aux.Name][3], 0),
    "aux_cx": (boxes[aux.Name][0] + boxes[aux.Name][2]) / 2,
    "sec_box": boxes[sec.Name], "top_box": boxes[top.Name], "fr_box": boxes[fr.Name],
}
json.dump(lay, open(os.path.join(D, "layout.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(lay, indent=1))
V.dump_dxf(os.path.join(D, "rb_sw.DXF"), lay["VIEWS"])

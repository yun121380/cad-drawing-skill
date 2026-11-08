"""复杂轴承座视图（A3 1:1，第一角），位置和剖切全部由 params.py 算出：
主视图（沿轴线看）：右半剖（剖到前后对称面 Z=0）+ 左边安装孔局部剖；左视图 A-A：沿 X=0 全剖；
俯视图：外形；局部放大图 I（4:1）：密封槽和倒角。视图摆放写进 layout.json 给 drawing.py 用。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sw_views as V
from params import *

D = os.path.dirname(os.path.abspath(__file__))
part = os.path.join(D, "轴承座.SLDPRT")
base = os.path.join(D, "zcz_sw")
# 主视图 / A-A / 俯视图中心（图纸 mm）。主视图的高度位置按尺寸行数推出来：俯视图上边 + Φ90 一行 + 主视图下面两行尺寸
# 共留 32 mm，改了参数视图变高也不会挤（实测：中心高 70→75 时主视图下面的 176 和俯视图上面的 Φ90 挤到了一起）
TC = (125, 80)
FC = (125, round(TC[1] + L / 2 + 32 + H_TOTAL / 2, 1))
AC = (275, FC[1])
assert FC[1] + H_TOTAL / 2 + 14 < 292 - 5, "主视图上面放不下 Φ20 尺寸了：换 A2 或者 1:1.5"
DET_AT, DET_K, DET_R = (362, 150), 4, 7

sw = V.connect()
drw = V.new_drawing(sw, "A3")
front = V.model_view(drw, part, "*前视", FC)
# 视图坐标原点 = 视图中心 = 外框中心 (X 0, Y H_TOTAL/2)
far = H_TOTAL / 2 + 15
sec = V.section(drw, front, (0, far), (0, -far), AC, "A")
top = V.projected(drw, front, TC)
V.half_section(drw, front, L / 2, side="right")
hx, hy = -HOLE_X, BASE_H / 2 - H_TOTAL / 2
V.broken_out(drw, front, [(hx + dx, hy + dy) for dx, dy in ((-13, -11), (9, -12), (11, -2), (9, 10), (-2, 12), (-14, 3))], L / 2)
det_c = (L / 2 - 6, AXIS_H + SEAL_D / 2 - H_TOTAL / 2)        # A-A 视图坐标：密封槽 + 倒角
det = V.detail(drw, sec, det_c, DET_R, DET_AT, (DET_K, 1), "I")
boxes = V.finish(drw, [front, sec, top, det])
V.export(drw, base)
VB = [tuple(round(v) + d for v, d in zip(b, (-3, -3, 3, 3))) for b in boxes.values()]
print("VIEWS =", VB)

# 放大图实际放在哪：找 DXF 里半径 = DET_R·DET_K 的圆弧
import ezdxf
msp = ezdxf.readfile(base + ".DXF").modelspace()
arc = [e for e in msp.query("ARC CIRCLE") if abs(e.dxf.radius - DET_R * DET_K) < 0.01]
arc = min(arc, key=lambda e: (e.dxf.center.x - DET_AT[0]) ** 2 + (e.dxf.center.y - DET_AT[1]) ** 2)  # 主视图里也可能有同半径的圆弧
dc = (round(arc.dxf.center.x, 3), round(arc.dxf.center.y, 3))
# 放大图的 GetOutline 实测时大时小（这次只有 27×29），视图框改用放大圆算，否则 Sheet 会把框外的图线当模板删掉
rr = DET_R * DET_K + 4
VB[3] = (round(dc[0] - rr), round(dc[1] - rr), round(dc[0] + rr), round(dc[1] + rr))
json.dump({"FC": FC, "AC": AC, "TC": TC, "VIEWS": VB, "DET": {"center": dc, "k": DET_K, "r": DET_R,
           "src": [AC[0] + det_c[0], AC[1] + det_c[1]]}}, open(os.path.join(D, "layout.json"), "w", encoding="utf-8"))
print("放大图中心", dc)
V.dump_dxf(base + ".DXF", VB)

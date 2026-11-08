"""半剖 + 局部剖示例（A3 1:1）：凸缘套筒，轴线竖直。
主视图：右半剖（矩形局部剖压在轴线上，剖到对称面 Z=0），左半外形上再局部剖一个 Φ8 径向孔；俯视图外形。
零件：凸缘 Φ100×15，筒体 Φ60 总高 95，内孔 Φ30，凸缘 4×Φ12（R40 均布在 X/Z 轴上），筒体左侧 Φ8 径向孔（Y=60）。"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import sw_part as S, sw_views as V
import pythoncom
from win32com.client import VARIANT

mm = 0.001
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
part = os.path.join(OUT, "bush_half.SLDPRT")
sw = S.connect(); sw.CloseAllDocuments(True)
p = S.new_part(sw)
sm = S.sketch_on(p, "front")
sm.CreateCenterLine(0, -0.01, 0, 0, 0.2, 0)
pts = [(15, 0), (50, 0), (50, 15), (30, 15), (30, 95), (15, 95)]
for a, b in zip(pts, pts[1:] + pts[:1]):
    sm.CreateLine(a[0] * mm, a[1] * mm, 0, b[0] * mm, b[1] * mm, 0)
sm.AddToDB = False
assert p.FeatureManager.FeatureRevolve2(True, True, False, False, False, False, 0, 0, 2 * math.pi, 0,
                                        False, False, 0, 0, 0, 0, 0, True, False, True)
sm = S.sketch_on(p, "top")
for x, z in ((40, 0), (-40, 0), (0, 40), (0, -40)):
    sm.CreateCircleByRadius(x * mm, z * mm, 0, 6 * mm)
S.cut_through(p)
# 径向孔：右视基准面（X=0）上画圆，单向盲切 40 只切穿一侧壁；用质心判断切到了哪边，要的是 -X 侧
st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
for flip in (False, True):
    sm = S.sketch_on(p, "right")
    sm.CreateCircleByRadius(0, 60 * mm, 0, 4 * mm)
    sm.AddToDB = False
    f = p.FeatureManager.FeatureCut4(True, False, flip, 0, 0, 40 * mm, 0, False, False, False, False, 0, 0,
                                     False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
    cx = p.Extension.GetMassProperties(1, st)[0]
    if cx > 0:
        break
    p.EditUndo2(1)                      # 切到 +X 侧了，撤销换方向
S.set_material(p)
S.save(p, part, also=())
print("box", [round(v / mm, 1) for v in p.GetPartBox(True)], "质心 x", round(cx / mm, 3))

base = os.path.join(OUT, "bush_half_sw")
drw = V.new_drawing(sw, "A3")
front = V.model_view(drw, part, "*前视", (120, 200))
top = V.projected(drw, front, (120, 85))
# 视图坐标原点 = 外框中心 (0, 47.5)；零件最前面 Z=50，剖到对称面 Z=0 -> depth 50
V.half_section(drw, front, 50, side="right")
# 径向孔在 X=-30..-15、Y=60 -> 视图 y=12.5；波浪线边界伸出左轮廓一点
V.broken_out(drw, front, [(-36, 3), (-22, 1), (-11, 7), (-12, 19), (-24, 24), (-37, 20)], 50)
boxes = V.finish(drw, [front, top])
V.export(drw, base)
VB = [tuple(round(v) + d for v, d in zip(b, (-3, -3, 3, 3))) for b in boxes.values()]
print("VIEWS =", VB)
V.dump_dxf(base + ".DXF", VB)

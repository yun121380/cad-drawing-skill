"""旋转剖、斜视图的试件。
摇臂 rocker：中间轮毂 Φ40 高 30（轴线 Y），孔 Φ20；臂 1 沿 +X 到 X=70，臂 2 在 XZ 平面内与 +X 成 150°、长 60；
  臂厚 10（Y 0..10）、宽 16；两臂端头各一个凸台 Φ26 高 20，孔 Φ12 / Φ10。
弯板 bent：底板 100×60×10（X -50..50，Y 0..10，Z ±30）；右端起一块 45° 斜板（厚 10，沿斜向长 70，宽 60），
  斜板中部一个垂直于板面的孔 Φ20。"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import sw_part as S
import pythoncom
from win32com.client import VARIANT
mm = 0.001
OUT = os.path.dirname(os.path.abspath(__file__))
sw = S.connect(); sw.CloseAllDocuments(True)


def poly(sm, pts):
    for a, b in zip(pts, pts[1:] + pts[:1]):
        sm.CreateLine(a[0] * mm, a[1] * mm, 0, b[0] * mm, b[1] * mm, 0)


def ext(p, d, mid=False):
    p.SketchManager.AddToDB = False
    for flip in (False, True):
        f = p.FeatureManager.FeatureExtrusion3(True, False, flip, 6 if mid else 0, 0, d * mm, 0, False, False, False, False,
                                               0, 0, False, False, False, False, True, True, True, 0, 0, False)
        if f or mid: return f


def rev(p, cut):
    p.SketchManager.AddToDB = False
    assert p.FeatureManager.FeatureRevolve2(True, True, False, cut, False, False, 0, 0, 2 * math.pi, 0,
                                            False, False, 0, 0, 0, 0, 0, True, False, True)


def vol(p):
    st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    return p.Extension.GetMassProperties(1, st)[3] * 1e9


# ---------------- 摇臂（上视草图 y = -Z）
p = S.new_part(sw)
sm = S.sketch_on(p, "top"); sm.CreateCircleByRadius(0, 0, 0, 20 * mm); ext(p, 30)
a2 = math.radians(150)
for ang, L in ((0.0, 70), (a2, 60)):
    ux, uz = math.cos(ang), math.sin(ang)            # 模型 X、Z 方向
    nx, nz = -uz, ux
    q = [(0 + nx * 8, 0 + nz * 8), (L * ux + nx * 8, L * uz + nz * 8), (L * ux - nx * 8, L * uz - nz * 8), (-nx * 8, -nz * 8)]
    sm = S.sketch_on(p, "top"); poly(sm, [(x, -z) for x, z in q]); ext(p, 10)
    sm = S.sketch_on(p, "top"); sm.CreateCircleByRadius(L * ux * mm, -L * uz * mm, 0, 13 * mm); ext(p, 20)
print("摇臂 体积", round(vol(p)))
# 孔：绕各自竖直轴旋转切除（前视草图只能画在 Z=0 平面，斜臂的孔改用上视草图贯穿切除）
sm = S.sketch_on(p, "top"); sm.CreateCircleByRadius(0, 0, 0, 10 * mm)
sm.CreateCircleByRadius(70 * mm, 0, 0, 6 * mm)
sm.CreateCircleByRadius(60 * math.cos(a2) * mm, -60 * math.sin(a2) * mm, 0, 5 * mm)
S.cut_through(p)
print("摇臂 打孔后", round(vol(p)), "外框", [round(v / mm, 1) for v in p.GetPartBox(True)])
S.set_material(p); S.save(p, os.path.join(OUT, "rocker.SLDPRT"), also=())

# ---------------- 弯板
p = S.new_part(sw)
sm = S.sketch_on(p, "front"); poly(sm, [(-50, 0), (50, 0), (50, 10), (-50, 10)]); ext(p, 60, mid=True)
c, s_ = math.cos(math.radians(45)), math.sin(math.radians(45))
# 斜板截面：从 (50,0)-(50,10) 这条边起，沿 45° 方向伸 70；厚度方向 n = (-s, c)
A = (50, 0); u = (c, s_); n = (-s_, c)
B = (A[0] + 70 * u[0], A[1] + 70 * u[1])
q = [A, B, (B[0] + 10 * n[0], B[1] + 10 * n[1]), (A[0] + 10 * n[0], A[1] + 10 * n[1])]
# 斜板的厚度朝内侧（-s, c）会和底板重叠一点，合并没关系
sm = S.sketch_on(p, "front"); poly(sm, q); ext(p, 60, mid=True)
# 斜板中部孔 Φ20：绕“过斜板中点、垂直于板面”的轴旋转切除
M = (A[0] + 40 * u[0], A[1] + 40 * u[1])
sm = S.sketch_on(p, "front")
sm.CreateCenterLine((M[0] - 20 * n[0]) * mm, (M[1] - 20 * n[1]) * mm, 0, (M[0] + 30 * n[0]) * mm, (M[1] + 30 * n[1]) * mm, 0)
r = [(M[0] - 5 * n[0], M[1] - 5 * n[1]), (M[0] + 15 * n[0], M[1] + 15 * n[1])]
poly(sm, [r[0], r[1], (r[1][0] + 10 * u[0], r[1][1] + 10 * u[1]), (r[0][0] + 10 * u[0], r[0][1] + 10 * u[1])])
rev(p, cut=True)
print("弯板 体积", round(vol(p)), "外框", [round(v / mm, 1) for v in p.GetPartBox(True)])
S.set_material(p); S.save(p, os.path.join(OUT, "bent.SLDPRT"), also=())

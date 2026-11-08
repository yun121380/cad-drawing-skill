"""复杂轴承座（HT200）建模。坐标：轴孔轴线沿 Z，位于 (X=0, Y=70)；底面 Y=0；前后对称 Z ±30，左右对称 X=0。
底座 160×16×60，底面中间凹槽 90×3；支承板厚 20（Z ±10），下端 X ±50，上端与 R45 圆筒相切；
圆筒 Φ90×60，轴孔 Φ52H7，两端 C1.5 倒角，两端密封槽 Φ60×5（Z ±20..25），中间油槽 Φ56×8；
顶部油杯凸台 Φ20 到 Y=122，M10 螺孔（底孔 Φ8.5）通到轴孔；底座 2×Φ13 通孔 + Φ22 深 2 锪平，X ±64。
铸造圆角 R3：支承板与底座、支承板与圆筒、油杯凸台与圆筒的交线。"""
import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import sw_part as S
import pythoncom
from win32com.client import VARIANT

mm = 0.001
D = os.path.dirname(os.path.abspath(__file__))
NONE = VARIANT(pythoncom.VT_DISPATCH, None)
sw = S.connect(); sw.CloseAllDocuments(True)


def poly(sm, pts):
    for a, b in zip(pts, pts[1:] + pts[:1]):
        sm.CreateLine(a[0] * mm, a[1] * mm, 0, b[0] * mm, b[1] * mm, 0)


def ext_mid(p, depth):
    p.SketchManager.AddToDB = False
    f = p.FeatureManager.FeatureExtrusion3(True, False, False, 6, 0, depth * mm, 0, False, False, False, False,
                                           0, 0, False, False, False, False, True, True, True, 0, 0, False)
    assert f, "拉伸失败"


def cut_mid(p, depth):
    p.SketchManager.AddToDB = False
    f = p.FeatureManager.FeatureCut4(True, False, False, 6, 0, depth * mm, 0, False, False, False, False, 0, 0,
                                     False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
    assert f, "切除失败"


def revolve(p, cut=False):
    p.SketchManager.AddToDB = False
    f = p.FeatureManager.FeatureRevolve2(True, True, False, cut, False, False, 0, 0, 2 * math.pi, 0,
                                         False, False, 0, 0, 0, 0, 0, True, False, True)
    assert f, "旋转失败"


def vol(p):
    st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    return p.Extension.GetMassProperties(1, st)[3] * 1e9


# ---- 探测右视基准面草图坐标：sketch(x, y) -> 模型 (?, ?)
p = S.new_part(sw); sm = S.sketch_on(p, "right")
poly(sm, [(10, 30), (20, 30), (20, 40), (10, 40)]); S.extrude(p, 5)
b = [round(v / mm, 1) for v in p.GetPartBox(True)]; sw.CloseDoc(p.GetTitle)
print("右视草图 (10..20, 30..40) ->", b)
assert abs(b[1] - 30) < 0.1 and abs(b[4] - 40) < 0.1, "右视草图 y 不是模型 Y"
ZS = 1 if b[2] > 0 else -1      # 草图 x = ZS * 模型 Z（轴孔轮廓前后对称，这里只是记录）

p = S.new_part(sw)
log = []
def step(name):
    v = vol(p); log.append((name, round(v))); print(f"{name:12s} 体积 {v:,.0f} mm³")

from params import *
hb, hw, hl = BASE_L / 2, WEB_FOOT / 2, L / 2
R = BOSS_D / 2; C = (0.0, AXIS_H)
sm = S.sketch_on(p, "front"); poly(sm, [(-hb, 0), (hb, 0), (hb, BASE_H), (-hb, BASE_H)]); ext_mid(p, L); step("底座")
# 支承板：下端 (±WEB_FOOT/2, BASE_H)，上端切于圆筒
def tangent(P):
    dx, dy = P[0] - C[0], P[1] - C[1]; d = math.hypot(dx, dy)
    a = math.atan2(dy, dx) + math.acos(R / d) * (1 if P[0] > 0 else -1)
    return (C[0] + R * math.cos(a), C[1] + R * math.sin(a))
tr, tl = tangent((hw, BASE_H)), tangent((-hw, BASE_H))
print("切点", [round(v, 3) for v in tr], [round(v, 3) for v in tl])
sm = S.sketch_on(p, "front"); poly(sm, [(-hw, BASE_H), (hw, BASE_H), tr, C, tl]); ext_mid(p, WEB_T); step("支承板")
sm = S.sketch_on(p, "front"); sm.CreateCircleByRadius(0, AXIS_H * mm, 0, R * mm); ext_mid(p, L); step("圆筒")
# 油杯凸台：绕竖直轴 X=0 旋转，从圆筒里面一直到 OIL_TOP
y0 = AXIS_H + BORE_D / 2 + 4
sm = S.sketch_on(p, "front"); sm.CreateCenterLine(0, (y0 - 10) * mm, 0, 0, (OIL_TOP + 10) * mm, 0)
poly(sm, [(0, y0), (OIL_D / 2, y0), (OIL_D / 2, OIL_TOP), (0, OIL_TOP)]); revolve(p); step("油杯凸台")
sm = S.sketch_on(p, "front"); poly(sm, [(-RECESS_W / 2, -1), (RECESS_W / 2, -1), (RECESS_W / 2, RECESS_H), (-RECESS_W / 2, RECESS_H)])
cut_mid(p, L + 40); step("底面凹槽")

# ---- 铸造圆角（在打孔之前做，交线干净）
def fillet(points, r):
    """按“离点最近的边”选边。SelectByID2 选 EDGE 是沿当前视向打射线，会选到挡在前面的边（实测把圆筒前端面
    的圆边倒了圆）；这里遍历实体的边，用 GetClosestPointOn 求距离，取最近的那条。"""
    p.ClearSelection2(True)
    edges = p.GetBodies2(0, True)[0].GetEdges()
    for x, y, z in points:
        best = min(edges, key=lambda e: math.dist(e.GetClosestPointOn(x * mm, y * mm, z * mm)[:3],
                                                  (x * mm, y * mm, z * mm)))
        d = math.dist(best.GetClosestPointOn(x * mm, y * mm, z * mm)[:3], (x * mm, y * mm, z * mm)) / mm
        print(f"  选边 {(round(x, 2), round(y, 2), z)} 距离 {d:.3f}", best.Select4(True, NONE))
    f = p.FeatureManager.FeatureFillet3(195, r * mm, 0, 0, 0, 0, 0)
    print("  圆角", f is not None)
    return f
v0 = vol(p)
yob = AXIS_H + math.sqrt(R * R - (OIL_D / 2) ** 2)          # 油杯凸台与圆筒交线在 X=±OIL_D/2 处的高度
fillet([(0, BASE_H, WEB_T / 2), (0, BASE_H, -WEB_T / 2), (hw, BASE_H, 0), (-hw, BASE_H, 0),   # 支承板与底座
        (0, AXIS_H - R, WEB_T / 2), (0, AXIS_H - R, -WEB_T / 2),                              # 支承板与圆筒
        (OIL_D / 2, yob, 0), (-OIL_D / 2, yob, 0)], FIL)                                      # 油杯凸台与圆筒
step("铸造圆角")
assert vol(p) > v0, "凹边倒圆后体积应该变大：圆角倒到别的边上了"

# ---- 轴孔（右视基准面上的旋转切除）：倒角、密封槽、油槽，前后对称
r0, rs, ro = BORE_D / 2, SEAL_D / 2, OILG_D / 2
z1, z2 = hl - SEAL_E, hl - SEAL_E - SEAL_W           # 密封槽 Z 范围（正侧）
half = [(hl + 1, r0 + CH), (hl, r0 + CH), (hl - CH, r0), (z1, r0), (z1, rs), (z2, rs), (z2, r0),
        (OILG_W / 2, r0), (OILG_W / 2, ro)]
prof = [(hl + 1, 0)] + half + [(-z, r) for z, r in reversed(half)] + [(-hl - 1, 0)]
sm = S.sketch_on(p, "right"); sm.CreateCenterLine(-0.1, AXIS_H * mm, 0, 0.1, AXIS_H * mm, 0)
poly(sm, [(ZS * z, AXIS_H + r) for z, r in prof]); revolve(p, cut=True); step("轴孔")
# 油孔（螺纹底孔），从轴孔里一直通到顶面
sm = S.sketch_on(p, "front"); sm.CreateCenterLine(0, (AXIS_H) * mm, 0, 0, (OIL_TOP + 5) * mm, 0)
poly(sm, [(0, AXIS_H + r0 - 6), (TAP_D / 2, AXIS_H + r0 - 6), (TAP_D / 2, OIL_TOP + 1), (0, OIL_TOP + 1)])
revolve(p, cut=True); step("油孔")
# 底座安装孔 + 锪平
for xc in (HOLE_X, -HOLE_X):
    sm = S.sketch_on(p, "front"); sm.CreateCenterLine(xc * mm, -0.01, 0, xc * mm, (BASE_H + 10) * mm, 0)
    s = 1 if xc > 0 else -1
    poly(sm, [(xc, -1), (xc + s * HOLE_D / 2, -1), (xc + s * HOLE_D / 2, BASE_H - CB_H), (xc + s * CB_D / 2, BASE_H - CB_H),
              (xc + s * CB_D / 2, BASE_H + 1), (xc, BASE_H + 1)])
    revolve(p, cut=True)
step("安装孔")

S.set_material(p, "灰铸铁")
path = os.path.join(D, "轴承座.SLDPRT")
S.save(p, path, also=(".STEP",))
print("外框", [round(v / mm, 2) for v in p.GetPartBox(True)], "质量", round(S.mass_kg(p), 3), "kg")
S.snapshot(p, os.path.join(D, "轴承座_3D.png"))
json.dump({"ZS": ZS, "log": log, "tr": tr, "mass_kg": round(S.mass_kg(p), 3)}, open(os.path.join(D, "build.json"), "w", encoding="utf-8"), ensure_ascii=False)

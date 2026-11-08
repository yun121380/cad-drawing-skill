"""一级直齿圆柱齿轮减速器 —— SolidWorks 建零件 + 装配。
全局坐标：X 沿两轴中心连线（输入轴 X=0，输出轴 X=100），Y 竖直向上（Y=0 为箱盖/箱座结合面），Z 沿轴线。
齿轮 m=2.5，z1=20（d1=50），z2=60（d2=150），a=100。齿轮按齿根圆建模（轮齿在工程图里按规定画法补画）。
轴承 6206（输入轴）、6207（输出轴），凸缘式端盖。所有零件都在全局坐标里建，装配时按变换矩阵就位并固定。"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import sw_part as S
import pythoncom
from win32com.client import VARIANT

mm = 0.001
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(D, exist_ok=True)
NONE = VARIANT(pythoncom.VT_DISPATCH, None)

sw = S.connect()
sw.CloseAllDocuments(True)


def box(p):
    b = p.GetPartBox(True)
    return [round(v / mm, 2) for v in b]


def poly(sm, pts, close=True):
    n = len(pts)
    for i in range(n if close else n - 1):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        sm.CreateLine(x1 * mm, y1 * mm, 0, x2 * mm, y2 * mm, 0)


def extrude_mid(p, depth):
    p.SketchManager.AddToDB = False
    f = p.FeatureManager.FeatureExtrusion3(True, False, False, 6, 0, depth * mm, 0, False, False, False, False,
                                           0, 0, False, False, False, False, True, True, True, 0, 0, False)
    assert f is not None, "中面拉伸失败"
    return f


def cut_mid(p, depth):
    p.SketchManager.AddToDB = False
    f = p.FeatureManager.FeatureCut4(True, False, False, 6, 0, depth * mm, 0, False, False, False, False, 0, 0,
                                     False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
    assert f is not None, "中面切除失败"
    return f


def cut_blind(p, depth):
    p.SketchManager.AddToDB = False
    for flip in (False, True):
        f = p.FeatureManager.FeatureCut4(True, False, flip, 0, 0, depth * mm, 0, False, False, False, False, 0, 0,
                                         False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
        if f is not None:
            return f
    raise AssertionError("盲孔切除失败")


def revolve(p):
    p.SketchManager.AddToDB = False
    f = p.FeatureManager.FeatureRevolve2(True, True, False, False, False, False, 0, 0, 2 * math.pi, 0,
                                         False, False, 0, 0, 0, 0, 0, True, False, True)
    assert f is not None, "旋转失败"
    return f


# ---------- 探测上视基准面草图坐标与模型 X/Z 的对应关系
p = S.new_part(sw)
sm = S.sketch_on(p, "top")
poly(sm, [(10, 30), (20, 30), (20, 40), (10, 40)])
S.extrude(p, 5)
b = box(p)
print("探测 上视草图 (10..20, 30..40) -> 模型盒", b)
ZS = 1 if b[2] > 0 else -1          # 草图 y = ZS * 模型 Z
assert abs(b[0] - 10) < 0.01 and abs(b[3] - 20) < 0.01, "上视草图 x 不是模型 X"
sw.CloseDoc(p.GetTitle)
print("ZS =", ZS)


def rev_part(name, axis_x, rz, mat="普通碳钢", extra=None):
    """绕 X=axis_x 的 Z 向轴线旋转。rz 是 (r, z) 轮廓（模型 mm）。"""
    p = S.new_part(sw)
    sm = S.sketch_on(p, "top")
    sm.CreateCenterLine(axis_x * mm, -200 * mm, 0, axis_x * mm, 200 * mm, 0)
    poly(sm, [(axis_x + r, ZS * z) for r, z in rz])
    revolve(p)
    if extra:
        extra(p)
    S.set_material(p, mat)
    path = os.path.join(D, name + ".SLDPRT")
    S.save(p, path, also=())
    print(f"{name}: 盒 {box(p)}  质量 {S.mass_kg(p):.3f} kg")
    return path


def rings(name, d, D_, B, ri, ro, rb):
    """深沟球轴承（规定画法用）：内圈、外圈、钢球（圆环体）三个实体，中心在原点，宽度 Z ±B/2。"""
    p = S.new_part(sw)
    h = B / 2
    for prof in ([(d / 2, -h), (ri, -h), (ri, h), (d / 2, h)], [(ro, -h), (D_ / 2, -h), (D_ / 2, h), (ro, h)]):
        sm = S.sketch_on(p, "top")
        sm.CreateCenterLine(0, -0.1, 0, 0, 0.1, 0)
        poly(sm, [(r, ZS * z) for r, z in prof])
        revolve(p)
    sm = S.sketch_on(p, "top")
    sm.CreateCenterLine(0, -0.1, 0, 0, 0.1, 0)
    rc = (ri + ro) / 2
    sm.CreateCircleByRadius(rc * mm, 0, 0, rb * mm)
    revolve(p)
    S.set_material(p, "合金钢")
    path = os.path.join(D, name + ".SLDPRT")
    S.save(p, path, also=())
    print(f"{name}: 盒 {box(p)}  实体数 {p.GetBodies2(0, True).__len__()}  质量 {S.mass_kg(p):.3f} kg")
    return path


def obround(sm, u1, u2, v, b):
    """草图里沿 u 方向的长圆（键槽轮廓）：u1..u2 是槽两端（含圆头），v 是中心线，宽 b（mm）。"""
    r = b / 2; ua, ub = min(u1, u2) + r, max(u1, u2) - r
    sm.CreateLine(ua * mm, (v + r) * mm, 0, ub * mm, (v + r) * mm, 0)
    sm.CreateLine(ua * mm, (v - r) * mm, 0, ub * mm, (v - r) * mm, 0)
    sm.CreateArc(ua * mm, v * mm, 0, ua * mm, (v + r) * mm, 0, ua * mm, (v - r) * mm, 0, 1)
    sm.CreateArc(ub * mm, v * mm, 0, ub * mm, (v - r) * mm, 0, ub * mm, (v + r) * mm, 0, 1)


def shaft_keyway(p, z1, z2, b, x_bottom, t):
    """轴上 +X 一侧的普通平键键槽（A 型圆头）：Z 范围 z1..z2，宽 b，槽底在 X = x_bottom。
    右视基准面草图 x = 模型 -Z、y = 模型 Y；从基准面平移到槽底开始往 +X 切。"""
    sm = S.sketch_on(p, "right")
    obround(sm, -z2, -z1, 0, b)
    area = b * (abs(z2 - z1) - b) + math.pi * b * b / 4
    S.cut_offset(p, x_bottom, 20, lambda q: S.has_plane_face(q, 0, x_bottom), max_removed=area * t * 1.3)


def hub_keyway(p, xc, b, y_top, z_half=30):
    """轮毂 +Y 一侧的贯通键槽：宽 b（X 方向，中心 xc），槽顶在 Y = y_top。上视草图画矩形，从孔里面开始往 +Y 切。"""
    sm = S.sketch_on(p, "top")
    poly(sm, [(xc - b / 2, -z_half), (xc + b / 2, -z_half), (xc + b / 2, z_half), (xc - b / 2, z_half)])
    S.cut_offset(p, y_top - 12, 12, lambda q: S.has_plane_face(q, 1, y_top), max_removed=b * 2 * z_half * 6)


parts = {}
# ---------- 3 齿轮轴（输入）：Φ30 轴颈 / Φ36 轴肩 / 齿根 Φ43.75 齿宽 45 / Φ28 密封段 / Φ24 伸出端
parts["gear_shaft"] = rev_part("齿轮轴", 0, [
    (0, -50), (15, -50), (15, -33), (18, -33), (18, -22.5), (21.875, -22.5), (21.875, 22.5), (18, 22.5),
    (18, 33), (15, 33), (15, 49), (14, 49), (14, 75), (12, 75), (12, 125), (0, 125)],
    extra=lambda p: shaft_keyway(p, 80, 120, 8, 12 - 4, 4))

# ---------- 5 输出轴：Φ35 轴颈 / Φ42 轴肩 / Φ40 齿轮段 / Φ35 套筒+轴承 / Φ32 密封段 / Φ28 伸出端
parts["out_shaft"] = rev_part("输出轴", 100, [
    (0, 51), (17.5, 51), (17.5, 33), (21, 33), (21, 20), (20, 20), (20, -18), (17.5, -18),
    (17.5, -50), (16, -50), (16, -75), (14, -75), (14, -130), (0, -130)],
    extra=lambda p: (shaft_keyway(p, -15, 17, 12, 100 + 20 - 5, 5), shaft_keyway(p, -125, -80, 8, 100 + 14 - 4, 4)))


# ---------- 4 大齿轮：轮毂 Φ64 / 腹板厚 12 / 轮缘 齿根 Φ143.75，齿宽 40，腹板 4×Φ20 减重孔
def web_holes(p):
    sm = S.sketch_on(p, "front")
    for k in range(4):
        a = math.radians(45 + 90 * k)
        sm.CreateCircleByRadius((100 + 46 * math.cos(a)) * mm, 46 * math.sin(a) * mm, 0, 10 * mm)
    cut_mid(p, 30)


parts["gear"] = rev_part("大齿轮", 100, [
    (20, -20), (32, -20), (32, -6), (60, -6), (60, -20), (71.875, -20), (71.875, 20), (60, 20), (60, 6),
    (32, 6), (32, 20), (20, 20)], extra=lambda p: (web_holes(p), hub_keyway(p, 100, 12, 20 + 3.3)))

# ---------- 6 套筒
parts["sleeve"] = rev_part("套筒", 100, [(17.5, -33), (22, -33), (22, -20), (17.5, -20)], mat="普通碳钢")

# ---------- 端盖（凸缘式）
parts["cap_in_blind"] = rev_part("输入轴闷盖", 0, [
    (0, -70), (41, -70), (41, -60), (31, -60), (31, -49), (24, -49), (24, -56), (0, -56)], mat="灰铸铁")
parts["cap_in_thru"] = rev_part("输入轴透盖", 0, [
    (15, 56), (24, 56), (24, 49), (31, 49), (31, 60), (41, 60), (41, 70), (15, 70)], mat="灰铸铁")
parts["cap_out_blind"] = rev_part("输出轴闷盖", 100, [
    (0, 56), (30, 56), (30, 50), (36, 50), (36, 60), (46, 60), (46, 70), (0, 70)], mat="灰铸铁")
parts["cap_out_thru"] = rev_part("输出轴透盖", 100, [
    (17, -56), (30, -56), (30, -50), (36, -50), (36, -60), (46, -60), (46, -70), (17, -70)], mat="灰铸铁")

# ---------- 轴承
parts["b6206"] = rings("轴承6206", 30, 62, 16, 18.5, 27.5, 4.4)
parts["b6207"] = rings("轴承6207", 35, 72, 17, 21.5, 32.0, 5.15)


# ---------- 2 箱盖
def tangent_pts(r1, r2, d=100.0):
    s = (r2 - r1) / d; c = math.sqrt(1 - s * s)
    return (-s * r1, c * r1), (d - s * r2, c * r2)


def cover():
    p = S.new_part(sw)
    sm = S.sketch_on(p, "front")
    (ax, ay), (bx, by) = tangent_pts(48, 98)
    sm.CreateArc(0, 0, 0, -48 * mm, 0, 0, ax * mm, ay * mm, 0, -1)
    sm.CreateLine(ax * mm, ay * mm, 0, bx * mm, by * mm, 0)
    sm.CreateArc(100 * mm, 0, 0, bx * mm, by * mm, 0, 198 * mm, 0, 0, -1)
    sm.CreateLine(198 * mm, 0, 0, -48 * mm, 0, 0)
    extrude_mid(p, 76)                                   # 外壁 Z ±38
    sm = S.sketch_on(p, "front")
    poly(sm, [(-68, 0), (218, 0), (218, 12), (-68, 12)])
    extrude_mid(p, 120)                                  # 结合面凸缘 Y 0..12，Z ±60
    sm = S.sketch_on(p, "front")
    for xc, r in ((0, 44), (100, 49)):                   # 轴承座凸台（上半）
        sm.CreateArc(xc * mm, 0, 0, (xc + r) * mm, 0, 0, (xc - r) * mm, 0, 0, 1)
        sm.CreateLine((xc - r) * mm, 0, 0, (xc + r) * mm, 0, 0)
    extrude_mid(p, 120)
    sm = S.sketch_on(p, "front")                         # 内腔
    (ax, ay), (bx, by) = tangent_pts(40, 90)
    sm.CreateArc(0, 0, 0, -40 * mm, 0, 0, ax * mm, ay * mm, 0, -1)
    sm.CreateLine(ax * mm, ay * mm, 0, bx * mm, by * mm, 0)
    sm.CreateArc(100 * mm, 0, 0, bx * mm, by * mm, 0, 190 * mm, 0, 0, -1)
    sm.CreateLine(190 * mm, 0, 0, -40 * mm, 0, 0)
    cut_mid(p, 60)
    sm = S.sketch_on(p, "front")                         # 轴承孔
    sm.CreateCircleByRadius(0, 0, 0, 31 * mm); sm.CreateCircleByRadius(100 * mm, 0, 0, 36 * mm)
    cut_mid(p, 200)
    sm = S.sketch_on(p, "top")                           # 结合面螺栓孔 4×Φ11
    for x in (-58, 208):
        for z in (-45, 45):
            sm.CreateCircleByRadius(x * mm, z * mm, 0, 5.5 * mm)
    cut_blind(p, 12)
    S.set_material(p, "灰铸铁")
    path = os.path.join(D, "箱盖.SLDPRT")
    S.save(p, path, also=())
    print(f"箱盖: 盒 {box(p)}  质量 {S.mass_kg(p):.3f} kg")
    return path


def base():
    p = S.new_part(sw)
    sm = S.sketch_on(p, "front")
    poly(sm, [(-48, -125), (198, -125), (198, 0), (-48, 0)])
    extrude_mid(p, 76)                                   # 箱壁 Z ±38
    sm = S.sketch_on(p, "front")
    poly(sm, [(-68, -12), (218, -12), (218, 0), (-68, 0)])
    extrude_mid(p, 120)                                  # 结合面凸缘
    sm = S.sketch_on(p, "front")
    poly(sm, [(-98, -125), (248, -125), (248, -107), (-98, -107)])
    extrude_mid(p, 150)                                  # 底座凸缘 Z ±75
    sm = S.sketch_on(p, "front")
    for xc, r in ((0, 44), (100, 49)):                   # 轴承座凸台（下半）
        sm.CreateArc(xc * mm, 0, 0, (xc - r) * mm, 0, 0, (xc + r) * mm, 0, 0, 1)
        sm.CreateLine((xc + r) * mm, 0, 0, (xc - r) * mm, 0, 0)
    extrude_mid(p, 120)
    sm = S.sketch_on(p, "front")                         # 内腔 Y -113..0
    poly(sm, [(-40, -113), (190, -113), (190, 0), (-40, 0)])
    cut_mid(p, 60)
    sm = S.sketch_on(p, "front")
    sm.CreateCircleByRadius(0, 0, 0, 31 * mm); sm.CreateCircleByRadius(100 * mm, 0, 0, 36 * mm)
    cut_mid(p, 200)
    sm = S.sketch_on(p, "top")                           # 结合面螺栓孔 4×Φ11（盲 12）
    for x in (-58, 208):
        for z in (-45, 45):
            sm.CreateCircleByRadius(x * mm, z * mm, 0, 5.5 * mm)
    cut_blind(p, 12)
    sm = S.sketch_on(p, "top")                           # 地脚螺栓孔 4×Φ18
    for x in (-80, 230):
        for z in (-58, 58):
            sm.CreateCircleByRadius(x * mm, z * mm, 0, 9 * mm)
    S.cut_through(p)
    S.set_material(p, "灰铸铁")
    path = os.path.join(D, "箱座.SLDPRT")
    S.save(p, path, also=())
    print(f"箱座: 盒 {box(p)}  质量 {S.mass_kg(p):.3f} kg")
    return path


parts["cover"] = cover()
parts["base"] = base()

import json
with open(os.path.join(D, "parts.json"), "w", encoding="utf-8") as f:
    json.dump({"ZS": ZS, "parts": parts}, f, ensure_ascii=False, indent=1)
print("完成")

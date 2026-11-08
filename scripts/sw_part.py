"""SolidWorks 2025 COM 建模辅助：连接、新建零件、草图、拉伸/切除、保存、导出。

只用来建 3D 模型（给论文插图、算质量、ANSYS 导入 STEP）。
不要用 SolidWorks 自动工程图交付：AutoDimension 排得很乱、轴测图比例失控、标题栏空白 —— 2D 图一律走 sw_views + sw2acad。
"""
import os
import pythoncom
import win32com.client
from win32com.client import VARIANT

TPL = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2025\templates"
NOTHING = VARIANT(pythoncom.VT_DISPATCH, None)  # SelectByID2 的 Callout 参数必须这样传
mm = 0.001  # API 单位是米

PLANES = {"front": "前视基准面", "top": "上视基准面", "right": "右视基准面"}  # 中文 gb 模板


def connect(visible=True):
    sw = win32com.client.Dispatch("SldWorks.Application")  # 没开会自动启动，约 30-60 s
    sw.Visible = visible
    return sw  # 注意 sw.RevisionNumber 是属性不是方法


def new_part(sw):
    return sw.NewDocument(os.path.join(TPL, "gb_part.prtdot"), 0, 0, 0)


def sketch_on(part, plane="front"):
    ok = part.Extension.SelectByID2(PLANES.get(plane, plane), "PLANE", 0, 0, 0, False, 0, NOTHING, 0)
    assert ok, f"选不中基准面 {plane}"
    part.SketchManager.InsertSketch(True)
    part.SketchManager.AddToDB = True  # 关掉捕捉/推理，坐标精确
    return part.SketchManager


def extrude(part, depth_mm, flip=False):
    """结束当前草图并拉伸。草图内的内环自动成孔。"""
    part.SketchManager.AddToDB = False
    f = part.FeatureManager.FeatureExtrusion3(
        True, False, flip, 0, 0, depth_mm * mm, 0, False, False, False, False,
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    assert f is not None, "拉伸失败（草图不封闭？）"
    return f


def cut_through(part):
    """完全贯穿切除。草图在基准面上时方向常常反，失败就自动反向再试。"""
    part.SketchManager.AddToDB = False
    for flip in (False, True):
        f = part.FeatureManager.FeatureCut4(
            True, False, flip, 1, 0, 0.01, 0.01, False, False, False, False, 0, 0,
            False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
        if f is not None:
            return f
    raise AssertionError("切除失败（两个方向都没切到实体）")


def has_plane_face(part, axis, value, tol=0.01):
    """零件上有没有一个垂直于 axis（0=X 1=Y 2=Z）、位于 axis 坐标 = value（mm）的平面面（键槽底面、台阶面等）。
    用来核对切除方向对不对：面的外框在该轴上是一个值。"""
    for b in part.GetBodies2(0, True) or []:
        fs = b.GetFaces
        for f in (fs() if callable(fs) else fs) or []:     # 晚绑定有时把无参方法当属性，有时不当（实测两种都有）
            bx = f.GetBox
            bx = bx() if callable(bx) else bx
            lo, hi = bx[axis] * 1000, bx[axis + 3] * 1000
            if abs(hi - lo) < tol and abs(lo - value) < tol:
                return True
    return False


def volume_mm3(part):
    st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    return part.Extension.GetMassProperties(1, st)[3] * 1e9


def cut_offset(part, start_mm, depth_mm, check, max_removed=None):
    """结束当前草图，从“草图基准面平移 start_mm”的位置开始切 depth_mm（键槽、轮毂槽：草图画在过轴线的基准面上，
    从槽底开始往外切）。方向组合（起始偏移反不反、切除方向反不反）逐个试，切完用 check(part) 核对
    （如 lambda p: has_plane_face(p, 0, 115) —— 槽底面在 X=115），不对就撤销再试。2026-11-08。
    只查槽底面不够：切反了（从槽底往轴心切）同样会在槽底位置留下一个平面——实测输出轴被切掉 15000 mm³。
    所以再给 max_removed（mm³，槽的体积上限，如 槽面积×槽深×1.3），切掉的比它多就算错。"""
    part.SketchManager.AddToDB = False
    part.SketchManager.InsertSketch(True)                   # 退出草图，后面每次重新选它（草图编辑中算不了质量属性）
    part.EditRebuild3
    v0 = volume_mm3(part)
    name = part.FeatureByPositionReverse(0).Name
    for flip_start in (False, True):
        for flip in (False, True):
            part.ClearSelection2(True)
            part.Extension.SelectByID2(name, "SKETCH", 0, 0, 0, False, 0, NOTHING, 0)
            f = part.FeatureManager.FeatureCut4(
                True, False, flip, 0, 0, depth_mm * mm, 0, False, False, False, False, 0, 0,
                False, False, False, False, False, True, True, True, True, False, 3, start_mm * mm, flip_start, False)
            if f is None:
                continue
            dv = v0 - volume_mm3(part)
            if check(part) and dv > 1 and (max_removed is None or dv <= max_removed):
                return f
            part.EditUndo2(1)
    raise AssertionError("偏移切除：四种方向都不对")


def set_material(part, name="普通碳钢", db="SOLIDWORKS Materials"):
    part.SetMaterialPropertyName2("", db, name)


def mass_kg(part):
    """CreateMassProperty 晚绑定调不到；GetMassProperties 的 status 是 byref，要传 VARIANT。
    返回数组 [cx, cy, cz, 体积m³, 面积m², 质量kg, ...]"""
    st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    return part.Extension.GetMassProperties(1, st)[5]


def save(part, path, also=(".STEP", ".x_t")):
    """保存 SLDPRT，并按 also 导出中性格式（给 ANSYS 用 STEP）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    e = part.SaveAs3(path, 0, 1)
    assert e == 0 and os.path.exists(path), f"保存失败 {e}"
    base = os.path.splitext(path)[0]
    for ext in also:
        part.SaveAs3(base + ext, 0, 1)
    return path


def snapshot(part, png, view="*等轴测"):
    """等轴测截图，给论文插图用。"""
    part.ShowNamedView2(view, 7)
    part.ViewZoomtofit2()
    part.SaveAs3(png, 0, 1)
    return png

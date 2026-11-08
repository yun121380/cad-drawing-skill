"""sw_std —— 用 SolidWorks Toolbox 的 GB 基础零件生成指定规格的标准件（2026-11-08）。

Toolbox 没有“按规格生成零件”的 COM 接口（toolboxapi.chm 里只有 PDM 相关的东西），但基础零件
C:\\SOLIDWORKS Data\\browser\\GB\\...\\*.sldprt 里驱动尺寸都有名字（螺栓 s/k/d/l，螺母 s/m/D，键 b/h/L……）。
做法：只读打开基础零件 → 删掉设计表（否则重建时尺寸被改回去）→ 按这里的 GB 尺寸表改驱动尺寸 → 压缩“螺纹纹理”
（一串环形切槽，工程图里会出一堆线；装饰螺纹线保留）→ 去掉 Toolbox 标记 → 写自定义属性（代号/名称/规格/材料）
→ 另存到项目目录。生成的是普通零件，装配、出图、明细栏都能直接用。

    import sw_std
    path = sw_std.make(sw, "bolt", "M10x40", out_dir)      # GB/T 5782 六角头螺栓
    sw_std.make(sw, "nut", "M10", out_dir)                 # GB/T 6170 1 型六角螺母
    sw_std.make(sw, "washer", "10", out_dir)               # GB/T 97.1 平垫圈
    sw_std.make(sw, "key", "8x7x36", out_dir)              # GB/T 1096 A 型普通平键 b×h×L
    sw_std.make(sw, "pin", "6x30", out_dir)                # GB/T 119.1 圆柱销 d×l
    sw_std.make(sw, "bearing", "6206", out_dir)            # GB/T 276 深沟球轴承
返回 (路径, 信息 dict)，信息里有 代号、名称、规格、材料，直接给明细栏用。"""
import os, re
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

LIB = r"C:\SOLIDWORKS Data\browser\GB"
NONE = VARIANT(pythoncom.VT_DISPATCH, None)

PITCH = {6: 1, 8: 1.25, 10: 1.5, 12: 1.75, 16: 2, 20: 2.5, 24: 3, 30: 3.5}
# GB/T 5782-2016 六角头螺栓：d: (s, k, b[l≤125])
BOLT = {6: (10, 4, 18), 8: (13, 5.3, 22), 10: (16, 6.4, 26), 12: (18, 7.5, 30), 16: (24, 10, 38),
        20: (30, 12.5, 46), 24: (36, 15, 54), 30: (46, 18.7, 66)}
# GB/T 6170-2015 1 型六角螺母：d: (s, m)
NUT = {6: (10, 5.2), 8: (13, 6.8), 10: (16, 8.4), 12: (18, 10.8), 16: (24, 14.8), 20: (30, 18), 24: (36, 21.5), 30: (46, 25.6)}
# GB/T 97.1-2002 平垫圈 A 级：规格: (d1, d2, h)
WASHER = {6: (6.4, 12, 1.6), 8: (8.4, 16, 1.6), 10: (10.5, 20, 2), 12: (13, 24, 2.5), 16: (17, 30, 3),
          20: (21, 37, 3), 24: (25, 44, 4), 30: (31, 56, 4)}
# GB/T 276-2013 深沟球轴承：代号: (d, D, B)
BEARING = {"6204": (20, 47, 14), "6205": (25, 52, 15), "6206": (30, 62, 16), "6207": (35, 72, 17), "6208": (40, 80, 18),
           "6209": (45, 85, 19), "6210": (50, 90, 20), "6211": (55, 100, 21), "6212": (60, 110, 22),
           "6304": (20, 52, 15), "6305": (25, 62, 17), "6306": (30, 72, 19), "6307": (35, 80, 21), "6308": (40, 90, 23),
           "6309": (45, 100, 25), "6310": (50, 110, 27)}
KEY_BH = {(4, 4), (5, 5), (6, 6), (8, 7), (10, 8), (12, 8), (14, 9), (16, 10), (18, 11), (20, 12), (22, 14), (25, 14), (28, 16)}

KINDS = {
    "bolt": (r"bolts and studs\hexagon head bolts\hexagon head bolts gb.sldprt", "GB/T 5782-2016", "六角头螺栓", "8.8 级"),
    "nut": (r"nuts\hexagon nuts\hex nuts, style 1-grades ab gb.sldprt", "GB/T 6170-2015", "1型六角螺母", "8 级"),
    "washer": (r"washers and rings\plain washer\plain washers-n series-grade a gb.sldprt", "GB/T 97.1-2002", "平垫圈", "200HV"),
    "key": (r"pins and keys\parallel keys\plain parallel keys.sldprt", "GB/T 1096-2003", "普通平键", "45"),
    "pin": (r"pins and keys\parallel pins\parallel pins unhardening steel gb.sldprt", "GB/T 119.1-2000", "圆柱销", "35"),
    "bearing": (r"bearing\rolling bearings\deep groove ball bearings gb.sldprt", "GB/T 276-2013", "深沟球轴承", ""),
}


def _dims(kind, size):
    """规格 → [(尺寸全名不带零件名, 值 mm)], 要压缩的特征, 规格字符串。"""
    nums = [float(v) for v in re.findall(r"[\d.]+", size)]
    if kind == "bolt":
        d, l = int(nums[0]), nums[1]; s, k, b = BOLT[d]; P = PITCH[d]
        return [("s@Sketch-BaseHead", s), ("k@BaseHead", k), ("d@Sketch3", d), ("l@BaseBody", l),
                ("lg@Plane2", max(l - b, 0.5)), ("D2@ThreadCosmetic1", d - 1.0825 * P)], \
            ["Cut-Revolve10", "LPattern10"], f"M{d}×{l:g}"
    if kind == "nut":
        d = int(nums[0]); s, m = NUT[d]; P = PITCH[d]
        return [("s@Sketch1", s), ("m@BaseNut", m), ("D@Sketch1", d - 1.0825 * P), ("D@ThreadCosmetic1", d)], \
            ["Cut-Revolve10", "LPattern10"], f"M{d}"
    if kind == "washer":
        d = int(nums[0]); d1, d2, h = WASHER[d]
        return [("d1@Sketch1", d1), ("d2@Sketch1", d2), ("h@Base-Extrude", h)], [], f"{d}"
    if kind == "key":
        b, h, L = nums
        if (int(b), int(h)) not in KEY_BH:
            raise ValueError(f"键 {b}×{h} 不是 GB/T 1096 的标准截面")
        return [("b@Sketch1", b), ("h@BaseKey", h), ("L@Sketch1", L), ("c@Chamfer1", 0.25 if b <= 6 else 0.4)], [], \
            f"{b:g}×{h:g}×{L:g}"
    if kind == "pin":
        d, l = nums
        return [("d@Sketch1", d), ("l@Sketch1", l), ("c@Sketch1", round(0.12 * d + 0.05, 2))], [], f"{d:g}×{l:g}"
    if kind == "bearing":
        d, D, B = BEARING[size]
        return [("d@Sketch2", d), ("DD@Sketch3", D), ("B@Sketch2", B), ("r@Fillet1", 0.6 if d < 30 else 1.0)], [], size
    raise ValueError(kind)


# 生成后零件自身的坐标约定（实测外框，2026-11-08）：
#   bolt：轴线 +X，头顶在 X=0，螺杆朝 +X；头下支承面在 X = 外框 xmax − l
#   nut / washer：轴线 Z，零件在 Z ∈ [−厚, 0]
#   key：长度沿 X（−(L−b/2) .. b/2），宽 Y ±b/2，高 Z ±h/2
#   pin：轴线 +X，X ∈ [0, l]
#   bearing：轴线 X，X ∈ [−B/2, B/2]
LOCAL = {"bolt": (0, 0, 0), "nut": (0, 0, 2), "washer": (0, 0, 2), "key": (0, 0, 0), "pin": (0, 0, 0), "bearing": (0, 0, 0)}
AXIS = {"bolt": (1, 0, 0), "nut": (0, 0, 1), "washer": (0, 0, 1), "key": (1, 0, 0), "pin": (1, 0, 0), "bearing": (1, 0, 0)}


def place(asm, sw, path, kind, origin, axis, ref=None, up=None):
    """把标准件放进装配体：零件自身轴线（AXIS[kind]）转到 axis，零件上的参考点 ref（零件坐标，mm，默认原点）
    放到 origin（装配坐标，mm）。up 指定第二个方向（零件的 +Y 转到哪；键的宽度方向等），不给就自动取垂直的。
    例：螺栓头下支承面中心放在孔口、螺杆朝 −Y：place(asm, sw, p, "bolt", (x, 12, z), (0,-1,0), ref=(xmax-l, 0, 0))"""
    import numpy as np
    a_l = np.array(AXIS[kind], float)
    a_t = np.array(axis, float); a_t /= np.linalg.norm(a_t)
    # 零件的第二基向量：与 a_l 垂直的 +Y 或 +X
    b_l = np.array((0, 1, 0) if abs(a_l[1]) < 0.9 else (1, 0, 0), float)
    if up is None:
        tmp = np.array((0, 0, 1) if abs(a_t[2]) < 0.9 else (1, 0, 0), float)
        b_t = np.cross(tmp, a_t); b_t /= np.linalg.norm(b_t)
    else:
        b_t = np.array(up, float); b_t -= b_t.dot(a_t) * a_t; b_t /= np.linalg.norm(b_t)
    c_l, c_t = np.cross(a_l, b_l), np.cross(a_t, b_t)
    L = np.array([a_l, b_l, c_l]); Tg = np.array([a_t, b_t, c_t])
    R = np.linalg.solve(L, Tg)                     # 行向量约定：p' = p·R + T，R 的第 i 行是零件第 i 个基向量的像
    ref = np.array(ref or (0, 0, 0), float)
    T = np.array(origin, float) - ref.dot(R)
    c = asm.AddComponent5(path, 0, "", False, "", 0, 0, 0)
    if c is None:
        raise RuntimeError("插入失败（零件要先在 SW 里打开）：" + path)
    mu = sw.GetMathUtility
    arr = VARIANT(0x2005, [float(v) for v in list(R.flatten()) + list(T / 1000) + [1.0, 0, 0, 0]])
    xf = wc.Dispatch(mu._oleobj_.Invoke(mu._oleobj_.GetIDsOfNames("CreateTransform"), 0, pythoncom.DISPATCH_METHOD, True, arr))
    c.Transform2 = xf
    return c


def make(sw, kind, size, out_dir, material="普通碳钢"):
    rel, std, cname, grade = KINDS[kind]
    dims, suppress, spec = _dims(kind, size)
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{std.split('-')[0].replace('/', '').replace(' ', '')}_{cname}_{spec.replace('×', 'x')}.SLDPRT"
    out = os.path.join(out_dir, fname)
    e, w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0), VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    p = sw.OpenDoc6(os.path.join(LIB, rel), 1, 1 | 64, "", e, w)        # 只读 + 静默，不碰库文件
    if p is None:
        raise RuntimeError(f"打不开 Toolbox 基础零件 {rel}（错误 {e.value}）")
    title = p.GetTitle
    try:
        p.DeleteDesignTable                                             # 设计表会在重建时把尺寸改回去
        missing = []
        for name, v in dims:
            prm = p.Parameter(name)
            if prm is None:
                missing.append(name); continue
            prm.SetSystemValue3(v / 1000, 2, NONE)                       # 2 = 所有配置
        p.EditRebuild3
        for fn in suppress:
            if p.Extension.SelectByID2(fn, "BODYFEATURE", 0, 0, 0, False, 0, NONE, 0):
                p.EditSuppress2
        p.ClearSelection2(True)
        try:
            p.Extension.ToolboxPartType = 0                              # 去掉 Toolbox 标记，变成普通零件
        except Exception:
            pass
        p.SetMaterialPropertyName2("", "SOLIDWORKS Materials", material)
        cpm = p.Extension.CustomPropertyManager("")
        info = {"代号": std, "名称": cname, "规格": spec, "材料": grade, "标记": f"{cname} {std.split('-')[0]} {spec}"}
        for k, v in info.items():
            cpm.Add3(k, 30, v, 1)
        p.EditRebuild3
        if os.path.exists(out):
            os.remove(out)
        r = p.SaveAs3(out, 0, 2)                                         # 2 = 另存为副本也行，这里直接另存
        if r != 0 or not os.path.exists(out):
            raise RuntimeError(f"另存失败 {r}：{out}")
        st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        mp = p.Extension.GetMassProperties(1, st)
        info["质量kg"] = round(mp[5], 4); info["体积mm3"] = round(mp[3] * 1e9, 1)
        info["外框"] = [round(v * 1000, 2) for v in p.GetPartBox(True)]
        if missing:
            info["没找到的尺寸"] = missing
        return out, info
    finally:
        sw.CloseDoc(p.GetTitle if p else title)

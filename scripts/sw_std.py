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
import os, re, math
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

def _cfg(k, default):
    import json
    try:
        return json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
                              encoding="utf-8")).get(k) or default
    except Exception:
        return default


LIB = _cfg("toolbox_gb", r"C:\SOLIDWORKS Data\browser\GB")      # 换电脑改 config.json
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


# ====================================================================== 2026-11-08：任意 Toolbox GB 件（读 Toolbox 自带尺寸库）
# 上面 make() 的六种件是手录尺寸表；下面 make_any() 直接解释 Toolbox 的配置库（toolbox_db），尺寸来自 SW 官方库。
# 新增常用件（kind → Toolbox 里的类型名、中文名、默认性能等级/材料）：
TB_KINDS = {
    "screw":         ("GB/T70.1-2000", "内六角圆柱头螺钉", "8.8 级"),       # size "M8x25"
    "screw_hex":     ("GB/T5783-2000", "六角头螺栓（全螺纹）", "8.8 级"),   # size "M8x25"，端盖螺钉常用
    "screw_pan":     ("GB/T67-2000", "开槽盘头螺钉", "4.8 级"),            # size "M5x12"
    "spring_washer": ("GB/T 93-1987", "标准型弹簧垫圈", "65Mn"),           # size "10"
    "taper_bearing": ("GB/T297-1994", "圆锥滚子轴承", ""),                 # size "30206"
    "oring":         ("series G (3452.1)", "O 形橡胶密封圈", "丁腈橡胶"),   # size "30x3.55"（内径×截面直径）
}
# 生成后零件自身坐标（实测外框，2026-11-08）：
#   screw / screw_hex / screw_pan：轴线 +X，头顶在 X=0，杆朝 +X，头下支承面在 X = 外框 xmax − l（同 bolt）
#   spring_washer / oring：轴线 Z（同 washer）；taper_bearing / felt：轴线 X（同 bearing）
LOCAL.update({k: (0, 0, 0) for k in TB_KINDS}); LOCAL["felt"] = (0, 0, 0)
AXIS.update({"screw": (1, 0, 0), "screw_hex": (1, 0, 0), "screw_pan": (1, 0, 0), "spring_washer": (0, 0, 1),
             "taper_bearing": (1, 0, 0), "oring": (0, 0, 1), "felt": (1, 0, 0)})


def _tb_sel(kind, size):
    nums = re.findall(r"[\d.]+", size)
    if kind in ("screw", "screw_hex", "screw_pan"):
        return {"Size": f"M{nums[0]}", "Length": nums[1]}, f"M{nums[0]}×{nums[1]}"
    if kind == "spring_washer":
        return {"Size": nums[0]}, nums[0]
    if kind == "taper_bearing":
        return {"Train": size[1:3], "Size": size}, size
    if kind == "oring":
        return {"Inside Diameter": nums[0], "Thickness": nums[1]}, f"{nums[0]}×{nums[1]} G"
    raise ValueError(kind)


_DB = None


def make_any(sw, key, sel, out_dir, cname=None, grade="", spec=None, material="普通碳钢", override=None):
    """按 Toolbox 配置库生成任意 GB 标准件。key：Toolbox 类型名的一部分（'GB/T70.1'、'GB/T 93'…，toolbox_db.DB.find）；
    sel：规格选择（{'Size': 'M8', 'Length': '25'}，键是配置表里的选项名，db.choices 可列出可选值）。
    返回 (路径, 信息)。信息同 make()：代号、名称、规格、材料、标记、质量kg、外框；另有 '没找到的尺寸'。
    规格不在表里直接报错并列出可选值。"""
    global _DB
    import toolbox_db
    _DB = _DB or toolbox_db.DB()
    t = _DB.find(key)
    r = _DB.resolve(t, sel)
    r["dims"].update(override or {})     # 个别尺寸用公称值覆盖（Toolbox 有的表存的是极限尺寸）
    if r["missing"]:
        raise ValueError(f"{t['name']}：规格不在 Toolbox 表里 —— " + "；".join(r["missing"]))
    m = re.search(r"GB[/\-]?T?\s*(\d+(?:\.\d+)?)(?:\s*-\s*((?:19|20)\d\d))?", r["mark"] or t["name"])
    std = (f"GB/T {m.group(1)}" + (f"-{m.group(2)}" if m.group(2) else "")) if m else t["name"]
    spec = spec or r["spec"]
    cname = cname or r["name_en"]
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{std.split('-')[0].replace('/', '').replace(' ', '')}_{cname}_"
                                f"{spec.replace('×', 'x').replace(' ', '')}.SLDPRT")
    e, w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0), VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    rel = re.sub(r"^GB[\\/]", "", t["filename"])
    src = os.path.join(LIB, rel)
    if not os.path.exists(src):          # 库里登记的路径和实际目录有时对不上（O 形圈实测），按文件名找
        base = os.path.basename(rel).lower()
        hit = [os.path.join(dp, f) for dp, _, fs in os.walk(LIB) for f in fs if f.lower() == base]
        src = hit[0] if hit else src
    p = sw.OpenDoc6(src, 1, 1 | 64, "", e, w)
    if p is None:
        raise RuntimeError(f"打不开 Toolbox 基础零件 {rel}（错误 {e.value}）")
    title = p.GetTitle
    try:
        p.DeleteDesignTable
        missing = []
        for name, v in r["dims"].items():
            prm = p.Parameter(name)
            if prm is None:
                missing.append(name); continue
            gt = prm.GetType
            ang = (gt() if callable(gt) else gt) == 1          # 1 = 角度尺寸（库里是度），0 = 长度（mm）
            prm.SetSystemValue3(math.radians(v) if ang else v / 1000, 2, NONE)
        p.EditRebuild3
        for fn, act in [(f, "on") for f in r["on"]] + [(f, "off") for f in r["off"]]:
            p.ClearSelection2(True)
            for typ in ("BODYFEATURE", "COSMETICTHREAD"):
                if p.Extension.SelectByID2(fn, typ, 0, 0, 0, False, 0, NONE, 0):
                    p.EditUnsuppress2 if act == "on" else p.EditSuppress2
                    break
        p.ClearSelection2(True)
        try:
            p.Extension.ToolboxPartType = 0
        except Exception:
            pass
        p.SetMaterialPropertyName2("", "SOLIDWORKS Materials", material)
        cpm = p.Extension.CustomPropertyManager("")
        info = {"代号": std, "名称": cname, "规格": spec, "材料": grade, "标记": f"{cname} {std.split('-')[0]} {spec}",
                "toolbox": t["name"]}
        for k, v in info.items():
            cpm.Add3(k, 30, v, 1)
        p.EditRebuild3
        if os.path.exists(out):
            os.remove(out)
        rr = p.SaveAs3(out, 0, 2)
        if rr != 0 or not os.path.exists(out):
            raise RuntimeError(f"另存失败 {rr}：{out}")
        st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        mp = p.Extension.GetMassProperties(1, st)
        info["质量kg"] = round(mp[5], 4); info["体积mm3"] = round(mp[3] * 1e9, 1)
        info["外框"] = [round(v * 1000, 2) for v in p.GetPartBox(True)]
        info["尺寸"] = r["dims"]
        if missing:
            info["没找到的尺寸"] = missing
        return out, info
    finally:
        sw.CloseDoc(p.GetTitle if p else title)


def make_tb(sw, kind, size, out_dir, material="普通碳钢"):
    """常用新增件的简写：make_tb(sw, "screw", "M8x25", dir)、("spring_washer", "10")、("taper_bearing", "30206")、
    ("screw_hex", "M8x25")、("screw_pan", "M5x12")、("oring", "30x3.55")。"""
    key, cname, grade = TB_KINDS[kind]
    sel, spec = _tb_sel(kind, size)
    ov = None
    if kind == "screw_hex":     # Toolbox 的 5783 表里 s、k 存的是极限值（M8：12.73、5.45），改成公称值（头部同 GB/T 5782）
        d = int(float(re.findall(r"[\d.]+", size)[0]))
        if d in BOLT:
            ov = {"s@Sketch2": BOLT[d][0], "k@BaseHead": BOLT[d][1]}
    path, info = make_any(sw, key, sel, out_dir, cname=cname, grade=grade, spec=spec,
                          material="天然橡胶" if kind == "oring" else material, override=ov)
    info["kind"] = kind
    return path, info


# ---------------------------------------------------------------------- 毡圈油封（Toolbox 没有，自己建）
# JB/ZQ 4606-1997 毡圈油封及槽：轴径 d: (毡圈 D, d1, B, 槽 D0, d0, b)。
# 按《机械设计课程设计手册》录入——这是手录的表，第一次用请对一遍手册。
FELT = {16: (29, 14, 6, 28, 16, 5), 20: (33, 19, 6, 32, 21, 5), 25: (39, 24, 7, 38, 26, 6), 30: (45, 29, 7, 44, 31, 6),
        35: (49, 34, 7, 48, 36, 6), 40: (53, 39, 7, 52, 41, 6), 45: (61, 44, 8, 60, 46, 7), 50: (69, 49, 8, 68, 51, 7),
        55: (74, 53, 8, 72, 56, 7), 60: (80, 58, 8, 78, 61, 7), 65: (84, 63, 8, 82, 66, 7), 70: (90, 68, 8, 88, 71, 7),
        75: (94, 73, 8, 92, 77, 7), 80: (102, 78, 9, 100, 82, 8)}


def make_felt(sw, d, out_dir):
    """毡圈油封 d（轴径）：矩形截面 d1..D × B 绕 X 轴旋转，X ∈ [−B/2, B/2]（同 bearing 约定）。
    返回 (路径, 信息)；信息里另有 '槽'=(D0, d0, b) 给端盖零件图用。"""
    import sw_part as S
    D_, d1, B, D0, d0, b = FELT[int(d)]
    p = S.new_part(sw)
    sm = S.sketch_on(p, "front")                       # 前视基准面：草图 x = 模型 X，y = 模型 Y
    sm.CreateCenterLine(-0.1, 0, 0, 0.1, 0, 0)
    pts = [(-B / 2, d1 / 2), (B / 2, d1 / 2), (B / 2, D_ / 2), (-B / 2, D_ / 2)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        sm.CreateLine(x1 / 1000, y1 / 1000, 0, x2 / 1000, y2 / 1000, 0)
    p.SketchManager.AddToDB = False
    f = p.FeatureManager.FeatureRevolve2(True, True, False, False, False, False, 0, 0, 2 * math.pi, 0,
                                         False, False, 0, 0, 0, 0, 0, True, False, True)
    if f is None:
        raise RuntimeError("毡圈旋转失败")
    info = {"代号": "JB/ZQ 4606-1997", "名称": "毡圈", "规格": f"{int(d)}", "材料": "半粗羊毛毡",
            "标记": f"毡圈 {int(d)} JB/ZQ 4606-1997", "槽": (D0, d0, b), "kind": "felt"}
    cpm = p.Extension.CustomPropertyManager("")
    for k in ("代号", "名称", "规格", "材料", "标记"):
        cpm.Add3(k, 30, info[k], 1)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"JBZQ4606_毡圈_{int(d)}.SLDPRT")
    if os.path.exists(out):
        os.remove(out)
    p.EditRebuild3
    if p.SaveAs3(out, 0, 2) != 0:
        raise RuntimeError("毡圈另存失败")
    st = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    mp = p.Extension.GetMassProperties(1, st)
    info["体积mm3"] = round(mp[3] * 1e9, 1); info["外框"] = [round(v * 1000, 2) for v in p.GetPartBox(True)]
    info["质量kg"] = round(mp[3] * 1e9 * 0.3e-6, 4)          # 羊毛毡密度约 0.3 g/cm³
    sw.CloseDoc(p.GetTitle)
    return out, info

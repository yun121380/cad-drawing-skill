"""装配：每个零件按变换矩阵放到全局坐标后固定；轴承 6206/6207 各用两次。
2026-11-08 加标准件（sw_std 从 Toolbox GB 基础零件生成）：三个平键、结合面 4 组螺栓 M10×40 + 垫圈 + 螺母。
大齿轮的轮毂键槽建在 +Y，装配时绕自身轴线转 -90° 到 +X，对上输出轴上的键。
最后跑干涉检查（SolidWorks MCP 的 check_interference），标准件信息写 std.json 给明细栏用。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import sw_part as S
import sw_std
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

mm = 0.001
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
STD = os.path.join(D, "std")
NONE = VARIANT(pythoncom.VT_DISPATCH, None)
parts = json.load(open(os.path.join(D, "parts.json"), encoding="utf-8"))["parts"]

sw = S.connect()
sw.CloseAllDocuments(True)

# ---- 标准件：生成零件（规格 → 文件）
std_specs = {"key_out": ("key", "12x8x32"), "key_ext": ("key", "8x7x45"), "key_in": ("key", "8x7x40"),
             "bolt": ("bolt", "M10x40"), "washer": ("washer", "10"), "nut": ("nut", "M10")}
std = {}
for k, (kind, size) in std_specs.items():
    path, info = sw_std.make(sw, kind, size, STD)
    std[k] = {"path": path, "kind": kind, **info}
    print(k, info["标记"], info["外框"])
sw.CloseAllDocuments(True)

# AddComponent 要求零件已在内存中打开
for path in list(parts.values()) + [v["path"] for v in std.values()]:
    e, w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0), VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    sw.OpenDoc6(path, 1, 1, "", e, w)

asm = sw.NewDocument(os.path.join(S.TPL, "gb_assembly.asmdot"), 0, 0, 0)
title = asm.GetTitle
mu = sw.GetMathUtility
I3 = [1.0, 0, 0, 0, 1, 0, 0, 0, 1]
ROT_Z_M90 = [0.0, -1, 0, 1, 0, 0, 0, 0, 1]          # 行向量约定：+X→-Y，+Y→+X（绕 Z 转 -90°）
placement = [("base", I3, (0, 0, 0)), ("cover", I3, (0, 0, 0)), ("gear_shaft", I3, (0, 0, 0)),
             ("out_shaft", I3, (0, 0, 0)),
             ("gear", ROT_Z_M90, (100, 100, 0)),     # 绕 (100,0) 转：(100,0,0)·R + T = (100,0,0)
             ("sleeve", I3, (0, 0, 0)),
             ("b6206", I3, (0, 0, -41)), ("b6206", I3, (0, 0, 41)), ("b6207", I3, (100, 0, -41.5)), ("b6207", I3, (100, 0, 41.5)),
             ("cap_in_blind", I3, (0, 0, 0)), ("cap_in_thru", I3, (0, 0, 0)), ("cap_out_blind", I3, (0, 0, 0)), ("cap_out_thru", I3, (0, 0, 0))]
sw.ActivateDoc3(title, False, 0, VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
for key, R, (x, y, z) in placement:
    c = asm.AddComponent5(parts[key], 0, "", False, "", 0, 0, 0)
    assert c is not None, key
    # 晚绑定直接 mu.CreateTransform 报“找不到成员”，按 DISPID 直接 Invoke 可以
    arr = VARIANT(0x2005, [float(v) for v in R] + [x * mm, y * mm, z * mm, 1, 0, 0, 0])
    xf = wc.Dispatch(mu._oleobj_.Invoke(mu._oleobj_.GetIDsOfNames("CreateTransform"), 0, pythoncom.DISPATCH_METHOD, True, arr))
    c.Transform2 = xf
    t = [round(v, 4) for v in c.Transform2.ArrayData]
    print(f"{c.Name2:20s} 平移 mm {[round(v / mm, 2) for v in t[9:12]]}")

# ---- 标准件就位
def key_at(k, x_bottom, zc):
    b, h, L = (float(v) for v in std_specs[k][1].split("x"))
    # 键：长度沿 Z、宽度沿 Y、高度沿 X（槽底在 x_bottom，键高 h 的中心在 x_bottom + h/2）
    sw_std.place(asm, sw, std[k]["path"], "key", (x_bottom + h / 2, 0, zc), (0, 0, 1), ref=(-(L - b) / 2, 0, 0), up=(0, 1, 0))


key_at("key_out", 100 + 20 - 5, 1)
key_at("key_ext", 100 + 14 - 4, -102.5)
key_at("key_in", 12 - 4, 100)
bolt_l = 40
bolt_bear = std["bolt"]["外框"][3] - bolt_l                      # 螺栓头下支承面（零件 X 坐标）
for x in (-58, 208):
    for z in (-45, 45):
        sw_std.place(asm, sw, std["bolt"]["path"], "bolt", (x, 12, z), (0, -1, 0), ref=(bolt_bear, 0, 0), up=(1, 0, 0))
        sw_std.place(asm, sw, std["washer"]["path"], "washer", (x, -12, z), (0, 1, 0))
        sw_std.place(asm, sw, std["nut"]["path"], "nut", (x, -14, z), (0, 1, 0), up=(1, 0, 0))
asm.EditRebuild3
# 全部固定
asm.ClearSelection2(True)
for c in asm.GetComponents(True):
    c.Select4(True, NONE, False)
asm.FixComponent
asm.ClearSelection2(True)
asm.EditRebuild3
out = os.path.join(D, "减速器.SLDASM")
if os.path.exists(out):
    os.remove(out)
e = asm.SaveAs3(out, 0, 1)
print("保存", out, e, "零件数", len(asm.GetComponents(True)))
b = asm.GetBox(0)
print("装配外框 mm", [round(v / mm, 2) for v in b])
json.dump({k: {kk: vv for kk, vv in v.items() if kk != "外框"} for k, v in std.items()},
          open(os.path.join(D, "std.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

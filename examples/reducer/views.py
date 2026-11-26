"""减速器装配图视图（A2 1:2，第一角）：
主视图 = 沿 Z 看（端盖、轴端为圆）；俯视图 = 沿结合面 Y=0 剖切的 A-A（拆去箱盖）；左视图在主视图右边。"""
import os
import sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import sw_views as V

asm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "减速器.SLDASM")
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reducer_sw")
sw = V.connect()
drw = V.new_drawing(sw, "A2", scale=(1, 2))
front = V.model_view(drw, asm, "*前视", (150, 320))
# 视图坐标原点 = 视图中心 = 装配外框中心 (75, -13.5)；结合面 Y=0 -> 视图 y=+13.5
cut = float(sys.argv[1]) if len(sys.argv) > 1 else 13.5
top = V.section(drw, front, (-200, cut), (200, cut), (150, 160), "A")
left = V.projected(drw, front, (345, 320))
boxes = V.finish(drw, [front, top, left])
V.export(drw, base)
VB = [tuple(round(v) + d for v, d in zip(b, (-3, -3, 3, 3))) for b in boxes.values()]
print("VIEWS =", VB)
# 2026-11-08：标注改按模型坐标写 —— 各视图的“模型 mm → 图纸 mm”仿射写进 layout.json
lay = {"front": V.view_affine(front), "top": V.view_affine(top), "left": V.view_affine(left),
       "boxes": {k: v for k, v in zip(("front", "top", "left"), boxes.values())}, "VIEWS": VB}
json.dump(lay, open(base.replace("reducer_sw", "reducer_layout.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(lay, indent=1))

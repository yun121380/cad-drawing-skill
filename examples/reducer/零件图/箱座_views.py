"""箱座零件图视图（A2 1:2）：主视图（*前视，左端地脚孔、结合面螺栓孔各做一处局部剖）+ 俯视图 + A-A（沿输出轴承孔轴线 X=100
剖开，放在左视图位置）。各视图的模型→图纸仿射、零件特征（审查尺寸用）写 箱座_layout.json / 箱座_features.json。
模型：外框 X -98..248、Y -125..0、Z ±75，外框中心 (75, -62.5, 0) = 视图坐标原点。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import sw_views as V

D = os.path.dirname(os.path.abspath(__file__))
part = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "箱座.SLDPRT")
sw = V.connect()
V.part_features(sw, part, os.path.join(D, "箱座_features.json"))
drw = V.new_drawing(sw, "A2", scale=(1, 2))
front = V.model_view(drw, part, "*前视", (175, 318))
top = V.projected(drw, front, (175, 178))
sec = V.section(drw, front, (25, 80), (25, -80), (395, 318), "A")
V.finish(drw, [front, top, sec])
# 局部剖：视图坐标 = 模型坐标 − 外框中心 (75, -62.5)；深度从零件最前面 Z=75 算
V.broken_out(drw, front, [(-170, -68), (-140, -68), (-137, -52), (-141, -38), (-170, -38), (-173, -54)], 75 - 58)   # 地脚孔 X=-80, Z=58
V.broken_out(drw, front, [(-146, 44), (-120, 44), (-118, 56), (-121, 68), (-146, 68), (-148, 56)], 75 - 45)       # 螺栓孔 X=-58, Z=45
boxes = V.finish(drw, [front, top, sec])
V.export(drw, os.path.join(D, "箱座_sw"))
names = {front.Name: "front", top.Name: "top", sec.Name: "sec"}
lay = {"front": V.view_affine(front), "top": V.view_affine(top), "sec": V.view_affine(sec),
       "boxes": {names[k]: b for k, b in boxes.items()},
       "VIEWS": [tuple(round(c) + d for c, d in zip(b, (-6, -6, 6, 6))) for b in boxes.values()]}
json.dump(lay, open(os.path.join(D, "箱座_layout.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps({k: lay[k] for k in ("front", "top", "sec", "boxes")}, indent=1))
import json as _j; print(_j.load(open(os.path.join(D, "箱座_features.json"), encoding="utf-8")))

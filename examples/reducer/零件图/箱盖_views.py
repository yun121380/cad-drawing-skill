"""箱盖零件图视图（A2 1:2）：主视图（*前视，开虚线显示内腔，左端螺栓孔局部剖）+ 俯视图 + A-A（沿输出轴承孔轴线 X=100
剖开，放在左视图位置）。各视图的模型→图纸仿射、零件特征（审查尺寸用）写 箱盖_layout.json / 箱盖_features.json。
模型：外框 X -68..218、Y 0..98、Z ±60，外框中心 (75, 49, 0) = 视图坐标原点。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import sw_views as V

D = os.path.dirname(os.path.abspath(__file__))
part = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "箱盖.SLDPRT")
sw = V.connect()
V.part_features(sw, part, os.path.join(D, "箱盖_features.json"))
drw = V.new_drawing(sw, "A2", scale=(1, 2))
front = V.model_view(drw, part, "*前视", (175, 310))
top = V.projected(drw, front, (175, 185))
sec = V.section(drw, front, (25, 70), (25, -70), (395, 310), "A")
V.finish(drw, [front, top, sec])
# 局部剖：视图坐标 = 模型坐标 − 外框中心 (75, 49)；深度从零件最前面 Z=60 算（螺栓孔 X=-58, Z=45）
V.broken_out(drw, front, [(-146, -53), (-120, -53), (-118, -43), (-121, -33), (-146, -33), (-148, -43)], 60 - 45)
V.hidden_lines(front, True)                     # 内腔（R40 / R90）只在主视图里用虚线表达
V.hidden_lines(top, False); V.hidden_lines(sec, False)   # 投影视图、剖视会跟着父视图显示虚线（实测），关掉
boxes = V.finish(drw, [front, top, sec])
V.export(drw, os.path.join(D, "箱盖_sw"))
names = {front.Name: "front", top.Name: "top", sec.Name: "sec"}
lay = {"front": V.view_affine(front), "top": V.view_affine(top), "sec": V.view_affine(sec),
       "boxes": {names[k]: b for k, b in boxes.items()},
       "VIEWS": [tuple(round(c) + d for c, d in zip(b, (-6, -6, 6, 6))) for b in boxes.values()]}
json.dump(lay, open(os.path.join(D, "箱盖_layout.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps({k: lay[k] for k in ("front", "top", "sec", "boxes")}, indent=1))
import json as _j; print(_j.load(open(os.path.join(D, "箱盖_features.json"), encoding="utf-8")))

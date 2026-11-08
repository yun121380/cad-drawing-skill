"""大齿轮零件图视图（A3 1:1）：主视图 = 过轴线的全剖 A-A（轴线水平，放左边），左视图 = 圆视图（*前视，键槽朝上）。
模型只建到齿根圆，轮齿按规定画法在 AutoCAD 里补（gear_teeth / gear_circles）。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import sw_views as V

D = os.path.dirname(os.path.abspath(__file__))
part = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "大齿轮.SLDPRT")
sw = V.connect()
drw = V.new_drawing(sw, "A3")
circ = V.model_view(drw, part, "*前视", (255, 175))
V.finish(drw, [circ])
vp = lambda X, Y, Z: V.sheet_to_view(circ, V.model_to_sheet(circ, (X, Y, Z)))
sec = V.section(drw, circ, vp(100, -90, 0), vp(100, 90, 0), (105, 175), "A")
boxes = V.finish(drw, [circ, sec])
V.export(drw, os.path.join(D, "大齿轮_sw"))
lay = {"circ": V.view_affine(circ), "sec": V.view_affine(sec),
       "box_circ": boxes[circ.Name], "box_sec": boxes[sec.Name],
       # 剖切面是对称面、按投影关系配置：国标不标剖切符号和 A-A。符号在圆视图框外，框不放大，Sheet 会当模板删掉
       "VIEWS": [tuple(round(c) + d for c, d in zip(b, (-4, -4, 4, 4))) for b in boxes.values()]}
json.dump(lay, open(os.path.join(D, "大齿轮_layout.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(lay, indent=1))

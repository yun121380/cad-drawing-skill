"""输出轴零件图视图（A3 1:1）：主视图 = *右视（轴线水平、两个键槽正对观察者），
两个移出断面放在剖切线延长线的下方。坐标映射（view_affine）写 输出轴_layout.json。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import sw_views as V

D = os.path.dirname(os.path.abspath(__file__))
part = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "输出轴.SLDPRT")
sw = V.connect()
drw = V.new_drawing(sw, "A3")
main = V.model_view(drw, part, "*右视", (190, 195))
V.finish(drw, [main])
vp = lambda X, Y, Z: V.sheet_to_view(main, V.model_to_sheet(main, (X, Y, Z)))
secs = {}
for lab, zc in (("A", 1), ("B", -102.5)):
    x = V.model_to_sheet(main, (100, 0, zc))[0]
    p1, p2 = vp(100, -32, zc), vp(100, 32, zc)
    # 断面放在剖切线延长线上（正下方）；投射方向朝右（look），看过去键槽在断面左边还是右边由 SW 定
    secs[lab] = V.section(drw, main, p1, p2, (x, 100), lab, surface_only=True, aligned=False, look=(x + 50, 195))
views = [main] + list(secs.values())
boxes = V.finish(drw, views)
V.export(drw, os.path.join(D, "输出轴_sw"))
lay = {"main": V.view_affine(main), "box_main": boxes[main.Name],
       "secs": {k: {"aff": V.view_affine(v), "box": boxes[v.Name]} for k, v in secs.items()},
       # 主视图框上下多留 16：剖切符号（粗短画 + 箭头）画在视图外框外面，框小了会被当模板删掉
       "VIEWS": [tuple(round(c) + d for c, d in zip(b, (-4, -16, 4, 16) if k == main.Name else (-4, -4, 4, 4)))
                 for k, b in boxes.items()]}
json.dump(lay, open(os.path.join(D, "输出轴_layout.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(lay, indent=1))

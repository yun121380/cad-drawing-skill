import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import sw_views as V
part = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "side_plate2.SLDPRT")
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "plate_sw")
sw = V.connect(); drw = V.new_drawing(sw, "A3", scale=(1, 2))
v1 = V.model_view(drw, part, "*前视", (215, 190))
v2 = V.projected(drw, v1, (215, 120))          # 俯视图在下（第一角）
boxes = V.finish(drw, [v1, v2]); V.export(drw, base)
V.dump_dxf(base + ".DXF", [(50, 140, 380, 240), (50, 100, 380, 140)])

import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import sw_views as V
asm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "wheel_asm.SLDASM")
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "asm_sw")
sw = V.connect(); drw = V.new_drawing(sw, "A3", scale=(1, 2))
end = V.model_view(drw, asm, "*前视", (270, 200))                 # 端视图（沿轴线看）
sec = V.section(drw, end, (0, 80), (0, -80), (120, 200), "A")    # 主视图 A-A（轴的剖面线在 AutoCAD 里删）
V.finish(drw, [end, sec]); V.export(drw, base)
V.dump_dxf(base + ".DXF", [(60, 150, 180, 250), (200, 150, 345, 250)])

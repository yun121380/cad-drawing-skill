import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import sw_views as V
part = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "bracket.SLDPRT")
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "bracket_sw")
sw = V.connect(); drw = V.new_drawing(sw, "A3")
# 第一角：主视图左上，左视图在其右，俯视图在其下
left = V.model_view(drw, part, "*左视", (290, 185))              # 左视图（视图坐标：横轴=模型 Z，竖轴=模型 Y）
# 主视图 = 从左视图沿前后对称面 z=0 竖直剖切，放在左视图左边 —— 这样高度方向不会被翻转
front = V.section(drw, left, (0, 60), (0, -60), (140, 185), "A")   # 视图坐标原点=视图中心，线要贯穿整个零件
top = V.model_view(drw, part, "*上视", (140, 85))               # 俯视图
V.hidden_lines(left, True)      # 建完剖视再开虚线，否则剖视图会继承虚线显示
V.hidden_lines(front, False)
V.finish(drw, [front, left, top]); V.export(drw, base)

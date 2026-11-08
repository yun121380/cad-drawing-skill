"""半剖 + 局部剖示例的 AutoCAD 整理（A3 1:1），视图由 bush_half_views.py 生成。
坐标取自 bush_half_sw.DXF（图纸 mm）：
  主视图：x = 120 + X，y = 152.5 + Y；轴线 x=120；底 152.5、凸缘顶 167.5、顶 247.5；筒体 x 90..150、内孔 105..135
          径向孔 Φ8：y 208.5..216.5（轴线 212.5），x 90..105
  俯视图：中心 (120, 85)，R50 / R30 / R15，4×Φ12 在 R40 上"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from sw2acad import Sheet, P

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
VIEWS = [(61, 144, 179, 256), (61, 26, 179, 144)]
with Sheet(D + r"\bush_half_sw.DWG", D + r"\bush_half_gb.dwg", views=VIEWS) as s:
    s.frame()
    s.title_block("凸缘套筒", "HB-01", material="45", scale="1:1", designer="", date="2026.11")
    s.to_center((120, 140), (120, 260))            # 半剖分界：局部剖矩形压在轴线上的细实线 -> 点画线
    s.line((120, 247.5), (120, 252)); s.line((120, 152.5), (120, 148))   # 轴线伸出轮廓
    s.line((84, 212.5), (111, 212.5))              # 径向孔轴线
    s.circle((120, 85), 40)                        # 俯视图孔分布圆
    # 主视图
    s.dimlin((70, 152.5), (170, 152.5), (120, 145), 0, "%%C100")
    s.dimlin((90, 247.5), (150, 247.5), (120, 257), 0, "%%C60")
    d = s.dimlin((105, 232), (135, 232), (120, 232), 0, "%%C30")   # 半剖里的对称尺寸：只画右半箭头
    d.DimLine1Suppress = True; d.ExtLine1Suppress = True
    d.TextPosition = P(128, 234.5)
    s.dimlin((150, 247.5), (170, 152.5), (182, 200), 90)            # 95
    s.dimlin((70, 152.5), (70, 167.5), (60, 160), 90)               # 15
    s.dimlin((90, 152.5), (84, 212.5), (52, 182), 90)               # 60（孔轴线高）
    s.dimlin((90, 208.5), (90, 216.5), (78, 230), 90, "%%C8")
    # 俯视图
    d = s.dimdia((160, 85), 6, 45, 12, "4×%%C12")
    s.dimdia((120, 85), 40, 135, 20, "%%C80")
    s.notes(["1. 未注倒角 C1。", "2. 调质处理 220~250HBW。"], p=(260, 120))

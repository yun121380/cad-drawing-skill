"""示例：电梯门挂板零件图（A3 横放，1:2）。用法：
    python hanger_plate.py <输出目录>
先在纸上定好坐标：图形按实际尺寸画，图框按 S 倍；视图之间留够尺寸线位置（每道尺寸 7*S）。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from acadkb import Drafter, render_pdf

out = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
DWG = os.path.join(out, "XJW-01-03 门挂板.dwg")
PDF = os.path.join(out, "XJW-01-03 门挂板.pdf")

d = Drafter(scale=2)
d.new_document(close_paths=[DWG])
inner = d.frame("A3")                       # (50,10,830,584)

# ---- 主视图：板 400×120，左下角 O ----
OX, OY = 170, 330
holes = [(60, 90, 6), (340, 90, 6), (40, 25, 4.5), (160, 25, 4.5), (240, 25, 4.5), (360, 25, 4.5)]
d.layer("粗实线")
d.rect((OX, OY), (OX + 400, OY + 120))
for hx, hy, r in holes:
    d.circle((OX + hx, OY + hy), r)
d.layer("中心线")
for hx, hy, r in holes:
    d.center_cross((OX + hx, OY + hy), r)

# ---- 左视图（第一角画法在主视图右侧），板厚 4 ----
LX = 640
d.layer("粗实线"); d.rect((LX, OY), (LX + 4, OY + 120))
d.layer("虚线")
for hy, r in ((90, 6), (25, 4.5)):
    for dy in (-r, r):
        d.line((LX, OY + hy + dy), (LX + 4, OY + hy + dy))
d.layer("中心线")
for hy in (90, 25):
    d.line((LX - 6, OY + hy), (LX + 10, OY + hy))

# ---- 尺寸 ----
d.layer("尺寸")
d.dimlin((OX, OY), (OX + 40, OY + 25), (OX + 20, OY - 22))                 # 下方孔距链
d.dimcont((OX + 160, OY + 25), (OX + 240, OY + 25), (OX + 360, OY + 25))   # 末段空出，避免与总长成封闭链
d.dimlin((OX, OY + 120), (OX + 60, OY + 90), (OX + 30, OY + 142))           # 上方孔距链
d.dimcont((OX + 340, OY + 90))
d.dimlin((OX, OY + 120), (OX + 400, OY + 120), (OX + 200, OY + 170))        # 总长
d.dimlin((OX, OY), (OX + 40, OY + 25), (OX - 22, OY + 12))                  # 孔高 25
d.dimbase((OX + 60, OY + 90))                                               #      90
d.dimlin((OX + 400, OY), (OX + 400, OY + 120), (OX + 422, OY + 60))         # 总高
d.dimlin((LX, OY + 120), (LX + 4, OY + 120), (LX + 2, OY + 142))            # 板厚
d.dimdia((OX + 60 + 4.243, OY + 90 + 4.243), (OX + 95, OY + 112), "2\\U+00D7%%C12")
d.dimdia((OX + 40 + 3.182, OY + 25 + 3.182), (OX + 85, OY + 60), "4\\U+00D7%%C9")

# ---- 技术要求 + 标题栏 ----
d.tech_notes((80, 230), ["未注线性尺寸公差按 GB/T 1804-m。", "去除毛刺，锐边倒钝。", "表面镀锌处理。"])
d.title_block(inner, "门挂板", "XJW-01-03", "1:2", "Q235", "徐嘉玮", "2026.11")

pdf = d.save_and_plot(DWG, PDF)
d.report()
print("PNG:", render_pdf(pdf, os.path.splitext(pdf)[0] + ".png"))

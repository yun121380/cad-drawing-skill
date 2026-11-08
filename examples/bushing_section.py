"""示例：回转体全剖 —— 门机滚轮轴套 XJW-01-05（A4 横放，1:1）。用法: python bushing_section.py <输出目录>

全剖要点（新手最容易错的地方）：
  1. 剖面线只填被剖到的实体：上下两块各画成封闭 pline，再分别在块内点一点填充。
  2. 剖切面后面看得见的轮廓线也要画：孔的两端口在剖视图里投影成竖线，
     要把上下两块实体连起来（下面的 end_lines）。不画的话，图看起来像两块分开的板。
  3. 轴线画中心线，两端各伸出轮廓约 5。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from acadkb import Drafter, render_pdf

out = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
DWG = os.path.join(out, "XJW-01-05 滚轮轴套.dwg")
PDF = os.path.join(out, "XJW-01-05 滚轮轴套.pdf")

d = Drafter(scale=1)
d.new_document(close_paths=[DWG])
inner = d.frame("A4")                      # (25,5,292,205)；标题栏占 x 112–292, y 5–45

# ---- 主视图（全剖，轴线水平）----
X0, X1, Y = 80, 130, 135
R, r, c = 20, 12.5, 1                      # 外圆半径、孔半径、外端倒角 C1
d.layer("粗实线")
up = [(X0, Y + r), (X0, Y + R - c), (X0 + c, Y + R), (X1 - c, Y + R), (X1, Y + R - c), (X1, Y + r)]
dn = [(x, 2 * Y - y) for x, y in up]
d.pline(*up, close=True)                   # 被剖到的上半块
d.pline(*dn, close=True)                   # 下半块
d.line((X0, Y + r), (X0, Y - r))           # 孔口端面线（剖切面后可见轮廓）
d.line((X1, Y + r), (X1, Y - r))
d.layer("剖面线")
d.hatch((X0 + 25, Y + 16))
d.hatch((X0 + 25, Y - 16))
d.layer("中心线")
d.line((X0 - 5, Y), (X1 + 5, Y))

# ---- 左视图（第一角画法在主视图右侧）----
LC = (200, Y)
d.layer("粗实线")
d.circle(LC, R)
d.circle(LC, R - c)                        # 倒角在端视图上可见的圆
d.circle(LC, r)
d.layer("中心线")
d.center_cross(LC, R)

# ---- 尺寸 ----
d.layer("尺寸")
d.dimlin((X0, Y - R + c), (X1, Y - R + c), ((X0 + X1) / 2, Y - R - 10))   # 50
d.dimlin((X0, Y + r), (X0, Y - r), (X0 - 9, Y), "%%C25H7")               # 回转体直径标在非圆视图上
d.dimlin((X0 + c, Y + R), (X0 + c, Y - R), (X0 - 17, Y), "%%C40")
tip = (X0 + c / 2, Y + R - c / 2)                                          # 倒角斜线中点
d.leader([tip, (X0 + 8, Y + R + 7), (X0 + 22, Y + R + 7)], "2×C1")

# ---- 技术要求 + 标题栏 ----
d.tech_notes((35, 82), ["未注线性尺寸公差按 GB/T 1804-m。",
                        "锡青铜铸件不得有气孔、砂眼、缩松等缺陷。",
                        "锐边倒钝，去除毛刺。"])
d.title_block(inner, "滚轮轴套", "XJW-01-05", "1:1", "ZCuSn10P1", "徐嘉玮", "2026.11")

pdf = d.save_and_plot(DWG, PDF)
d.report()
print("PNG:", render_pdf(pdf, os.path.splitext(pdf)[0] + ".png"))

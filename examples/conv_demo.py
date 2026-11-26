import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import ezdxf
D = os.getcwd()          # 输出写到当前目录
src = os.path.join(D, "blank.dxf")
doc = ezdxf.new("R2010"); doc.saveas(src)
from sw2acad import Sheet
with Sheet(src, os.path.join(D, "规定画法测试.dwg"), views=[(0, 0, 420, 297)]) as s:
    s.frame()
    L = lambda a, b: s.line(a, b, "粗实线")
    T = lambda p, t: s._text(p, 3.5, t)
    # 1 外螺纹 M20，螺纹长 30，C1.5 倒角
    y = 245; x0 = 40
    L((x0, y - 8.5), (x0, y + 8.5)); L((x0, y + 8.5), (x0 + 1.5, y + 10)); L((x0, y - 8.5), (x0 + 1.5, y - 10))
    L((x0 + 1.5, y + 10), (x0 + 70, y + 10)); L((x0 + 1.5, y - 10), (x0 + 70, y - 10)); L((x0 + 1.5, y - 10), (x0 + 1.5, y + 10))
    s.line((x0 - 3, y), (x0 + 73, y))
    s.thread_shaft((x0, y), (1, 0), 30, 20)
    s.circle((150, y), 10, "粗实线"); s.circle((150, y), 8.5, "粗实线")      # 大径 + 倒角圆（应被删）
    s.thread_shaft_circle((150, y), 20); s.center_cross((150, y), 10)
    T((80, 225), "外螺纹 M20")
    # 2 花键 6×23×26×6
    y = 185
    L((x0, y - 13), (x0 + 70, y - 13)); L((x0, y + 13), (x0 + 70, y + 13)); L((x0, y - 13), (x0, y + 13))
    s.line((x0 - 3, y), (x0 + 73, y))
    s.spline_shaft((x0, y), (1, 0), 40, 26, 23)
    s.circle((150, y), 13, "粗实线"); s.spline_circle((150, y), 26, 23, 6, 6); s.center_cross((150, y), 13)
    T((80, 163), "花键 " + _c if False else "矩形花键 6×23×26×6")
    # 3 压缩弹簧
    s.spring((215, 140), (0, 1), 80, 30, 4, 6.5)
    T((215, 130), "压缩弹簧 d4 D30 n6.5 H80")
    # 4 锥齿轮 m3 z25 δ45 R≈53 b16
    m, z = 3, 25; dl = 45; d = m * z; R = d / 2 / math.sin(math.radians(dl))
    s.line((260, 200), (372, 200))
    r = s.bevel_teeth((262, 200), (1, 0), dl, R, 16, m)
    s.bevel_circles((330, 110), r["d"], r["da"], R, 16, k=0.8)
    T((320, 240), f"锥齿轮 m3 z25 δ45° R{R:.1f}")
    # 5 蜗杆 d1=40 m4
    y = 90
    s.line((x0 - 5, y), (x0 + 75, y))
    s.worm_teeth((x0, y), (1, 0), 70, 40, 4)
    s.worm_circles((150, y), 40, 4)
    T((80, 60), "蜗杆 m4 d1=40")
    # 6 蜗轮 z2=40 a=100 b2=36 de2=172，1:2 画一半
    s.line((240, -45), (305, -45))
    s.worm_wheel_section((272, -45), (1, 0), 100, 40, 4, 36, 172, sides=(1,), k=1, root=True)
    T((272, 30), "蜗轮剖视（上半，1:2）")
    s.check()

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
    import win32com.client as _wc

    def body(pts, scale=0.55, ang=0.0):
        """剖到的轮体：粗实线闭合轮廓 + ANSI31 剖面线（同一零件上下两半用同一角度、间距）"""
        s.layer("粗实线")
        pl = s.ms.AddLightWeightPolyline(_wc.VARIANT(0x2005, [c for q in pts for c in q])); pl.Closed = True
        s.layer("剖面线")
        h = s.ms.AddHatch(1, "ANSI31", True); h.AppendOuterLoop(_wc.VARIANT(0x2009, [pl]))
        h.PatternScale = scale; h.PatternAngle = math.radians(ang); h.Evaluate()

    # 4 锥齿轮 m3 z25 δ45° b16：过轴线全剖（轮齿按不剖，剖面线只到齿根）+ 圆视图
    m, z, dl, b = 3, 25, 45, 16
    d = m * z; R = d / 2 / math.sin(math.radians(dl))
    A = (262, 215)                                    # 分度圆锥顶点，轴线向右
    cd, sd_ = math.cos(math.radians(dl)), math.sin(math.radians(dl))
    hF, ri = 1.2 * m, (R - b) / R
    ro = (R * cd + hF * sd_, R * sd_ - hF * cd)      # 大端齿根（轴向 t, 半径 r）
    rn = ((R - b) * cd + hF * ri * sd_, (R - b) * sd_ - hF * ri * cd)   # 小端齿根
    back = (ro[0] + 4.9 * sd_, ro[1] - 4.9 * cd)     # 背锥面向里延伸
    rb, rh, t_back, t_hub = 10, 18, back[0], 20      # 孔半径、轮毂半径、背面、轮毂前端
    front = (rn[0] + (rn[1] - rh) / cd * sd_, rh)     # 小端端面延伸到轮毂
    loc = [rn, ro, back, (t_back, rb), (t_hub, rb), (t_hub, rh), front]
    for sg in (1, -1):
        body([(A[0] + t, A[1] + sg * r) for t, r in loc])
    s.bevel_teeth(A, (1, 0), dl, R, b, m)
    s.line((A[0] + t_hub - 4, A[1]), (A[0] + t_back + 5, A[1]))     # 轴线
    C = (360, 215)
    s.bevel_circles(C, d, d + 2 * m * cd, R, b)
    s.circle(C, rb, "粗实线"); s.circle(C, rh, "粗实线")
    s.center_cross(C, (d + 2 * m * cd) / 2)
    T((330, 168), f"锥齿轮 m3 z25 δ45° R{R:.1f}（剖视 + 圆视图）")

    # 5 蜗杆 d1=40 m4
    y = 90
    s.line((x0 - 5, y), (x0 + 75, y))
    s.worm_teeth((x0, y), (1, 0), 70, 40, 4)
    s.worm_circles((150, y), 40, 4)
    T((80, 60), "蜗杆 m4 d1=40")
    # 6 蜗轮 z2=40 a=100 b2=36 de2=172（比例 0.6）：过轴线全剖（轮齿按不剖）+ 圆视图
    kw, a, d1, mw, b2, de2, z2 = 0.6, 100, 40, 4, 36, 172, 40
    Cw = (285, 95)                                    # 蜗轮轴线（水平）和中间平面的交点
    rf = d1 / 2 + 1.2 * mw
    arc = [(t, a - math.sqrt(rf * rf - t * t)) for t in [-b2 / 2 + i * b2 / 12 for i in range(13)]]
    web = [(b2 / 2, 66), (6, 66), (6, 34), (20, 34), (20, 20), (-20, 20), (-20, 34), (-6, 34), (-6, 66), (-b2 / 2, 66)]
    for sg in (1, -1):
        body([(Cw[0] + t * kw, Cw[1] + sg * r * kw) for t, r in arc + web], scale=0.45)
    s.worm_wheel_section(Cw, (1, 0), a, d1, mw, b2, de2, k=kw, root=True)
    s.line((Cw[0] - 18, Cw[1]), (Cw[0] + 18, Cw[1]))  # 轴线
    Cc = (357, 95)                                    # 圆视图：外圆、分度圆、轮缘内圆、轮毂、孔
    s.worm_wheel_circles(Cc, mw * z2, de2, k=kw)
    for r in (66, 34, 20):
        s.circle(Cc, r * kw, "粗实线")
    s.center_cross(Cc, de2 / 2 * kw)
    T((330, 30), "蜗轮 m4 z2=40 a=100（剖视 + 圆视图）")

    s.check()

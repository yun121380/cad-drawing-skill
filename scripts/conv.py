"""conv —— 规定画法（2026-11-08）：外螺纹、花键、圆柱螺旋压缩弹簧、直齿锥齿轮、蜗杆蜗轮。
这些函数挂在 sw2acad.Sheet 上当方法用（s.thread_shaft(...)），坐标都是图纸 mm；k = 视图比例（1:2 传 0.5），
直径、长度这些参数给模型 mm。

建模约定（和圆柱齿轮一样：模型只建“毛坯”，规定画法在 AutoCAD 里补）：
  外螺纹   轴段按大径 d 建成光轴（端部倒角照建）；这里补小径细实线、终止线，圆视图补 3/4 小径细圆、删倒角圆。
  花键     轴段按大径 D 建成光轴；这里补小径细实线、终止线、30° 尾线；圆视图画出全部齿形、删掉整圆。
  弹簧     不建模（SW 螺旋扫描出图是一堆样条）：直接画剖视的规定画法。
  锥齿轮   毛坯建到齿根圆锥（轮齿这一圈不建），剖面线天然停在齿根；这里补齿顶线、齿根线、分度线、背锥线。
  蜗杆     同圆柱齿轮：用 gear_teeth（齿根线可省略）；蜗轮建到齿根喉圆，这里补喉部圆弧和分度圆弧。
"""
import math
import win32com.client as wc


def _P(x, y):
    return wc.VARIANT(0x2005, [float(x), float(y), 0.0])


def _frame(p0, u):
    L = math.hypot(*u); ux, uy = u[0] / L, u[1] / L
    return ux, uy, -uy, ux              # 轴向单位向量、法向（逆时针 90°）


def _pt(p0, ux, uy, nx, ny, t, s):
    return (p0[0] + ux * t + nx * s, p0[1] + uy * t + ny * s)


METRIC_P = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2, 16: 2, 18: 2.5, 20: 2.5, 22: 2.5,
            24: 3, 27: 3, 30: 3.5, 33: 3.5, 36: 4, 42: 4.5, 48: 5}


def minor_dia(d, P=None):
    """普通螺纹小径 d1 = d − 1.0825P（GB/T 196），P 不给时取粗牙。"""
    P = P or METRIC_P[int(round(d))]
    return d - 1.0825 * P


# ---------------------------------------------------------------------- 外螺纹（GB/T 4459.1）
def thread_shaft(s, p0, u, length, d, P=None, sides=(1, -1), k=1.0, end_line=True):
    """外螺纹非圆视图：p0 = 轴线和螺纹端面（倒角端）的交点，u = 沿轴线指向螺纹终止处的方向，length = 螺纹长度。
    画小径细实线（端部画进倒角里，国标允许画到倒角处）、螺纹终止线粗实线（画到大径）。大径轮廓 SW 已画（粗实线）。
    sides：画轴线哪一侧（半剖/局部时只画一侧）。返回小径 d1。"""
    d1 = minor_dia(d, P)
    ux, uy, nx, ny = _frame(p0, u)
    Lk = length * k
    for sd in sides:
        s.line(_pt(p0, ux, uy, nx, ny, 0, sd * d1 / 2 * k), _pt(p0, ux, uy, nx, ny, Lk, sd * d1 / 2 * k), "细实线")
    if end_line:
        a = min(sides) * d / 2 * k if -1 in sides else 0
        b = max(sides) * d / 2 * k if 1 in sides else 0
        s.line(_pt(p0, ux, uy, nx, ny, Lk, a), _pt(p0, ux, uy, nx, ny, Lk, b), "粗实线")
    return d1


def thread_shaft_circle(s, c, d, P=None, k=1.0, gap_start=0, erase_chamfer=True):
    """外螺纹圆视图：大径粗实线圆（SW 已画），小径画约 3/4 圈细实线圆弧（缺口在 gap_start 起的 90° 内），
    倒角圆不画——erase_chamfer=True 时删掉圆心在 c、半径介于小径和大径之间的圆（SW 画出来的倒角圆）。"""
    d1 = minor_dia(d, P)
    if erase_chamfer:
        for e in s._items():
            if e.ObjectName == "AcDbCircle" and math.dist(e.Center[:2], c) < 0.05 and \
                    d1 / 2 * k - 0.6 < e.Radius < d / 2 * k - 0.05:
                e.Delete()
    s.layer("细实线")
    s.ms.AddArc(_P(*c), d1 / 2 * k, math.radians(gap_start + 90), math.radians(gap_start + 360))
    return d1


# ---------------------------------------------------------------------- 矩形花键（GB/T 4459.3、GB/T 1144）
def spline_shaft(s, p0, u, length, D, d, sides=(1, -1), k=1.0, tail=True):
    """外花键非圆视图：p0 = 轴线和花键端面交点，u 指向花键终止处，length = 工作长度。大径 D 轮廓 SW 已画；
    这里画小径 d 细实线（画满工作长度）、终止线细实线（垂直于轴线，画到大径）、尾部 30° 细斜线（从小径到大径）。"""
    ux, uy, nx, ny = _frame(p0, u)
    Lk = length * k
    for sd in sides:
        s.line(_pt(p0, ux, uy, nx, ny, 0, sd * d / 2 * k), _pt(p0, ux, uy, nx, ny, Lk, sd * d / 2 * k), "细实线")
        s.line(_pt(p0, ux, uy, nx, ny, Lk, 0), _pt(p0, ux, uy, nx, ny, Lk, sd * D / 2 * k), "细实线")
        if tail:
            dt = (D - d) / 2 / math.tan(math.radians(30)) * k
            s.line(_pt(p0, ux, uy, nx, ny, Lk, sd * d / 2 * k), _pt(p0, ux, uy, nx, ny, Lk + dt, sd * D / 2 * k), "细实线")


def spline_circle(s, c, D, d, N, B, k=1.0, rot=90, erase=True):
    """外花键圆视图（断面或端视）：画出全部 N 个齿（齿顶在大径圆弧上、齿侧是宽 B 的两条平行线、齿间是小径圆弧），
    rot 是第一个齿的方位角（度）。erase=True 先删掉圆心在 c、半径 = D/2 的整圆（光轴模型的外圆）和倒角圆。"""
    R, r, hb = D / 2 * k, d / 2 * k, B / 2 * k
    if erase:
        for e in s._items():
            if e.ObjectName == "AcDbCircle" and math.dist(e.Center[:2], c) < 0.05 and r + 0.05 < e.Radius <= R + 0.05:
                e.Delete()
    aR, ar = math.asin(hb / R), math.asin(hb / r)             # 齿侧线和两圆交点的半角
    s.layer("粗实线")
    for i in range(N):
        th = math.radians(rot) + 2 * math.pi * i / N
        ca, sa = math.cos(th), math.sin(th)
        for sg in (1, -1):                                     # 两条齿侧线
            a = (math.sqrt(r * r - hb * hb), sg * hb); b = (math.sqrt(R * R - hb * hb), sg * hb)
            q = [(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca) for x, y in (a, b)]
            s.ms.AddLine(_P(*q[0]), _P(*q[1]))
        s.ms.AddArc(_P(*c), R, th - aR, th + aR)                  # 齿顶
        nxt = math.radians(rot) + 2 * math.pi * (i + 1) / N
        s.ms.AddArc(_P(*c), r, th + ar, nxt - ar)                 # 齿间小径


def spline_mark(N, d, D, B, fit=("f7", "a11", "d10"), std="GB/T 1144-2001"):
    """矩形花键标记：'6×23f7×26a11×6d10 GB/T 1144-2001'（外花键）；内花键 fit=("H7","H10","H11")。
    图上写成 s.note([...], "{\\Fgdt;}" 之类不好表示花键符号，直接写这段字即可，符号可省略。"""
    return f"{N}×{d:g}{fit[0]}×{D:g}{fit[1]}×{B:g}{fit[2]} {std}"


# ---------------------------------------------------------------------- 圆柱螺旋压缩弹簧（GB/T 4459.4）
def spring(s, p0, u, H0, D2, d, n, n2=2.0, k=1.0, keep=2, hatch=True):
    """压缩弹簧剖视的规定画法：p0 = 轴线和下端面的交点，u = 轴线方向（指向上端面），H0 自由高度，D2 中径，d 簧丝直径，
    n 有效圈数，n2 支承圈数（两端各 n2/2 圈并紧磨平）。剖开后可见：两侧簧丝断面（小圆，画剖面线；d 在图上 < 2 mm 时涂黑）
    + 后半圈簧丝的轮廓（连接左侧断面和右侧下一个断面的两条公切线）。n > 4 时中间只画两端各 keep 圈，
    其余用通过簧丝中心的细点画线连起来（国标允许）。端面磨平：最外的断面被端面切平。返回节距 t。"""
    ux, uy, nx, ny = _frame(p0, u)
    W = lambda t, sd: _pt(p0, ux, uy, nx, ny, t * k, sd * D2 / 2 * k)
    t = (H0 - (n2 - 0.5) * d) / n                          # 节距（GB/T 23935：两端磨平 H0 = n·t + (n2 − 0.5)·d）
    r = d / 2 * k
    # 每半圈一个断面，左右交替。增量：支承圈每半圈 d/2（并紧），有效圈每半圈 t/2；最后整体缩放到首尾断面中心
    # 离端面 d/4（端面磨平，最外的断面被切掉一部分）。
    half = int(round(2 * (n + n2)))
    nb = int(round(n2))                                   # 每端支承半圈数 = n2/2 圈 × 2
    inc = [d / 2 if (j < nb or j >= half - nb) else t / 2 for j in range(half)]
    zs = [0.0]
    for v in inc:
        zs.append(zs[-1] + v)
    sc = (H0 - d / 2) / zs[-1]
    zc = [(d / 4 + z * sc, -1 if j % 2 == 0 else 1) for j, z in enumerate(zs)]
    # 省略中间：保留两端各 keep 圈（2·keep 个断面）
    show = list(range(len(zc)))
    if n > 4:
        kk = int(2 * (keep + n2 / 2))
        show = list(range(0, kk + 1)) + list(range(len(zc) - kk - 1, len(zc)))
        show = sorted(set(show))
    hatch_loops = []
    s.layer("粗实线")
    for i in show:
        z, sd = zc[i]
        c = W(z, sd)
        if z - d / 2 < -1e-6 or z + d / 2 > H0 + 1e-6:     # 被端面磨平：圆弧 + 弦
            zcut = 0.0 if z < H0 / 2 else H0
            h = abs(z - zcut) * k                         # 圆心到端面的距离
            a = math.acos(min(1, h / r))
            # 端面法向（指向圆心外侧）的角度：沿 -u 或 +u
            base = math.atan2(-uy, -ux) if zcut == 0 else math.atan2(uy, ux)
            arc = s.ms.AddArc(_P(*c), r, base + a, base - a + 2 * math.pi)
            p1 = (c[0] + r * math.cos(base + a), c[1] + r * math.sin(base + a))
            p2 = (c[0] + r * math.cos(base - a), c[1] + r * math.sin(base - a))
            s.ms.AddLine(_P(*p1), _P(*p2))
            hatch_loops.append(("cut", c, base, a))
        else:
            s.ms.AddCircle(_P(*c), r)
            hatch_loops.append(("circle", c))
    # 后半圈轮廓：断面 i（一侧）→ 断面 i+1（另一侧），两条公切线（两圆等径：中心连线平移 ±r）
    # 只画“左 → 右”那半圈（经过后面、看得见）；“右 → 左”那半圈在前面，剖切时被切掉了（不画，否则成 X 形交叉）
    for i in range(0, len(zc) - 1, 2):
        if i not in show or i + 1 not in show:
            continue
        a, b = W(*zc[i]), W(*zc[i + 1])
        L = math.dist(a, b); vx, vy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for sg in (1, -1):
            s.ms.AddLine(_P(a[0] - vy * r * sg, a[1] + vx * r * sg), _P(b[0] - vy * r * sg, b[1] + vx * r * sg))
    if n > 4:                                             # 中间省略部分：两侧簧丝中心的点画线
        gap = [i for i in range(len(zc)) if i not in show]
        z0, z1 = zc[gap[0] - 1][0], zc[gap[-1] + 1][0]
        for sd in (1, -1):
            s.line(W(z0, sd), W(z1, sd), "中心线")
    s.line(W(-3 / k, 0), W(H0 + 3 / k, 0), "中心线")      # 轴线
    if hatch:
        _hatch_wires(s, hatch_loops, r)
    return t


def _hatch_wires(s, loops, r):
    """簧丝断面：图上直径 ≥ 2 mm 画剖面线（ANSI31），更小涂黑（国标允许）。"""
    small = 2 * r < 2.0
    for lp in loops:
        c = lp[1]
        tmp = []
        if lp[0] == "circle":
            g = s.ms.AddCircle(_P(*c), r); tmp.append(g)
        else:
            _, c, base, a = lp
            arc = s.ms.AddArc(_P(*c), r, base + a, base - a + 2 * math.pi)
            p1 = (c[0] + r * math.cos(base + a), c[1] + r * math.sin(base + a))
            p2 = (c[0] + r * math.cos(base - a), c[1] + r * math.sin(base - a))
            ln = s.ms.AddLine(_P(*p1), _P(*p2)); tmp += [arc, ln]
        s.layer("剖面线")
        h = s.ms.AddHatch(0 if small else 1, "SOLID" if small else "ANSI31", True)
        h.AppendOuterLoop(wc.VARIANT(0x2009, tmp))
        if not small:
            h.PatternScale = max(0.25, r / 3)
        h.Evaluate()
        for g in tmp:
            g.Delete()
        s.layer("粗实线")


# ---------------------------------------------------------------------- 直齿锥齿轮（GB/T 4459.2）
def bevel_teeth(s, apex, u, delta, R, b, m, sides=(1, -1), k=1.0, ha=1.0, c=0.2, pitch_to_apex=False):
    """锥齿轮非圆视图（轴线在图面内、一般是过轴线的全剖）：apex = 分度圆锥顶点（图纸坐标），u = 轴线方向（从锥顶指向
    大端背锥一侧），delta = 分锥角（度），R = 外锥距，b = 齿宽，m = 大端模数。
    画：齿顶线、齿根线（粗实线，都收敛于锥顶）、大端背锥线和小端端面线（粗实线，垂直于分锥母线）、分度线（点画线，
    伸出 3 mm；pitch_to_apex=True 画到锥顶）。轮齿按不剖处理，剖面线只到齿根——模型建到齿根圆锥。返回齿顶圆直径 da。"""
    ux, uy, nx, ny = _frame(apex, u)
    dl = math.radians(delta)
    out = {}
    for sd in sides:
        g = (math.cos(dl) * ux + math.sin(dl) * nx * sd, math.cos(dl) * uy + math.sin(dl) * ny * sd)   # 分锥母线方向
        nb = (-math.sin(dl) * ux + math.cos(dl) * nx * sd, -math.sin(dl) * uy + math.cos(dl) * ny * sd)  # 背锥方向（离轴线向外）
        Pk = lambda L, h: (apex[0] + (g[0] * L + nb[0] * h) * k, apex[1] + (g[1] * L + nb[1] * h) * k)
        hA, hF = ha * m, (ha + c) * m
        ri = (R - b) / R
        to, ro = Pk(R, hA), Pk(R, -hF)                                  # 大端齿顶、齿根
        ti, rin = Pk((R - b), hA * ri), Pk((R - b), -hF * ri)           # 小端（向锥顶收缩）
        s.line(ti, to, "粗实线"); s.line(rin, ro, "粗实线")
        s.line(ro, to, "粗实线"); s.line(rin, ti, "粗实线")
        p_end = Pk(R + 3 / k, 0)
        p_start = apex if pitch_to_apex else Pk(R - b - 3 / k, 0)
        s.line(p_start, p_end, "中心线")
        out[sd] = {"tip_outer": to, "root_outer": ro, "tip_inner": ti, "root_inner": rin}
    z_d = 2 * R * math.sin(dl)                     # 大端分度圆直径
    return {"d": z_d, "da": z_d + 2 * ha * m * math.cos(dl), "pts": out}


def bevel_circles(s, c, d, da, R, b, k=1.0):
    """锥齿轮圆视图：大端齿顶圆、小端齿顶圆粗实线，大端分度圆点画线；齿根圆不画（GB/T 4459.2）。
    d、da 是大端分度圆、齿顶圆直径（bevel_teeth 返回），小端按 (R−b)/R 收缩。"""
    ri = (R - b) / R
    s.circle(c, da / 2 * k, "粗实线")
    s.circle(c, da / 2 * ri * k, "粗实线")
    s.circle(c, d / 2 * k, "中心线")


# ---------------------------------------------------------------------- 蜗杆、蜗轮（GB/T 4459.2）
def worm_teeth(s, p0, u, length, d1, m, sides=(1, -1), k=1.0, root=False):
    """蜗杆非圆视图：齿顶线粗实线（da1 = d1 + 2m）、分度线点画线（伸出 3）、齿根线细实线（root=True 时画，可省略）。
    p0 = 轴线和螺旋部分一端的交点，u 指向另一端，length = 螺旋部分长度。模型按齿根圆建光轴。"""
    ux, uy, nx, ny = _frame(p0, u)
    W = lambda t, r: _pt(p0, ux, uy, nx, ny, t * k, r * k)
    ra, rf = d1 / 2 + m, d1 / 2 - 1.2 * m
    for sd in sides:
        s.line(W(0, sd * ra), W(length, sd * ra), "粗实线")
        s.line(W(0, sd * rf), W(0, sd * ra), "粗实线"); s.line(W(length, sd * rf), W(length, sd * ra), "粗实线")
        s.line(W(-3 / k, sd * d1 / 2), W(length + 3 / k, sd * d1 / 2), "中心线")
        if root:
            s.line(W(0, sd * rf), W(length, sd * rf), "细实线")


def worm_circles(s, c, d1, m, k=1.0):
    """蜗杆圆视图：齿顶圆粗实线、分度圆点画线，齿根圆不画。"""
    s.circle(c, (d1 / 2 + m) * k, "粗实线"); s.circle(c, d1 / 2 * k, "中心线")


def worm_wheel_section(s, c_wheel, u, a, d1, m, b2, de2, sides=(1, -1), k=1.0, root=False):
    """蜗轮过轴线的剖视（轴线在图面内，蜗杆轴线垂直于图面）：c_wheel = 蜗轮轴线和中间平面的交点，u = 蜗轮轴线方向，
    a = 中心距，d1 = 蜗杆分度圆直径，m 模数，b2 = 蜗轮宽度，de2 = 蜗轮外圆直径。
    以蜗杆轴线为圆心：喉部齿顶圆弧（r = d1/2 − m，粗实线，延伸到和外圆 de2 相交为止）、分度圆弧（r = d1/2，点画线）；
    两侧外圆 de2 的直线到端面、端面线到齿根圆弧（r = d1/2 + 1.2m）。轮齿按不剖处理——模型建到齿根喉圆，
    齿根圆弧 SW 已画；root=True 时这里也画（没建模型时）。"""
    ux, uy, nx, ny = _frame(c_wheel, u)
    half = b2 / 2
    rt, rp, rf = d1 / 2 - m, d1 / 2, d1 / 2 + 1.2 * m
    for sd in sides:
        ow = _pt(c_wheel, ux, uy, nx, ny, 0, sd * a * k)         # 蜗杆轴线（垂直图面）
        base = math.atan2(-ny * sd, -nx * sd)                    # 从蜗杆轴线指向蜗轮轴线
        on = lambda r, th: (ow[0] + r * k * math.cos(base + th), ow[1] + r * k * math.sin(base + th))
        # 齿顶圆弧到外圆为止：a − rt·cosθ = de2/2；同时不超过端面
        tt = math.acos(max(-1, min(1, (a - de2 / 2) / rt)))
        if rt * math.sin(tt) > half:
            tt = math.asin(half / rt)
        tp = min(math.asin(min(1, half / rp)), math.acos(max(-1, min(1, (a - de2 / 2 - 2) / rp))))   # 分度弧伸出外圆 2 mm 为止
        tf = math.asin(min(1, half / rf))
        s.layer("粗实线"); s.ms.AddArc(_P(*ow), rt * k, base - tt, base + tt)
        s.layer("中心线"); s.ms.AddArc(_P(*ow), rp * k, base - tp, base + tp)
        if root:
            s.layer("粗实线"); s.ms.AddArc(_P(*ow), rf * k, base - tf, base + tf)
        for sg in (1, -1):
            p = on(rt, sg * tt)
            tax = (p[0] - c_wheel[0]) * ux + (p[1] - c_wheel[1]) * uy          # 该点的轴向坐标（图纸 mm）
            q = _pt(c_wheel, ux, uy, nx, ny, tax, sd * de2 / 2 * k)
            if math.dist(p, q) > 0.05:
                s.line(p, q, "粗实线")
            e = _pt(c_wheel, ux, uy, nx, ny, sg * half * k, sd * de2 / 2 * k)
            s.line(q, e, "粗实线")                                            # 外圆
            s.line(e, on(rf, sg * tf), "粗实线")                              # 端面到齿根圆弧
        s.line((ow[0] - 3 * ux, ow[1] - 3 * uy), (ow[0] + 3 * ux, ow[1] + 3 * uy), "中心线")   # 蜗杆轴线位置
        s.line((ow[0] - 3 * nx, ow[1] - 3 * ny), (ow[0] + 3 * nx, ow[1] + 3 * ny), "中心线")


def worm_wheel_circles(s, c, d2, de2, k=1.0):
    """蜗轮圆视图：外圆 de2 粗实线、分度圆点画线；喉圆、齿根圆不画（GB/T 4459.2）。"""
    s.circle(c, de2 / 2 * k, "粗实线"); s.circle(c, d2 / 2 * k, "中心线")


METHODS = ("thread_shaft", "thread_shaft_circle", "spline_shaft", "spline_circle", "spring", "bevel_teeth",
           "bevel_circles", "worm_teeth", "worm_circles", "worm_wheel_section", "worm_wheel_circles")

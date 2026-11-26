"""placer —— 粗糙度、形位公差框格、基准、零件序号的自动放置（2026-11-08）。

以前这些符号要自己算坐标、看 2~4 轮渲染图再挪。现在只给“标在哪个要素上”，位置自动挑：
    s.auto_rough(((x1,y1),(x2,y2)), "1.6", out=(0,1))          # 表面 = 视图里那条轮廓线，out = 指向材料外面
    s.auto_gtol("h", "0.015", "A-B", tip, out=(0,1))           # tip = 箭头落点（表面上，或直径尺寸线终端）
    s.auto_datum(foot, "A", out=(0,1))
    s.auto_balloons([(零件上一点, 序号), ...], box=视图框)      # 自动分到视图四周、排成一排、指引线不交叉

做法：从当前图里收集“障碍物”（文字、尺寸数字、已放的符号是硬障碍；轮廓线、剖面线、中心线是软障碍），
建 shapely STRtree；对每个符号枚举几十个候选（直接标在表面上的不同位置 / 标在延长线上 / 指引线引出的不同长度、
左右两侧……），按“压字 ≫ 压剖面线 > 压轮廓线 > 离要素远”打分，取最低分画出来，再把它的外形加进障碍物。
GB/T 131-2006 的读向规则（符号只能从下方或右方读）、GB/T 1182 的箭头垂直于表面，都在候选生成时保证。
放完照样跑 s.check()。"""
import math
from shapely.geometry import LineString, Polygon, box as sbox, Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

HARD, HATCH, LINE, CENTER = "hard", "hatch", "line", "center"
COST = {HARD: 1000.0, HATCH: 30.0, LINE: 40.0, CENTER: 6.0}


def _arc_pts(c, r, a0, a1, n=24):
    sw = (a1 - a0) % (2 * math.pi) or 2 * math.pi
    return [(c[0] + r * math.cos(a0 + sw * i / n), c[1] + r * math.sin(a0 + sw * i / n)) for i in range(n + 1)]


class Obstacles:
    """当前图里的障碍物索引。新加的实体在 ModelSpace 末尾，refresh() 只处理新增部分；有删除就整体重建。"""

    def __init__(self, sheet):
        self.s = sheet
        self.items = []          # (geom, kind)
        self.n_seen = 0
        self.tail = None
        self.tree = None
        self.extra = []          # 本模块放下的符号外形（硬障碍）

    def _geom(self, e):
        t = e.ObjectName
        lay = e.Layer
        kind = CENTER if lay == "中心线" else HATCH if lay == "剖面线" else LINE
        try:
            if t == "AcDbLine":
                return [(LineString([e.StartPoint[:2], e.EndPoint[:2]]), kind)]
            if t == "AcDbArc":
                return [(LineString(_arc_pts(e.Center[:2], e.Radius, e.StartAngle, e.EndAngle)), kind)]
            if t == "AcDbCircle":
                return [(LineString(_arc_pts(e.Center[:2], e.Radius, 0, 2 * math.pi, 36)), kind)]
            if t in ("AcDbPolyline", "AcDb2dPolyline"):
                c = list(e.Coordinates); st = 2 if t == "AcDbPolyline" else 3
                q = [(c[i], c[i + 1]) for i in range(0, len(c), st)]
                if getattr(e, "Closed", False):
                    q.append(q[0])
                return [(LineString(q), kind)] if len(q) > 1 else []
            if t == "AcDbSpline":
                c = list(e.FitPoints) if e.NumberOfFitPoints else list(e.ControlPoints)
                q = [(c[i], c[i + 1]) for i in range(0, len(c), 3)]
                return [(LineString(q), kind)] if len(q) > 1 else []
            if t == "AcDbLeader":
                c = list(e.Coordinates); q = [(c[i], c[i + 1]) for i in range(0, len(c), 3)]
                return [(LineString(q), LINE)] if len(q) > 1 else []
            if t == "AcDbHatch":
                if lay != "剖面线":                                  # 实心小三角（基准、箭头）
                    mn, mx = e.GetBoundingBox(); return [(sbox(mn[0], mn[1], mx[0], mx[1]), HARD)]
                try:
                    reg = self.s._dxf_hatch_region(e)
                    if reg is not None and not reg.is_empty:
                        return [(reg, HATCH)]
                except Exception:
                    pass
                mn, mx = e.GetBoundingBox()
                return [(sbox(mn[0], mn[1], mx[0], mx[1]), HATCH)]
            if t in ("AcDbText", "AcDbMText", "AcDbFcf", "AcDbBlockReference"):
                mn, mx = e.GetBoundingBox()
                return [(sbox(mn[0] - 0.4, mn[1] - 0.4, mx[0] + 0.4, mx[1] + 0.4), HARD)]
            if "Dimension" in t:
                out = []
                tp = e.TextPosition; h = e.TextHeight * (self.s.S or 1)
                import re
                txt = re.sub(r"\{\\[^;]*;|[{}]|\\S[^;]*;", "", e.TextOverride or f"{e.Measurement:g}")
                txt = re.sub(r"%%[CcPpDd]", "x", txt).replace("<>", "000")
                w = len(txt) * h * 0.7 + 1
                rec = self.dimrec.get(e.Handle)
                vert = rec is not None and rec[4] % 180 == 90
                if vert:
                    out.append((sbox(tp[0] - h / 2 - 0.6, tp[1] - w / 2, tp[0] + h / 2 + 0.6, tp[1] + w / 2), HARD))
                else:
                    out.append((sbox(tp[0] - w / 2, tp[1] - h / 2 - 0.6, tp[0] + w / 2, tp[1] + h / 2 + 0.6), HARD))
                if rec is not None:                                     # 尺寸线、尺寸界线
                    _, p1, p2, loc, ang = rec
                    ax = 0 if ang == 0 else 1; pr = 1 - ax
                    e1 = list(p1); e1[pr] = loc[pr]; e2 = list(p2); e2[pr] = loc[pr]
                    out += [(LineString([p1, e1]), LINE), (LineString([p2, e2]), LINE),
                            (LineString([e1, e2]), HARD if abs(e1[ax] - e2[ax]) > 0.1 else LINE)]
                else:
                    mn, mx = e.GetBoundingBox()
                    out.append((sbox(mn[0], mn[1], mx[0], mx[1]).boundary, LINE))
                return out
        except Exception:
            return []
        return []

    def refresh(self):
        ms = self.s.ms
        n = ms.Count
        rebuild = n < self.n_seen
        if not rebuild and self.n_seen and self.tail is not None:
            try:
                rebuild = ms.Item(self.n_seen - 1).Handle != self.tail
            except Exception:
                rebuild = True
        if rebuild:
            self.items, self.n_seen = [], 0
        if n == self.n_seen and self.tree is not None:
            return self
        self.dimrec = {r[0].Handle: r for r in self.s._dims}
        for i in range(self.n_seen, n):
            try:
                self.items += self._geom(ms.Item(i))
            except Exception:
                pass
        self.n_seen = n
        self.tail = ms.Item(n - 1).Handle if n else None
        allg = self.items + self.extra
        self.geoms = [g for g, _ in allg]; self.kinds = [k for _, k in allg]
        self.tree = STRtree(self.geoms)
        return self

    def add(self, geom):
        """放下的符号外形当硬障碍记下（它本身的实体也会在下次 refresh 时读进来，这里先补上外形，避免同一批里互相压）。"""
        self.extra.append((geom, HARD))
        self.geoms.append(geom); self.kinds.append(HARD)
        self.tree = STRtree(self.geoms)

    def cost(self, body, leader=None, ignore=None, line_w=2.0):
        """body：符号/文字的外形（多边形），压上什么都扣分；leader：指引线（线），只怕压字。
        ignore：忽略和它相交的软障碍（表面本身那条线）。"""
        c = 0.0
        for i in self.tree.query(body):
            g, k = self.geoms[i], self.kinds[i]
            if not g.intersects(body):
                continue
            if ignore is not None and k != HARD and g.geom_type == "LineString" and g.within(ignore.buffer(0.1)):
                continue                                  # 表面线本身（符号尖端就落在它上面）
            if k == HARD:
                c += COST[HARD]
            elif g.geom_type in ("Polygon", "MultiPolygon"):
                c += COST[k] * min(1.0, g.intersection(body).area / max(body.area, 1e-6)) + COST[k] * 0.2
            else:
                c += COST[k] * (0.3 + min(1.0, g.intersection(body).length / 5))
        if leader is not None:
            # 指引线起点（箭头尖 / 基准三角形）本来就贴着要素和尺寸线，前 1.5 mm 不算
            if leader.length > 2:
                from shapely.ops import substring
                leader = substring(leader, 1.5, leader.length)
            for i in self.tree.query(leader):
                g, k = self.geoms[i], self.kinds[i]
                if g.intersects(leader):
                    if k == HARD:
                        c += 300
                    elif k == LINE:
                        c += line_w
        return c


def _obs(s):
    if not hasattr(s, "_placer_obs"):
        s._placer_obs = Obstacles(s)
    return s._placer_obs.refresh()


def _inside(s, g, margin=2):
    x0, y0, x1, y1 = s.inner
    b = g.bounds
    return b[0] >= x0 + margin and b[1] >= y0 + margin and b[2] <= x1 - margin and b[3] <= y1 - margin


# ---------------------------------------------------------------------- 粗糙度符号外形
def _rough_body(tip, ang, ra, h=3.5):
    H1, H2 = 1.4 * h, 3.0 * h
    t30 = math.tan(math.radians(30))
    w = H2 * t30 + (3.2 * h if ra is not None else 0)
    pts = [(-H1 * t30, H1), (0, 0), (H2 * t30, H2), (w, H2)]
    if ra is not None:
        tx = H2 * t30 + 0.6; tw = (len(f"Ra {ra}") * h * 0.7)
        pts += [(tx, H2 - h - 0.8), (tx + tw, H2 - h - 0.8), (tx + tw, H2 - 0.2), (w, H2)]
    c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    q = [(tip[0] + x * c - y * s_, tip[1] + x * s_ + y * c) for x, y in pts]
    return Polygon(q).convex_hull.buffer(1.0)          # 留 1 mm 间隙，别贴着别的线


def _unit(v):
    L = math.hypot(*v); return (v[0] / L, v[1] / L)


def auto_rough(s, seg, ra, out, h=3.5, mode="remove", allow=("direct", "ext", "leader"), verbose=True):
    """粗糙度自动放置。seg = 表面在视图里的那条轮廓线 ((x1,y1),(x2,y2))（图纸坐标），out = 指向材料外侧的法向。
    候选：① 直接标在轮廓线上（只有朝上、朝左的面能直接标，GB/T 131 读向）；② 标在轮廓线的延长线上（细实线延长）；
    ③ 带箭头的指引线引出、水平线上放符号（任何朝向都行，朝下/朝右的面只能这样）。返回选中的方案说明。"""
    O = _obs(s)
    a, b = seg; n = _unit(out)
    L = math.dist(a, b); u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    surf = LineString([a, b])
    cands = []
    up, left = n[1] > 0.9, n[0] < -0.9
    ang = 0 if up else 90 if left else None
    if ang is not None and "direct" in allow:
        for t in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9):
            tip = (a[0] + u[0] * L * t, a[1] + u[1] * L * t)
            body = _rough_body(tip, ang, ra, h)
            if not _inside(s, body):
                continue
            cands.append((O.cost(body, ignore=surf) + abs(t - 0.5) * 4, "direct", tip, body, None))
    if ang is not None and "ext" in allow:
        for end, sg in ((a, -1), (b, 1)):
            for d in (4, 8, 12, 18):
                tip = (end[0] + u[0] * sg * d, end[1] + u[1] * sg * d)
                body = _rough_body(tip, ang, ra, h)
                ext = LineString([end, (tip[0] + u[0] * sg * 3, tip[1] + u[1] * sg * 3)])
                if not _inside(s, body):
                    continue
                cands.append((O.cost(body, ext, ignore=surf) + 6 + d * 0.3, "ext", tip, body, (end, sg, d)))
    if "leader" in allow:
        H2 = 3.0 * h; w = H2 * math.tan(math.radians(30)) + 3.2 * h + 1.4 * h * math.tan(math.radians(30)) + 2
        for t in (0.5, 0.3, 0.7, 0.15, 0.85):
            p = (a[0] + u[0] * L * t, a[1] + u[1] * L * t)
            for Lg in (6, 10, 15, 21, 28):
                for tilt in (0, 30, -30):
                    th = math.radians(tilt)
                    d = (n[0] * math.cos(th) - n[1] * math.sin(th), n[0] * math.sin(th) + n[1] * math.cos(th))
                    sh = (p[0] + d[0] * Lg, p[1] + d[1] * Lg)
                    for right in (True, False):
                        if abs(d[1]) < 0.2 and ((d[0] > 0) != right):
                            continue                              # 水平引出时，水平线接着往外走
                        # 和 Sheet.rough_leader 的几何一致：向右时符号尖端在 shelf + a，向左时在 shelf − w − 1
                        a_ = 1.4 * h * math.tan(math.radians(30)) + 1
                        w_ = 3.0 * h * math.tan(math.radians(30)) + 3.2 * h
                        tip = (sh[0] + a_, sh[1]) if right else (sh[0] - w_ - 1, sh[1])
                        body = _rough_body(tip, 0, ra, h)
                        ld = LineString([p, sh])
                        if not _inside(s, body):
                            continue
                        c = O.cost(body, ld) + 10 + Lg * 0.4      # 引出时符号不许再碰表面本身 + abs(tilt) * 0.05 + abs(t - 0.5) * 3
                        cands.append((c, "leader", tip, body, (p, sh, right)))
    if not cands:
        raise RuntimeError(f"粗糙度 Ra{ra}：图框里放不下（seg={seg}）")
    c, how, tip, body, extra = min(cands, key=lambda z: z[0])
    if how == "direct":
        s.rough(tip, ra, ang=ang, h=h, mode=mode)
    elif how == "ext":
        end, sg, d = extra
        s.line(end, (tip[0] + u[0] * sg * 3, tip[1] + u[1] * sg * 3), "细实线")
        s.rough(tip, ra, ang=ang, h=h, mode=mode)
    else:
        p, sh, right = extra
        s.rough_leader(p, (sh[0] + (0.01 if right else -0.01), sh[1]), ra, h=h)
    O.add(body)
    if verbose:
        print(f"  粗糙度 Ra{ra}：{how}，代价 {c:.0f}" + ("  ← 压到东西了，看一眼" if c >= 100 else ""))
    return how, c


# ---------------------------------------------------------------------- 形位公差框格
def auto_gtol(s, sym, value, datum, tip, out, h=3.5, verbose=True):
    """形位公差框格自动放置：tip = 箭头落点（被测表面上一点，或直径尺寸线的终端——标轴线时），
    out = 箭头来的方向（指向材料外，箭头沿 −out 垂直指向表面）。指引线：框格一端 → 折点 → 箭头；
    折点在 tip + out·L（L 取 8~36），框格放折点左边或右边、同一高度。返回框格对象。"""
    import win32com.client as wc
    O = _obs(s)
    n = _unit(out)
    tol = s.gtol(sym, value, datum, (-5000, -5000), [(-4990, -4990), (-4980, -4980)])     # 先放到图外量大小
    mn, mx = tol.GetBoundingBox(); fw, fh = mx[0] - mn[0], mx[1] - mn[1]
    tol_leader = _last_leader(s)
    cands = []
    for Lg in (8, 12, 16, 20, 26, 32, 40):
        E = (tip[0] + n[0] * Lg, tip[1] + n[1] * Lg)
        for side in (1, -1):                        # 框格在折点右边 / 左边
            if abs(n[1]) < 0.2 and (n[0] > 0) != (side > 0):
                continue                            # 水平引出：框格接着往外放
            gap = 4 if abs(n[1]) > 0.2 else 0
            x_near = E[0] + side * gap
            x0 = x_near if side > 0 else x_near - fw
            body = sbox(x0 - 0.5, E[1] - fh / 2 - 0.5, x0 + fw + 0.5, E[1] + fh / 2 + 0.5)
            ld = LineString([tip, E, (x_near, E[1])]) if gap else LineString([tip, E])
            if not _inside(s, body):
                continue
            c = O.cost(body, ld) + Lg * 0.5 + (0 if side > 0 else 2)
            cands.append((c, x0, E, side))
    if not cands:
        raise RuntimeError("形位公差框格放不下")
    c, x0, E, side = min(cands, key=lambda z: z[0])
    # 删掉量尺寸用的临时对象，按选中的位置重画（gtol 自己会从框格端点连引线）
    tol.Delete()
    if tol_leader is not None:
        tol_leader.Delete()
    frame_at = (x0, E[1])
    pts = [E, tip] if abs(n[1]) > 0.2 else [tip]
    if side < 0:                                    # 框格在左：gtol 判断第一个折点在框格左边才从左端出，这里在右边 → 从右端出
        pass
    t2 = s.gtol(sym, value, datum, frame_at, pts)
    O.add(sbox(x0 - 0.5, E[1] - fh / 2 - 0.5, x0 + fw + 0.5, E[1] + fh / 2 + 0.5))
    if verbose:
        print(f"  形位公差 {sym} {value}：折点 {tuple(round(v, 1) for v in E)}，代价 {c:.0f}" + ("  ← 看一眼" if c >= 100 else ""))
    return t2


def _last_leader(s):
    n = s.ms.Count
    for i in range(n - 1, max(-1, n - 4), -1):
        e = s.ms.Item(i)
        if e.ObjectName == "AcDbLeader":
            return e
    return None


# ---------------------------------------------------------------------- 基准符号
def auto_datum(s, foot, letter, out, h=3.5, slide=None, verbose=True):
    """基准符号自动放置：foot = 三角形贴的点（表面上 / 尺寸线终端），out = 引出方向。
    gap 在 4~16 里挑；slide=((x1,y1),(x2,y2)) 给出表面线段时，foot 还可以沿表面滑动（标轴线的基准别给 slide，
    它必须和尺寸线对齐）。"""
    O = _obs(s)
    n = _unit(out); b = 2 * h
    feet = [foot]
    if slide:
        a, c = slide
        feet += [(a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t) for t in (0.5, 0.3, 0.7, 0.15, 0.85)]
    cands = []
    for fi, f in enumerate(feet):
        for gap in (5, 8, 11, 15):
            end = (f[0] + n[0] * gap, f[1] + n[1] * gap)
            cx, cy = end[0] + n[0] * b / 2, end[1] + n[1] * b / 2
            body = sbox(cx - b / 2 - 0.5, cy - b / 2 - 0.5, cx + b / 2 + 0.5, cy + b / 2 + 0.5)
            ld = LineString([f, end])
            if not _inside(s, body):
                continue
            cands.append((O.cost(body, ld) + gap * 0.3 + fi * 3, f, gap, body))
    c, f, gap, body = min(cands, key=lambda z: z[0])
    s.datum(f, letter, direction=n, gap=gap, h=h)
    O.add(body)
    if verbose:
        print(f"  基准 {letter}：gap {gap}，代价 {c:.0f}" + ("  ← 看一眼" if c >= 100 else ""))


# ---------------------------------------------------------------------- 零件序号
def auto_balloons(s, items, box, sides=("top", "left", "right", "bottom"), first=12, pitch=10, h=5, verbose=True,
                  inset=30):
    """装配图零件序号自动排（GB/T 4458.2）：items = [(零件上一点, 序号), ...]，box = 视图外框。
    每个序号分到离它最近的允许的一侧，同一侧的序号排成一排（水平行或竖直列）、按零件点的位置排序（指引线不交叉），
    间距不小于 pitch；整排离视图 first 起，压到东西就往外挪。返回 {序号: 横线起点}。"""
    O = _obs(s)
    x0, y0, x1, y1 = box
    groups = {k: [] for k in sides}
    off0 = first + 4

    def probe(p, side):                     # 把这个序号单独拉到某一侧时，指引线要穿过多少东西（离视图远近都试）
        best_c = None
        for off in range(-inset, first + 60, 4):        # 负的 = 排在视图外框里面的空白处（轴伸出端两边这种）
            q = {"top": (p[0], y1 + off), "bottom": (p[0], y0 - off), "left": (x0 - off, p[1]),
                 "right": (x1 + off, p[1])}[side]
            c = O.cost(sbox(q[0] - 4, q[1] - 0.3, q[0] + 4, q[1] + h + 1.5), LineString([p, q]), line_w=8)
            c += math.dist(p, q) * 0.3 + (5000 if not _inside(s, Point(q).buffer(4)) else 0)
            best_c = c if best_c is None else min(best_c, c)
        return best_c
    for p, num in items:                    # 不按“最近的边”分：按指引线穿过的东西（尺寸线、文字）最少的一侧
        groups[min(sides, key=lambda k: probe(p, k))].append((p, num))
    res = {}
    for side, its in groups.items():
        if not its:
            continue
        horiz = side in ("top", "bottom")
        its.sort(key=lambda it: it[0][0] if horiz else -it[0][1])
        # 沿排方向的位置：先取零件点的投影，再按 pitch 推开（保持顺序）
        pos = [it[0][0] if horiz else it[0][1] for it in its]
        if not horiz:
            pos = [-v for v in pos]
        for i in range(1, len(pos)):
            pos[i] = max(pos[i], pos[i - 1] + pitch)
        lo, hi = (x0, x1) if horiz else (-y1, -y0)
        shift = max(0, pos[-1] - hi + 0) if pos[-1] > hi else 0
        pos = [v - shift for v in pos]
        if not horiz:
            pos = [-v for v in pos]
        best = None

        def uncross(at):
            """相邻两条指引线交叉就交换两个序号的位置，直到不交叉（只按零件点排序不够：点有远有近）。"""
            order = list(range(len(its)))
            for _ in range(len(its) ** 2 + 1):
                changed = False
                for i in range(len(order) - 1):
                    a, b = order[i], order[i + 1]
                    if LineString([its[a][0], at[i]]).crosses(LineString([its[b][0], at[i + 1]])):
                        order[i], order[i + 1] = b, a; changed = True
                if not changed:
                    break
            return [its[i] for i in order]
        for off in range(-inset, first + 60, 3):
            if side == "top":    at = [(v, y1 + off) for v in pos]
            elif side == "bottom": at = [(v, y0 - off) for v in pos]
            elif side == "left": at = [(x0 - off, v) for v in pos]
            else:                at = [(x1 + off, v) for v in pos]
            its_o = uncross(at)
            c = 0; bodies = []
            for (p, num), q in zip(its_o, at):
                right = side != "left"
                x2 = q[0] + (8 if right else -8)
                bd = sbox(min(q[0], x2) - 0.5, q[1] - 0.3, max(q[0], x2) + 0.5, q[1] + h + 1.5)
                bodies.append(bd)
                if not _inside(s, bd):
                    c += 5000
                c += O.cost(bd, LineString([p, q]), line_w=4)
            c += abs(off - first) * 0.3
            if best is None or c < best[0]:
                best = (c, at, bodies, its_o)
            if c < 50:
                break
        c, at, bodies, its = best
        for (p, num), q, bd in zip(its, at, bodies):
            s.balloon(p, q, num, h=h)
            O.add(bd)
            res[num] = q
        if verbose:
            print(f"  序号 {side}：{[n for _, n in its]}，代价 {c:.0f}" + ("  ← 看一眼" if c >= 200 else ""))
    return res


METHODS = ("auto_rough", "auto_gtol", "auto_datum", "auto_balloons")

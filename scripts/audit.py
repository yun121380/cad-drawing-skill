"""audit —— 尺寸完整性审查（2026-11-08）：拿零件模型的几何特征核对图上的尺寸“标全了没有、有没有封闭链”。

check() 只能查“字压线”这类排版问题，查不了“少标了一个台阶的轴向定位”。这里补上：
  1. views 步骤里 sw_views.part_features(sw, 零件, json) 读出零件的特征：垂直于 X/Y/Z 的平面位置、圆柱面（轴线、半径）；
  2. AutoCAD 步骤最后 s.audit_dims(features, [(仿射, 视图框), ...])：把每个线性尺寸的两端按视图仿射换回模型坐标，
     按轴向建图：节点 = 平面位置、孔/轴的轴线位置、圆柱的两条外轮廓线位置；边 = 尺寸（对称尺寸还连到中点）；
     圆柱的轮廓线和轴线之间有隐含的边（直径/槽宽标了，半边就定了）。然后报告：
       · 某个平面/轴线和其余要素不连通 —— 缺定位尺寸；
       · 一个尺寸连起来的两点已经被别的尺寸连起来了 —— 封闭尺寸链（除非是参考尺寸）；
       · 某个圆柱面的直径/半径在图上哪儿都找不到（Φ、R、M 螺纹、槽宽都算）——缺直径；
       · 视图里虚线很多 —— 提示考虑剖视（只是提示，该不该剖还是要人判断）。
只认正交视图（主/俯/左/剖视/放大图），斜视图里的尺寸跳过。分布圆上的孔（Φ92 上均布）按“孔心到某轴线距离 = 图上某个 Φ/2”算已定位。
"""
import math, re

TOL = 0.05


def _dsu(n):
    p = list(range(n))

    def f(x):
        while p[x] != x:
            p[x] = p[p[x]]; x = p[x]
        return x

    def u(a, b):
        ra, rb = f(a), f(b)
        if ra == rb:
            return False
        p[ra] = rb; return True
    return f, u


def _texts(s):
    """图上所有文字和尺寸文字（尺寸的 <> 换成实测值）。"""
    out = []
    for e in s._items():
        t = e.ObjectName
        try:
            if "Dimension" in t:
                m = e.Measurement
                ov = e.TextOverride
                txt = ov.replace("<>", f"{m:g}") if ov else f"{m:g}"
                if not ov and "Radial" in t:
                    txt = f"R{m:g}"                      # 半径尺寸没写覆盖文字时，数字前的 R 是标注样式加的
                elif not ov and "Diametric" in t:
                    txt = f"%%C{m:g}"
                out.append((txt, m, ov))
            elif t in ("AcDbText", "AcDbMText"):
                out.append((e.TextString, None, None))
        except Exception:
            pass
    return out


def _numbers(texts):
    """从文字里取直径 / 半径 / 螺纹 / 普通数值。"""
    dia, rad, mth, plain = set(), set(), set(), set()
    for s, meas, ov in texts:
        t = re.sub(r"\{\\[^;]*;|[{}]|\\S[^;]*;", " ", s)
        for v in re.findall(r"(?:%%[Cc]|Φ|φ)\s*(\d+(?:\.\d+)?)", t):
            dia.add(float(v))
        for v in re.findall(r"(?<![A-Za-z])R\s*(\d+(?:\.\d+)?)", t):
            rad.add(float(v))
        for v in re.findall(r"M\s*(\d+(?:\.\d+)?)", t):
            mth.add(float(v))
        if meas is not None:
            plain.add(round(meas, 3))
            if ov and re.search(r"%%[Cc]", ov) and "<>" in ov:
                dia.add(round(meas, 3))
        for v in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d.])", t):
            plain.add(float(v))
    return dia, rad, mth, plain


def audit_dims(s, features, views, ignore_r=(), ignore=(), hidden_hint=6, verbose=True):
    """features：sw_views.part_features 的结果；views：[(view_affine, 视图框), ...]（layout.json 里的）。
    ignore_r：不用查的半径（齿轮齿根圆这种按规定不注的）；ignore：不用查的节点 [(轴号, 坐标)]。
    返回 [(说明, x, y)]，和 check() 一样的格式。"""
    issues = []
    AX = "XYZ"
    # ---------- 节点
    nodes = {0: [], 1: [], 2: []}            # 轴号 → [(坐标, 说明)]
    implicit = {0: [], 1: [], 2: []}         # 隐含边 (坐标1, 坐标2)

    def add(ax, v, what):
        for c, w in nodes[ax]:
            if abs(c - v) < TOL:
                return
        nodes[ax].append((v, what))
    for ax, v in features["planes"]:
        add(ax, v, f"平面 {AX[ax]}={v:g}")
    holes = []
    for d, o, r, span in features["cyls"]:
        k = [i for i in range(3) if abs(abs(d[i]) - 1) < 1e-6]
        if not k:
            continue
        a = k[0]
        for i in range(3):
            if i == a:
                continue
            add(i, o[i], f"{'Φ%g' % (2 * r)} 轴线 {AX[i]}={o[i]:g}")
            for sg in (1, -1):
                add(i, o[i] + sg * r, f"Φ{2 * r:g} 轮廓 {AX[i]}={o[i] + sg * r:g}")
                implicit[i].append((o[i], o[i] + sg * r))
        holes.append((a, o, r))
    ign = {(a, round(v, 2)) for a, v in ignore}

    # ---------- 尺寸 → 模型坐标
    def to_model(p, ax_sheet):
        for aff, box in views:
            x0, y0, x1, y1 = box
            if not (x0 - 2 <= p[0] <= x1 + 2 and y0 - 2 <= p[1] <= y1 + 2):
                continue
            es = [aff["ex"], aff["ey"], aff["ez"]]
            i = max(range(3), key=lambda j: abs(es[j][ax_sheet]))
            if abs(es[i][ax_sheet]) < 1e-6 or any(abs(es[j][ax_sheet]) > 1e-6 for j in range(3) if j != i):
                return None                      # 斜视图 / 旋转视图
            return i, (p[ax_sheet] - aff["o"][ax_sheet]) / es[i][ax_sheet]
        return None

    dims = {0: [], 1: [], 2: []}
    skipped = 0
    for d, p1, p2, loc, ang in s._dims:
        axs = 0 if ang % 180 == 0 else 1
        a, b = to_model(p1, axs), to_model(p2, axs)
        if not a or not b or a[0] != b[0]:
            skipped += 1; continue
        try:
            label = (d.TextOverride or "").replace("<>", "") or f"{d.Measurement:g}"
        except Exception:
            label = "?"
        dims[a[0]].append((a[1], b[1], label, loc))
    dia, rad, mth, plain = _numbers(_texts(s))
    # ---------- 每个轴向：连通性 + 封闭链
    for ax in range(3):
        pts = [c for c, _ in nodes[ax]]
        virt = set()
        for c1, c2, _, _ in dims[ax]:               # 尺寸端点不在任何要素上（如对称尺寸的一半），也当节点
            for c in (c1, c2, (c1 + c2) / 2):       # 中点：对称尺寸（齿宽 40、腹板 12 都对称于中面）靠它连起来
                if all(abs(c - q) > TOL for q in pts):
                    pts.append(c); nodes[ax].append((c, f"尺寸端点 {AX[ax]}={c:g}"))
                    if c == (c1 + c2) / 2:
                        virt.add(len(pts) - 1)
        idx = lambda v: min(range(len(pts)), key=lambda i: abs(pts[i] - v))
        n = len(pts)
        if n == 0:
            continue
        fD, uD = _dsu(n)
        fF, uF = _dsu(n)
        cyl_r = {round(2 * r, 3) for _, _, r in holes}
        done = set()
        for c1, c2, lab, loc in dims[ax]:
            i, j = idx(c1), idx(c2)
            if i == j:
                continue
            key = (min(i, j), max(i, j))
            size_dim = round(abs(c2 - c1), 3) in cyl_r     # 直径尺寸：定的是大小不是位置，两段同径轴颈各标一次不算封闭
            if key in done or size_dim:
                uD(i, j)
            elif not uD(i, j):
                issues.append((f"{AX[ax]} 向可能是封闭尺寸链：{lab}（{c1:g}→{c2:g}）两端已经被别的尺寸定了", round(loc[0], 1), round(loc[1], 1)))
            done.add(key)
            uF(i, j)
            m = (c1 + c2) / 2                          # 对称尺寸：中点（要素或虚拟对称面）和两端连上
            for q in range(len(pts)):
                if abs(pts[q] - m) < TOL and q not in (i, j):
                    uF(q, i); uF(q, j)
        for c1, c2 in implicit[ax]:
            uF(idx(c1), idx(c2))
        # 分布圆上的孔：孔心到某条平行轴线的距离 = 图上某个 Φ/2 → 认为已定位（极坐标定位）
        for a, o, r in holes:
            for a2, o2, r2 in holes:
                if a2 != a or (o2 == o):
                    continue
                dd = math.dist([o[i] for i in range(3) if i != a], [o2[i] for i in range(3) if i != a])
                if dd > 1 and any(abs(2 * dd - v) < 0.05 for v in dia) and ax != a:
                    uF(idx(o[ax]), idx(o2[ax]))
        comps = {}
        for i in range(n):
            comps.setdefault(fF(i), []).append(i)
        if len(comps) > 1:
            main = max(comps.values(), key=len)
            for comp in comps.values():
                if comp is main:
                    continue
                cs = sorted(pts[i] for i in comp if i not in virt and (ax, round(pts[i], 2)) not in ign)
                if not cs:
                    continue
                planes = [f"{c:g}" for c in cs if any(abs(v - c) < TOL and w.startswith("平面") for v, w in nodes[ax])]
                issues.append((f"{AX[ax]} 向缺定位尺寸：{AX[ax]}={', '.join(f'{c:g}' for c in cs)} 这一组"
                               f"（{'平面 ' + '/'.join(planes) if planes else '轴线/轮廓'}）和其余要素之间没有尺寸连起来", None, None))
    # ---------- 直径
    seen = set()
    for a, o, r in holes:
        if round(r, 3) in seen or any(abs(r - x) < 0.01 for x in ignore_r):
            continue
        seen.add(round(r, 3))
        D = 2 * r
        ok = any(abs(D - v) < 0.02 for v in dia) or any(abs(r - v) < 0.02 for v in rad) or \
            any(abs(D - v) < 0.02 for v in plain)                  # 槽宽（键槽圆头 = 槽宽）
        if not ok and mth:
            from conv import minor_dia
            ok = any(abs(D - minor_dia(m)) < 0.4 or abs(D - m) < 0.02 for m in mth)
        if not ok:
            issues.append((f"Φ{D:g}（R{r:g}）的圆柱面在图上没有直径/半径尺寸", None, None))
    # ---------- 虚线多：提示剖视
    for aff, box in views:
        x0, y0, x1, y1 = box; n = 0
        for e in s._items():
            if e.Layer == "虚线":
                try:
                    mn, mx = e.GetBoundingBox()
                except Exception:
                    continue
                if x0 <= mn[0] and mx[0] <= x1 and y0 <= mn[1] and mx[1] <= y1:
                    n += 1
        if n >= hidden_hint:
            issues.append((f"提示：视图 {tuple(round(v) for v in box)} 有 {n} 段虚线，内部结构是不是该剖开表达", round((x0 + x1) / 2), round((y0 + y1) / 2)))
    if verbose:
        print(f"== 尺寸审查：{len(issues)} 处" + (f"（{skipped} 个尺寸不在给定的正交视图里，跳过）" if skipped else ""))
        for it in issues:
            print("  ", it[0], "" if it[1] is None else f"@({it[1]}, {it[2]})")
    return issues


METHODS = ("audit_dims",)

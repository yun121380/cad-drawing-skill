"""gb_hatch —— 装配图剖面线按国标整理（GB/T 4457.5-2013 剖面区域的表示法、GB/T 4459.7 滚动轴承）（2026-11-10）。

SW 导出的剖视里所有零件都是同角度、同间距的 ANSI31，每个封闭区域一块 HATCH；局部放大图的剖面线
又是 SW_HATCH_n 块里的一堆线段。这里按 SW 同时导出的同名 DXF 算区域，在 AutoCAD 里改：
    s.hatch_material(指垫内一点, "非金属", 0.5)   # 橡胶、塑料、尼龙…换交叉网格；"涂黑" 换 SOLID
    s.narrow_hatches(2.0)                           # 宽 ≤ 2 mm 的剖面（允许涂黑），返回 [(内部一点, 宽度)]
    s.stagger_hatches(details, same=..., axes=...)  # 相邻零件错开，同一零件各视图（含放大图）一致
Sheet 上的这几个方法都转到这里同名的函数（第一个参数是 Sheet）。

国标要点：
- 相邻零件剖面线方向相反，或方向一致而间隔不同；同一零件在各视图中方向、间隔一致；
- 金属 45° 细实线（ANSI31）；非金属（已有规定符号者除外）交叉细实线网格（ANSI37）；
- 剖面区域宽 ≤ 2 mm 允许涂黑，相邻两块涂黑之间留 ≥ 0.7 mm 间隙；
- 实心件（轴、键、销、螺栓、连杆…）纵剖、外购件不画剖面线（Sheet.unhatch）；滚动轴承内外圈剖面线可以一致，
  滚动体不画。
顺序：先 unhatch、hatch_material，最后 stagger_hatches（它只改 ANSI31，换过图案的块不参与）。"""
import math
import os
import re

import ezdxf
from ezdxf import bbox
from ezdxf import path as zpath
import win32com.client as wc

from acad_common import retry


def _inside(pt, polys):
    """奇偶规则：polys 是一块 HATCH 的全部边界（外圈 + 孔）。"""
    x, y = pt
    c = False
    for poly in polys:
        for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
    return c


class SwDxf:
    """SW 和 DWG 一起导出的 DXF：HATCH 边界、放大图剖面线块、SW 自带的放大图标签都从这里读。"""

    def __init__(self, path):
        self.doc = ezdxf.readfile(path)
        self.msp = self.doc.modelspace()
        self.hatches = [(bbox.extents([h]), h) for h in self.msp.query("HATCH")]

    def _block_items(self, prefix):
        for ins in self.msp.query("INSERT"):
            if ins.dxf.name.startswith(prefix):
                ox, oy = ins.dxf.insert.x, ins.dxf.insert.y
                for e in self.doc.blocks.get(ins.dxf.name):
                    yield ox, oy, e

    def hatch_region(self, p):
        """包含图纸点 p 的最小那块 HATCH（和 Sheet.unhatch 同一挑法）的边界多边形；没有返回 None。"""
        c = [(b.size.x * b.size.y, h) for b, h in self.hatches
             if b.has_data and b.extmin.x <= p[0] <= b.extmax.x and b.extmin.y <= p[1] <= b.extmax.y]
        if not c:
            print("gb_hatch: 没找到包含", p, "的剖面线")
            return None
        h = min(c, key=lambda t: t[0])[1]
        return [[(v.x, v.y) for v in pth.flattening(0.02)] for pth in zpath.from_hatch(h)]

    def detail_hatch_lines(self, regions, c_parent, k, c_det, r_det):
        """放大图（图纸上圆心 c_det、半径 r_det 的放大圆）的剖面线段里，中点换回父视图后落在 regions
        任一块里的。c_parent 是放大中心在父视图里的图纸坐标，k 是放大图对父视图的比例。
        放大图 = 父视图绕圆心放大 k 倍，所以拿父视图里同一零件那块 HATCH 的边界去挑放大图里的线段
        （放大图里实心件的剖面线也这样挑出来用 delete 删；Sheet.unhatch 只认 HATCH）。"""
        regions = [r for r in regions if r]
        out = []
        for ox, oy, e in self._block_items("SW_HATCH"):
            if e.dxftype() != "LINE":
                continue
            a = (ox + e.dxf.start.x, oy + e.dxf.start.y)
            b = (ox + e.dxf.end.x, oy + e.dxf.end.y)
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if (m[0] - c_det[0]) ** 2 + (m[1] - c_det[1]) ** 2 > r_det ** 2:
                continue
            q = (c_parent[0] + (m[0] - c_det[0]) / k, c_parent[1] + (m[1] - c_det[1]) / k)
            if any(_inside(q, r) for r in regions):
                out.append((a, b))
        return out

    def label_items(self, texts=r"I{1,3}|IV|V|1 : 1"):
        """SW 自带放大图标签的文字插入点和线段：SW_NOTE 块里的全部，加上模型空间里内容是罗马数字的 MTEXT。
        SW 把它们放得离视图很远，用 delete 删掉后用 Sheet.view_label 重标。"""
        pts, segs = [], []
        for ox, oy, e in self._block_items("SW_NOTE"):
            if e.dxftype() == "MTEXT":
                pts.append((ox + e.dxf.insert.x, oy + e.dxf.insert.y))
            elif e.dxftype() == "LINE":
                segs.append(((ox + e.dxf.start.x, oy + e.dxf.start.y), (ox + e.dxf.end.x, oy + e.dxf.end.y)))
        for e in self.msp.query("MTEXT"):
            if re.fullmatch(texts, e.plain_text().strip()):
                pts.append((e.dxf.insert.x, e.dxf.insert.y))
        return pts, segs


def sheet_dxf(s):
    """Sheet 源 DWG 同名的 DXF（sw_views 导出 DWG 时一起写的）。"""
    return SwDxf(os.path.splitext(s.src)[0] + ".DXF")


def delete(s, pts=(), segs=(), tol=0.02):
    """在 Sheet 里扫一遍：插入点落在 pts 上的文字、两端点和 segs 里某条重合的直线都删掉。返回 (文字数, 直线数)。"""
    def near(p, q):
        return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol

    nt = nl = 0
    for e in s._items():
        t = retry(lambda: e.ObjectName)
        if t in ("AcDbMText", "AcDbText") and pts:
            p = retry(lambda: e.InsertionPoint)
            if any(near(p, q) for q in pts):
                retry(lambda: e.Delete()); nt += 1
        elif t == "AcDbLine" and segs:
            a, b = retry(lambda: e.StartPoint), retry(lambda: e.EndPoint)
            if any((near(a, u) and near(b, v)) or (near(a, v) and near(b, u)) for u, v in segs):
                retry(lambda: e.Delete()); nl += 1
    return nt, nl


STYLES = [(0, 1.0), (90, 1.0), (0, 0.55), (90, 0.55), (0, 1.6), (90, 1.6)]   # (相对 SW 原样转过的角度°, 间距倍数)


def _near_boxes(a, b, tol):
    return (b.bounds[0] - tol <= a.bounds[2] and a.bounds[0] - tol <= b.bounds[2]
            and b.bounds[1] - tol <= a.bounds[3] and a.bounds[1] - tol <= b.bounds[3])


def _mirror(g, ax):
    from shapely import affinity
    return affinity.scale(g, -1, 1, origin=(ax[1], 0)) if ax[0] == "x" else affinity.scale(g, 1, -1, origin=(0, ax[1]))


def _mirror_pairs(regs, gap, eps=0.3):
    """互为镜像、又不相邻（间距 > gap）的两块剖面区域（回转零件剖开后轴线两侧的两块、关于中心线对称的管壁）。
    SW 每个封闭区域导成一块 HATCH，同一零件的这几块剖面线要一致。镜像轴只试竖直和水平，位置不限：
    两个不相邻的一样的块（轴承内外圈简化成同样的矩形、上下两个同型号轴承）并成一组也没关系。"""
    pairs = []
    for i, a in enumerate(regs):
        ax0, ay0, ax1, ay1 = a.bounds
        for j in range(i + 1, len(regs)):
            b = regs[j]
            if abs(a.area - b.area) > 0.03 * max(a.area, b.area):
                continue
            bx0, by0, bx1, by1 = b.bounds
            tries = []
            if abs((ax1 - ax0) - (bx1 - bx0)) < eps and abs(ay0 - by0) < eps and abs(ay1 - by1) < eps:
                tries.append(("x", (ax0 + bx1) / 2))
            if abs((ay1 - ay0) - (by1 - by0)) < eps and abs(ax0 - bx0) < eps and abs(ax1 - bx1) < eps:
                tries.append(("y", (ay0 + by1) / 2))
            for ax in tries:
                if _mirror(a, ax).symmetric_difference(b).area < 0.03 * a.area and a.distance(b) > gap:
                    pairs.append((i, j))
                    break
    return pairs


def _part_pairs(regs, axes, gap, eps=0.3, reach=40):
    """同一零件被孔分开、两边又不完全对称的两块：一块绕零件的对称轴 axes 翻过去落在另一块里
    （轮毂一侧和管壁连成一块、衬套一侧开键槽、叉板一侧连着杆件）。区域互不重叠，翻过去的位置上有料，
    对称的装配里就是它自己的另一半。axes 要是真正的对称轴（关节轴线）：绕偶然配上对的镜像轴
    翻，小零件会落进别的大零件里；离轴线 reach（图纸 mm）以外的块也不翻，隔着几个关节翻过去落到哪里纯属巧合。"""
    pairs = []
    for i, a in enumerate(regs):
        for j, b in enumerate(regs):
            if i == j:
                continue
            bx0, by0, bx1, by1 = b.bounds
            for ax in axes:
                lo, hi = (a.bounds[0], a.bounds[2]) if ax[0] == "x" else (a.bounds[1], a.bounds[3])
                if min(abs(lo - ax[1]), abs(hi - ax[1])) > reach:
                    continue
                m = _mirror(a, ax)
                mx0, my0, mx1, my1 = m.bounds
                if (bx0 - eps <= mx0 and mx1 <= bx1 + eps and by0 - eps <= my0 and my1 <= by1 + eps
                        and m.difference(b).area < 0.03 * a.area and a.distance(b) > gap):
                    pairs.append((i, j))
                    break
    return pairs


def plan_styles(regs, tol=1.0, same=(), axes=()):
    """每块剖面区域的样式（STYLES 下标）。同一零件的几块并成一组：互为镜像的、一块绕对称轴 axes（[("x", 竖直轴的 x)
    或 ("y", 水平轴的 y)]）翻过去落在另一块里的，加上 same 里指定的（下标列表，如轴承内外圈）。区域间距 ≤ tol（图纸 mm）的两组算相邻：留 1~2 mm
    间隙的两个零件在图上也像贴着。邻居多的组先定，取邻居都没用的第一种，所以多数零件仍是 SW 原来的 45°。"""
    root = list(range(len(regs)))

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i
    pairs = _mirror_pairs(regs, tol) + _part_pairs(regs, axes, tol)
    for i, j in pairs + [(g[0], k) for g in same if g for k in g[1:]]:
        root[find(i)] = find(j)
    adj = {}
    for i, a in enumerate(regs):
        for j in range(i + 1, len(regs)):
            b = regs[j]
            if _near_boxes(a, b, tol) and a.distance(b) <= tol and find(i) != find(j):
                adj.setdefault(find(i), set()).add(find(j))
                adj.setdefault(find(j), set()).add(find(i))
    style = {}
    for g in sorted({find(i) for i in range(len(regs))}, key=lambda g: -len(adj.get(g, ()))):
        used = {style[h] for h in adj.get(g, ()) if h in style}
        style[g] = next(k for k in range(len(STYLES)) if k not in used)
    return [style[find(i)] for i in range(len(regs))]


def _polys(reg):
    """shapely 区域 → detail_hatch_lines 要的边界点列（外圈 + 孔，奇偶规则）。"""
    out = []
    for g in getattr(reg, "geoms", [reg]):
        if g.geom_type == "Polygon":
            out.append(list(g.exterior.coords))
            out += [list(r.coords) for r in g.interiors]
    return out


def _hatch_lines(area, ang, sp, origin):
    """area（shapely 区域）里方向角 ang、间距 sp、过 origin 的一族平行线段。"""
    from shapely.geometry import LineString
    if area.is_empty:
        return []
    ux, uy = math.cos(ang), math.sin(ang)
    nx, ny = -uy, ux
    x0, y0, x1, y1 = area.bounds
    proj = [x * nx + y * ny for x in (x0, x1) for y in (y0, y1)]
    c0 = origin[0] * nx + origin[1] * ny
    cx, cy, R = (x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0)
    out = []
    for n in range(math.ceil((min(proj) - c0) / sp), math.floor((max(proj) - c0) / sp) + 1):
        t = c0 + n * sp - (cx * nx + cy * ny)
        px, py = cx + t * nx, cy + t * ny
        g = LineString([(px - R * ux, py - R * uy), (px + R * ux, py + R * uy)]).intersection(area)
        for piece in getattr(g, "geoms", [g]):
            if piece.geom_type == "LineString" and piece.length > 0.05:
                out.append((tuple(piece.coords[0]), tuple(piece.coords[-1])))
    return out


def stagger_hatches(s, sw=None, details=(), tol=1.0, same=(), axes=()):
    """装配图相邻零件的剖面线错开（GB/T 4457.5：相邻零件方向相反或间距不同，同一零件各处一致）。
    样式按 plan_styles 定，改 HATCH 的角度和比例。details 是放大图 [(c_parent, k, c_det, r_det)]（参数同
    SwDxf.detail_hatch_lines；sw 是对应的 SwDxf，省略时读 Sheet 源 DWG 同名的 DXF）：换了样式的零件，
    放大图里 SW 画的线段删掉，按同一样式重画，和父视图一致。same 是几组图纸点，每组点所在的剖面当
    同一零件（镜像认不出来的，如轴承内外圈、被螺孔切成内外两块的端盖、在两个视图里剖到不同部位的同一零件）；
    axes 是图上的对称轴（见 plan_styles）。要在 unhatch、hatch_material 之后调。
    返回 (各样式的块数, 放大图删掉的线段数, 重画的线段数)。"""
    from collections import Counter
    from shapely import affinity
    from shapely.geometry import Point
    hs = []
    for e in s._items():
        if retry(lambda: e.ObjectName) != "AcDbHatch" or retry(lambda: e.PatternName) != "ANSI31":
            continue
        try:
            reg = s._dxf_hatch_region(e)
        except RuntimeError as err:
            print("stagger_hatches 跳过：", err)
            continue
        if reg is not None and not reg.is_empty:
            hs.append((e, reg))
    regs = [reg for _, reg in hs]
    groups = []
    for pts in same:
        g = []
        for p in pts:
            c = [(r.area, i) for i, r in enumerate(regs) if r.distance(Point(p)) < 1e-6]
            if c:
                g.append(min(c)[1])
            else:
                print("stagger_hatches：same 的点不在剖面里", p)
        groups.append(g)
    style = plan_styles(regs, tol, groups, axes)
    for (e, _), st in zip(hs, style):
        if st:
            da, ks = STYLES[st]
            a0, s0 = retry(lambda: e.PatternAngle), retry(lambda: e.PatternScale)

            def apply(e=e, a=a0 + math.radians(da), sc=s0 * ks):
                e.PatternAngle = a
                e.PatternScale = sc
                e.Evaluate()
            retry(apply)
    if details and sw is None:
        sw = sheet_dxf(s)
    old, new = [], []
    for c_par, k, c_det, r_det in details:
        disk = Point(c_det).buffer(r_det, 128)
        for (_, reg), st in zip(hs, style):
            if not st or reg.distance(Point(c_par)) > r_det / k:
                continue
            segs = sw.detail_hatch_lines([_polys(reg)], c_par, k, c_det, r_det)
            if not segs:
                continue
            (ax, ay), (bx, by) = segs[0]
            ang = math.atan2(by - ay, bx - ax)
            nx, ny = -math.sin(ang), math.cos(ang)
            offs = sorted({round((a[0] + b[0]) / 2 * nx + (a[1] + b[1]) / 2 * ny, 2) for a, b in segs})
            gaps = [q - p for p, q in zip(offs, offs[1:]) if q - p > 0.1]
            da, ks = STYLES[st]
            area = affinity.translate(affinity.scale(reg, k, k, origin=c_par),
                                      c_det[0] - c_par[0], c_det[1] - c_par[1]).intersection(disk)
            old += segs
            new += _hatch_lines(area, ang + math.radians(da), (min(gaps) if gaps else 3.175) * ks, c_det)
    if old:
        delete(s, segs=old)
        for a, b in new:
            s.line(a, b, "剖面线")
    return dict(Counter(STYLES[v] for v in style)), len(old), len(new)


# ---------------------------------------------------------------- 按材料换剖面符号
MATERIALS = {"金属": "ANSI31", "非金属": "ANSI37", "涂黑": "SOLID"}


def _hatch_at(s, inside):
    """包围盒含 inside 的 HATCH 里面积最小的那块（挑法同 Sheet.unhatch）；没有返回 None。"""
    cands = []
    for e in s._items():
        if retry(lambda: e.ObjectName) == "AcDbHatch":
            mn, mx = retry(lambda: e.GetBoundingBox())
            if mn[0] <= inside[0] <= mx[0] and mn[1] <= inside[1] <= mx[1]:
                cands.append(((mx[0] - mn[0]) * (mx[1] - mn[1]), e))
    return min(cands, key=lambda c: c[0])[1] if cands else None


def _rebuild(s, h, name, scale):
    """SetPattern 不认时：按 DXF 里的边界重建一块图案为 name 的剖面线（做法同 Sheet.clip_hatch），原对象删掉。"""
    from shapely.geometry import Polygon
    reg = s._dxf_hatch_region(h)
    polys = [g for g in getattr(reg, "geoms", [reg]) if isinstance(g, Polygon) and g.area > 0.001]
    lay = h.Layer
    nh = s.ms.AddHatch(1, name, False)
    tmp = []

    def loop(ring):
        xy = []
        for x, y in list(ring.coords)[:-1]:
            xy += [float(x), float(y)]
        pl = s.ms.AddLightWeightPolyline(wc.VARIANT(0x2005, xy)); pl.Closed = True
        tmp.append(pl)
        return wc.VARIANT(0x2009, [pl])
    for i, g in enumerate(polys):
        (nh.AppendOuterLoop if i == 0 else nh.AppendInnerLoop)(loop(g.exterior))
        for r in g.interiors:
            nh.AppendInnerLoop(loop(r))
    if name != "SOLID":
        nh.PatternScale = scale
    nh.Layer = lay
    nh.Evaluate()
    for pl in tmp:
        pl.Delete()
    h.Delete()
    return nh


def hatch_material(s, inside, material="非金属", scale=1.0):
    """把包含 inside 点的那块剖面线换成 material 的剖面符号：MATERIALS 里的名字，或直接给 AutoCAD 图案名。
    间距 = 原来的 × scale（窄条里网格太疏看不出是网格，可以给 0.5）。返回换好的 HATCH，没找到返回 None。"""
    h = _hatch_at(s, inside)
    if h is None:
        print("hatch_material 没找到包含", inside, "的剖面线")
        return None
    name = MATERIALS.get(material, material)
    sc = retry(lambda: h.PatternScale) * scale

    def apply():
        h.SetPattern(1, name)                   # 1 = acHatchPatternTypePreDefined
        if name != "SOLID":
            h.PatternAngle = 0.0
            h.PatternScale = sc
        h.Evaluate()
    try:
        retry(apply)
    except Exception as err:                    # noqa: BLE001  COM 报错类型不固定
        print("hatch_material: SetPattern 失败，按边界重建：", err)
        return _rebuild(s, h, name, sc)
    return h


def narrow_hatches(s, w=2.0):
    """宽度不超过 w（图纸 mm）的 ANSI31 剖面：向内缩 w/2 就没了的。返回 [(区域内一点, 估算宽度 2×面积/周长)]。
    国标只是“允许”涂黑，斜线还看得清就不必改；要涂黑的再 hatch_material(s, 点, "涂黑")。"""
    out = []
    for e in s._items():
        if retry(lambda: e.ObjectName) != "AcDbHatch" or retry(lambda: e.PatternName) != "ANSI31":
            continue
        try:
            reg = s._dxf_hatch_region(e)
        except RuntimeError:
            continue
        if reg is None or reg.area < 0.05 or not reg.buffer(-w / 2).is_empty:     # 不到 0.05 mm² 的碎片图上看不见
            continue
        p = reg.representative_point()
        out.append(((round(p.x, 2), round(p.y, 2)), round(2 * reg.area / max(reg.length, 1e-9), 2)))
    return out

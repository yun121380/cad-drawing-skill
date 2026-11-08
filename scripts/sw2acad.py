"""sw2acad: SolidWorks 导出的工程图 DWG -> AutoCAD 里纯 COM 整理成国标图（不碰键盘鼠标）。

分工：SolidWorks 只负责投影（视图、剖视、剖面线、中心符号，用 gb_a3 模板，不自动标尺寸）；
这里负责：图线分国标图层、字体换 gbenor/gbcbig、补中心线、标尺寸、填标题栏、写技术要求、存 DWG、出 PDF。

用法见 ../examples/hub_flange.py：
    with Sheet(src_dwg, out_dwg, views=[(x0,y0,x1,y1), ...]) as s:
        s.dimlin(p1, p2, loc, ang=90, txt="%%C60"); s.dimdia(...); s.rough(...); s.datum(...); s.gtol(...)
        s.title({...}); s.notes([...])
坐标都是图纸 mm（1:1 出图时等于零件尺寸），用 sw_views.dump_dxf 从 SW 导出的 DXF 里读。
"""
import sys, time, os, math
import pythoncom
import win32com.client as wc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acad_common import retry, PDF_MEDIA, PDF_PC3, SHEETS, setup_doc
import com_filter
import json as _json
try:      # 标题栏默认值（学校、班级、设计人），换环境只改 config.json
    CONFIG = _json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
except Exception:
    CONFIG = {}
com_filter.install()      # AutoCAD 忙时所有 COM 调用自动等待重试，不再抛"被呼叫方拒绝接收呼叫"

ACAD_EXE = os.environ.get("ACAD_EXE", r"C:\Program Files\Autodesk\AutoCAD 2024\acad.exe")


def set_pdf_device(lay):
    """先刷新设备列表再设 NoView pc3（新生成的 pc3 不刷新会报 Invalid input，实测）；还不行就退回 DWG To PDF.pc3。"""
    lay.RefreshPlotDeviceInfo()
    try:
        lay.ConfigName = PDF_PC3
    except Exception:
        lay.ConfigName = "DWG To PDF.pc3"
    lay.RefreshPlotDeviceInfo()


def mapper(aff):
    """sw_views.view_affine 的结果 → 函数 M(x, y, z)：模型坐标（mm）→ 图纸坐标。"""
    o, ex, ey, ez = aff["o"], aff["ex"], aff["ey"], aff["ez"]
    return lambda x, y, z: (o[0] + x * ex[0] + y * ey[0] + z * ez[0], o[1] + x * ex[1] + y * ey[1] + z * ez[1])


def P(x, y):
    return wc.VARIANT(0x2005, [float(x), float(y), 0.0])


def live_acad():
    """拿到一个能响应的 AutoCAD；ROT 里残留的死对象会报 RPC 不可用，这时重新启动。"""
    try:
        a = wc.GetActiveObject("AutoCAD.Application"); a.Documents.Count
        return a
    except Exception:
        os.startfile(ACAD_EXE)
        for _ in range(60):
            time.sleep(5)
            try:
                a = wc.GetActiveObject("AutoCAD.Application"); a.ActiveDocument.Name
                # 刚能响应时还在加载插件/菜单；这时打开文档、改 SDI 曾让 AutoCAD 访问冲突崩溃（2026-11-07）
                for _ in range(60):
                    if a.GetAcadState().IsQuiescent:
                        break
                    time.sleep(1)
                time.sleep(10)
                return a
            except Exception:
                pass
        raise RuntimeError("AutoCAD 启动超时")


class Sheet:
    def __init__(self, src, out, views, sheet="A3", view_scale=1, own_frame=True):
        """坐标一律是图纸 mm。view_scale=2 表示视图按 1:2 画，尺寸自动 ×2 显示实际值（LinearScaleFactor）。
        own_frame=True：删掉 SW 模板自带的图框/标题栏/分区格，改用 frame()+title_block() 自己画（推荐）。"""
        self.src, self.out, self.views, self.sheet, self.S = src, out, views, sheet, 1
        self.k = view_scale
        self.own_frame = own_frame
        self.pdf = os.path.splitext(out)[0] + time.strftime("_%H%M%S") + ".pdf"  # WPS 会锁住旧 PDF
        self._dims = []          # dimlin 记下 (对象, p1, p2, loc, ang)，check() 查“尺寸线太挤”用

    # ------------------------------------------------------------------ 打开 + 分层
    def _find_doc(self, path):
        a = self.a
        for i in range(retry(lambda: a.Documents.Count)):
            d = retry(lambda i=i: a.Documents.Item(i))
            if retry(lambda: d.FullName).lower() == path.lower():
                return d
        return None

    def _once(self, fn, check, what, timeout=60):
        """只调一次（Open/Add 绝不能重试：调用其实成功了却抛异常时，重试会把同一文件反复打开，
        2026-11-07 这样把 AutoCAD 弄成访问冲突崩溃），然后轮询 check() 确认结果。"""
        try:
            fn()
        except Exception as ex:
            print(f"{what} 返回异常（多半其实已成功，下面核对）:", ex)
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                r = check()
                if r:
                    return r
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError(f"{what} 失败")

    def __enter__(self):
        a = self.a = live_acad()
        # 不要改 SDI！实测（2026-11-07，两次复现）：AutoCAD 刚启动时 SetVariable("SDI", 0) 后再 Documents.Open，
        # 立刻 FATAL ERROR 访问冲突崩溃；不改 SDI 直接 Open 正常。
        # SDI=1 时 Open 会替换当前文档 —— 正好省掉"关旧文档"这步；同名文件已开着时 Open 也只是重新载入。
        sdi = retry(lambda: a.ActiveDocument.GetVariable("SDI"))
        if sdi == 0:   # 多文档模式下才需要先关掉同名的旧文档（先垫一个空白文档，关最后一个会退出）
            olds = [p for p in (self.src, self.out) if self._find_doc(p)]
            if olds:
                n0 = retry(lambda: a.Documents.Count)
                self._once(lambda: a.Documents.Add("acadiso.dwt"),
                           lambda: retry(lambda: a.Documents.Count) > n0, "新建空白文档")
                for p in olds:
                    d = self._find_doc(p)
                    if d: self._once(lambda: d.Close(False), lambda: not self._find_doc(p), "关闭 " + p)
        doc = self._once(lambda: a.Documents.Open(self.src), lambda: self._find_doc(self.src), "打开 " + self.src)
        retry(lambda: doc.Activate()); self.doc = doc
        self._idle()
        retry(lambda: setup_doc(doc, a, self.S))                         # 国标图层 / HZ 字体 / GB 标注样式
        self.ms = retry(lambda: doc.ModelSpace)
        self._idle()
        self._relayer()
        for i in range(doc.TextStyles.Count):    # SW 的长仿宋 TTF 本机没有
            st = doc.TextStyles.Item(i)
            try:
                st.fontFile = "gbenor.shx"; st.BigFontFile = "gbcbig.shx"; st.Width = 1
            except Exception as ex:
                print("style", st.Name, ex)
        return self

    def _idle(self, timeout=60):
        """等 AutoCAD 刚打开文档后的后台处理（重生成、字体加载）结束，否则逐个对象调 COM 会被拒。"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.a.GetAcadState().IsQuiescent:
                    return
            except Exception:
                pass
            time.sleep(0.5)

    def _items(self):
        n = retry(lambda: self.ms.Count)                 # AutoCAD 忙时会“拒绝接收呼叫”，逐个重试
        return [retry(lambda i=i: self.ms.Item(i)) for i in range(n)]

    def _in_views(self, e, margin=0):
        mn, mx = retry(lambda: e.GetBoundingBox())
        m = margin
        return any(x0 - m <= mn[0] and mx[0] <= x1 + m and y0 - m <= mn[1] and mx[1] <= y1 + m
                   for x0, y0, x1, y1 in self.views)

    def _relayer(self):
        moved = {}
        queue = self._items()
        while queue:
            e = queue.pop()
            n = e.ObjectName
            if n == "AcDbBlockReference" and self._in_views(e):
                kids = list(e.Explode())
                if "CENTERMARK" in e.Name.upper():          # SW 中心符号块 -> 炸开放中心线层
                    for x in kids:
                        x.Layer = "中心线"; x.Linetype = "ByLayer"; x.Lineweight = -1
                        moved["中心线"] = moved.get("中心线", 0) + 1
                else:                                       # 其他块（如局部放大图的 SW_HATCH_n）炸开后按类型分层
                    queue.extend(kids)
                e.Delete(); continue
            if not self._in_views(e):
                if self.own_frame and not (self._is_view_label(e) and self._in_views(e, margin=30)):
                    e.Delete(); moved["删除模板图框"] = moved.get("删除模板图框", 0) + 1
                continue
            lt = e.Linetype.upper()
            if n == "AcDbHatch":
                lay = "剖面线"
            elif n == "AcDbMText":
                lay = "文字"; e.StyleName = "HZ"
            elif lt.startswith("CENTER") or lt.startswith("PHANTOM"):   # SW 自动中心线
                lay = "中心线"
            elif lt.startswith("HIDDEN") or lt.startswith("DASH"):
                # SW 的剖切线两端短画也是 HIDDEN；真正的不可见轮廓线是细的
                lay = "粗实线" if self._is_cut_stroke(e) else "虚线"
            elif n in ("AcDbLine", "AcDbCircle", "AcDbArc", "AcDbSpline", "AcDbPolyline", "AcDbEllipse"):
                lay = "粗实线" if e.Lineweight >= 25 else "细实线"
            else:
                lay = "细实线"
            e.Layer = lay; e.Linetype = "ByLayer"; e.Lineweight = -1
            moved[lay] = moved.get(lay, 0) + 1
        print("分层:", moved)

    @staticmethod
    def _is_view_label(e):
        """SW 视图标注（"A-A"、剖切符号旁的 "A"、"B 2:1"）—— 不在视图框里也要保留。"""
        if e.ObjectName not in ("AcDbMText", "AcDbText"):
            return False
        import re
        s = re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", e.TextString).strip()
        return bool(re.fullmatch(r"[A-Z](\s*[-—]\s*[A-Z])?(\s*\d+\s*:\s*\d+)?", s))

    def _is_cut_stroke(self, e):
        """SW 把剖切符号的两段短画也导成 HIDDEN 线（约 6.3 mm）。按国标它是粗实线短画。
        判据：直线且长度 < 8 mm。短的真虚线会被误判 —— 出图后检查，必要时手动改层。"""
        return e.ObjectName == "AcDbLine" and e.Length < 8

    # ------------------------------------------------------------------ 绘制
    def layer(self, name):
        self.doc.ActiveLayer = self.doc.Layers.Item(name)

    def line(self, p1, p2, layer="中心线"):
        self.layer(layer); return self.ms.AddLine(P(*p1), P(*p2))

    def circle(self, c, r, layer="中心线"):
        self.layer(layer); return self.ms.AddCircle(P(*c), r)

    def to_center(self, p1, p2, tol=0.05):
        """半剖分界线：把落在直线 p1-p2 上的细实线/中心线段删掉，换成 p1→p2 一整条点画线。
        SW 局部剖矩形压在对称线上的那条边导出为细实线，国标里半剖的分界是点画线。返回删了几段。"""
        (ax, ay), (bx, by) = p1, p2
        L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L
        def on(p):
            t = (p[0] - ax) * ux + (p[1] - ay) * uy
            return abs((p[0] - ax) * uy - (p[1] - ay) * ux) < tol and -tol <= t <= L + tol
        hit = [e for e in self._items() if e.ObjectName == "AcDbLine" and e.Layer in ("细实线", "中心线")
               and on(e.StartPoint) and on(e.EndPoint)]
        # SW 把这条边按零件轮廓断成好几段，各段点画线的画/空节奏对不上，看上去像实线；而且穿过孔的地方没有线。
        # 删掉各段，在 p1-p2 之间画一整条点画线（p1/p2 就取到轮廓外 3~5 mm）。
        for e in hit:
            e.Delete()
        self.line(p1, p2, "中心线")
        print("to_center 合并了", len(hit), "段")
        return len(hit)

    def dimlin(self, p1, p2, loc, ang=0, txt="", k=None):
        """线性尺寸。ang=0 水平、90 竖直；txt 覆盖文字（Φ 写 %%C）。k：这一个尺寸的测量比例，
        局部放大图 4:1 里标注时 k=0.25（默认用 Sheet 的 view_scale）。"""
        self.layer("尺寸")
        d = self.ms.AddDimRotated(P(*p1), P(*p2), P(*loc), math.radians(ang))
        d.LinearScaleFactor = self.k if k is None else k
        self._dims.append((d, tuple(p1[:2]), tuple(p2[:2]), tuple(loc[:2]), ang))
        if txt: d.TextOverride = txt
        return d

    def dimdia(self, c, r, ang_deg, leader, txt=""):
        self.layer("尺寸"); a = math.radians(ang_deg)
        d = self.ms.AddDimDiametric(P(c[0] + r * math.cos(a), c[1] + r * math.sin(a)),
                                    P(c[0] - r * math.cos(a), c[1] - r * math.sin(a)), leader)
        d.LinearScaleFactor = self.k
        if txt: d.TextOverride = txt
        return d

    def dimrad(self, c, r, ang_deg, leader, txt=""):
        self.layer("尺寸"); a = math.radians(ang_deg)
        d = self.ms.AddDimRadial(P(*c), P(c[0] + r * math.cos(a), c[1] + r * math.sin(a)), leader)
        d.LinearScaleFactor = self.k
        if txt: d.TextOverride = txt
        return d

    def rough(self, tip, ra, ang=0, h=3.5, mode="remove"):
        """GB/T 131 表面粗糙度符号：tip 为尖端（落在表面上），ang=0 时开口朝上，按逆时针转 ang 度。
        mode："remove" 去除材料（短边封口成三角，加工面用这个）、"keep" 不去除材料（V 里内切圆，铸造毛坯面）、
        "any" 基本符号。ra 为 None 时只画符号（如"其余"后面的那个）。文字只能从下方或右方读：竖直面用 ang=90。"""
        self.layer("细实线")
        H1, H2 = 1.4 * h, 3.0 * h
        t30 = math.tan(math.radians(30))
        loc = [(-H1 * t30, H1), (0, 0), (H2 * t30, H2), (H2 * t30 + 3.2 * h, H2)]
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        T = lambda x, y: (tip[0] + x * c - y * s, tip[1] + x * s + y * c)
        g = [T(x, y) for x, y in loc]
        self.ms.AddLine(P(*g[0]), P(*g[1])); self.ms.AddLine(P(*g[1]), P(*g[2]))
        if ra is not None:
            self.ms.AddLine(P(*g[2]), P(*g[3]))
        if mode == "remove":
            self.ms.AddLine(P(*g[0]), P(*T(H1 * t30, H1)))
        elif mode == "keep":
            rr = (2 * H1 * t30) / (2 * math.sqrt(3))              # 等边三角形（边长 2·H1·tan30）的内切圆半径
            self.ms.AddCircle(P(*T(0, H1 - rr)), rr)
        if ra is None:
            return
        tx, ty = H2 * t30 + 0.6, H2 - h - 0.8
        self.layer("文字")
        t = self.ms.AddText(f"Ra {ra}", P(*T(tx, ty)), h)
        t.StyleName = "HZ"; t.Rotation = math.radians(ang)

    def erase_in(self, box, keep_layers=("中心线",)):
        """删掉包围盒完全落在 box=(x0,y0,x1,y1) 内的对象（中心线层除外）。用来去掉 SW 的剖切符号（剖切面是对称面、
        按投影关系配置时国标可省略标注）。返回删了几个。"""
        x0, y0, x1, y1 = box; n = 0
        for e in self._items():
            try:
                if e.Layer in keep_layers:
                    continue
                mn, mx = retry(lambda: e.GetBoundingBox())
            except Exception:
                continue
            if x0 <= mn[0] and mx[0] <= x1 and y0 <= mn[1] and mx[1] <= y1:
                e.Delete(); n += 1
        return n

    def note(self, pts, text, h=3.5, w=None):
        """带箭头的指引线 + 水平线上的文字（倒角 C1.5、孔的旁注等），文字始终水平。pts=[箭头尖, 折点...]，
        文字写在最后一点之后的水平线上。用 MText，可以写 {\\Fgdt;v}（沉孔/锪平 ⌴）、{\\Fgdt;x}（深度 ↧）、
        {\\Fgdt;w}（埋头孔 ⌵）；w 是水平线长度，默认按字数估。"""
        import re
        self.layer("细实线")
        end = pts[-1]; right = end[0] >= pts[-2][0]
        plain = re.sub(r"\{\\F[^;]*;(.)\}", r"\1", text).replace("%%C", "C")
        w = w or len(plain) * h * 0.72 + 2
        shelf = (end[0] + (w if right else -w), end[1])
        flat = [float(v) for p in list(pts) + [shelf] for v in (p[0], p[1], 0)]
        self.ms.AddLeader(wc.VARIANT(0x2005, flat), None, 2)
        x = min(end[0], shelf[0]) + 0.8
        self.layer("文字")
        t = self.ms.AddMText(P(x, end[1] + 0.8), w, text)
        t.StyleName = "HZ"; t.Height = h; t.AttachmentPoint = 7      # 左下角对齐
        t.InsertionPoint = P(x, end[1] + 0.8)
        return t

    def datum(self, foot, letter, direction=(1, 0), gap=8, h=3.5):
        """基准符号：实心三角形贴在 foot（要素轮廓/延长线上），沿 direction 引出到方框。"""
        dx, dy = direction; nx, ny = -dy, dx; a = 2.0
        self.layer("细实线")
        tri = [foot[0] + nx * a, foot[1] + ny * a, 0, foot[0] - nx * a, foot[1] - ny * a, 0,
               foot[0] + dx * a * 1.7, foot[1] + dy * a * 1.7, 0]
        pl = self.ms.AddPolyline(wc.VARIANT(0x2005, [float(v) for v in tri])); pl.Closed = True
        hp = self.ms.AddHatch(0, "SOLID", True); hp.AppendOuterLoop(wc.VARIANT(0x2009, [pl])); hp.Evaluate()
        end = (foot[0] + dx * gap, foot[1] + dy * gap)
        self.ms.AddLine(P(foot[0] + dx * a * 1.7, foot[1] + dy * a * 1.7), P(*end))
        b = 2 * h; cx, cy = end[0] + dx * b / 2, end[1] + dy * b / 2
        sq = [cx - b/2, cy - b/2, 0, cx + b/2, cy - b/2, 0, cx + b/2, cy + b/2, 0, cx - b/2, cy + b/2, 0]
        q = self.ms.AddPolyline(wc.VARIANT(0x2005, [float(v) for v in sq])); q.Closed = True
        self.layer("文字")
        t = self.ms.AddText(letter, P(cx, cy), h); t.StyleName = "HZ"
        t.Alignment = 10; t.TextAlignmentPoint = P(cx, cy)   # acAlignmentMiddleCenter

    def gtol(self, sym, value, datum, frame_at, arrow_pts):
        """形位公差框格。sym 是 gdt 字体代号：b 垂直度 f 平行度 c 平面度 r 同轴度 j 位置度 t 全跳动 h 圆跳动。
        frame_at 为框格左端中点；arrow_pts 为从框格到被测要素的引线折点（最后一点是箭头）。"""
        self.layer("尺寸")
        txt = "{\\Fgdt;%s}%%%%v%s" % (sym, value) + ("%%%%v%s" % datum if datum else "")
        tol = self.ms.AddTolerance(txt, P(*frame_at), P(1, 0))
        mn, mx = retry(lambda: tol.GetBoundingBox())             # 引线从框格右端中点出发，保证连上
        if arrow_pts[0][0] < frame_at[0]:                         # 被测要素在框格左边：从左端出发
            arrow_pts = [(mn[0], frame_at[1])] + list(arrow_pts)
        else:
            arrow_pts = [(mx[0], frame_at[1])] + list(arrow_pts)
        pts = [float(v) for p in arrow_pts[::-1] for v in (p[0], p[1], 0)]
        self.ms.AddLeader(wc.VARIANT(0x2005, pts), None, 2)   # AcLeaderType: 2 = acLineWithArrow（1 是样条，会画成曲线）
        return tol

    def rough_leader(self, on_surface, shelf, ra, h=3.5):
        """指引线式粗糙度：箭头落在表面 on_surface，折到水平基线 shelf，符号立在基线上（用于竖直面/空间不够处）。"""
        H2 = 3.0 * h; w = H2 * math.tan(math.radians(30)) + 3.2 * h
        a = 1.4 * h * math.tan(math.radians(30)) + 1
        if shelf[0] < on_surface[0]:          # 引线往左下/左上走：水平线向左伸，符号放在左端，引线不穿过符号
            tip = (shelf[0] - w - 1, shelf[1])
            pts = [float(v) for p in (on_surface, shelf, (tip[0] - a, shelf[1])) for v in (p[0], p[1], 0)]
            self.layer("细实线")
            self.ms.AddLeader(wc.VARIANT(0x2005, pts), None, 2)
            self.rough(tip, ra)
            return
        tip = (shelf[0] + a, shelf[1])
        pts = [float(v) for p in (on_surface, shelf, (tip[0] + w, shelf[1])) for v in (p[0], p[1], 0)]
        self.layer("细实线")
        self.ms.AddLeader(wc.VARIANT(0x2005, pts), None, 2)
        self.rough(tip, ra)

    # ------------------------------------------------------------------ 图框 / 标题栏 / 明细栏 / 序号
    def _text(self, p, h, s, just="MC", layer="文字"):
        self.layer(layer)
        t = self.ms.AddText(s, P(*p), h); t.StyleName = "HZ"
        if just:
            t.Alignment = {"MC": 10, "ML": 9, "MR": 11, "BL": 0}[just]
            t.TextAlignmentPoint = P(*p)
        return t

    def table(self, top_right, widths, rows, row_h=7, h=3.5):
        """通用表格（齿轮参数表等，GB/T 4459.2 放图纸右上角）：top_right 为表格右上角，widths 各列宽，
        rows 每行一个元组（格里写的字，空串留空）。外框粗实线、内格细实线，字居中。返回 (x0, y0, x1, y1)。"""
        x1, y1 = top_right; W = sum(widths); x0 = x1 - W; y0 = y1 - row_h * len(rows)
        self._rect(x0, y0, x1, y1, "粗实线")
        self.layer("细实线")
        for i in range(1, len(rows)):
            self.ms.AddLine(P(x0, y1 - i * row_h), P(x1, y1 - i * row_h))
        xs = [x0]
        for w in widths:
            xs.append(xs[-1] + w)
        for x in xs[1:-1]:
            self.ms.AddLine(P(x, y0), P(x, y1))
        for i, row in enumerate(rows):
            yc = y1 - (i + 0.5) * row_h
            for j, cell in enumerate(row):
                if cell != "":
                    self._text(((xs[j] + xs[j + 1]) / 2, yc), h, str(cell))
        return x0, y0, x1, y1

    def _rect(self, x0, y0, x1, y1, layer):
        self.layer(layer)
        pts = [x0, y0, 0, x1, y0, 0, x1, y1, 0, x0, y1, 0]
        pl = self.ms.AddPolyline(wc.VARIANT(0x2005, [float(v) for v in pts])); pl.Closed = True
        return pl

    def frame(self):
        """国标横放图框（留装订边），返回内框 (x0, y0, x1, y1)。1:1 出图时图纸 mm = 模型 mm。"""
        B, L, a, c = SHEETS[self.sheet]
        self._rect(0, 0, L, B, "细实线")
        self.inner = (a, c, L - c, B - c)
        # SW 模板的分区字母 A~F 在内框外面，又长得像视图标注（单个大写字母），_relayer 会留下它们：这里删掉
        x0, y0, x1, y1 = self.inner
        for e in self._items():
            if e.ObjectName in ("AcDbText", "AcDbMText"):
                p = retry(lambda: e.InsertionPoint)
                if not (x0 < p[0] < x1 and y0 < p[1] < y1):
                    e.Delete()
        self._rect(*self.inner, "粗实线")
        return self.inner

    def title_block_gb(self, name, code, material="", scale="1:1", weight="", company=None,
                       designer=None, date=None, sheets=(1, 1)):
        """GB/T 10609.1 标准标题栏 180×56（几何照抄 SW 的 gb 模板）：左 80 为更改区 + 签字区，中 50 为材料标记/
        阶段标记/重量/比例/共张第张，右 50 为单位名称/图样名称/图样代号。返回左上角（明细栏从这里往上长）。
        company/designer/date 不传时取 scripts/config.json 里的默认值。"""
        cfg = CONFIG
        company = cfg.get("company", "") if company is None else company
        designer = cfg.get("designer", "") if designer is None else designer
        date = (cfg.get("date") or time.strftime("%Y.%m")) if date is None else date
        x1, y0 = self.inner[2], self.inner[1]; X = x1 - 180
        u = lambda x, y: (X + x, y0 + y)
        L = lambda a, b, lay="细实线": (self.layer(lay), self.ms.AddLine(P(*u(*a)), P(*u(*b))))
        self._rect(X, y0, x1, y0 + 56, "粗实线")
        L((80, 0), (80, 56), "粗实线"); L((130, 0), (130, 56), "粗实线")
        for y in (7, 14, 21, 35, 42, 49):
            L((0, y), (80, y))
        L((0, 28), (130, 28), "粗实线")
        for y in (9, 18, 38):
            L((80, y), (180, y))
        for x in (10, 20, 36):                      # 更改区列宽 10/10/16/16/12/16
            L((x, 28), (x, 56))
        for x in (12, 24, 40):                      # 签字区列宽 12/12/16/12/12/16
            L((x, 0), (x, 28))
        for x in (52, 64):
            L((x, 0), (x, 56))
        for x in (86.5, 93, 99.5):                  # 阶段标记 4 格
            L((x, 18), (x, 28))
        L((106, 18), (106, 38)); L((118, 18), (118, 38)); L((106, 0), (106, 9))
        T = lambda x, y, s, h=3.5: s and self._text(u(x, y), h, s)
        for x, s in ((5, "标记"), (15, "处数"), (28, "分区"), (44, "更改文件号"), (58, "签名"), (72, "年、月、日")):
            T(x, 31.5, s, 3.5 if len(s) <= 2 else 2.5)
        for y, a, b in ((24.5, "设计", "标准化"), (17.5, "校核", "工艺"), (10.5, "主管设计", "审核"), (3.5, "", "批准")):
            T(6, y, a, 3.5 if len(a) <= 2 else 2.5); T(46, y, b, 3.5 if len(b) <= 2 else 2.5)
        T(18, 24.5, designer); T(32, 24.5, date, 2.5)
        T(93, 33, "阶段标记", 2.5); T(112, 33, "重量"); T(124, 33, "比例")
        T(112, 23, weight + ("kg" if weight else ""), 2.5); T(124, 23, scale)
        T(93, 4.5, f"共 {sheets[0]} 张"); T(118, 4.5, f"第 {sheets[1]} 张")
        T(105, 47, material, 5)
        T(155, 47, company, 5); T(155, 28, name, 7); T(155, 13.5, code, 5)
        return u(0, 56)

    def transition(self, box, gap=0.8, rmax=5, kinds=("spline", "slant", "arc")):
        """过渡线：铸件圆角处 SW 画成粗实线的那些小线（样条、斜短线、小圆弧）改成细实线，直线两端各缩 gap 不与轮廓相接。
        只处理完全落在 box 内的对象 —— 正面看到的圆角轮廓（真实外形）不要框进来。"""
        x0, y0, x1, y1 = box; n = 0
        for e in self._items():
            if e.Layer != "粗实线":
                continue
            mn, mx = retry(lambda: e.GetBoundingBox())
            if not (x0 <= mn[0] and mx[0] <= x1 and y0 <= mn[1] and mx[1] <= y1):
                continue
            t = e.ObjectName
            if t == "AcDbSpline" and "spline" in kinds:
                e.Layer = "细实线"; n += 1
            elif t == "AcDbArc" and "arc" in kinds and e.Radius <= rmax:
                sweep = (e.EndAngle - e.StartAngle) % (2 * math.pi)
                da = min(gap / e.Radius, sweep * 0.2)      # 小圆弧只有十几度，缩多了会反成大半个圆（实测）
                e.StartAngle = e.StartAngle + da; e.EndAngle = e.EndAngle - da
                e.Layer = "细实线"; n += 1
            elif t == "AcDbLine" and "slant" in kinds:
                s, f = e.StartPoint, e.EndPoint
                dx, dy = f[0] - s[0], f[1] - s[1]; Lg = math.hypot(dx, dy)
                if abs(dx) > 0.05 and abs(dy) > 0.05 and Lg > 2 * gap:
                    ux, uy = dx / Lg * gap, dy / Lg * gap
                    e.StartPoint = P(s[0] + ux, s[1] + uy); e.EndPoint = P(f[0] - ux, f[1] - uy)
                    e.Layer = "细实线"; n += 1
        print("过渡线", box, n, "条")
        return n

    def thread_hole(self, x_axis, y_top, depth, d, d1, side="both", down=True):
        """内螺纹（剖开的非圆视图，孔轴线竖直）：大径 d 画细实线、螺纹终止线画粗实线；剖面线本来就画到小径 d1（底孔）。
        side：both / right / left（半剖里只画剖开那一半）。down=True 表示螺孔从 y_top 往下。"""
        y_end = y_top - depth if down else y_top + depth
        xs = {"both": (-1, 1), "right": (1,), "left": (-1,)}[side]
        for sgn in xs:
            self.line((x_axis + sgn * d / 2, y_end), (x_axis + sgn * d / 2, y_top), "细实线")
        xa = x_axis - d / 2 if -1 in xs else x_axis
        xb = x_axis + d / 2 if 1 in xs else x_axis
        self.line((xa, y_end), (xb, y_end), "粗实线")

    def thread_circle(self, c, d, gap_start=90):
        """内螺纹圆视图：大径画约 3/4 圈细实线圆弧（缺口在第一象限）。小径圆 SW 已画成粗实线。"""
        self.layer("细实线")
        self.ms.AddArc(P(*c), d / 2, math.radians(gap_start), math.radians(360))

    def half_dia(self, c, r, ang, txt, over=6, h=3.5, frac=0.55):
        """半剖/对称图形里只画一半的直径尺寸：箭头落在 ang 方向的圆周上（从里往外指），尺寸线过圆心再伸出 over，
        数字写在线的上方、与线平行，字的中点在离圆心 frac×r 处（同心圆多时调它，让字落在两圆之间）。"""
        a = math.radians(ang)
        tip = (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
        end = (c[0] - over * math.cos(a), c[1] - over * math.sin(a))
        self.layer("尺寸")
        self.ms.AddLeader(wc.VARIANT(0x2005, [tip[0], tip[1], 0.0, end[0], end[1], 0.0]), None, 2)
        rot = ang if -90 < ((ang + 180) % 360) - 180 <= 90 else ang + 180      # 字头朝上
        rr = math.radians(rot)
        mid = (c[0] + frac * r * math.cos(a), c[1] + frac * r * math.sin(a))
        ux, uy = math.cos(rr), math.sin(rr); nx, ny = -uy, ux
        self.layer("文字")
        t = self.ms.AddText(txt, P(0, 0), h); t.StyleName = "HZ"; t.Rotation = rr
        w = len(txt.replace("%%C", "C")) * h * 0.7      # 用对齐方式 + 旋转实测位置跑偏，改成左对齐、按估算字宽居中
        t.InsertionPoint = P(mid[0] + nx * 0.8 - ux * w / 2, mid[1] + ny * 0.8 - uy * w / 2)
        return t

    def gear_teeth(self, p0, u, width, ra, r, rf, sides=(1, -1), hidden=(), k=1.0):
        """圆柱齿轮非圆视图（轴线在图面内、剖开或不剖）的轮齿规定画法（GB/T 4459.2）：齿顶线粗实线、分度线点画线
        （伸出端面 3）、齿根线粗实线（剖视中轮齿按不剖处理，剖面线只画到齿根线——所以齿轮模型建到齿根圆、轮齿
        这一圈不建，SW 给的剖面线天然就停在齿根）。p0：轴线与一侧端面的交点（图纸坐标）；u：轴线方向；width：齿宽；
        ra/r/rf：齿顶/分度/齿根半径（模型 mm，k=视图比例的倒数，如 1:2 传 0.5）；sides：画轴线哪一侧（+1/-1，
        法向 n = u 逆时针转 90°）；hidden：哪一侧的齿顶线画虚线（啮合区被另一个齿轮挡住的那一侧）。"""
        L = math.hypot(*u); ux, uy = u[0] / L, u[1] / L; nx, ny = -uy, ux
        P2 = lambda t, s: (p0[0] + ux * t + nx * s, p0[1] + uy * t + ny * s)
        w = width * k
        for sd in sides:
            lay = "虚线" if sd in hidden else "粗实线"
            self.line(P2(0, sd * ra * k), P2(w, sd * ra * k), lay)                     # 齿顶线
            self.line(P2(0, sd * rf * k), P2(0, sd * ra * k), lay)                     # 两端面上齿根→齿顶
            self.line(P2(w, sd * rf * k), P2(w, sd * ra * k), lay)
            self.line(P2(-3, sd * r * k), P2(w + 3, sd * r * k), "中心线")             # 分度线

    def gear_circles(self, c, ra, r, rf=None, k=1.0):
        """圆柱齿轮圆视图：齿顶圆粗实线、分度圆点画线、齿根圆细实线（可省略，rf=None）。"""
        self.circle(c, ra * k, "粗实线"); self.circle(c, r * k, "中心线")
        if rf:
            self.circle(c, rf * k, "细实线")

    def rot_label(self, p, letter, ccw=True, angle=None, h=5):
        """旋转配置的斜视图/向视图标注（GB/T 4458.1）：字母 + 旋转符号（半圆弧加箭头，半径≈字高），
        箭头方向与旋转方向一致；需要时在后面注角度。p 为字母中心。"""
        self._text(p, h, letter)
        r = h * 0.7; c = (p[0] + h * 1.25, p[1] - h * 0.35)
        self.layer("细实线")
        self.ms.AddArc(P(*c), r, 0, math.pi)
        end = (c[0] - r, c[1]) if ccw else (c[0] + r, c[1])        # 逆时针：箭头在左端，朝下
        tri = [end[0] - 0.7, end[1] + 0.2, 0, end[0] + 0.7, end[1] + 0.2, 0, end[0], end[1] - 1.6, 0]
        pl = self.ms.AddPolyline(wc.VARIANT(0x2005, [float(v) for v in tri])); pl.Closed = True
        hp = self.ms.AddHatch(0, "SOLID", True); hp.AppendOuterLoop(wc.VARIANT(0x2009, [pl])); hp.Evaluate()
        if angle:
            self._text((c[0] + r + 1.5 + len(angle) * h * 0.35, p[1]), h * 0.7, angle)

    def cut_path(self, pts, stroke=5):
        """剖切线（旋转剖、阶梯剖）：SW 把剖切路径导成长的 HIDDEN 线，`_relayer` 会分到虚线层——国标应该是
        细点画线（也可以不画）。这里删掉落在折线 pts 各段上的虚线/细实线，改画细点画线；并在每个转折点画
        国标要求的粗短画（沿两段方向各 stroke mm）。起止两端的粗短画和箭头 SW 已经画了。"""
        n = 0
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1]); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            on = lambda q: abs((q[0] - a[0]) * uy - (q[1] - a[1]) * ux) < 0.1 and \
                -0.5 <= (q[0] - a[0]) * ux + (q[1] - a[1]) * uy <= L + 0.5
            for e in self._items():
                if e.ObjectName == "AcDbLine" and e.Layer in ("虚线", "细实线", "中心线") and \
                        on(e.StartPoint) and on(e.EndPoint) and e.Length > 1:
                    e.Delete(); n += 1
            self.line(a, b, "中心线")
        for a, m, b in zip(pts, pts[1:], pts[2:]):             # 转折处的粗短画
            for q in (a, b):
                L = math.hypot(q[0] - m[0], q[1] - m[1])
                self.line(m, (m[0] + (q[0] - m[0]) / L * stroke, m[1] + (q[1] - m[1]) / L * stroke), "粗实线")
        print("剖切线：删了", n, "段虚线")

    def cut_end(self, p, seg_dir, look_dir, letter, stroke=5, arrow=7, h=5):
        """剖切符号的一端（GB/T 4458.6）：p 是剖切线端点，seg_dir 是从端点指向剖切线内部的方向，
        look_dir 是投射方向（箭头指向）。画粗短画 + 细线箭头 + 字母。"""
        L = math.hypot(*seg_dir); sx, sy = seg_dir[0] / L, seg_dir[1] / L
        L = math.hypot(*look_dir); lx, ly = look_dir[0] / L, look_dir[1] / L
        self.line(p, (p[0] + sx * stroke, p[1] + sy * stroke), "粗实线")
        tip = (p[0] + lx * arrow, p[1] + ly * arrow)
        self.line(p, tip, "细实线")
        a = (tip[0] - lx * 3 + ly * 0.8, tip[1] - ly * 3 - lx * 0.8)
        b = (tip[0] - lx * 3 - ly * 0.8, tip[1] - ly * 3 + lx * 0.8)
        pl = self.ms.AddPolyline(wc.VARIANT(0x2005, [float(v) for v in (*tip, 0, *a, 0, *b, 0)])); pl.Closed = True
        hp = self.ms.AddHatch(0, "SOLID", True); hp.AppendOuterLoop(wc.VARIANT(0x2009, [pl])); hp.Evaluate()
        self._text((p[0] - sx * 4 + lx * 3, p[1] - sy * 4 + ly * 3), h, letter)

    def _dxf_hatch_region(self, h):
        """AutoCAD 里一块剖面线 h 的填充区域（shapely 多边形）。COM 拿不到导入剖面线的边界（GetLoopAt 要关联对象），
        改从 SW 同时导出的同名 DXF 里按外框找到同一块剖面线，边界展平后按奇偶规则合成区域。"""
        import ezdxf
        from ezdxf import bbox as _bb, path as _path
        from shapely.geometry import Polygon
        if not hasattr(self, "_dxf_hatches"):
            f = os.path.splitext(self.src)[0] + ".DXF"
            self._dxf_hatches = []
            for x in ezdxf.readfile(f).modelspace().query("HATCH"):
                b = _bb.extents([x])
                self._dxf_hatches.append(((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y), x))
        mn, mx = retry(lambda: h.GetBoundingBox())
        hb = (mn[0], mn[1], mx[0], mx[1])
        cand = min(self._dxf_hatches, key=lambda t: max(abs(a - b) for a, b in zip(t[0], hb)))
        if max(abs(a - b) for a, b in zip(cand[0], hb)) > 0.5:
            raise RuntimeError(f"DXF 里没找到外框 {hb} 的剖面线")
        reg = None
        for p in _path.from_hatch(cand[1]):
            pts = [(v.x, v.y) for v in p.flattening(0.01)]
            if len(pts) < 3:
                continue
            g = Polygon(pts).buffer(0)
            reg = g if reg is None else reg.symmetric_difference(g)
        return reg

    def clip_hatch(self, h, a0, a1, keep):
        """把剖面线 h 沿直线 a0→a1 裁成一半，只留叉积符号为 keep（+1 左侧 / -1 右侧）那边；返回新剖面线
        （图案、比例、角度、图层照旧，原对象删掉）。边界是展平的多段线，填充看不出区别。"""
        from shapely.geometry import Polygon, MultiPolygon
        reg = self._dxf_hatch_region(h)
        ux, uy = a1[0] - a0[0], a1[1] - a0[1]; L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
        nx, ny = -uy * keep, ux * keep                   # 指向要保留一侧的法向
        R = 5000
        half = Polygon([(a0[0] - ux * R, a0[1] - uy * R), (a0[0] + ux * R, a0[1] + uy * R),
                        (a0[0] + ux * R + nx * R, a0[1] + uy * R + ny * R),
                        (a0[0] - ux * R + nx * R, a0[1] - uy * R + ny * R)])
        part = reg.intersection(half)
        polys = [g for g in (part.geoms if hasattr(part, "geoms") else [part]) if isinstance(g, Polygon) and g.area > 0.01]
        if not polys:
            h.Delete(); return None
        name, ptype = h.PatternName, h.PatternType
        ang, scl, lay = h.PatternAngle, h.PatternScale, h.Layer
        nh = self.ms.AddHatch(ptype, name, False)
        tmp = []

        def loop(ring):
            xy = []
            for x, y in list(ring.coords)[:-1]:
                xy += [float(x), float(y)]
            pl = self.ms.AddLightWeightPolyline(wc.VARIANT(0x2005, xy)); pl.Closed = True
            tmp.append(pl)
            return wc.VARIANT(0x2009, [pl])
        first = True
        for g in polys:
            if first:
                nh.AppendOuterLoop(loop(g.exterior)); first = False
            else:
                nh.AppendInnerLoop(loop(g.exterior))       # 奇偶规则：不相交的外环当内环也照样填
            for r in g.interiors:
                nh.AppendInnerLoop(loop(r))
        nh.PatternAngle = ang; nh.PatternScale = scl; nh.Layer = lay
        nh.Evaluate()
        for pl in tmp:
            pl.Delete()
        h.Delete()
        return nh

    def splice_aligned(self, keep_box, axis, keep_side, src_box, src_axis, src_side, src_pts, dst_pts):
        """旋转剖拼接（SW 的 API 做不出真正的旋转剖，实测只给出投影的阶梯剖，倾斜部分被缩短）：
        keep_box 里的主剖视图只留 axis（竖直线 x=axis）keep_side 一侧（+1 右 / -1 左）；
        src_box 里另做的、沿倾斜剖切面剖开的剖视图，取它 src_axis（两点定的直线）src_side 一侧的对象，
        用 src_pts → dst_pts 三对点定的仿射变换（含旋转/镜像）搬到主剖视图的另一半，然后删掉 src_box 里剩下的东西。
        实心轮毂（没有中心孔）时剖面线跨过轴线：按轴线把剖面线裁成一半（clip_hatch，边界取自同名 DXF），2026-11-08。"""
        import numpy as np

        def side(e, a0, a1):
            # 用实际几何点判断在轴线哪一侧：直线用端点，圆弧用圆周采样点，剖面线等用外框中心。
            # 不能用外框四角：源视图是斜着放的，紧贴斜轴线的对象外框角会跨到另一侧（实测剖面线被当成跨轴线丢了）
            t = e.ObjectName
            if t == "AcDbLine":
                cs = [e.StartPoint, e.EndPoint]
            elif t in ("AcDbArc", "AcDbCircle"):
                c0, r = e.Center, e.Radius
                sa, ea = (e.StartAngle, e.EndAngle) if t == "AcDbArc" else (0.0, 2 * math.pi)
                sw_ = (ea - sa) % (2 * math.pi) or 2 * math.pi
                cs = [(c0[0] + r * math.cos(sa + sw_ * k / 8), c0[1] + r * math.sin(sa + sw_ * k / 8)) for k in range(9)]
            else:
                mn, mx = retry(lambda: e.GetBoundingBox())
                cs = [((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2)]
            vals = [(a1[0] - a0[0]) * (q[1] - a0[1]) - (a1[1] - a0[1]) * (q[0] - a0[0]) for q in cs]
            if all(v >= -0.05 for v in vals): return 1
            if all(v <= 0.05 for v in vals): return -1
            return 0

        def inbox(e, b):
            mn, mx = retry(lambda: e.GetBoundingBox())
            return b[0] <= mn[0] and mx[0] <= b[2] and b[1] <= mn[1] and mx[1] <= b[3]

        # 1) 主剖视图：删掉另一侧（竖直轴线 x=axis：side 用 (axis,0)->(axis,1)，左侧为 +1）
        a0, a1 = (axis, 0.0), (axis, 1.0)
        n_del = n_cut = 0
        for e in self._items():
            if not inbox(e, keep_box) or e.Layer in ("文字",):
                continue
            sd = side(e, a0, a1)                    # +1 = 左侧
            want = -1 if keep_side > 0 else 1      # 要保留的一侧
            if sd == -want:
                e.Delete(); n_del += 1
            elif sd == 0 and e.ObjectName == "AcDbHatch":     # 实心轮毂：剖面线跨轴线，裁掉另一半
                self.clip_hatch(e, a0, a1, want); n_cut += 1
            elif sd == 0 and e.ObjectName != "AcDbLine":
                mn, mx = retry(lambda: e.GetBoundingBox())
                print("   主视图里跨轴线、保留：", e.ObjectName, e.Layer, [round(v, 1) for v in (mn[0], mn[1], mx[0], mx[1])])
            elif sd == 0 and e.ObjectName == "AcDbLine" and e.Layer != "中心线":
                s, f = e.StartPoint, e.EndPoint    # 跨轴线的直线截掉另一半
                if (s[0] - axis) * keep_side < 0:
                    e.StartPoint = P(axis, s[1] + (f[1] - s[1]) * (axis - s[0]) / (f[0] - s[0]))
                else:
                    e.EndPoint = P(axis, s[1] + (f[1] - s[1]) * (axis - s[0]) / (f[0] - s[0]))
                n_cut += 1
        # 2) 求仿射：dst = M·src + t
        S = np.array([[p[0], p[1], 1.0] for p in src_pts]); Dm = np.array(dst_pts, float)
        sol = np.linalg.solve(S, Dm)              # 3×2
        M, t = sol[:2].T, sol[2]
        mat = [[M[0, 0], M[0, 1], 0.0, t[0]], [M[1, 0], M[1, 1], 0.0, t[1]], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        moved, hatches = 0, []
        b0, b1 = src_axis
        cross = lambda q: (b1[0] - b0[0]) * (q[1] - b0[1]) - (b1[1] - b0[1]) * (q[0] - b0[0])
        for e in self._items():
            if not inbox(e, src_box):
                continue
            sd = side(e, *src_axis)
            if sd == 0 and e.ObjectName == "AcDbLine" and e.Layer != "中心线":
                s, f = e.StartPoint, e.EndPoint    # 跨轴线的直线（轮毂孔后壁的上下边线等）：截到要的一侧再搬
                cs, cf = cross(s), cross(f); tt = cs / (cs - cf)
                m = P(s[0] + (f[0] - s[0]) * tt, s[1] + (f[1] - s[1]) * tt)
                if (cs > 0) == (src_side > 0):
                    e.EndPoint = m
                else:
                    e.StartPoint = m
                sd = src_side
            elif sd == 0 and e.ObjectName == "AcDbHatch":
                e = self.clip_hatch(e, b0, b1, src_side); sd = src_side
                if e is None:
                    continue
            elif sd == 0:
                mn, mx = retry(lambda: e.GetBoundingBox())
                print("   源视图里跨轴线、丢掉：", e.ObjectName, e.Layer, [round(v, 1) for v in (mn[0], mn[1], mx[0], mx[1])])
            if sd == src_side and e.Layer != "文字":
                e.TransformBy(wc.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, mat))    # 4×4 二维 double 数组
                moved += 1
                if e.ObjectName == "AcDbHatch":
                    hatches.append(e)
            else:
                e.Delete()
        # 搬过来的剖面线跟着转了角度；同一零件剖面线方向、间距要一致：照主视图那半边的剖面线改回来
        ref = [e for e in self._items() if e.ObjectName == "AcDbHatch" and inbox(e, keep_box) and e not in hatches]
        if ref:
            for h in hatches:
                h.PatternAngle = ref[0].PatternAngle; h.PatternScale = ref[0].PatternScale; h.Evaluate()
        # 孔的圆柱面被切成两半时 SW 会画出背面的接缝线，正好落在轴线上：删掉（轴线另画点画线）
        for e in self._items():
            if e.ObjectName == "AcDbLine" and e.Layer == "粗实线" and inbox(e, keep_box) and \
                    abs(e.StartPoint[0] - axis) < 0.05 and abs(e.EndPoint[0] - axis) < 0.05:
                e.Delete()
        print(f"旋转剖拼接：主视图删 {n_del}、截 {n_cut}；搬过来 {moved} 个对象")

    def center_cross(self, c, r, ext=3):
        """重画圆的十字中心线（水平+竖直，超出圆 ext）：先删掉圆心附近原有的中心线（旋转过的视图里 SW 的中心
        符号跟着转成了斜十字）。"""
        for e in self._items():
            if e.Layer == "中心线" and e.ObjectName == "AcDbLine":
                m = [(e.StartPoint[i] + e.EndPoint[i]) / 2 for i in (0, 1)]
                if math.hypot(m[0] - c[0], m[1] - c[1]) < r + ext + 1 and e.Length < 2 * (r + ext) + 2:
                    e.Delete()
        self.line((c[0] - r - ext, c[1]), (c[0] + r + ext, c[1]))
        self.line((c[0], c[1] - r - ext), (c[0], c[1] + r + ext))

    def erase_text(self, s, regex=False):
        """删掉内容等于 s 的文字（如 SW 自动放的放大图标签 "I"，位置不可控，删了自己重写）。
        regex=True 时 s 当正则整体匹配，例如 r"视图\\s*[A-Z].*"（SW 的斜视图标签“视图 A”、旋转后还带角度）。"""
        import re
        n = 0
        for e in self._items():
            if e.ObjectName in ("AcDbText", "AcDbMText"):
                t = re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", e.TextString).replace("\\P", " ").strip()
                if (re.fullmatch(s, t, re.S) if regex else t == s):
                    e.Delete(); n += 1
        return n

    def view_label(self, name, at, scale=None, h=5, keep_near=None):
        """统一重画视图名（SW 的标签位置、有没有、带不带“视图”“详图”前缀和比例每次都可能不同，2026-11-08）：
        先删掉所有“视图名/详图名”是 name 的 SW 标签（"A-A"、"视图 B"、"B 2:1"、"详图 I 4:1"、旋转后带的角度），
        再在 at（文字中心）按国标写：
          - 剖视 / 向视 / 斜视："A-A" 或 "B"，字高 h；
          - 局部放大图（name 是罗马数字且给了 scale）：罗马数字 + 细横线 + 下面的比例（如 4:1）。
        keep_near=(x,y)：只删离这个点 60 mm 以内的（剖切符号旁的字母 "A" 是另一回事，别用本函数删）。"""
        import re
        pat = re.compile(r"(视图|详图|剖面|截面)?\s*" + r"\s*[-—]\s*".join(map(re.escape, name.split("-"))) + r"(\s*[\d.]+\s*:\s*[\d.]+)?(\s*[⌒∩]?\s*[\d.]+\s*°)?")
        n = 0
        for e in self._items():
            if e.ObjectName not in ("AcDbText", "AcDbMText"):
                continue
            t = re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", e.TextString).replace("\\P", " ").strip()
            if not pat.fullmatch(t):
                continue
            if keep_near is not None:
                q = e.InsertionPoint
                if math.hypot(q[0] - keep_near[0], q[1] - keep_near[1]) > 60:
                    continue
            e.Delete(); n += 1
        if scale and re.fullmatch(r"[IVX]+", name):
            w = max(9, len(name) * 3 + 6)
            self._text((at[0], at[1] + 3.5), h, name)
            self.line((at[0] - w, at[1]), (at[0] + w, at[1]), "细实线")
            self._text((at[0], at[1] - 4), h * 0.7, scale)
        else:
            self._text(at, h, name if not scale else f"{name} {scale}")
        return n

    # ------------------------------------------------------------------ 尺寸自动排布
    def auto_dims(self, box, side, items, first=10, step=7, k=None, h=3.5):
        """把一组同方向的尺寸自动排到视图的一侧（GB/T 4458.4：小尺寸在里、大尺寸在外，尺寸线间距 7，
        第一道离轮廓 10）。box=(x0,y0,x1,y1) 视图轮廓外框；side：below/above（水平尺寸）、left/right（竖直尺寸）；
        items：[(p1, p2) 或 (p1, p2, 文字)]。按跨度从小到大，逐个放进最里面那一排里不和已有尺寸（连文字）重叠的位置；
        链式尺寸首尾相接可以同排。返回 (尺寸对象列表, 最外一排离轮廓的距离)。"""
        horiz = side in ("below", "above")
        ax = 0 if horiz else 1
        kk = self.k if k is None else k

        def label(it):
            if len(it) > 2 and it[2]:
                import re
                return len(re.sub(r"%%[CcPpDd]", "x", re.sub(r"\{\\[^;]*;|[{}]|\\S[^;]*;", "", it[2])))
            return len(f"{abs(it[1][ax] - it[0][ax]) * kk:g}")

        def interval(it):
            lo, hi = sorted((it[0][ax], it[1][ax]))
            tw = label(it) * h * 0.7 + 2
            if hi - lo < tw + 6:                       # 放不下文字，AutoCAD 会把字放到外侧：区间按字宽加长
                hi += tw
            return lo, hi

        rows, out = [], []
        for it in sorted(items, key=lambda it: abs(it[1][ax] - it[0][ax])):
            lo, hi = interval(it)
            for r, row in enumerate(rows):
                if all(lo >= b - 0.01 or hi <= a + 0.01 for a, b in row):
                    row.append((lo, hi)); break
            else:
                rows.append([(lo, hi)]); r = len(rows) - 1
            off = first + step * r
            mid = (it[0][ax] + it[1][ax]) / 2
            if side == "below":   loc = (mid, box[1] - off)
            elif side == "above": loc = (mid, box[3] + off)
            elif side == "left":  loc = (box[0] - off, mid)
            else:                 loc = (box[2] + off, mid)
            out.append(self.dimlin(it[0], it[1], loc, 0 if horiz else 90, it[2] if len(it) > 2 else "", k))
        return out, first + step * (len(rows) - 1) if rows else 0

    def check_geometry(self, verbose=True, min_gap=5.0, tip_tol=0.6):
        """check() 的几何部分：
        ① 平行尺寸线间距 < min_gap（重叠范围内）——“挤但没重叠”；
        ② 引线箭头尖没落在任何图线 / 尺寸线端点上——“引线悬空”；
        ③ 同一数值、同一方向的尺寸出现两次以上——“可能重复标注”（只是提示，链式里相同数值是正常的）。"""
        issues = []
        D = self._dims
        for i in range(len(D)):
            for j in range(i + 1, len(D)):
                (_, a1, a2, la, anga), (_, b1, b2, lb, angb) = D[i], D[j]
                if anga != angb:
                    continue
                ax = 0 if anga == 0 else 1; pr = 1 - ax
                if abs(la[pr] - lb[pr]) < 0.01:
                    continue                                  # 同一排（链式）
                sa = sorted((a1[ax], a2[ax])); sb = sorted((b1[ax], b2[ax]))
                if min(sa[1], sb[1]) - max(sa[0], sb[0]) > 1 and abs(la[pr] - lb[pr]) < min_gap:
                    issues.append((f"尺寸线太挤：间距 {abs(la[pr] - lb[pr]):.1f} mm", round(la[0], 1), round(la[1], 1)))
        # ② 引线
        pts_segs, circ = [], []
        for e in self._items():
            t = e.ObjectName
            try:
                if t == "AcDbLine" and e.Layer in ("粗实线", "细实线", "虚线", "中心线", "剖面线"):
                    pts_segs.append((e.StartPoint[:2], e.EndPoint[:2]))
                elif t in ("AcDbArc", "AcDbCircle") and e.Layer in ("粗实线", "细实线", "虚线", "中心线"):   # 中心线圆：齿面粗糙度指到分度圆
                    circ.append((e.Center[:2], e.Radius))
                elif t == "AcDbPolyline" and e.Layer in ("粗实线", "细实线"):
                    c = list(e.Coordinates); q = [(c[i], c[i + 1]) for i in range(0, len(c), 2)]
                    pts_segs += list(zip(q, q[1:] + ([q[0]] if e.Closed else [])))
                elif t == "AcDbSpline":
                    c = list(e.FitPoints) if e.NumberOfFitPoints else list(e.ControlPoints)
                    q = [(c[i], c[i + 1]) for i in range(0, len(c), 3)]
                    pts_segs += list(zip(q, q[1:]))
            except Exception:
                pass
        for d, p1, p2, loc, ang in D:                         # 尺寸线两端（形位公差箭头常指在这里）
            ax = 0 if ang == 0 else 1; pr = 1 - ax
            e1 = list(p1); e1[pr] = loc[pr]; e2 = list(p2); e2[pr] = loc[pr]
            pts_segs.append((tuple(e1), tuple(e2)))

        def dseg(p, a, b):
            vx, vy = b[0] - a[0], b[1] - a[1]; L2 = vx * vx + vy * vy
            t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
            return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)
        for e in self._items():
            if e.ObjectName != "AcDbLeader":
                continue
            c = list(e.Coordinates); tip = (c[0], c[1])
            dmin = min([dseg(tip, a, b) for a, b in pts_segs] + [abs(math.hypot(tip[0] - cc[0], tip[1] - cc[1]) - r) for cc, r in circ] + [99])
            if dmin > tip_tol:
                issues.append((f"引线箭头悬空：离最近的图线 {dmin:.1f} mm", round(tip[0], 1), round(tip[1], 1)))
        # ③ 重复
        from collections import defaultdict
        seen = defaultdict(list)
        for d, p1, p2, loc, ang in D:
            try:
                key = ((d.TextOverride or "").replace("<>", "") or f"{d.Measurement:.2f}", ang)
            except Exception:
                continue
            seen[key].append(loc)
        for (txt, ang), locs in seen.items():
            if len(locs) > 1 and len({(round(l[0]), round(l[1])) for l in locs}) > 1:
                rows = {round(l[1 if ang == 0 else 0], 1) for l in locs}
                if len(rows) > 1:                              # 同排的链式相同数值不算
                    issues.append((f"提示：{txt!r} 标了 {len(locs)} 次，确认不是重复标注", round(locs[0][0], 1), round(locs[0][1], 1)))
        if verbose:
            print(f"== 几何检查：{len(issues)} 处")
            for it in issues:
                print("  ", it)
        return issues

    # ------------------------------------------------------------------ 自动检查：文字压线、文字互相重叠
    def check(self, thresh=5, ppm=10, verbose=True):
        """出图前自动检查“文字被线/剖面线穿过”和“文字互相重叠”（2026-11-08）。
        做法：把所有文字（文字层、尺寸数字）临时改成蓝色，用彩色打印样式出一张临时 PDF，按 ppm 像素/mm 栅格化；
        每段文字取它的蓝色像素外框，外框里如果有非蓝色的墨迹（轮廓线、中心线、剖面线、别的尺寸线……）超过 thresh
        个像素，就算压线。比用几何求交可靠：剖面线、尺寸、公差框格的 COM 对象都不能 Explode（实测），
        用 SendCommand 炸开又会把 AutoCAD 的 COM 卡死（实测要强杀 acad.exe）。返回 [(说明, x, y)]，颜色检查完恢复。"""
        import re, fitz, numpy as np
        a, doc = self.a, self.doc
        BLUE = 5                                             # 图层里没用到蓝色（虚线层是 6 洋红）
        tc = a.GetInterfaceObject("AutoCAD.AcCmColor.24"); tc.ColorIndex = BLUE
        bylayer = a.GetInterfaceObject("AutoCAD.AcCmColor.24"); bylayer.ColorIndex = 256
        anchors, dims_old, txt_old = [], [], []
        for e in self._items():                              # 改图层颜色实测不生效（文字还是黑的），逐个对象改
            t = e.ObjectName
            if "Dimension" in t:
                dims_old.append((e, e.TextColor)); e.TextColor = BLUE
                p = e.TextPosition; s = e.TextOverride or str(round(e.Measurement, 3))
                anchors.append((p[0], p[1], s))
            elif t in ("AcDbText", "AcDbMText") and e.Layer == "文字":
                txt_old.append(e); e.TrueColor = tc
                try:
                    mn, mx = e.GetBoundingBox()
                except Exception:                            # 空字符串（明细栏空格）没有外框：Null extents
                    continue
                anchors.append(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, e.TextString))
        import glob
        for old in glob.glob(os.path.splitext(self.out)[0] + "_check*.pdf"):   # 旧的校核图删得掉就删（WPS 开着会锁）
            try: os.remove(old)
            except OSError: pass
        pdf = os.path.splitext(self.out)[0] + time.strftime("_check%H%M%S.pdf")
        try:
            def plot():
                lo = doc.ActiveLayout
                set_pdf_device(lo)
                lo.CanonicalMediaName = PDF_MEDIA[self.sheet]; lo.PlotType = 1
                lo.UseStandardScale = False; lo.SetCustomScale(1, 1); lo.CenterPlot = True
                lo.PlotRotation = 0; lo.PlotWithLineweights = True; lo.StyleSheet = "acad.ctb"
                doc.SetVariable("BACKGROUNDPLOT", 0)
                if os.path.exists(pdf):
                    os.remove(pdf)
                doc.Plot.PlotToFile(pdf)
            # 先缩放到范围：按“范围”打印，范围没刷新时（刚删掉/搬走了图框外的对象，如旋转剖拼接用的辅助视图）
            # 整张图会被居中偏移，像素坐标就对不上了（实测偏了一百多 mm）
            self.a.ZoomExtents()
            retry(plot, tries=30, delay=0.5)
            for _ in range(40):
                if os.path.exists(pdf): break
                time.sleep(0.5)
        finally:
            for e in txt_old:
                e.TrueColor = bylayer
            for e, c in dims_old:
                e.TextColor = c
        from scipy import ndimage
        Bh, Lw = SHEETS[self.sheet][0], SHEETS[self.sheet][1]
        page = fitz.open(pdf)[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(ppm * 25.4 / 72, ppm * 25.4 / 72), alpha=False)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(int)
        R, G, Bc = img[..., 0], img[..., 1], img[..., 2]
        blue = (Bc > 140) & (R < 120) & (G < 120)
        # 别的墨迹：够暗、而且不偏蓝（蓝字边缘的抗锯齿像素是暗蓝色，实测会被误当成线：标题栏每个字都报压线）
        ink = (np.minimum(np.minimum(R, G), Bc) < 150) & (Bc - np.maximum(R, G) < 40)
        sx, sy = pix.w / Lw, pix.h / Bh                      # 像素/mm（PDF 页面 = 整张图纸）
        mm = lambda v: max(1, int(round(v * sx)))
        # 字形膨胀 0.9 mm 连成一段段文字；“附近”用 0.35 mm 膨胀：落在字形 0.35 mm 以内的别的墨迹才算压线
        words, nw = ndimage.label(ndimage.binary_dilation(blue, iterations=mm(0.9)))
        near = ndimage.binary_dilation(blue, iterations=mm(0.35))
        issues = []
        for k, sl in enumerate(ndimage.find_objects(words), start=1):
            if sl is None:
                continue
            comp = (words[sl] == k)
            n = int((ink[sl] & near[sl] & comp).sum())
            y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
            bx0, bx1 = x0 / sx, x1 / sx; by0, by1 = Bh - y1 / sy, Bh - y0 / sy
            inside = [s for ax, ay, s in anchors if bx0 - 0.5 <= ax <= bx1 + 0.5 and by0 - 0.5 <= ay <= by1 + 0.5]
            name = " / ".join(re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", s)[:16] for s in inside) or "?"
            what = []
            if n > thresh:
                what.append(f"线 {n} 像素")
            if len(inside) > 1:
                what.append("几段文字挤在一起")
            if what:
                issues.append((f"{name!r}：{'，'.join(what)}", round((bx0 + bx1) / 2, 1), round((by0 + by1) / 2, 1)))
        if verbose:
            print(f"== 检查：{nw} 段文字，{len(issues)} 处可能有问题（彩色校核图 {pdf}）")
            for it in issues:
                print("  ", it)
        self.check_pdf = pdf
        geo = self.check_geometry(verbose)
        return issues + geo

    def title_block(self, name, code, material="", scale="1:1", weight="", qty="1",
                    designer="", date="", school=None, cls=None):
        """学生用标题栏 180×40，贴内框右下角（参照 GB/T 10609.1 简化）。返回左上角坐标（明细栏从这里往上长）。
        school/cls 不传时取 scripts/config.json。"""
        school = CONFIG.get("company", "") if school is None else school
        cls = CONFIG.get("class", "") if cls is None else cls
        x1, y0 = self.inner[2], self.inner[1]; X = x1 - 180
        u = lambda x, y: (X + x, y0 + y)
        self._rect(X, y0, x1, y0 + 40, "粗实线")
        self.layer("细实线")
        for y in (10, 20, 30):
            self.ms.AddLine(P(*u(0, y)), P(*u(70, y)))
        for x in (12, 37, 55):
            self.ms.AddLine(P(*u(x, 0)), P(*u(x, 40)))
        self.layer("粗实线")
        self.ms.AddLine(P(*u(70, 0)), P(*u(70, 40))); self.ms.AddLine(P(*u(130, 0)), P(*u(130, 40)))
        self.ms.AddLine(P(*u(70, 20)), P(*u(130, 20))); self.ms.AddLine(P(*u(130, 20)), P(*u(180, 20)))
        self.layer("细实线")
        self.ms.AddLine(P(*u(70, 10)), P(*u(130, 10)))
        for x in (85, 115):                              # 0–20 两行都有
            self.ms.AddLine(P(*u(x, 0)), P(*u(x, 20)))
        self.ms.AddLine(P(*u(100, 10)), P(*u(100, 20)))  # 只有"比例/数量"那一行有；"材料"值占 85–115
        for i, lab in enumerate(("设计", "校核", "审核", "批准")):
            self._text(u(6, 35 - 10 * i), 3.5, lab)
        self._text(u(24.5, 35), 3.5, designer); self._text(u(46, 35), 2.5, date)
        self._text(u(100, 30), 7, name)
        self._text(u(77.5, 15), 3.5, "比例"); self._text(u(92.5, 15), 3.5, scale)
        self._text(u(107.5, 15), 3.5, "数量"); self._text(u(122.5, 15), 3.5, qty)
        self._text(u(77.5, 5), 3.5, "材料"); self._text(u(100, 5), 3.5, material)
        self._text(u(122.5, 5), 2.5, (weight + "kg") if weight else "")
        self._text(u(155, 30), 5, code)
        self._text(u(155, 14), 3.5, school); self._text(u(155, 6), 3.5, cls)
        return u(0, 40)

    BOM_COLS = (("序号", 8), ("代号", 40), ("名称", 44), ("数量", 8), ("材料", 38), ("重量/kg", 22), ("备注", 20))

    def bom(self, rows, origin=None, h=7):
        """明细栏（GB/T 10609.2 列宽，共 180），表头贴在标题栏上方，序号从下往上 1,2,3…。
        rows: [(代号, 名称, 数量, 材料, 重量, 备注), ...]，按序号顺序给。"""
        X, Y = origin or (self.inner[2] - 180, self.inner[1] + 40)
        n = len(rows)
        xs = [X]
        for _, w in self.BOM_COLS:
            xs.append(xs[-1] + w)
        top = Y + h * (n + 1)
        self.layer("粗实线")
        for x in xs:                                    # 竖线：粗
            self.ms.AddLine(P(x, Y), P(x, top))
        self.ms.AddLine(P(X, Y + h), P(X + 180, Y + h))  # 表头上边：粗
        self.layer("细实线")
        for k in range(2, n + 2):
            self.ms.AddLine(P(X, Y + h * k), P(X + 180, Y + h * k))
        for (lab, _), x0, x1 in zip(self.BOM_COLS, xs, xs[1:]):
            self._text(((x0 + x1) / 2, Y + h / 2), 3.5, lab)
        for i, r in enumerate(rows):
            yc = Y + h * (i + 1) + h / 2
            cells = (str(i + 1),) + tuple(str(v) for v in r)
            for j, (s, x0, x1) in enumerate(zip(cells, xs, xs[1:])):
                if s:
                    self._text(((x0 + x1) / 2, yc), 3.5 if len(s) <= 12 else 2.5, s)
        return top

    def balloon(self, on_part, at, n, h=5):
        """零件序号（GB/T 4458.2）：零件上一个小圆点，细实线指引到 at，水平短线上写序号。
        同一视图的序号要沿水平或竖直方向排齐，按顺时针或逆时针顺序。"""
        self.layer("细实线")
        dot = self.ms.AddCircle(P(*on_part), 0.6)
        hp = self.ms.AddHatch(0, "SOLID", True); hp.AppendOuterLoop(wc.VARIANT(0x2009, [dot])); hp.Evaluate()
        self.ms.AddLine(P(*on_part), P(*at))
        right = at[0] >= on_part[0]
        x2 = at[0] + (8 if right else -8)
        self.ms.AddLine(P(*at), P(x2, at[1]))
        self._text(((at[0] + x2) / 2, at[1] + 0.8 + h / 2), h, str(n))

    def break_center_under_text(self, margin=1.0, layers=("中心线",), only=None):
        """国标：尺寸数字不能被任何图线穿过，否则把图线断开。轴上的配合尺寸（%%C40H7/r6）文字常骑在轴线上——
        这里把穿过尺寸文字框的点画线断开（按 TextPosition、字数×0.7 字高估文字框，四周留 margin）。
        放在所有尺寸标完之后、check() 之前调。返回断开的条数。
        only=[尺寸对象...] 时只处理这几个尺寸；配合 layers=("中心线", "粗实线") 可以把实在躲不开的轮廓线（如窄轴上
        的键）也断开——国标允许，但别全局对粗实线用，压线的尺寸应该先挪。竖直尺寸的文字框按转 90° 算。"""
        import re
        rects, angs = [], None
        for e in (only if only is not None else self._items()):
            if "Dimension" not in e.ObjectName:
                continue
            try:
                # 竖直尺寸：AddDimRotated(…, 90°) 建的尺寸 Rotation 读回来是 0（实测），所以按 dimlin 记下的角度判断
                if angs is None:
                    angs = {d.Handle: ang for d, *_r, ang in self._dims}
                vert = angs.get(e.Handle, 0) % 180 == 90 or abs(math.sin(getattr(e, "TextRotation", 0) or 0)) > 0.7
                txt = e.TextOverride or f"{e.Measurement:g}"
                h = e.TextHeight
                tp = e.TextPosition
            except Exception:
                continue
            t = re.sub(r"\{\\[^;]*;|[{}]|\\S[^;]*;|\\H[^;]*;", "", txt)
            t = re.sub(r"%%[CcPpDd]", "x", t).replace("<>", "000")
            w = len(t) * h * 0.7
            if vert:
                w, h = h, w
            rects.append((tp[0] - w / 2 - margin, tp[1] - h / 2 - margin, tp[0] + w / 2 + margin, tp[1] + h / 2 + margin))
        total = 0
        for _ in range(20):                                     # 一条轴线常穿过好几个尺寸：断一次、再扫一遍
            n = self._break_pass(rects, layers)
            total += n
            if n == 0:
                break
        return total

    def _break_pass(self, rects, layers):
        n = 0
        for e in self._items():
            if e.ObjectName != "AcDbLine" or e.Layer not in layers:
                continue
            for x0, y0, x1, y1 in rects:
                a, b = e.StartPoint, e.EndPoint
                dx, dy = b[0] - a[0], b[1] - a[1]
                t0, t1 = 0.0, 1.0                              # Liang–Barsky：线段落在框里的参数区间
                ok = True
                for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
                    if abs(p) < 1e-12:
                        if q < 0: ok = False; break
                    else:
                        r = q / p
                        if p < 0: t0 = max(t0, r)
                        else: t1 = min(t1, r)
                if not ok or (t1 - t0) * math.hypot(dx, dy) < 0.05:
                    continue
                pa =(a[0] + dx * t0, a[1] + dy * t0); pb = (a[0] + dx * t1, a[1] + dy * t1)
                if t1 < 1:
                    self.line(pb, (b[0], b[1]), e.Layer)
                if t0 > 0:
                    e.EndPoint = P(*pa)
                else:
                    e.Delete()
                n += 1
                break                                           # 这条线已经改了，剩下的框交给新生成的那段（下一轮不再处理）
        return n

    def balloon_group(self, on_part, at, ns, h=5):
        """紧固件组的公共指引线序号（GB/T 4458.2：螺栓、垫圈、螺母这样一组可以共用一条指引线）：
        一个圆点、一条指引线到 at，序号自下而上竖排，每个序号下面一条水平短线。ns 按从下往上的顺序给。"""
        self.layer("细实线")
        dot = self.ms.AddCircle(P(*on_part), 0.6)
        hp = self.ms.AddHatch(0, "SOLID", True); hp.AppendOuterLoop(wc.VARIANT(0x2009, [dot])); hp.Evaluate()
        self.ms.AddLine(P(*on_part), P(*at))
        right = at[0] >= on_part[0]
        x2 = at[0] + (8 if right else -8)
        for i, n in enumerate(ns):
            y = at[1] + i * (h + 3)
            self.layer("细实线")
            self.ms.AddLine(P(at[0], y), P(x2, y))
            self._text(((at[0] + x2) / 2, y + 0.8 + h / 2), h, str(n))

    def unhatch(self, inside, also_lines_x=None):
        """装配图里实心件（轴、键、销、螺栓）纵剖不画剖面线：删掉包含 inside 点的那块剖面线。
        SW 每个零件的剖面导成独立的 HATCH，用面积最小的、包围盒含该点的那一块。"""
        cands = []
        for e in self._items():
            if e.ObjectName == "AcDbHatch":
                mn, mx = retry(lambda: e.GetBoundingBox())
                if mn[0] <= inside[0] <= mx[0] and mn[1] <= inside[1] <= mx[1]:
                    cands.append(((mx[0] - mn[0]) * (mx[1] - mn[1]), e))
        if not cands:
            print("unhatch 没找到包含", inside, "的剖面线"); return
        min(cands, key=lambda c: c[0])[1].Delete()

    def move_label(self, text, to, near=None):
        """挪 SW 的视图标注（如 "A-A"），避免和尺寸打架。near=(x,y) 时只挪离它最近的那个同名标注。"""
        import re
        hits = []
        for e in self._items():
            if e.ObjectName in ("AcDbMText", "AcDbText"):
                s = re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", e.TextString).strip()
                if s.replace("—", "-") == text:
                    p = e.InsertionPoint
                    hits.append(((p[0] - near[0]) ** 2 + (p[1] - near[1]) ** 2 if near else 0, e))
        if not hits:
            print("move_label 没找到", text); return
        e = min(hits, key=lambda h: h[0])[1]
        p = e.InsertionPoint                      # Move 要两个三维点 VARIANT，原始 tuple 会报参数错误
        e.Move(wc.VARIANT(0x2005, [float(p[0]), float(p[1]), 0.0]), P(*to))

    def title(self, rep):
        """替换 SW 模板标题栏占位符，如 {'“图样名称”': '轮毂', '“图样代号”': 'SL-02-05', '普通碳钢': '45'}。"""
        hit = set()
        for e in self._items():
            if e.ObjectName == "AcDbMText":
                s = e.TextString
                for k, v in rep.items():
                    if k in s:
                        e.TextString = s = s.replace(k, v); hit.add(k)
                if e.StyleName.upper().startswith("SLD"):
                    e.StyleName = "HZ"
        miss = set(rep) - hit
        if miss: print("标题栏没找到:", miss)

    def notes(self, items, p=(40, 70)):
        self.layer("文字")
        t = self.ms.AddText("技术要求", P(*p), 5); t.StyleName = "HZ"
        for k, s in enumerate(items):
            t = self.ms.AddText(s, P(p[0], p[1] - 8 - 7 * k), 3.5); t.StyleName = "HZ"

    def report(self):
        for e in self._items():
            if "Dimension" in e.ObjectName:
                print(f"  尺寸 {round(e.Measurement, 3):>8}  {e.TextOverride}")

    # ------------------------------------------------------------------ 存盘出图
    def __exit__(self, et, ev, tb):
        if et: return False
        self.report()
        self.a.ZoomExtents()
        retry(lambda: self.doc.SaveAs(self.out))
        pdf = self.pdf

        def plot():
            a2 = wc.GetActiveObject("AutoCAD.Application"); doc = a2.ActiveDocument; lay = doc.ActiveLayout
            set_pdf_device(lay)
            lay.CanonicalMediaName = PDF_MEDIA[self.sheet]; lay.PlotType = 1
            lay.UseStandardScale = False; lay.SetCustomScale(1, 1); lay.CenterPlot = True
            lay.PlotRotation = 0; lay.PlotWithLineweights = True; lay.StyleSheet = "monochrome.ctb"
            doc.SetVariable("BACKGROUNDPLOT", 0)
            doc.Plot.PlotToFile(pdf)
        retry(plot, tries=60, delay=0.5)
        for _ in range(30):
            if os.path.exists(pdf): break
            time.sleep(0.5)
        print("DWG", self.out, "| PDF", pdf if os.path.exists(pdf) else "失败")
        if os.path.exists(pdf):              # 打印用 NoView pc3 后 PDF 不再被 WPS 锁住：把同名的旧时间戳 PDF 清掉
            import glob, re
            base = os.path.splitext(self.out)[0]
            for old in glob.glob(base + "_*.pdf"):
                if old not in (pdf, getattr(self, "check_pdf", None)) and re.search(r"_(check)?\d{6}\.pdf$", old):
                    try: os.remove(old)
                    except OSError: pass
        return False

"""acadkb —— 在 AutoCAD 2024 里"模拟键盘敲命令"画国标工程图的工具库。

分工：COM 只做一次性准备（新建文档、图层、字体、标注样式）和收尾（保存、打印 PDF）；
所有图线 / 尺寸 / 文字都用 pyautogui 往命令行敲，每个对象画完用 ModelSpace.Count 核对，
不够就 Esc + U 撤销后重画（最多 3 次），避免一步错位导致后面全乱。

约定：图形 1:1 按实际尺寸画；图框、标题栏、字高、尺寸样式按 S 倍放大（出图比例 1:S）。
用法见 ../examples/hanger_plate.py。运行期间不能碰键盘鼠标。
"""
import os, time
import pyautogui, win32gui, win32con, win32api, win32clipboard
import win32com.client

pyautogui.PAUSE = 0.02

def retry(fn, tries=100, delay=0.2):
    """AutoCAD 忙时 COM 调用会抛"被呼叫方拒绝接收呼叫"(RPC_E_CALL_REJECTED)，或返回 <unknown> 包装。
    凡是在命令刚结束/文档刚开关后调 COM 的地方都包一层。（本机 pywin32 没有 CoRegisterMessageFilter，无法全局处理）"""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


LAYERS = {  # 名称: (颜色索引, 线型, 线宽 1/100mm)
    "粗实线": (7, "Continuous", 50),
    "细实线": (7, "Continuous", 25),
    "中心线": (1, "CENTER", 25),
    "虚线": (6, "HIDDEN", 25),
    "剖面线": (7, "Continuous", 25),
    "尺寸": (3, "Continuous", 25),
    "文字": (7, "Continuous", 25),
}

# 国标图幅（横放）: (B, L, a 装订边, c 其余边)
SHEETS = {"A4": (210, 297, 25, 5), "A3": (297, 420, 25, 5), "A2": (420, 594, 25, 10),
          "A1": (594, 841, 25, 10), "A0": (841, 1189, 25, 10)}
# "DWG To PDF NoView.pc3"：DWG To PDF.pc3 的副本，只把 View_New_File 改成 FALSE —— 打印完不再自动用 WPS 打开，
# 旧 PDF 就不会被锁住（2026-11-08）。由 ensure_pdf_pc3() 自动生成（解压 pc3、改一行、按 adler32 重写文件头）。
PDF_PC3 = "DWG To PDF NoView.pc3"


def ensure_pdf_pc3():
    import zlib, struct, glob
    for d in glob.glob(os.path.join(os.environ.get("APPDATA", ""), "Autodesk", "AutoCAD 20*", "*", "*", "Plotters")):
        src, dst = os.path.join(d, "DWG To PDF.pc3"), os.path.join(d, PDF_PC3)
        if os.path.exists(dst) or not os.path.exists(src):
            continue
        b = open(src, "rb").read()
        t = zlib.decompress(b[60:]).decode("latin1").replace('name="View_New_File\n  value=TRUE',
                                                              'name="View_New_File\n  value=FALSE')
        c = zlib.compress(t.encode("latin1"))
        open(dst, "wb").write(b[:48] + struct.pack("<III", zlib.adler32(c), len(t), len(c)) + c)


try:
    ensure_pdf_pc3()
except Exception as _ex:      # 生成失败就还用原来的
    print("生成 NoView pc3 失败，改用 DWG To PDF.pc3：", _ex)
    PDF_PC3 = "DWG To PDF.pc3"


PDF_MEDIA = {"A4": "ISO_full_bleed_A4_(297.00_x_210.00_MM)",
             "A3": "ISO_full_bleed_A3_(420.00_x_297.00_MM)",
             "A2": "ISO_full_bleed_A2_(594.00_x_420.00_MM)",
             "A1": "ISO_full_bleed_A1_(841.00_x_594.00_MM)",
             "A0": "ISO_full_bleed_A0_(841.00_x_1189.00_MM)"}


class Drafter:
    def __init__(self, scale=1, wait=0.12, dim_wait=0.3):
        self.S = scale
        self.wait = wait
        self.dim_wait = dim_wait
        self.acad = self._connect()
        self.doc = None

    # ------------------------------------------------------------ 连接/准备
    @staticmethod
    def _connect():
        try:
            return win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception:
            pass
        # COM 冷启动经常报"服务器运行失败"，直接起 exe 再轮询
        os.startfile(r"C:\Program Files\Autodesk\AutoCAD 2024\acad.exe")
        for _ in range(60):
            time.sleep(5)
            try:
                a = win32com.client.GetActiveObject("AutoCAD.Application")
                a.ActiveDocument  # 等到能响应
                return a
            except Exception:
                pass
        raise RuntimeError("AutoCAD 启动超时")

    def focus(self):
        """AutoCAD 切前台 + 强制美式键盘。搜狗等输入法会自己切回中文吞掉字母，所以每次都切并核对。"""
        import win32process, ctypes
        for _ in range(8):
            try:
                hwnd = self.acad.HWND
                pyautogui.press("alt")  # 绕过 Windows 前台锁
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                fg = win32gui.GetForegroundWindow()
                win32api.PostMessage(fg, 0x0050, 0, 0x04090409)  # WM_INPUTLANGCHANGEREQUEST
                time.sleep(0.4)
                tid = win32process.GetWindowThreadProcessId(fg)[0]
                hkl = ctypes.windll.user32.GetKeyboardLayout(tid) & 0xFFFF
                if hkl != 0x0409:
                    raise RuntimeError("键盘布局仍是 %#x" % hkl)
                self._hwnd = fg
                self._pid = win32process.GetWindowThreadProcessId(fg)[1]
                pyautogui.press("esc")
                return
            except Exception as e:
                last = e
                time.sleep(0.5)
        raise RuntimeError(f"无法把 AutoCAD 切到前台/英文键盘: {last}")

    def new_document(self, close_paths=()):
        """新建 acadiso 文档并配置图层/字体/标注样式。close_paths: 要先关掉(不保存)的同名文件。"""
        self.focus(); pyautogui.press("esc"); time.sleep(0.5)
        close = {os.path.abspath(p).lower() for p in close_paths}
        try:
            self.acad.ActiveDocument.SetVariable("SDI", 0)  # SDI=1 时 Documents.Add 报错
        except Exception:
            pass
        docs = retry(lambda: [(d, d.Name, d.FullName) for d in self.acad.Documents])
        for d, name, full in docs:
            if name.startswith("Drawing") or full.lower() in close:
                retry(lambda: d.Close(False))
        for _ in range(20):  # 刚关完文档时 Documents 会短暂失效
            try:
                time.sleep(1)
                self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
                self.doc = self.acad.Documents.Add("acadiso.dwt")
                break
            except Exception:
                pass
        else:
            raise RuntimeError("Documents.Add 失败")
        time.sleep(1.5)
        self.doc = self.acad.ActiveDocument
        self._setup()
        for _ in range(20):  # 刚建完文档时 HWND 也可能"被呼叫方拒绝"
            try:
                win32gui.ShowWindow(self.acad.HWND, win32con.SW_MAXIMIZE)
                break
            except Exception:
                time.sleep(0.5)
        self.focus()   # 含切英文键盘
        self.esc()
        self.k("DYNMODE", "0")  # 动态输入下坐标被当成相对坐标；COM 设不了，只能敲
        self.k("UCS", "W")
        self.esc(); time.sleep(0.5)
        assert self.var("DYNMODE") == 0, "DYNMODE 没关掉"
        return self.doc

    def _setup(self):
        doc, acad, S = self.doc, self.acad, self.S
        for lt in ("CENTER", "HIDDEN"):
            try:
                doc.Linetypes.Load(lt, "acadiso.lin")
            except Exception:
                pass
        for n, (c, lt, lw) in LAYERS.items():
            L = doc.Layers.Add(n)
            tc = acad.GetInterfaceObject("AutoCAD.AcCmColor.24")  # L.color 在晚绑定下设不了
            tc.ColorIndex = c
            L.TrueColor = tc
            L.Linetype = lt
            L.Lineweight = lw
        st = doc.TextStyles.Add("HZ")
        st.fontFile = "gbenor.shx"
        st.BigFontFile = "gbcbig.shx"
        st.Height = 0
        st.Width = 1
        doc.ActiveTextStyle = st
        # 国标尺寸：字高3.5、箭头3、尺寸线间距7、文字与尺寸线对齐
        dv = dict(DIMSCALE=S, DIMTXSTY="HZ", DIMTXT=3.5, DIMASZ=3, DIMEXO=0, DIMEXE=2,
                  DIMGAP=1, DIMDLI=7, DIMDEC=0, DIMTIH=0, DIMTOH=0, DIMTAD=1,
                  DIMLUNIT=2, DIMADEC=0, DIMCLRD=256, DIMCLRE=256, DIMCLRT=256)
        for k, v in dv.items():
            doc.SetVariable(k, v)
        ds = doc.DimStyles.Add("GB"); ds.CopyFrom(doc); doc.ActiveDimStyle = ds
        doc.SetVariable("DIMTIH", 1); doc.SetVariable("DIMTOH", 1)
        for child in ("GB$3", "GB$4"):  # 直径/半径子样式：文字水平
            c = doc.DimStyles.Add(child); c.CopyFrom(doc)
        doc.SetVariable("DIMTIH", 0); doc.SetVariable("DIMTOH", 0)
        doc.ActiveDimStyle = ds
        for k, v in dict(OSMODE=0, ORTHOMODE=0, SNAPMODE=0, GRIDMODE=0, LTSCALE=S * 0.5,
                         PSLTSCALE=0, LWDISPLAY=1, TEXTSTYLE="HZ", BACKGROUNDPLOT=0).items():
            try:
                doc.SetVariable(k, v)
            except Exception:
                pass

    def var(self, name):
        for _ in range(100):
            try:
                return self.doc.GetVariable(name)
            except Exception:  # 命令执行中 COM 会拒绝调用
                time.sleep(0.1)
        raise RuntimeError("AutoCAD 无响应")

    def count(self):
        for _ in range(100):
            try:
                return self.doc.ModelSpace.Count
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("AutoCAD 无响应（多半停在某个命令提示上，截屏看命令行）")

    # ------------------------------------------------------------ 键盘原语
    def k(self, *lines, wait=None):
        """逐行敲入命令行，每行后回车；'' = 单独回车。只能是 ASCII。"""
        w = self.wait if wait is None else wait
        for s in lines:
            if s:
                pyautogui.write(s, interval=0.012)
            pyautogui.press("enter")
            time.sleep(w)

    def esc(self):
        pyautogui.press("esc"); pyautogui.press("esc"); time.sleep(0.15)

    @staticmethod
    def clip(text):
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()

    def paste_enter(self, text):
        self.clip(text)
        pyautogui.hotkey("ctrl", "v"); time.sleep(0.15)
        pyautogui.press("enter"); time.sleep(0.2)

    def ensure(self):
        """前台不是 AutoCAD 或输入法被切成中文时，重新 focus()。"""
        import win32process, ctypes
        fg = win32gui.GetForegroundWindow()
        tid, pid = win32process.GetWindowThreadProcessId(fg)
        hkl = ctypes.windll.user32.GetKeyboardLayout(tid) & 0xFFFF
        # 命令行/在位编辑器是 acad 自己的 WPF 子窗口，前台是它们也算正常
        if pid != getattr(self, "_pid", None) or hkl != 0x0409:
            print("  前台/键盘被改动，重新 focus: pid=%s hkl=%#x" % (pid, hkl))
            self.focus()

    def checked(self, n_add, fn, *a):
        """执行 fn，核对新增对象数，不足就撤销重做。"""
        for attempt in range(3):
            self.ensure()
            n0 = self.count()
            fn(*a)
            time.sleep(0.3)
            got = self.count() - n0
            if got >= n_add:
                return
            print(f"  重做 {fn.__name__}{a[:2]}: 新增 {got}/{n_add}")
            self.esc(); time.sleep(0.5)
            if got:
                self.k("U"); self.esc()
        raise RuntimeError(f"{fn.__name__}{a} 连续 3 次失败，截屏(F2 看命令历史)排查")

    @staticmethod
    def P(p):
        return "%g,%g" % p

    # ------------------------------------------------------------ 绘图命令
    def layer(self, name):
        self.k("CLAYER")
        self.paste_enter(name)  # 中文图层名：命令行里 Ctrl+V 可以用

    def zoom_extents(self):
        """点选对象(圆/弧)前必须先让它在屏幕上可见，否则 *Invalid selection*。"""
        self.k("ZOOM", "E", wait=0.5)

    def rect(self, p1, p2):
        self.checked(1, lambda: self.k("RECTANG", self.P(p1), self.P(p2)))

    def line(self, *pts):
        self.checked(len(pts) - 1, lambda: self.k("LINE", *map(self.P, pts), ""))

    def pline(self, *pts, close=False):
        self.checked(1, lambda: self.k("PLINE", *map(self.P, pts), "C" if close else ""))

    def circle(self, c, r):
        self.checked(1, lambda: self.k("CIRCLE", self.P(c), "%g" % r))

    def arc(self, center, start, end):
        """圆心-起点-端点，逆时针。"""
        self.checked(1, lambda: self.k("ARC", "C", self.P(center), self.P(start), self.P(end)))

    def center_cross(self, c, r, ext=5):
        """孔的十字中心线，超出圆 ext。调用前切到中心线层。"""
        x, y = c
        e = r + ext
        self.line((x - e, y), (x + e, y))
        self.line((x, y - e), (x, y + e))

    def hatch(self, inside_pt, pattern="ANSI31", scale=None):
        """在封闭区域内点一点填充剖面线（区域须在屏幕上可见）。"""
        sc = "%g" % (scale or self.S)
        self.checked(1, lambda: self.k("-HATCH", "P", pattern, sc, "0", self.P(inside_pt), "", wait=0.4))

    def text(self, p, h, s, just="MC"):
        """单行文字。h 为图纸字高(mm)，自动乘 S。just=None 表示左对齐（p 为左下起点）。
        总是显式给 J：不带 J 时 AutoCAD 会沿用上一次的对齐方式（TEXTJUSTIFY）。"""
        H = "%g" % (h * self.S)
        jj = just or "L"
        def _t():
            self.k("TEXT", "J", jj, self.P(p), H, "0", wait=0.15)
            time.sleep(0.5)
            self.clip(s)
            pyautogui.hotkey("ctrl", "v"); time.sleep(0.3)
            pyautogui.press("enter"); time.sleep(0.4)   # 换行
            pyautogui.press("enter"); time.sleep(0.6)   # 空行回车 = 结束
        _t.__name__ = "text"
        self.checked(1, _t)

    def leader(self, pts, s):
        """带箭头引线 + 注释文字。pts[0] 是箭头尖（落在被注对象上），最后一点是文字处，
        最后一段水平。倒角注法：箭头指在倒角斜线上，引线沿 45° 引出，再水平引出，写 C1 或 2×C1。"""
        def _l():
            self.k("LEADER", *map(self.P, pts), "", wait=self.dim_wait)
            self.clip(s)
            pyautogui.hotkey("ctrl", "v"); time.sleep(0.2)
            pyautogui.press("enter"); time.sleep(0.3)   # 第二行提示
            pyautogui.press("enter"); time.sleep(0.5)   # 空行结束
        _l.__name__ = "leader"
        self.checked(1, _l)

    def dimlin(self, p1, p2, loc, text=None):
        """线性尺寸。loc 在两点 x 范围外 → 竖直尺寸；在 y 范围外 → 水平尺寸。
        text 可覆盖文字，如 '%%C30H7'、'2\\U+00D7%%C12'（× 要写成 \\U+00D7）。"""
        w = self.dim_wait
        seq = ["DIMLINEAR", self.P(p1), self.P(p2)] + (["T", text] if text else []) + [self.P(loc)]
        self.checked(1, lambda: self.k(*seq, wait=w))

    def dimcont(self, *pts):
        w = self.dim_wait
        def _c():
            self.k("DIMCONTINUE", *map(self.P, pts), "", "", wait=w); self.esc()
        self.checked(len(pts), _c)

    def dimbase(self, *pts):
        w = self.dim_wait
        def _b():
            self.k("DIMBASELINE", *map(self.P, pts), "", "", wait=w); self.esc()
        self.checked(len(pts), _b)

    def _radial(self, cmd, on_curve, loc, text):
        w = self.dim_wait
        seq = [cmd, self.P(on_curve)] + (["T", text] if text else []) + [self.P(loc)]
        self.checked(1, lambda: self.k(*seq, wait=w))

    def dimdia(self, on_circle, loc, text=None):
        """on_circle 必须精确落在圆上（如 (cx+r*0.7071, cy+r*0.7071)）且圆在屏幕可见。"""
        self._radial("DIMDIAMETER", on_circle, loc, text)

    def dimrad(self, on_arc, loc, text=None):
        self._radial("DIMRADIUS", on_arc, loc, text)

    # ------------------------------------------------------------ 图框/标题栏
    def frame(self, size="A3"):
        """画国标横放图框，返回内框 (x0, y0, x1, y1)（已乘 S）。"""
        B, L, a, c = SHEETS[size]
        S = self.S
        self.layer("细实线"); self.rect((0, 0), (L * S, B * S))
        self.zoom_extents()
        self.layer("粗实线")
        box = (a * S, c * S, (L - c) * S, (B - c) * S)
        self.rect(box[:2], box[2:])
        self.sheet = size
        return box

    def title_block(self, inner, name, code, scale_txt, material, designer, date,
                    school=("机械电子工程", "毕业设计")):
        """学生用简化标题栏 180×40，放在内框右下角。"""
        S = self.S
        X, Y = inner[2] - 180 * S, inner[1]
        u = lambda x, y: (X + x * S, Y + y * S)
        self.layer("粗实线"); self.rect(u(0, 0), u(180, 40))
        self.layer("细实线")
        for y in (10, 20, 30):
            self.line(u(0, y), u(80, y))
        self.line(u(15, 0), u(15, 40)); self.line(u(50, 0), u(50, 40))
        self.layer("粗实线")
        self.line(u(80, 0), u(80, 40)); self.line(u(130, 0), u(130, 40)); self.line(u(80, 20), u(180, 20))
        self.layer("细实线")
        self.line(u(80, 10), u(130, 10)); self.line(u(100, 0), u(100, 20))
        self.layer("文字")
        for i, lab in enumerate(("设计", "校核", "审核", "批准")):
            self.text(u(7.5, 35 - 10 * i), 3.5, lab)
        self.text(u(32.5, 35), 3.5, designer)
        self.text(u(65, 35), 3.5, date)
        self.text(u(105, 30), 7, name)
        self.text(u(90, 15), 3.5, "比例"); self.text(u(115, 15), 3.5, scale_txt)
        self.text(u(90, 5), 3.5, "材料"); self.text(u(115, 5), 3.5, material)
        self.text(u(155, 30), 5, code)
        self.text(u(155, 14), 3.5, school[0])
        if len(school) > 1:
            self.text(u(155, 6), 3.5, school[1])

    def tech_notes(self, p, items, title="技术要求"):
        S = self.S
        self.layer("文字")
        x, y = p
        self.text((x, y), 5, title, just=None)
        for i, s in enumerate(items):
            self.text((x + 5 * S, y - (12.5 + 9 * i) * S), 3.5, f"{i + 1}. {s}", just=None)

    # ------------------------------------------------------------ 收尾
    def save_and_plot(self, dwg, pdf=None):
        """保存 DWG 并按图幅/比例出 PDF（单色、带线宽）。返回实际 PDF 路径。"""
        self.esc(); self.zoom_extents(); time.sleep(0.5)
        self.doc.SaveAs(dwg)
        if not pdf:
            return None
        if os.path.exists(pdf):
            try:
                os.remove(pdf)
            except OSError:  # 旧 PDF 被阅读器占用时 PlotToFile 会静默不覆盖
                base, ext = os.path.splitext(pdf)
                pdf = base + time.strftime("_%H%M%S") + ext
                print("旧 PDF 被占用，改存为", pdf)
        for _ in range(30):  # SaveAs 后旧的 doc 包装会短暂变成 <unknown>，重新取
            try:
                time.sleep(0.5)
                self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
                self.doc = self.acad.ActiveDocument
                lay = self.doc.ActiveLayout
                break
            except Exception:
                pass
        else:
            raise RuntimeError("取不到 ActiveLayout")
        lay.RefreshPlotDeviceInfo()
        try:
            lay.ConfigName = PDF_PC3
        except Exception:
            lay.ConfigName = "DWG To PDF.pc3"
        lay.RefreshPlotDeviceInfo()
        lay.CanonicalMediaName = PDF_MEDIA[getattr(self, "sheet", "A3")]
        lay.PlotType = 1  # acExtents：图框外框就是图纸边界
        lay.UseStandardScale = False
        lay.SetCustomScale(1, self.S)
        lay.CenterPlot = True
        lay.PlotRotation = 0
        lay.PlotWithLineweights = True
        lay.StyleSheet = "monochrome.ctb"
        self.doc.Plot.PlotToFile(pdf)
        for _ in range(30):
            if os.path.exists(pdf):
                break
            time.sleep(0.5)
        return pdf

    def report(self):
        """列出模型空间对象统计 + 所有文字/尺寸覆盖文字，用于核对。"""
        from collections import Counter
        c = Counter()
        lines = []
        for e in self.doc.ModelSpace:
            n = e.ObjectName
            c[n] += 1
            if n == "AcDbText":
                lines.append("  文字: " + e.TextString)
            elif "Dimension" in n:
                lines.append(f"  尺寸: {round(e.Measurement, 2)} {e.TextOverride}")
        print(dict(c))
        print("\n".join(lines))


def render_pdf(pdf, png, dpi=130):
    """PDF 第一页转 PNG，用 Read 看效果。"""
    import fitz
    fitz.open(pdf)[0].get_pixmap(dpi=dpi).save(png)
    return png

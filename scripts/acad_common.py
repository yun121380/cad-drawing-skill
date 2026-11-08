"""AutoCAD 公共部分：COM 重试、国标图层/图幅、文档初始化（图层、HZ 字体、GB 标注样式）、PDF 打印配置。
原来放在 acadkb.py（模拟键盘逐笔画的老路线）里，2026-11-08 删掉那条路线后挪到这里，sw2acad 用。"""
import os, time


def retry(fn, tries=100, delay=0.2):
    """AutoCAD 忙时 COM 调用会抛"被呼叫方拒绝接收呼叫"(RPC_E_CALL_REJECTED)，或返回 <unknown> 包装。
    凡是在命令刚结束/文档刚开关后调 COM 的地方都包一层。有副作用的调用（Open/Add/Close）别整个包进来，见 SKILL.md。"""
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

PDF_MEDIA = {"A4": "ISO_full_bleed_A4_(297.00_x_210.00_MM)",
             "A3": "ISO_full_bleed_A3_(420.00_x_297.00_MM)",
             "A2": "ISO_full_bleed_A2_(594.00_x_420.00_MM)",
             "A1": "ISO_full_bleed_A1_(841.00_x_594.00_MM)",
             "A0": "ISO_full_bleed_A0_(841.00_x_1189.00_MM)"}

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


def setup_doc(doc, acad, S=1):
    """国标图层、HZ 字体（gbenor + gbcbig）、GB 标注样式（字高 3.5、箭头 3、文字与尺寸线对齐；直径/半径子样式文字水平）。
    S = 出图比例的倒数（1:2 传 2），标注样式按它放大。"""
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

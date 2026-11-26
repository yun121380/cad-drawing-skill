"""env_check —— 换电脑 / 重装软件后先跑一遍：python env_check.py
逐项检查这套流程依赖的东西，缺什么打印什么、该改 config.json 的哪一项。不启动 SW/AutoCAD，不改任何文件。"""
import os, sys, json, glob, importlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ok_all = True


def item(name, ok, hint=""):
    global ok_all
    ok_all &= bool(ok)
    print(("  [OK] " if ok else "  [缺] ") + name + ("" if ok else f"  —— {hint}"))


cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
print("== 软件路径（config.json）")
acad = cfg.get("acad_exe", "")
item(f"AutoCAD  {acad}", os.path.exists(acad), "改 config.json 的 acad_exe（要 AutoCAD 2018 以上，COM 名 AutoCAD.Application）")
item(f"SolidWorks  {cfg.get('sw_exe')}", os.path.exists(cfg.get("sw_exe", "")), "改 sw_exe")
tpl = cfg.get("sw_templates", "")
for t in ("gb_part.prtdot", "gb_a3.drwdot", "gb_a2.drwdot"):
    item(f"SW 国标模板 {t}", os.path.exists(os.path.join(tpl, t)), "改 sw_templates（SW 选项→文件位置→文件模板）")
lib = cfg.get("toolbox_gb", "")
import sw_std
for k, (rel, *_r) in sw_std.KINDS.items():
    item(f"Toolbox GB 基础零件 {k}", os.path.exists(os.path.join(lib, rel)), "改 toolbox_gb，或在 SW 里装 Toolbox GB 库")

print("== AutoCAD 字体 / 打印")
fonts = glob.glob(os.path.join(os.path.dirname(acad), "Fonts", "gbenor.shx")) + \
    glob.glob(os.path.join(os.path.dirname(acad), "Fonts", "gbcbig.shx"))
item("gbenor.shx + gbcbig.shx", len(fonts) == 2, "AutoCAD 安装目录 Fonts 下要有这两个国标字体")
pc3 = glob.glob(os.path.join(os.environ.get("APPDATA", ""), "Autodesk", "AutoCAD 20*", "*", "*", "Plotters", "DWG To PDF.pc3"))
item("DWG To PDF.pc3", bool(pc3), "先手动打开一次 AutoCAD，让它生成用户 Plotters 目录")

print("== Python 包（装在用户 site-packages；别用 python -I）")
for m in ("win32com.client", "pythoncom", "fitz", "ezdxf", "shapely", "numpy", "scipy"):
    try:
        importlib.import_module(m); item(m, True)
    except Exception as ex:
        item(m, False, f"pip install {'pywin32' if 'win32' in m or m == 'pythoncom' else 'pymupdf' if m == 'fitz' else m}（{ex}）")

print("== 自带模块自测")
import gbtol
bad = gbtol._selftest()
item("gbtol 公差表 40 个常用值", not bad, f"对不上：{bad}")
import sw_mem
gb = sw_mem.private_gb()
item(f"sw_mem 读进程内存（SW 当前 {gb:.2f} GB，上限 {sw_mem.limit_default()} GB）", True)

print("== 结论：", "全部通过" if ok_all else "有缺项，按上面提示改 config.json 或安装后再跑")

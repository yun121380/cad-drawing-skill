import fitz, glob, os, sys
pdf = sorted([f for f in glob.glob("轴承座_*.pdf") if "check" not in f], key=os.path.getmtime)[-1]
d = fitz.open(pdf); p = d[0]; s = 72 / 25.4; H = 297
p.get_pixmap(dpi=130).save("chk_full.png")
for n, (x0, y0, x1, y1) in {"front": (22, 120, 215, 292), "aa": (185, 120, 345, 292), "top": (22, 30, 245, 125), "det": (315, 100, 415, 210)}.items():
    p.get_pixmap(dpi=220, clip=fitz.Rect(x0 * s, (H - y1) * s, x1 * s, (H - y0) * s)).save(f"chk_{n}.png")
print(pdf)

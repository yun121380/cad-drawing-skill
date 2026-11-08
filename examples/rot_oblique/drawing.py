"""旋转剖 + 局部斜视图演示的 AutoCAD 整理。坐标全部来自 views.py 写的 layout.json。"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from sw2acad import Sheet, P

D = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(D, "layout.json"), encoding="utf-8"))
sp, ap, fp, tp = L["splice"], L["aux_pts"], L["fr_pts"], L["top_pts"]
off = lambda p, dx=0, dy=0: (p[0] + dx, p[1] + dy)

with Sheet(D + r"\rb_sw.DWG", D + r"\旋转剖与斜视图.dwg", views=L["VIEWS"]) as s:
    s.frame()
    s.title_block_gb("摇臂与弯板", "SL-RB-01", material="Q235A", scale="1:1",
                     date="2026.11")
    # ---------------- 旋转剖：S1 留 +X 半边，S2 的斜臂半边转过来拼上
    side_boss = (lambda a0, a1, q: 1 if (a1[0] - a0[0]) * (q[1] - a0[1]) - (a1[1] - a0[1]) * (q[0] - a0[0]) >= 0 else -1)(
        *sp["src_axis"], sp["src_boss"])
    s.splice_aligned(sp["keep_box"], sp["axis_x"], sp["keep_side"], sp["src_box"], sp["src_axis"], side_boss,
                     sp["src_pts"], sp["dst_pts"])
    s.erase_text("Z"); s.erase_text("Z-Z")
    # 俯视图上 SW 的直剖切线（沿 X 轴）换成折线剖切符号：两端各删掉 SW 的短画/箭头/字母，删掉沿线的虚线
    (x0, y0), (x1, y1) = sp["s1_line"]
    for x in (x0, x1):
        s.erase_in((x - 13, y0 - 13, x + 13, y0 + 14))
    s.erase_text("A")
    hub, e1 = tp["hub"], (x1 - 6, y0)
    a = math.radians(150); dsh = (math.cos(a), -math.sin(a))          # 斜臂方向（图纸坐标，俯视图 Z 朝下）
    e2 = (hub[0] + 80 * dsh[0], hub[1] + 80 * dsh[1])
    s.cut_path([e1, hub, e2])
    for e in s._items():                                              # 主剖切线在轮毂左边那段（沿 X 轴的虚线）
        if e.ObjectName == "AcDbLine" and e.Layer == "虚线":
            sp_, ep_ = e.StartPoint, e.EndPoint
            if abs(sp_[1] - y0) < 0.1 and abs(ep_[1] - y0) < 0.1 and min(sp_[0], ep_[0]) < hub[0] - 1:
                e.Delete()
    s.cut_end(e1, (-1, 0), (0, 1), "A")
    perp = [(-dsh[1], dsh[0]), (dsh[1], -dsh[0])]
    s.cut_end(e2, (-dsh[0], -dsh[1]), max(perp, key=lambda v: v[1]), "A")     # 箭头朝剖视图那边（向上）
    s.line((hub[0], sp["dst_pts"][0][1] - 4), (hub[0], sp["dst_pts"][1][1] + 4))      # 剖视图里轮毂轴线
    # ---------------- 斜视图：SW 的“视图 B ⌒45°”换成国标的“B + 旋转符号”；孔的中心线摆正
    s.erase_text(r"视图\s*[A-Z].*", regex=True); s.erase_text(r"[\d.]+\s*°", regex=True)
    # 主视图上斜视图的投射箭头：SW 导出的字母 "B" 有两份、而且压在箭头上 —— 留一份，挪到箭头尾部右上方
    import re
    bs = [e for e in s._items() if e.ObjectName in ("AcDbText", "AcDbMText") and
          re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", e.TextString).strip() == "B" and e.InsertionPoint[1] > 150]
    for e in bs[1:]:
        e.Delete()
    if bs:
        q = bs[0].InsertionPoint
        bs[0].Move(P(q[0], q[1]), P(q[0] - 1, q[1] + 5))
    vb = L["VIEWS"][3]
    s.rot_label(((vb[0] + vb[2]) / 2 - 4, vb[3] + 5), "B", ccw=False)
    s.center_cross(ap["hole"], 10)
    # ---------------- 尺寸（少量，验证位置对得上）
    s.dimlin(sp["dst_pts"][0], (sp["dst_pts"][0][0] + 70, sp["dst_pts"][0][1]), (sp["dst_pts"][0][0] + 35, 160))  # 70
    s.dimlin(sp["dst_pts"][2], sp["dst_pts"][0], ((sp["dst_pts"][2][0] + sp["dst_pts"][0][0]) / 2, 160))       # 60（真长）
    s.ms.AddDimAngular(P(*hub), P(hub[0] + 30, hub[1]), P(hub[0] + 30 * dsh[0], hub[1] + 30 * dsh[1]),
                       P(hub[0] + 12, hub[1] + 20)).TextOverride = "150%%D"
    s.dimlin(ap["end_lo"], ap["end_hi"], (ap["end_lo"][0] + 12, (ap["end_lo"][1] + ap["end_hi"][1]) / 2), 90)  # 60
    d = s.dimdia(ap["hole"], 10, 135, 12, "%%C20")
    s.dimlin(ap["hole"], (ap["end_lo"][0], ap["hole"][1]), (ap["hole"][0] + 15, ap["end_lo"][1] - 6))           # 30
    s.dimlin(fp["b0"], fp["b1"], (fp["b0"][0] + 50, fp["b0"][1] - 9))                                             # 100
    s.dimlin(fp["b0"], fp["t0"], (fp["b0"][0] - 7, fp["b0"][1] + 5), 90)                                          # 10
    s.ms.AddDimAngular(P(*fp["A"]), P(*fp["A20"]), P(*fp["U20"]), P(fp["A"][0] + 22, fp["A"][1] + 7)).TextOverride = "45%%D"
    s.check()

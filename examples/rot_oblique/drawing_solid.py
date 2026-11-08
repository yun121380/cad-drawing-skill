"""实心轮毂摇臂旋转剖的 AutoCAD 拼接（视图见 views_solid.py）：剖面线跨轴线，splice_aligned 自动按轴线裁。"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from sw2acad import Sheet, P

D = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(D, "layout_solid.json"), encoding="utf-8"))
sp = L["splice"]
with Sheet(D + r"\rs_sw.DWG", D + r"\实心轮毂旋转剖.dwg", views=L["VIEWS"]) as s:
    s.frame()
    s.title_block_gb("摇臂（实心轮毂）", "SL-RS-01", material="Q235A", scale="1:1", date="2026.11")
    side_boss = (lambda a0, a1, q: 1 if (a1[0] - a0[0]) * (q[1] - a0[1]) - (a1[1] - a0[1]) * (q[0] - a0[0]) >= 0 else -1)(
        *sp["src_axis"], sp["src_boss"])
    s.splice_aligned(sp["keep_box"], sp["axis_x"], sp["keep_side"], sp["src_box"], sp["src_axis"], side_boss,
                     sp["src_pts"], sp["dst_pts"])
    s.erase_text("Z"); s.erase_text("Z-Z")
    # 俯视图：SW 的直剖切线换成折线剖切符号
    (x0, y0), (x1, y1) = sp["s1_line"]
    for x in (x0, x1):
        s.erase_in((x - 13, y0 - 13, x + 13, y0 + 14))
    s.erase_text("A")
    hub, e1 = L["hub"], (x1 - 6, y0)
    a = math.radians(150); dsh = (math.cos(a), -math.sin(a))
    e2 = (hub[0] + 80 * dsh[0], hub[1] + 80 * dsh[1])
    s.cut_path([e1, hub, e2])
    for e in s._items():
        if e.ObjectName == "AcDbLine" and e.Layer == "虚线":
            sp_, ep_ = e.StartPoint, e.EndPoint
            if abs(sp_[1] - y0) < 0.1 and abs(ep_[1] - y0) < 0.1 and min(sp_[0], ep_[0]) < hub[0] - 1:
                e.Delete()
    s.cut_end(e1, (-1, 0), (0, 1), "A")
    perp = [(-dsh[1], dsh[0]), (dsh[1], -dsh[0])]
    s.cut_end(e2, (-dsh[0], -dsh[1]), max(perp, key=lambda v: v[1]), "A")
    ax = sp["axis_x"]; yb, yt = sp["dst_pts"][0][1], sp["dst_pts"][1][1]
    s.line((ax, yb - 4), (ax, yt + 4))                       # 剖视图里轮毂轴线（点画线，压在剖面线分界上）
    s.view_label("A-A", ((sp["dst_pts"][2][0] - 13 + sp["keep_box"][2]) / 2, sp["keep_box"][3] + 8))   # 拼接后视图变宽，视图名居中
    s.dimlin(sp["dst_pts"][0], (sp["dst_pts"][0][0] + 70, sp["dst_pts"][0][1]), (ax + 35, yb - 10))
    s.dimlin(sp["dst_pts"][2], sp["dst_pts"][0], ((sp["dst_pts"][2][0] + ax) / 2, yb - 10))
    s.check()

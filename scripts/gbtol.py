"""gbtol —— GB/T 1800.1-2020（≡ISO 286-1）公差查表，GB/T 1095 键槽，GB/T 1804 一般公差（2026-11-08）。

图上的 k6、H7、N9 偏差值不要再手写：
    import gbtol as T
    T.limits("k6", 35)            -> (0.018, 0.002)        单位 mm（上偏差, 下偏差）
    T.limits("H7", 62)            -> (0.030, 0.0)
    T.tol_text("%%C35k6")         -> "%%C35k6({\\H0.7x;\\S+0.018^+0.002;})"   给 dimlin 的 txt
    T.tol_text("%%C40js6")        -> "%%C40js6(%%P0.008)"
    T.tol_text("12N9", code=False)-> "12({\\H0.7x;\\S0^-0.043;})"            只写偏差不写代号
    T.tol_text("%%C40H7/r6")      -> 原样返回（装配图配合代号不注偏差）
    T.verify_text(dim.TextOverride) -> None 或 "k6 Φ35 应为 +0.018/+0.002，图上写了 ..."
    T.keyway(40)                  -> GB/T 1095 键槽 dict（b、h、t1、t2、轴槽深 d-t1、毂槽深 d+t2 及偏差）
    T.general("m", 120)           -> 0.3     GB/T 1804 线性尺寸一般公差 ±

表格范围：基本尺寸 0~500 mm；轴 a b c cd d e ef f fg g h js j k m n p r s t u，孔同字母大写（J 只有 6/7/8 级）。
数值按 GB/T 1800.1-2020 表 1（标准公差）、表 2/表 3（基本偏差、Δ 值）录入，模块自测见文件末尾 _selftest()。"""
import re

# ---------------------------------------------------------------- 尺寸分段（大于 a 至 b）
R13 = [3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]                      # 主段
R23 = [3, 6, 10, 14, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450, 500]  # 细分段


def _idx(size, bounds):
    if not (0 < size <= bounds[-1]):
        raise ValueError(f"基本尺寸 {size} 超出 0~{bounds[-1]} mm")
    for i, b in enumerate(bounds):
        if size <= b:
            return i


def _sub(size, table):
    """table 按 R23 细分段给（25 个值）；也接受按 R13 给的 13 个值。"""
    if len(table) == len(R13):
        return table[_idx(size, R13)]
    return table[_idx(size, R23)]


# ---------------------------------------------------------------- 标准公差 IT1~IT18（μm），13 个主段
IT = {
    1:  [0.8, 1, 1, 1.2, 1.5, 1.5, 2, 2.5, 3.5, 4.5, 6, 7, 8],
    2:  [1.2, 1.5, 1.5, 2, 2.5, 2.5, 3, 4, 5, 7, 8, 9, 10],
    3:  [2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15],
    4:  [3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20],
    5:  [4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27],
    6:  [6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40],
    7:  [10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63],
    8:  [14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97],
    9:  [25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155],
    10: [40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250],
    11: [60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400],
    12: [100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630],
    13: [140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970],
    14: [250, 300, 360, 430, 520, 620, 740, 870, 1000, 1150, 1300, 1400, 1550],
    15: [400, 480, 580, 700, 840, 1000, 1200, 1400, 1600, 1850, 2100, 2300, 2500],
    16: [600, 750, 900, 1100, 1300, 1600, 1900, 2200, 2500, 2900, 3200, 3600, 4000],
    17: [1000, 1200, 1500, 1800, 2100, 2500, 3000, 3500, 4000, 4600, 5200, 5700, 6300],
    18: [1400, 1800, 2200, 2700, 3300, 3900, 4600, 5400, 6300, 7200, 8100, 8900, 9700],
}


def it(grade, size):
    """标准公差值 μm。"""
    return IT[int(grade)][_idx(size, R13)]


# ---------------------------------------------------------------- 轴的基本偏差（μm）
# 上偏差 es（a~h）：
_ES = {
    "a": [-270, -270, -280, -290, -290, -300, -300, -310, -320, -340, -360, -380, -410, -460, -520, -580, -660, -740, -820, -920, -1050, -1200, -1350, -1500, -1650],
    "b": [-140, -140, -150, -150, -150, -160, -160, -170, -180, -190, -200, -220, -240, -260, -280, -310, -340, -380, -420, -480, -540, -600, -680, -760, -840],
    "c": [-60, -70, -80, -95, -95, -110, -110, -120, -130, -140, -150, -170, -180, -200, -210, -230, -240, -260, -280, -300, -330, -360, -400, -440, -480],
    "d": [-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230],
    "e": [-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135],
    "f": [-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68],
    "g": [-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20],
    "h": [0] * 13,
}
_ES_SMALL = {"cd": [-34, -46, -56], "ef": [-10, -14, -18], "fg": [-4, -6, -8]}      # 只到 10 mm
# 下偏差 ei（k~u），13 主段或 25 细分段：
_EI = {
    "m": [2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23],
    "n": [4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40],
    "p": [6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68],
    "r": [10, 15, 19, 23, 23, 28, 28, 34, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94, 98, 108, 114, 126, 132],
    "s": [14, 19, 23, 28, 28, 35, 35, 43, 43, 53, 59, 71, 79, 92, 100, 108, 122, 130, 140, 158, 170, 190, 208, 232, 252],
    "t": [None, None, None, None, None, None, 41, 48, 54, 66, 75, 91, 104, 122, 134, 146, 166, 180, 196, 218, 240, 268, 294, 330, 360],
    "u": [18, 23, 28, 33, 33, 41, 48, 60, 70, 87, 102, 124, 144, 170, 190, 210, 236, 258, 284, 315, 350, 390, 435, 490, 540],
}
_K47 = [0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5]                 # k 的 ei：IT4~IT7；≤IT3 和 >IT7 为 0
_J = {5: [-2, -2, -2, -3, -4, -5, -7, -9, -11, -13, -16, -18, -20],          # j 的 ei
      6: [-2, -2, -2, -3, -4, -5, -7, -9, -11, -13, -16, -18, -20],
      7: [-4, -4, -5, -6, -8, -10, -12, -15, -18, -21, -26, -28, -32]}
# 孔 J 的 ES（GB/T 1800.1 表 3）
_JH = {6: [2, 5, 5, 6, 8, 10, 13, 16, 18, 22, 25, 29, 33],
       7: [4, 6, 8, 10, 12, 14, 18, 22, 26, 30, 36, 39, 43],
       8: [6, 10, 12, 15, 20, 24, 28, 34, 41, 47, 55, 60, 66]}
# Δ 值（IT3~IT8），13 主段
_DELTA = {3: [0, 1, 1, 1, 1.5, 1.5, 2, 2, 3, 3, 4, 4, 5],
          4: [0, 1.5, 1.5, 2, 2, 3, 3, 4, 4, 4, 4, 5, 5],
          5: [0, 1, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7, 7],
          6: [0, 3, 3, 3, 4, 5, 6, 7, 7, 9, 9, 11, 13],
          7: [0, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23],
          8: [0, 6, 7, 9, 12, 14, 16, 19, 23, 26, 29, 32, 34]}


def _js(grade, size):
    # GB/T 1800.1-2020（ISO 286-1:2010）：±IT/2，不再按老标准把奇数 IT 往下凑偶数（JS9 b=12 → ±0.0215）
    return it(grade, size) / 2


def shaft_dev(letter, grade, size):
    """轴的极限偏差 (es, ei)，μm。"""
    g = int(grade); T = it(g, size)
    if letter in _ES:
        es = _sub(size, _ES[letter]); return es, es - T
    if letter in _ES_SMALL:
        if size > 10:
            raise ValueError(f"{letter} 只用于 ≤10 mm")
        es = _ES_SMALL[letter][_idx(size, [3, 6, 10])]; return es, es - T
    if letter == "js":
        h = _js(g, size); return h, -h
    if letter == "j":
        if g not in _J:
            raise ValueError("轴 j 只有 5/6/7 级")
        ei = _J[g][_idx(size, R13)]
        if g == 6 and size <= 3:
            return 4, -2                                        # j6 ≤3 mm 特例
        return ei + T, ei
    if letter == "k":
        ei = _K47[_idx(size, R13)] if 4 <= g <= 7 else 0
        return ei + T, ei
    if letter in _EI:
        ei = _sub(size, _EI[letter])
        if ei is None:
            raise ValueError(f"{letter} 在 {size} mm 没有值（t 从 24 mm 起）")
        return ei + T, ei
    raise ValueError(f"轴的基本偏差 {letter!r} 不在表里")


def hole_dev(letter, grade, size):
    """孔的极限偏差 (ES, EI)，μm。"""
    L = letter.lower(); g = int(grade); T = it(g, size)
    if L in _ES or L in _ES_SMALL:                       # A~H：EI = −es
        es, _ = shaft_dev(L, g, size); EI = -es; return EI + T, EI
    if L == "js":
        h = _js(g, size); return h, -h
    if L == "j":
        if g not in _JH:
            raise ValueError("孔 J 只有 6/7/8 级")
        ES = _JH[g][_idx(size, R13)]; return ES, ES - T
    i = _idx(size, R13)
    D = _DELTA[g][i] if 3 <= g <= 8 else 0
    if L == "k":
        if size <= 3: ES = 0
        else: ES = (-_K47[i] + D) if g <= 8 else 0
        return ES, ES - T
    if L == "m":
        m = _EI["m"][i]
        if size <= 3: ES = -2
        else: ES = (-m + D) if g <= 8 else -m
        return ES, ES - T
    if L == "n":
        n = _EI["n"][i]
        if size <= 3: ES = -4
        else: ES = (-n + D) if g <= 8 else 0
        return ES, ES - T
    if L in ("p", "r", "s", "t", "u"):
        ei = _sub(size, _EI[L])
        if ei is None:
            raise ValueError(f"{letter} 在 {size} mm 没有值")
        ES = -ei + (D if g <= 7 else 0)
        return ES, ES - T
    raise ValueError(f"孔的基本偏差 {letter!r} 不在表里")


_CODE = re.compile(r"^([A-Za-z]{1,2})(\d{1,2})$")


def dev(code, size):
    """'k6' / 'H7' → (上偏差, 下偏差) μm。大写 = 孔，小写 = 轴。"""
    m = _CODE.match(code)
    if not m:
        raise ValueError(f"公差带代号 {code!r} 写法不对")
    L, g = m.group(1), int(m.group(2))
    return hole_dev(L, g, size) if L[0].isupper() else shaft_dev(L, g, size)


def limits(code, size):
    """→ (上偏差, 下偏差)，单位 mm。"""
    a, b = dev(code, size)
    return round(a / 1000, 4), round(b / 1000, 4)


def fmt(v_mm):
    """偏差写法：0 写 '0'，其余带符号三位小数（半微米时四位）。"""
    if abs(v_mm) < 1e-9:
        return "0"
    s = f"{v_mm:+.4f}"
    return s[:-1] if s.endswith("0") else s


STACK = "({\\H0.7x;\\S%s^%s;})"
_TXT = re.compile(r"^(?P<pre>.*?)(?P<dia>%%[Cc])?(?P<n>\d+(?:\.\d+)?)(?P<code>[A-Za-z]{1,2}\d{1,2})(?P<rest>.*)$")


def tol_text(txt, code=True):
    """'%%C35k6' → 带叠写极限偏差的尺寸文字（零件图用）。前缀（'2×'）保留；'H7/r6' 这种配合代号原样返回。
    code=False：只写偏差（如键槽宽 '12N9' → '12(0/-0.043)'）。"""
    if "/" in txt or "\\S" in txt:
        return txt
    m = _TXT.match(txt)
    if not m or m.group("rest"):
        raise ValueError(f"看不懂 {txt!r}：要写成 [前缀][%%C]基本尺寸+公差带，如 %%C35k6")
    n = float(m.group("n")); c = m.group("code")
    hi, lo = limits(c, n)
    head = m.group("pre") + (m.group("dia") or "") + m.group("n") + (c if code else "")
    if c.lower().startswith("js"):
        return head + f"(%%P{fmt(hi)[1:]})"
    return head + STACK % (fmt(hi), fmt(lo))


_STK = re.compile(r"\\S([+\-]?[\d.]+)\^([+\-]?[\d.]+);")


def verify_text(txt):
    """核对尺寸文字里手写的偏差和公差带代号是否一致。没有代号或没有偏差的文字返回 None；对得上返回 None；
    对不上返回说明字符串。只认 '%%C35k6({\\H0.7x;\\S+0.018^+0.002;})' 和 '(%%P0.008)' 两种写法。"""
    if not txt or "/" in txt.split("(")[0]:
        return None
    t = re.sub(r"\\H[^;]*;|[{}]", "", txt)
    m = re.match(r"^.*?(?:%%[Cc])?(\d+(?:\.\d+)?)([A-Za-z]{1,2}\d{1,2})", t)
    if not m:
        return None
    n, c = float(m.group(1)), m.group(2)
    try:
        hi, lo = limits(c, n)
    except KeyError:  # 公差等级超出 IT 表（如订货号 6SL3210 里的 SL32），不是公差带代号
        return None
    except ValueError as ex:
        return f"{c} {n:g}：{ex}"
    s = _STK.search(t)
    if s:
        a, b = float(s.group(1)), float(s.group(2))
        if abs(a - hi) > 1e-6 or abs(b - lo) > 1e-6:
            return f"{n:g}{c} 应为 {fmt(hi)}/{fmt(lo)}，图上写了 {s.group(1)}/{s.group(2)}"
        return None
    p = re.search(r"%%[Pp]([\d.]+)", t)
    if p:
        if abs(float(p.group(1)) - hi) > 1e-6 or abs(hi + lo) > 1e-9:
            return f"{n:g}{c} 应为 {fmt(hi)}/{fmt(lo)}，图上写了 ±{p.group(1)}"
    return None


# ---------------------------------------------------------------- GB/T 1095-2003 平键键槽
# (d 上限, b, h, t1 轴槽深, t2 毂槽深)
_KEY = [(8, 2, 2, 1.2, 1.0), (10, 3, 3, 1.8, 1.4), (12, 4, 4, 2.5, 1.8), (17, 5, 5, 3.0, 2.3), (22, 6, 6, 3.5, 2.8),
        (30, 8, 7, 4.0, 3.3), (38, 10, 8, 5.0, 3.3), (44, 12, 8, 5.0, 3.3), (50, 14, 9, 5.5, 3.8), (58, 16, 10, 6.0, 4.3),
        (65, 18, 11, 7.0, 4.4), (75, 20, 12, 7.5, 4.9), (85, 22, 14, 9.0, 5.4), (95, 25, 14, 9.0, 5.4),
        (110, 28, 16, 10.0, 6.4), (130, 32, 18, 11.0, 7.4)]
KEY_FIT = {"正常": ("N9", "JS9"), "紧密": ("P9", "P9"), "松": ("H9", "D10")}


def keyway(d, fit="正常"):
    """轴径 d → 键槽尺寸（GB/T 1095）。返回 dict：b h t1 t2、轴槽宽/毂槽宽公差带、
    'shaft_depth'=(d−t1, 上, 下) 轴上标注用、'hub_depth'=(d+t2, 上, 下) 轮毂上标注用（mm）。"""
    for dmax, b, h, t1, t2 in _KEY:
        if d <= dmax:
            break
    else:
        raise ValueError(f"轴径 {d} 超出键槽表（≤130）")
    dt = 0.1 if b <= 6 else 0.2 if b <= 28 else 0.3
    sw_, hw = KEY_FIT[fit]
    return {"b": b, "h": h, "t1": t1, "t2": t2, "shaft_width": f"{b}{sw_}", "hub_width": f"{b}{hw}",
            "shaft_depth": (round(d - t1, 2), 0.0, -dt), "hub_depth": (round(d + t2, 2), dt, 0.0)}


def depth_text(v):
    """keyway()['shaft_depth'] 这种 (值, 上, 下) → 叠写文字。"""
    n, a, b = v
    return f"{n:g}" + STACK % (fmt(a), fmt(b))


# ---------------------------------------------------------------- GB/T 1804-2000 一般公差（线性尺寸 ±，mm）
_GEN_B = [3, 6, 30, 120, 400, 1000, 2000, 4000]
_GEN = {"f": [0.05, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, None], "m": [0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 2],
        "c": [0.2, 0.3, 0.5, 0.8, 1.2, 2, 3, 4], "v": [None, 0.5, 1, 1.5, 2.5, 4, 6, 8]}


def general(cls, size):
    """GB/T 1804 线性尺寸一般公差 ±值（0.5~4000 mm）。"""
    for i, b in enumerate(_GEN_B):
        if size <= b:
            return _GEN[cls][i]
    raise ValueError("超出 4000 mm")


def _selftest():
    """常用值对照（机械设计手册 / GB/T 1800.2 表）。"""
    cases = {("k6", 35): (0.018, 0.002), ("r6", 40): (0.050, 0.034), ("k6", 28): (0.015, 0.002),
             ("H7", 62): (0.030, 0), ("H7", 40): (0.025, 0), ("N9", 12): (0, -0.043), ("N9", 8): (0, -0.036),
             ("JS9", 12): (0.0215, -0.0215), ("K7", 40): (0.007, -0.018), ("N7", 40): (-0.008, -0.033),
             ("P7", 40): (-0.017, -0.042), ("M7", 40): (0, -0.025), ("R7", 40): (-0.025, -0.050),
             ("S7", 40): (-0.034, -0.059), ("f7", 30): (-0.020, -0.041), ("g6", 25): (-0.007, -0.020),
             ("h6", 50): (0, -0.016), ("js6", 40): (0.008, -0.008), ("m6", 30): (0.021, 0.008),
             ("n6", 45): (0.033, 0.017), ("p6", 60): (0.051, 0.032), ("s6", 70): (0.078, 0.059),
             ("u6", 20): (0.054, 0.041), ("u6", 25): (0.061, 0.048), ("e8", 40): (-0.050, -0.089), ("d9", 60): (-0.100, -0.174),
             ("H8", 100): (0.054, 0), ("F8", 20): (0.053, 0.020), ("G7", 30): (0.028, 0.007),
             ("D10", 12): (0.120, 0.050), ("P9", 12): (-0.018, -0.061), ("H9", 12): (0.043, 0),
             ("K6", 72): (0.004, -0.015), ("J7", 50): (0.014, -0.011), ("t6", 40): (0.064, 0.048),
             ("h7", 72): (0, -0.030), ("k5", 50): (0.013, 0.002)}
    bad = []
    for (c, n), want in cases.items():
        got = limits(c, n)
        if any(abs(a - b) > 1e-6 for a, b in zip(got, want)):
            bad.append((c, n, got, want))
    assert tol_text("%%C35k6") == "%%C35k6({\\H0.7x;\\S+0.018^+0.002;})", tol_text("%%C35k6")
    assert tol_text("12N9", code=False) == "12({\\H0.7x;\\S0^-0.043;})"
    assert tol_text("%%C40js6") == "%%C40js6(%%P0.008)"
    assert tol_text("2×%%C10H7").startswith("2×%%C10H7(")
    assert verify_text("%%C35k6({\\H0.7x;\\S+0.018^+0.002;})") is None
    assert verify_text("%%C35k6({\\H0.7x;\\S+0.018^+0.003;})")
    assert verify_text("%%C40H7/r6") is None
    kw = keyway(40); assert kw["b"] == 12 and kw["shaft_depth"] == (35.0, 0.0, -0.2) and kw["hub_depth"] == (43.3, 0.2, 0.0)
    kw = keyway(28); assert kw["b"] == 8 and kw["shaft_depth"][0] == 24
    assert general("m", 120) == 0.3 and general("m", 121) == 0.5
    return bad


if __name__ == "__main__":
    b = _selftest()
    print("自测：", "全部通过" if not b else b)

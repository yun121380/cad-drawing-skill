"""toolbox_db —— 直接读 SolidWorks Toolbox 自带的尺寸数据库（swbrowser.sldedb，就是 SQLite），2026-11-08。

Toolbox 没有“按规格生成零件”的 COM 接口，但它的配置规则全在库里：
  GB_TYPE_*            每种标准件一行：Name（'Hex GB/T70.1-2000'）、Filename（基础零件）、ConfigurationTable、DataTable
  GB_CFG_<x>           配置表：每个 grid 项 = 一个驱动尺寸（Dimension 列，如 'd@Sketch2'）+ 取值规则（ValueList，如 '{[THD_DIA]}'）
                       + 数据来源（AltDataSource，如 '+DATA_THRD'）+ 过滤条件（RelationField，'[Size=Controller@Size][TPU=Controller@Pitch]'）
  GB_DATA_<x>          尺寸表
这里把这套规则解释一遍：给出用户选的规格（{'Size': 'M8', 'Length': '25'}），得到每个驱动尺寸的值、要压缩/解压的特征、
标记（'GB/T 70.1-2000 M8X25'）。尺寸值全部来自 SW 官方库，不是手抄的。sw_std.make_any() 用它生成零件。

    import toolbox_db as TB
    db = TB.DB()
    t = db.find("GB/T70.1")                 # 按 Name/Title/Filename 模糊找
    r = db.resolve(t, {"Size": "M8", "Length": "25"})
    r["dims"]  -> {'d@Sketch2': 8.0, 'l@BaseBody': 25.0, 'dk@Sketch1': 13.0, ...}
    r["mark"]  -> 'GB/T 70.1-2000  M8X25'
    db.choices(t, "Length", {"Size": "M8"}) -> ['12', '16', ...]   某个可选项的全部取值
"""
import os, re, shutil, sqlite3, tempfile

DB_PATH = r"C:\SOLIDWORKS Data\lang\english\swbrowser.sldedb"


def _f(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def _eq(a, b):
    fa, fb = _f(a), _f(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) < 1e-9
    return str(a).strip().lower() == str(b).strip().lower()


class DB:
    def __init__(self, path=None, std="GB"):
        path = path or DB_PATH
        tmp = os.path.join(tempfile.gettempdir(), "swbrowser_copy.sqlite")     # 复制一份只读用，不碰原库
        if not os.path.exists(tmp) or os.path.getmtime(tmp) < os.path.getmtime(path):
            shutil.copy(path, tmp)
        self.c = sqlite3.connect(tmp)
        self.std = std
        self.tables = {r[0].lower(): r[0] for r in self.c.execute("select name from sqlite_master where type='table'")}

    # ------------------------------------------------------------------ 表
    def _t(self, ref):
        """'+CFG_x' / '+DATA_x' / 'GB_DATA_x' → 真实表名。"""
        n = ref.lstrip("+")
        if not n.lower().startswith(self.std.lower() + "_"):
            n = f"{self.std}_{n}"
        if n.lower() not in self.tables:
            raise KeyError(f"库里没有表 {n}")
        return self.tables[n.lower()]

    def rows(self, ref):
        cur = self.c.execute(f'select * from "{self._t(ref)}"')
        cols = [d[0].lower() for d in cur.description]
        out = [dict(zip(cols, r)) for r in cur]
        return [r for r in out if r.get("enabled", 1) in (1, "1", None)]

    def types(self):
        out = []
        for low, name in self.tables.items():
            if low.startswith(self.std.lower() + "_type_"):
                cur = self.c.execute(f'select * from "{name}"')
                cols = [d[0].lower() for d in cur.description]
                if "configurationtable" in cols:
                    out += [dict(zip(cols, r)) for r in cur]
        return out

    def find(self, key):
        """按 Name / Title / Filename 找标准件类型（忽略大小写、空格、'/'）。唯一匹配才返回，否则报出候选。"""
        norm = lambda s: re.sub(r"[\s/_\-]", "", str(s or "")).lower()
        k = norm(key)
        hits = [t for t in self.types() if k in norm(t["name"]) or k in norm(t["title"]) or k in norm(t["filename"])]
        if len(hits) == 1:
            return hits[0]
        exact = [t for t in hits if norm(t["name"]).endswith(k) or k in norm(t["name"]).split("gb")[-1]]
        if len(exact) == 1:
            return exact[0]
        if not hits:
            raise KeyError(f"Toolbox {self.std} 里没找到 {key!r}")
        raise KeyError(f"{key!r} 匹配到多个：" + "；".join(t["name"] for t in hits[:12]))

    # ------------------------------------------------------------------ 解释配置表
    def _cfg(self, t):
        cur = self.c.execute(f'select * from "{self._t(t["configurationtable"])}" order by Grid_Item_Number')
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, r)) for r in cur]

    @staticmethod
    def _sub(s, row, grids, main):
        s = re.sub(r"<grid(\d+)>", lambda m: str(grids.get(int(m.group(1)), "")), s, flags=re.I)
        s = re.sub(r"Controller@(\w+)", lambda m: str(main.get(m.group(1).lower(), "")), s)
        if row is not None:
            s = re.sub(r"\[(\w[\w ]*)\]", lambda m: str(row.get(m.group(1).lower(), m.group(0))), s)
        return s

    def _template(self, vl, row, grids, main):
        s = (vl or "").strip()
        if s.startswith("{") and s.endswith("}"):
            s = s[1:-1]
        s = self._sub(s, row, grids, main)
        m = re.search(r"\$IF\$(.*?)\$ENDIF\$", s)
        if m:                                       # $IF$a=b:值|1=1:值$ENDIF$
            val = ""
            for branch in m.group(1).split("|"):
                cond, _, v = branch.partition(":")
                a, _, b = cond.partition("=")
                if _eq(a, b):
                    val = v; break
            s = s[:m.start()] + val + s[m.end():]
        return s.strip().strip('"')

    def _filter(self, rows, rel, grids, main):
        for col, val in re.findall(r"\[(\w+)=([^\]]*)\]", rel or ""):
            v = self._sub(val, None, grids, main)
            rows = [r for r in rows if _eq(r.get(col.lower(), ""), v)]
        return rows

    def choices(self, t, grid_name, sel=None):
        """某个可选项（'Length'、'Size'、'Thickness'…）在当前选择下的全部取值。"""
        r = self.resolve(t, sel or {}, want=grid_name)
        return r

    def resolve(self, t, sel, want=None):
        """sel：{'Size': 'M8', 'Length': '25', 'Thread Display': 'Cosmetic'}（键用配置表里的 Grid_Item_Name，
        大小写不敏感；也可以用 grid 号）。没给的可选项取表里第一个。返回 dict：
        dims（尺寸名 → mm）、on/off（要解压/压缩的特征）、mark（标记）、grids（全部 grid 值）、missing（选项值在表里没找到）。"""
        selk = {(k.lower() if isinstance(k, str) else k): v for k, v in sel.items()}
        main_rows = self.rows(t["datatable"])
        cfg = self._cfg(t)
        grids, dims, on, off, missing = {}, {}, [], [], []
        main = {}
        for g in cfg:
            n, name = g["grid_item_number"], (g["grid_item_name"] or "").strip()
            user = selk.get(name.lower(), selk.get(n))
            src = g["altdatasource"]
            if g["controller"] == 1 and not src:           # 主选项：决定主数据行
                col = re.fullmatch(r"\{\[(\w+)\]\}", g["valuelist"] or "")
                col = col.group(1).lower() if col else "size"
                cand = main_rows
                if user is not None:
                    cand = [r for r in main_rows if _eq(r.get(col), user)]
                    if not cand:
                        missing.append(f"{name}={user}（可选：{', '.join(str(r.get(col)) for r in main_rows[:40])}…）")
                        cand = main_rows
                if want and name.lower() == want.lower():
                    return [r.get(col) for r in main_rows]
                main = cand[0]; grids[n] = main.get(col)
                continue
            rows = self.rows(src) if src else [main]
            rows = self._filter(rows, g["relationfield"], grids, main)
            vl = g["valuelist"] or ""
            single = re.fullmatch(r"\{\[(\w+)\]\}", vl)
            is_choice = (g["grid_item_type"] or "").upper() in ("STRING_COMBO", "NUMERIC_COMBO")
            if want and name.lower() == want.lower():
                return [r.get(single.group(1).lower()) for r in rows] if single else []
            row = rows[0] if rows else None
            if single and user is not None and rows:
                hit = [r for r in rows if _eq(r.get(single.group(1).lower()), user)]
                if hit:
                    row = hit[0]
                else:
                    missing.append(f"{name}={user}（可选：{', '.join(str(r.get(single.group(1).lower())) for r in rows[:40])}）")
            elif g["dimension"] == "SUPPRESSION" and rows:
                pick = user or "Cosmetic"                   # 默认装饰螺纹线：保留 ThreadCosmetic，压缩螺纹纹理
                hit = [r for r in rows if _eq(r.get("thread_display"), pick)]
                row = hit[0] if hit else rows[0]
            if row is None:
                continue
            val = self._template(vl, row, grids, main)
            grids[n] = val
            if g["dimension"] == "SUPPRESSION":
                on += [x for x in (row.get("onfeatures") or "").split(",") if x]
                off += [x for x in (row.get("offfeatures") or "").split(",") if x]
            elif g["dimension"] and _f(val) is not None:
                dims[g["dimension"]] = _f(val)
            _ = is_choice
        mark = grids.get(910) or grids.get(999) or ""
        return {"dims": dims, "on": on, "off": off, "mark": re.sub(r"\s+", " ", mark).strip(), "spec": grids.get(900, ""),
                "name_en": grids.get(920, ""), "material": grids.get(930, ""), "grids": grids, "missing": missing,
                "file": t["filename"], "type": t["name"]}


if __name__ == "__main__":
    db = DB()
    for key, sel in (("GB/T70.1", {"Size": "M8", "Length": "25"}), ("GB/T5783", {"Size": "M8", "Length": "25"}),
                     ("GB/T67-2000", {"Size": "M5", "Length": "12"}), ("GB/T 93-1987", {"Size": "10"}),
                     ("GB/T297", {"Train": "02", "Size": "30206"}), ("series G (3452.1)", {"Inside Diameter": "30", "Thickness": "3.55"})):
        t = db.find(key); r = db.resolve(t, sel)
        print(t["name"], "|", r["mark"], "|", r["dims"], "| off", r["off"], "| missing", r["missing"])

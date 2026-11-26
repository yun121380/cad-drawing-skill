import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import sw_views as V, sw_std, sw_mem
sw = V.connect()
out = os.path.join(os.getcwd(), "std")   # 输出写到当前目录
res = {}
for kind, size in (("screw", "M8x25"), ("screw_hex", "M8x25"), ("screw_pan", "M5x12"), ("spring_washer", "10"),
                   ("taper_bearing", "30206"), ("taper_bearing", "30207"), ("oring", "30x3.55")):
    p, info = sw_std.make_tb(sw, kind, size, out)
    res[f"{kind} {size}"] = info
    print(kind, size, "->", os.path.basename(p)); print("   ", {k: info[k] for k in ("代号", "规格", "质量kg", "外框")}, info.get("没找到的尺寸"))
p, info = sw_std.make_felt(sw, 30, out); res["felt 30"] = info
print("felt", info)
print("SW 内存 GB", round(sw_mem.private_gb(), 2))
json.dump(res, open(os.path.join(out, "std_test.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

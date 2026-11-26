"""sw_mem —— SolidWorks 内存守护（2026-11-08）。

SW 关了文档也不怎么释放内存，连续建零件/装配/出几张工程图后私有内存能涨到 15 GB，把 AutoCAD 挤崩。
这里在三个时机自动处理：
  * sw_views.connect() / sw_part.connect()：连上之前先看一眼，超过上限就让 SW 退出再重开；
  * sw_views.export() 之后：超过上限就退出（下次 connect 自动重开）；
  * sw2acad.Sheet 进入时（转去 AutoCAD 了，SW 用不着）：超过上限就退出。
上限取 scripts/config.json 的 "sw_mem_limit_gb"（默认 6）。有**未保存**的文档时不退出，只打印警告——
不会替你丢掉手工改了还没存的东西。不依赖 psutil：用 tasklist 找进程、psapi.GetProcessMemoryInfo 读 PrivateUsage。

    import sw_mem
    sw_mem.private_gb()            -> 3.42（没开 SW 时 0）
    sw_mem.recycle(limit_gb=6)     -> True 表示退出了
"""
import os, json, time, ctypes, subprocess
from ctypes import wintypes

_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def limit_default():
    try:
        return float(json.load(open(_CFG, encoding="utf-8")).get("sw_mem_limit_gb", 6))
    except Exception:
        return 6.0


def _pids(image):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, errors="ignore").stdout
    pids = []
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == image.lower():
            pids.append(int(parts[1]))
    return pids


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]


def private_gb(image="SLDWORKS.exe"):
    """该映像名所有进程私有内存之和（GB）。"""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True); ps = ctypes.WinDLL("psapi")
    total = 0
    for pid in _pids(image):
        h = k32.OpenProcess(0x1000 | 0x0010, False, pid)        # QUERY_LIMITED_INFORMATION | VM_READ
        if not h:
            continue
        try:
            c = _PMC(); c.cb = ctypes.sizeof(c)
            if ps.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                total += c.PrivateUsage
        finally:
            k32.CloseHandle(h)
    return total / 1024 ** 3


def _dirty_docs(sw):
    names = []
    try:
        d = sw.GetFirstDocument
        while d:
            try:
                if d.GetSaveFlag:                     # True = 有未保存的修改
                    names.append(d.GetTitle)
            except Exception:
                pass
            d = d.GetNext
    except Exception:
        pass
    return names


def recycle(limit_gb=None, force=False, verbose=True):
    """SW 私有内存超过 limit_gb（或 force=True）时：确认没有未保存的文档 → 关闭全部文档 → ExitApp → 等进程退出
    （60 s 还在就 taskkill）。返回是否退出了。"""
    limit_gb = limit_default() if limit_gb is None else limit_gb
    gb = private_gb()
    if gb == 0 or (gb < limit_gb and not force):
        return False
    import win32com.client as wc
    try:
        sw = wc.GetActiveObject("SldWorks.Application")
    except Exception:
        sw = None
    if sw is not None:
        dirty = _dirty_docs(sw)
        if dirty:
            print(f"[sw_mem] SolidWorks 占 {gb:.1f} GB，但这些文档有未保存的修改，不自动退出：{dirty}")
            return False
        if verbose:
            print(f"[sw_mem] SolidWorks 占 {gb:.1f} GB ≥ {limit_gb} GB：关闭全部文档并退出，下次 connect 自动重开")
        try:
            sw.CloseAllDocuments(True)
            sw.ExitApp()
        except Exception as ex:
            print("[sw_mem] ExitApp 异常（继续等进程退出）：", ex)
        del sw
    for _ in range(60):
        if not _pids("SLDWORKS.exe"):
            break
        time.sleep(1)
    else:
        print("[sw_mem] SolidWorks 60 s 没退出，强制结束")
        subprocess.run(["taskkill", "/IM", "SLDWORKS.exe", "/F"], capture_output=True)
        time.sleep(3)
    return True


if __name__ == "__main__":
    print(f"SolidWorks 私有内存 {private_gb():.2f} GB，上限 {limit_default()} GB")

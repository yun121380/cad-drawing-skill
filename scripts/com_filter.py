"""com_filter —— 给当前线程注册 COM 消息过滤器，AutoCAD/SolidWorks 忙时自动重试。

不注册的话，AutoCAD 在重生成、刚打开文档、打印时会直接拒绝调用，抛
"被呼叫方拒绝接收呼叫"(RPC_E_CALL_REJECTED)，任何一行 COM 调用都可能中招。
本机 pywin32 没有 CoRegisterMessageFilter，这里用 comtypes + ole32 自己注册。

    import com_filter; com_filter.install()     # 进程里调一次即可（STA 线程）
"""
import ctypes
from ctypes import HRESULT, POINTER, c_void_p, c_ulong
import comtypes
from comtypes import GUID, IUnknown, COMMETHOD, COMObject

SERVERCALL_ISHANDLED = 0
SERVERCALL_RETRYLATER = 2
PENDINGMSG_WAITDEFPROCESS = 2


class IMessageFilter(IUnknown):
    _iid_ = GUID("{00000016-0000-0000-C000-000000000046}")
    _methods_ = [
        COMMETHOD([], c_ulong, "HandleInComingCall",
                  (["in"], c_ulong, "dwCallType"), (["in"], c_void_p, "htaskCaller"),
                  (["in"], c_ulong, "dwTickCount"), (["in"], c_void_p, "lpInterfaceInfo")),
        COMMETHOD([], c_ulong, "RetryRejectedCall",
                  (["in"], c_void_p, "htaskCallee"), (["in"], c_ulong, "dwTickCount"),
                  (["in"], c_ulong, "dwRejectType")),
        COMMETHOD([], c_ulong, "MessagePending",
                  (["in"], c_void_p, "htaskCallee"), (["in"], c_ulong, "dwTickCount"),
                  (["in"], c_ulong, "dwPendingType")),
    ]


class _Filter(COMObject):
    _com_interfaces_ = [IMessageFilter]
    timeout_ms = 120_000

    def IMessageFilter_HandleInComingCall(self, this, dwCallType, htaskCaller, dwTickCount, lpInterfaceInfo):
        return SERVERCALL_ISHANDLED

    def IMessageFilter_RetryRejectedCall(self, this, htaskCallee, dwTickCount, dwRejectType):
        if dwRejectType == SERVERCALL_RETRYLATER and dwTickCount < self.timeout_ms:
            return 150          # 150 ms 后重试
        return 0xFFFFFFFF       # 放弃，调用方收到异常

    def IMessageFilter_MessagePending(self, this, htaskCallee, dwTickCount, dwPendingType):
        return PENDINGMSG_WAITDEFPROCESS


_installed = None


def install():
    global _installed
    if _installed is not None:
        return
    import pythoncom
    pythoncom.CoInitialize()            # 和 win32com 共用同一个 STA
    f = _Filter()
    ptr = f.QueryInterface(IMessageFilter)
    old = POINTER(IMessageFilter)()
    hr = ctypes.oledll.ole32.CoRegisterMessageFilter(ptr, ctypes.byref(old))
    _installed = (f, ptr)               # 保持引用，防止被回收
    return hr

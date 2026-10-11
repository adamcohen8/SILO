"""Fail closed on interface/route changes, suspend/resume, or monitor failure."""
import ctypes as C
import os
import threading

from .folders import AccessDenied


class WindowsLifecycle:
    def __init__(self):
        if os.name != 'nt': raise AccessDenied('Native lifecycle monitoring requires Windows')
        self.changed = threading.Event()
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.ip = C.WinDLL('iphlpapi', use_last_error=True)
        self.kernel.GetTickCount64.argtypes = []
        self.kernel.GetTickCount64.restype = C.c_uint64
        self.kernel.QueryUnbiasedInterruptTime.argtypes = [C.POINTER(C.c_uint64)]
        self.kernel.QueryUnbiasedInterruptTime.restype = C.c_int
        self.callback_type = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_int)
        self.callback = self.callback_type(lambda context, row, kind: self.changed.set())
        self.handles = []
        self.ip.CancelMibChangeNotify2.argtypes = [C.c_void_p]
        self.ip.CancelMibChangeNotify2.restype = C.c_uint32
        try:
            for name in ('NotifyIpInterfaceChange', 'NotifyRouteChange2'):
                function = getattr(self.ip, name)
                function.argtypes = [C.c_ushort, self.callback_type, C.c_void_p, C.c_ubyte, C.POINTER(C.c_void_p)]
                function.restype = C.c_uint32
                handle = C.c_void_p()
                if function(0, self.callback, None, 0, C.byref(handle)):
                    raise AccessDenied('Windows network lifecycle monitoring unavailable')
                self.handles.append(handle)
            self.sleep_offset = self._offset()
        except BaseException:
            self.close(); raise

    def _offset(self):
        unbiased = C.c_uint64()
        if not self.kernel.QueryUnbiasedInterruptTime(C.byref(unbiased)):
            raise AccessDenied('Windows suspend/resume state unavailable')
        return self.kernel.GetTickCount64() - unbiased.value // 10000

    def check(self):
        if self.changed.is_set() or abs(self._offset() - self.sleep_offset) > 500:
            raise AccessDenied('Network or suspend/resume state changed; restart and revalidate the contained session')

    def close(self):
        errors = []
        for handle in self.handles:
            if self.ip.CancelMibChangeNotify2(handle): errors.append(handle)
        self.handles.clear()
        if errors: raise AccessDenied('Network lifecycle notification cleanup incomplete')

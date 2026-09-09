"""G2 owned-window startup focus; temporary input attachment always detached."""
import ctypes
from ctypes import wintypes
from startup_focus import WindowsFocus,acquire_foreground as base_acquire
from player_verify import need

class StartupFocus(WindowsFocus):
    def __init__(self):
        super().__init__()
        self.kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        self.kernel.GetCurrentThreadId.argtypes=[];self.kernel.GetCurrentThreadId.restype=wintypes.DWORD
        self.api.AttachThreadInput.argtypes=[wintypes.DWORD,wintypes.DWORD,wintypes.BOOL];self.api.AttachThreadInput.restype=wintypes.BOOL
        self.api.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int];self.api.ShowWindow.restype=wintypes.BOOL
    def activate(self,window,pid):
        need(self.owner(window)==pid and self.api.IsWindowVisible(window),"Window ownership changed")
        if super().activate(window,pid):return True
        current=self.kernel.GetCurrentThreadId()
        foreground=self.api.GetWindowThreadProcessId(self.api.GetForegroundWindow(),None)
        attached=False
        try:
            if foreground and foreground!=current:
                attached=bool(self.api.AttachThreadInput(current,foreground,True))
            need(self.owner(window)==pid,"Window ownership changed during attachment")
            self.api.ShowWindow(window,9)
            return bool(self.api.SetForegroundWindow(window))
        finally:
            if attached:need(bool(self.api.AttachThreadInput(current,foreground,False)),"Failed to detach startup input threads")

def acquire_foreground(process,timeout_seconds=10,api=None):
    result=base_acquire(process,timeout_seconds,api or StartupFocus())
    result["method"]="owned-pid/SetForegroundWindow/temporary-AttachThreadInput"
    return result

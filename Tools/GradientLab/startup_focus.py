"""Windows foreground acquisition for an owned Player, only during startup."""
import ctypes,datetime as dt,time
from ctypes import wintypes
from player_verify import need

class WindowsFocus:
    def __init__(self):
        self.api=ctypes.WinDLL("user32",use_last_error=True)
        self.callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        signatures={
            "GetForegroundWindow":([],wintypes.HWND),
            "GetWindowThreadProcessId":([wintypes.HWND,ctypes.POINTER(wintypes.DWORD)],wintypes.DWORD),
            "IsWindowVisible":([wintypes.HWND],wintypes.BOOL),
            "SetForegroundWindow":([wintypes.HWND],wintypes.BOOL),
            "EnumWindows":([self.callback_type,wintypes.LPARAM],wintypes.BOOL),
        }
        for name,(args,result) in signatures.items():
            f=getattr(self.api,name);f.argtypes=args;f.restype=result
    def owner(self,window):
        pid=wintypes.DWORD()
        self.api.GetWindowThreadProcessId(window,ctypes.byref(pid))
        return pid.value
    def foreground_pid(self):
        return self.owner(self.api.GetForegroundWindow())
    def windows(self,pid):
        found=[]
        @self.callback_type
        def collect(window,_):
            if self.owner(window)==pid and self.api.IsWindowVisible(window):found.append(window)
            return True
        self.api.EnumWindows(collect,0)
        return found
    def activate(self,window,pid):
        need(self.owner(window)==pid and self.api.IsWindowVisible(window),"Window ownership changed")
        return bool(self.api.SetForegroundWindow(window))

def acquire_foreground(process,timeout_seconds=10,api=None):
    need(type(process.pid) is int and process.pid>0,"Owned Player PID invalid")
    api=api or WindowsFocus();start=time.monotonic();mutations=0;last_change=None
    while time.monotonic()-start<timeout_seconds:
        need(process.poll() is None,"Owned Player exited before foreground acquisition")
        if api.foreground_pid()==process.pid:
            return dict(pid=process.pid,acquiredUtc=dt.datetime.now(dt.timezone.utc).isoformat(),
                durationSeconds=time.monotonic()-start,activationCalls=mutations,lastActivationUtc=last_change,
                method="owned-pid/SetForegroundWindow",acquired=True)
        for window in api.windows(process.pid):
            api.activate(window,process.pid);mutations+=1
            last_change=dt.datetime.now(dt.timezone.utc).isoformat()
            if api.foreground_pid()==process.pid:break
        time.sleep(.01)
    raise TimeoutError("Owned Player foreground acquisition timed out")


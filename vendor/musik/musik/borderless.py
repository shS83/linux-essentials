"""Desktop-composited borderless windows; never request a display mode."""
import sys

from PySide6.QtCore import Qt


class BorderlessWindow:
    def __init__(self, widget):
        self.widget = widget
        self.active = False
        self.geometry = None

    def toggle(self):
        self.set_active(not self.active)

    def set_active(self, active):
        if active == self.active:
            return
        w = self.widget
        if sys.platform == "win32":
            self._windows(active)
        else:
            if active:
                self.geometry = w.geometry()
                self.flags = w.windowFlags()
                self.state = w.windowState()
                screen = w.screen()
                w.setWindowFlags(self.flags | Qt.WindowType.FramelessWindowHint)
                w.showNormal()
                w.setGeometry(screen.geometry())
            else:
                w.setWindowFlags(self.flags)
                w.setGeometry(self.geometry)
                w.setWindowState(self.state)
            w.show()
        self.active = active
        w.raise_()
        w.activateWindow()

    def _windows(self, active):
        # Keep the HWND and OpenGL context alive throughout the transition.
        import ctypes as c
        from ctypes import wintypes as t

        class Placement(c.Structure):
            _fields_ = [("length", t.UINT), ("flags", t.UINT), ("showCmd", t.UINT),
                        ("min", t.POINT), ("max", t.POINT), ("normal", t.RECT)]

        class MonitorInfo(c.Structure):
            _fields_ = [("size", t.DWORD), ("monitor", t.RECT),
                        ("work", t.RECT), ("flags", t.DWORD)]

        u = c.WinDLL("user32", use_last_error=True)
        def api(name, result, *args):
            fn = getattr(u, name)
            fn.restype, fn.argtypes = result, args
            return fn

        get_style = api("GetWindowLongPtrW", c.c_ssize_t, t.HWND, c.c_int)
        set_style = api("SetWindowLongPtrW", c.c_ssize_t, t.HWND, c.c_int, c.c_ssize_t)
        get_place = api("GetWindowPlacement", t.BOOL, t.HWND, c.c_void_p)
        set_place = api("SetWindowPlacement", t.BOOL, t.HWND, c.c_void_p)
        monitor_from = api("MonitorFromWindow", t.HANDLE, t.HWND, t.DWORD)
        monitor_info = api("GetMonitorInfoW", t.BOOL, t.HANDLE, c.c_void_p)
        set_pos = api("SetWindowPos", t.BOOL, t.HWND, t.HWND, c.c_int, c.c_int,
                      c.c_int, c.c_int, t.UINT)
        layer = api("SetLayeredWindowAttributes", t.BOOL, t.HWND, t.DWORD, t.BYTE, t.DWORD)
        hwnd = int(self.widget.winId())
        if active:
            placement = Placement()
            placement.length = c.sizeof(placement)
            info = MonitorInfo()
            info.size = c.sizeof(info)
            if not get_place(hwnd, c.byref(placement)) or not monitor_info(monitor_from(hwnd, 2), c.byref(info)):
                raise c.WinError(c.get_last_error())
            self.geometry = self.widget.normalGeometry() if self.widget.isMaximized() else self.widget.geometry()
            self.placement = placement
            self.style = get_style(hwnd, -16)
            self.ex_style = get_style(hwnd, -20)
            # Alpha 254/255 requires desktop blending. Fully opaque screen-sized
            # OpenGL windows can be promoted by a driver into fullscreen scanout.
            ex_style = (self.ex_style & ~0x00020301) | 0x00080000
            set_style(hwnd, -20, ex_style)
            if not layer(hwnd, 0, 254, 2):
                set_style(hwnd, -20, self.ex_style)
                raise c.WinError(c.get_last_error())
            set_style(hwnd, -16, self.style & ~0x01CF0000)
            r = info.monitor
            if not set_pos(hwnd, 0, r.left, r.top, r.right-r.left, r.bottom-r.top, 0x0060):
                error = c.get_last_error()
                set_style(hwnd, -16, self.style)
                set_place(hwnd, c.byref(self.placement))
                set_style(hwnd, -20, self.ex_style)
                raise c.WinError(error)
        else:
            set_style(hwnd, -16, self.style)
            set_place(hwnd, c.byref(self.placement))
            # Keep blending enabled until the window has its original size.
            set_style(hwnd, -20, self.ex_style)
            set_pos(hwnd, None, 0, 0, 0, 0, 0x0277)

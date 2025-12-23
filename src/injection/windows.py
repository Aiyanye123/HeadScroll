"""
M8: 输入注入模块 - Windows 实现
使用 ctypes 调用 SendInput 发送滚轮事件
"""

import ctypes
from ctypes import wintypes
from typing import Optional

from utils import get_logger

from .base import InputInjector


# Windows API 常量
MOUSEEVENTF_WHEEL = 0x0800
WM_MOUSEWHEEL = 0x020A
WHEEL_DELTA = 120  # Windows 标准滚轮单位

# 某些 Python 版本的 wintypes 里没有 LRESULT
LRESULT = getattr(wintypes, "LRESULT", wintypes.LPARAM)

INPUT_MOUSE = 0


class MOUSEINPUT(ctypes.Structure):
    """鼠标输入结构"""
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    """输入结构"""
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", MOUSEINPUT),
        ]
    
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT_UNION),
    ]


class POINT(ctypes.Structure):
    """屏幕坐标"""
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class WindowsInjector(InputInjector):
    """Windows 平台滚轮注入实现"""
    
    def __init__(
        self,
        use_smooth_scroll: bool = True,
        target_mode: str = "cursor",
        target_process: Optional[str] = None
    ):
        """
        初始化 Windows 注入器
        
        Args:
            use_smooth_scroll: 是否使用平滑滚动（小步多次）
        """
        self.use_smooth_scroll = use_smooth_scroll
        self.target_mode = target_mode  # cursor / foreground / process
        self.target_process = target_process
        self._user32: Optional[ctypes.WinDLL] = None
        self._kernel32: Optional[ctypes.WinDLL] = None
        self._send_input = None
        self._initialized = False
        self._last_error: Optional[str] = None
        self._logger = get_logger("injector")
    
    def init(self) -> bool:
        """初始化 Windows API"""
        try:
            self._user32 = ctypes.windll.user32
            self._kernel32 = ctypes.windll.kernel32
            self._send_input = self._user32.SendInput
            self._send_input.argtypes = [
                wintypes.UINT,
                ctypes.POINTER(INPUT),
                ctypes.c_int
            ]
            self._send_input.restype = wintypes.UINT
            self._user32.SendMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            self._user32.SendMessageW.restype = LRESULT
            self._user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
            self._user32.GetCursorPos.restype = wintypes.BOOL
            self._user32.WindowFromPoint.argtypes = [POINT]
            self._user32.WindowFromPoint.restype = wintypes.HWND
            self._user32.GetForegroundWindow.argtypes = []
            self._user32.GetForegroundWindow.restype = wintypes.HWND
            self._user32.EnumWindows.argtypes = [
                ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
                wintypes.LPARAM,
            ]
            self._user32.EnumWindows.restype = wintypes.BOOL
            self._user32.IsWindowVisible.argtypes = [wintypes.HWND]
            self._user32.IsWindowVisible.restype = wintypes.BOOL
            self._user32.GetWindowThreadProcessId.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.DWORD),
            ]
            self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            self._kernel32.OpenProcess.argtypes = [
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
            ]
            self._kernel32.OpenProcess.restype = wintypes.HANDLE
            self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            self._kernel32.CloseHandle.restype = wintypes.BOOL
            self._kernel32.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.LPWSTR,
                ctypes.POINTER(wintypes.DWORD),
            ]
            self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
            self._initialized = True
            self._last_error = None
            return True
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._logger.error(f"Injector init failed: {self._last_error}")
            self._initialized = False
            return False
    
    def scroll(self, delta: int) -> bool:
        """
        发送滚轮事件
        
        Args:
            delta: 滚轮步进，正值向下滚
            
        Returns:
            是否成功
        """
        if not self._initialized or self._send_input is None:
            return False
        
        if delta == 0:
            return True
        
        try:
            if self.use_smooth_scroll:
                # 平滑滚动：每次发送 1 个单位
                for _ in range(abs(delta)):
                    wheel_delta = -WHEEL_DELTA if delta > 0 else WHEEL_DELTA
                    if not self._send_wheel_by_mode(wheel_delta):
                        self._send_wheel_event(wheel_delta)
            else:
                # 一次性发送
                wheel_delta = -delta * WHEEL_DELTA
                if not self._send_wheel_by_mode(wheel_delta):
                    self._send_wheel_event(wheel_delta)
            return True
        except Exception:
            return False
    
    def _send_wheel_event(self, wheel_delta: int) -> None:
        """发送单次滚轮事件"""
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = 0
        inp.mi.dy = 0
        inp.mi.mouseData = ctypes.c_ulong(wheel_delta & 0xFFFFFFFF).value
        inp.mi.dwFlags = MOUSEEVENTF_WHEEL
        inp.mi.time = 0
        inp.mi.dwExtraInfo = None
        
        self._send_input(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _send_wheel_by_mode(self, wheel_delta: int) -> bool:
        """按目标模式发送滚轮事件"""
        mode = (self.target_mode or "cursor").lower()
        if mode == "foreground":
            return self._send_wheel_to_foreground_window(wheel_delta)
        if mode == "process":
            return self._send_wheel_to_process_window(wheel_delta)
        return self._send_wheel_to_cursor_window(wheel_delta)

    def _send_wheel_to_cursor_window(self, wheel_delta: int) -> bool:
        """向鼠标所在窗口直接发送滚轮事件"""
        if self._user32 is None:
            return False
        pt = POINT()
        if not self._user32.GetCursorPos(ctypes.byref(pt)):
            return False
        hwnd = self._user32.WindowFromPoint(pt)
        if not hwnd:
            return False
        return self._send_wheel_to_window(hwnd, wheel_delta, pt)

    def _send_wheel_to_foreground_window(self, wheel_delta: int) -> bool:
        """向前台窗口发送滚轮事件"""
        if self._user32 is None:
            return False
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return False
        pt = POINT()
        if not self._user32.GetCursorPos(ctypes.byref(pt)):
            pt.x, pt.y = 0, 0
        return self._send_wheel_to_window(hwnd, wheel_delta, pt)

    def _send_wheel_to_process_window(self, wheel_delta: int) -> bool:
        """向指定进程的窗口发送滚轮事件"""
        hwnd = self._find_window_by_process_name(self.target_process)
        if not hwnd:
            # 未找到目标进程窗口时，回退到前台窗口
            return self._send_wheel_to_foreground_window(wheel_delta)
        pt = POINT()
        if self._user32 and self._user32.GetCursorPos(ctypes.byref(pt)):
            pass
        else:
            pt.x, pt.y = 0, 0
        return self._send_wheel_to_window(hwnd, wheel_delta, pt)

    def _send_wheel_to_window(self, hwnd: int, wheel_delta: int, pt: POINT) -> bool:
        """向指定窗口发送滚轮事件"""
        if self._user32 is None:
            return False
        delta = ctypes.c_short(wheel_delta).value & 0xFFFF
        wparam = delta << 16
        lparam = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        self._user32.SendMessageW(hwnd, WM_MOUSEWHEEL, wparam, lparam)
        return True

    def _find_window_by_process_name(self, process_name: Optional[str]) -> Optional[int]:
        """按进程名查找一个可见顶层窗口句柄"""
        if not process_name or self._user32 is None or self._kernel32 is None:
            return None
        target = process_name.lower()
        if not target.endswith(".exe"):
            target = target + ".exe"

        hwnd_found = {"hwnd": None}

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd, lparam):
            if not self._user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD(0)
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            name = self._get_process_name(pid.value)
            if name and name.lower() == target:
                hwnd_found["hwnd"] = hwnd
                return False
            return True

        self._user32.EnumWindows(enum_proc, 0)
        return hwnd_found["hwnd"]

    def _get_process_name(self, pid: int) -> Optional[str]:
        """获取进程可执行文件名"""
        if self._kernel32 is None:
            return None
        handle = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            buf_len = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(buf_len.value)
            if self._kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(buf_len)):
                path = buf.value
                return path.split("\\\\")[-1]
            return None
        finally:
            self._kernel32.CloseHandle(handle)
    
    def shutdown(self) -> None:
        """关闭注入器"""
        self._initialized = False
        self._user32 = None
        self._kernel32 = None
        self._send_input = None
        self._last_error = None
    
    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def last_error(self) -> Optional[str]:
        """初始化失败时的错误信息"""
        return self._last_error

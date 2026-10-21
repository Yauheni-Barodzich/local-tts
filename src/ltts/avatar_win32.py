"""Win32: окно аватара — color-key до WebView2 и перетаскивание через NCHITTEST."""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Any

_LOG = logging.getLogger(__name__)

# Точный цвет, который Win32 вырезает. Почти чёрный: кромка сглаживания выглядит тенью, не каймой.
CHROMA_HEX = "#010102"
CHROMA_RGB = (1, 1, 2)

DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMSBT_NONE = 1
WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
WM_NCHITTEST = 0x0084
WM_NCLBUTTONDBLCLK = 0x00A3
WM_SYSCOMMAND = 0x0112
HTCAPTION = 2
HTTRANSPARENT = -1
SC_MAXIMIZE = 0xF030

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DONOTROUND = 1

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
_user32.SetWindowLongW.restype = ctypes.c_long
_user32.SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    wintypes.BYTE,
    wintypes.DWORD,
]
_user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
_user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
_user32.SetWindowPos.restype = wintypes.BOOL
_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumChildWindows.argtypes = [wintypes.HWND, _WNDENUMPROC, wintypes.LPARAM]
_user32.EnumChildWindows.restype = wintypes.BOOL

GWLP_WNDPROC = -4
_WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)
_user32.CallWindowProcW.argtypes = [
    ctypes.c_void_p,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
_user32.CallWindowProcW.restype = ctypes.c_ssize_t
_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongPtrW.restype = ctypes.c_void_p
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
_user32.SetWindowLongPtrW.restype = ctypes.c_void_p

_form_hwnds: set[int] = set()
_old_wndproc: dict[int, int] = {}

def _page_bg_script(hex_color: str) -> str:
    return (
        "(function(){"
        "var c='"
        + hex_color
        + "';"
        "function apply(){"
        "var el=document.documentElement;"
        "if(el) el.style.backgroundColor=c;"
        "if(document.body) document.body.style.backgroundColor=c;"
        "var d=document.getElementById('dragpad');"
        "if(d) d.style.backgroundColor=c;"
        "}"
        "if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',apply);"
        "else apply();"
        "})();"
    )

_chroma_script_added: set[int] = set()
_enum_refs: list[Any] = []


def _hwnd(form: Any) -> int | None:
    try:
        handle = form.Handle
        try:
            return int(handle.ToInt64())
        except Exception:
            return int(handle.ToInt32())
    except Exception:
        return None


def _hwnd_id(hwnd: int) -> int:
    return int(hwnd) & 0xFFFFFFFFFFFFFFFF


def _effective_page_rgb() -> tuple[int, int, int]:
    from .avatar_config import effective_page_chroma_hex, parse_chroma_rgb

    return parse_chroma_rgb(effective_page_chroma_hex())


def _chroma_color_opaque():
    from System.Drawing import Color

    r, g, b = _effective_page_rgb()
    return Color.FromArgb(255, r, g, b)


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _disable_window_accent(hwnd: int) -> None:
    try:
        accent = _ACCENT_POLICY(ACCENT_DISABLED, 0, 0, 0)
        data = _WINDOWCOMPOSITIONATTRIBDATA(
            WCA_ACCENT_POLICY,
            ctypes.byref(accent),
            ctypes.sizeof(accent),
        )
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception as e:
        _LOG.debug("disable_window_accent: %s", e)


def clear_dwm_backdrop(hwnd: int) -> None:
    try:
        dwm = ctypes.windll.dwmapi
        none_backdrop = ctypes.c_int(DWMSBT_NONE)
        dwm.DwmSetWindowAttribute(
            hwnd,
            DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(none_backdrop),
            ctypes.sizeof(none_backdrop),
        )
        dark_off = ctypes.c_int(0)
        dwm.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_off),
            ctypes.sizeof(dark_off),
        )
        square = ctypes.c_int(DWMWCP_DONOTROUND)
        dwm.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(square),
            ctypes.sizeof(square),
        )
    except Exception as e:
        _LOG.debug("clear_dwm_backdrop: %s", e)
    _disable_window_accent(hwnd)


def exclude_from_taskbar(hwnd: int) -> None:
    style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)


_gdi = ctypes.WinDLL("gdi32", use_last_error=True)
_gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi.CreateCompatibleDC.restype = wintypes.HDC
_gdi.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_gdi.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi.SelectObject.restype = wintypes.HGDIOBJ
_gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi.DeleteObject.restype = wintypes.BOOL
_gdi.DeleteDC.argtypes = [wintypes.HDC]
_gdi.DeleteDC.restype = wintypes.BOOL
_gdi.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_uint,
]
_gdi.GetDIBits.restype = ctypes.c_int
_gdi.CreateRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
_gdi.CreateRectRgn.restype = wintypes.HANDLE
_gdi.CombineRgn.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.c_int]
_gdi.CombineRgn.restype = ctypes.c_int
_gdi.ExtCreateRegion.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p]
_gdi.ExtCreateRegion.restype = wintypes.HANDLE
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
_user32.GetWindowRect.restype = wintypes.BOOL
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_uint]
_user32.PrintWindow.restype = wintypes.BOOL
_user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
_user32.SetWindowRgn.restype = ctypes.c_int

_PW_RENDERFULLCONTENT = 2
_RGN_OR = 2


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_ushort),
        ("biBitCount", ctypes.c_ushort),
        ("biCompression", ctypes.c_uint),
        ("biSizeImage", ctypes.c_uint),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint),
        ("biClrImportant", ctypes.c_uint),
    ]


def _matches_rgb(b: int, g: int, r: int, rgb: tuple[int, int, int], tol: int) -> bool:
    cr, cg, cb = rgb
    return abs(r - cr) <= tol and abs(g - cg) <= tol and abs(b - cb) <= tol


def _page_bg_tolerance(enabled: bool, key_tol: int) -> int:
    """Фон страницы и чёрный кадр WebView (#000 / #010102) всегда вырезаются."""
    if not enabled:
        return 16
    return max(2, min(int(key_tol), 16))


def _content_runs(
    buf: bytes,
    width: int,
    height: int,
    page: tuple[int, int, int],
    key_rgb: tuple[int, int, int],
    page_tol: int,
    key_tol: int,
) -> tuple[list[tuple[int, int, int, int]], int]:
    """Горизонтальные отрезки непрозрачного персонажа и хеш маски."""
    pr, pg, pb = page
    kr, kg, kb = key_rgb
    use_key = key_tol >= 0
    rects: list[tuple[int, int, int, int]] = []
    mask = 2166136261
    mv = memoryview(buf)
    for y in range(height):
        row = y * width * 4
        x = 0
        while x < width:
            i = row + x * 4
            b, g, r = mv[i], mv[i + 1], mv[i + 2]
            bg = abs(r - pr) <= page_tol and abs(g - pg) <= page_tol and abs(b - pb) <= page_tol
            if not bg and use_key:
                bg = abs(r - kr) <= key_tol and abs(g - kg) <= key_tol and abs(b - kb) <= key_tol
            if bg:
                x += 1
                continue
            start = x
            x += 1
            while x < width:
                j = row + x * 4
                b, g, r = mv[j], mv[j + 1], mv[j + 2]
                bg = abs(r - pr) <= page_tol and abs(g - pg) <= page_tol and abs(b - pb) <= page_tol
                if not bg and use_key:
                    bg = abs(r - kr) <= key_tol and abs(g - kg) <= key_tol and abs(b - kb) <= key_tol
                if bg:
                    break
                x += 1
            rects.append((start, y, x, y + 1))
            mask = (mask ^ (start + (x << 8) + (y << 16))) * 16777619 & 0xFFFFFFFF
    return rects, mask


class _RGNDATAHEADER(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint),
        ("iType", ctypes.c_uint),
        ("nCount", ctypes.c_uint),
        ("nRgnSize", ctypes.c_uint),
        ("rcBound", _RECT),
    ]


_RDH_RECTANGLES = 1


def _region_from_rects(rects: list[tuple[int, int, int, int]], width: int, height: int):
    n = len(rects)
    if n == 0:
        return _gdi.CreateRectRgn(0, 0, 0, 0)
    hdr_size = ctypes.sizeof(_RGNDATAHEADER)
    rect_size = ctypes.sizeof(_RECT)
    total = hdr_size + n * rect_size
    raw = (ctypes.c_byte * total)()
    hdr = _RGNDATAHEADER.from_buffer(raw)
    hdr.dwSize = hdr_size
    hdr.iType = _RDH_RECTANGLES
    hdr.nCount = n
    hdr.nRgnSize = n * rect_size
    hdr.rcBound.left = 0
    hdr.rcBound.top = 0
    hdr.rcBound.right = width
    hdr.rcBound.bottom = height
    arr = (_RECT * n).from_buffer(raw, hdr_size)
    for i, (left, top, right, bottom) in enumerate(rects):
        arr[i].left = left
        arr[i].top = top
        arr[i].right = right
        arr[i].bottom = bottom
    region = _gdi.ExtCreateRegion(None, total, ctypes.cast(raw, ctypes.c_void_p))
    if region:
        return region
    _LOG.debug("avatar shape: ExtCreateRegion failed n=%s, fallback", n)
    region = _gdi.CreateRectRgn(0, 0, 0, 0)
    if not region:
        return None
    for left, top, right, bottom in rects:
        run = _gdi.CreateRectRgn(left, top, right, bottom)
        if not run:
            continue
        _gdi.CombineRgn(region, region, run, _RGN_OR)
        _gdi.DeleteObject(run)
    return region


def _is_chroma(b: int, g: int, r: int) -> bool:
    from .avatar_config import chroma_from_layout

    key = chroma_from_layout()
    page_tol = _page_bg_tolerance(bool(key["enabled"]), int(key["tolerance"]))
    if _matches_rgb(b, g, r, key["rgb"], page_tol):
        return True
    if key["enabled"]:
        return _matches_rgb(b, g, r, key["key_rgb"], int(key["tolerance"]))
    return False


def _capture_client(hwnd: int, *, unclip: bool = False) -> tuple[int, int, bytes] | None:
    if unclip:
        # Пустая обрезка не даёт PrintWindow увидеть страницу — снимаем её до кадра.
        _user32.SetWindowRgn(hwnd, None, False)
    rect = _RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width < 2 or height < 2:
        return None
    hdc = _user32.GetDC(hwnd)
    if not hdc:
        return None
    mem = bmp = None
    try:
        mem = _gdi.CreateCompatibleDC(hdc)
        bmp = _gdi.CreateCompatibleBitmap(hdc, width, height)
        if not mem or not bmp:
            return None
        _gdi.SelectObject(mem, bmp)
        if not _user32.PrintWindow(hwnd, mem, _PW_RENDERFULLCONTENT):
            return None
        info = _BITMAPINFOHEADER()
        info.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.biWidth = width
        info.biHeight = -height
        info.biPlanes = 1
        info.biBitCount = 32
        info.biCompression = 0
        buf = (ctypes.c_ubyte * (width * height * 4))()
        if _gdi.GetDIBits(mem, bmp, 0, height, buf, ctypes.byref(info), 0) == 0:
            return None
        return width, height, bytes(buf)
    finally:
        if bmp:
            _gdi.DeleteObject(bmp)
        if mem:
            _gdi.DeleteDC(mem)
        _user32.ReleaseDC(hwnd, hdc)


def refresh_avatar_shape(form: Any) -> str | int:
    """WebView2 не вырезается color-key. Окно обрезается по пикселям персонажа.

    Возвращает хеш маски, ``empty`` (кадра ещё нет) или ``fail``.
    """
    hwnd = _hwnd(form)
    if not hwnd:
        return "fail"
    had = getattr(form, "_ltts_shape", None)
    captured = _capture_client(hwnd, unclip=(had == 0))
    if captured is None:
        _LOG.debug("avatar shape: capture failed")
        if had == 0:
            form._ltts_shape = None
        return "fail"
    width, height, buf = captured
    from .avatar_config import chroma_from_layout

    key = chroma_from_layout()
    enabled = bool(key["enabled"])
    key_tol = int(key["tolerance"]) if enabled else -1
    page_tol = _page_bg_tolerance(enabled, int(key["tolerance"]))
    rects, mask = _content_runs(
        buf,
        width,
        height,
        key["rgb"],
        key["key_rgb"],
        page_tol,
        key_tol,
    )
    if not rects:
        # Кадра ещё нет: не прячем окно. Пустая область потом не даёт его вернуть.
        if had == 0:
            form._ltts_shape = None
        return "empty"
    if mask == getattr(form, "_ltts_shape", None):
        return mask
    region = _region_from_rects(rects, width, height)
    if not region:
        return "fail"
    if _user32.SetWindowRgn(hwnd, region, True):
        form._ltts_shape = mask
        _LOG.debug("avatar shape: region %sx%s runs=%s", width, height, len(rects))
        return mask
    _gdi.DeleteObject(region)
    _LOG.warning("avatar shape: SetWindowRgn failed %s", ctypes.get_last_error())
    return "fail"


def _proc_addr(proc: Any) -> int:
    return _hwnd_id(ctypes.cast(proc, ctypes.c_void_p).value or 0)


@_WNDPROC
def _wndproc(hwnd, msg, wparam, lparam):
    try:
        if msg == WM_NCHITTEST:
            # Дети WebView2 пропускают hit-test родителю, форма отвечает как заголовок.
            if _hwnd_id(hwnd) in _form_hwnds:
                return HTCAPTION
            return HTTRANSPARENT
        if msg == WM_NCLBUTTONDBLCLK:
            return 0
        if msg == WM_SYSCOMMAND and (int(wparam) & 0xFFF0) == SC_MAXIMIZE:
            return 0
    except Exception:
        _LOG.debug("wndproc", exc_info=True)
    old = _old_wndproc.get(_hwnd_id(hwnd))
    if old:
        return _user32.CallWindowProcW(old, hwnd, msg, wparam, lparam)
    return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _subclass(hwnd: int, *, is_form: bool) -> None:
    hwnd = _hwnd_id(hwnd)
    if is_form:
        _form_hwnds.add(hwnd)
    ours = _proc_addr(_wndproc)
    current = _hwnd_id(_user32.GetWindowLongPtrW(hwnd, GWLP_WNDPROC) or 0)
    if current == ours:
        return
    _old_wndproc[hwnd] = current
    _user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.c_void_p(ours))


def enable_native_drag(form: Any) -> None:
    """Клики в WebView2 не доходят до WinForms.MouseDown — тащим через WM_NCHITTEST."""
    hwnd = _hwnd(form)
    if not hwnd:
        return
    _subclass(hwnd, is_form=True)
    found: list[int] = []

    @_WNDENUMPROC
    def _enum(child, _lp):
        found.append(_hwnd_id(child))
        return True

    _enum_refs.append(_enum)
    _user32.EnumChildWindows(hwnd, _enum, 0)
    for child in found:
        _subclass(child, is_form=False)


def set_webview2_chroma_background(wv: Any) -> None:
    try:
        opaque = _chroma_color_opaque()
        wv.DefaultBackgroundColor = opaque
        core = wv.CoreWebView2
        if core is None:
            return
        try:
            from Microsoft.Web.WebView2.Core import CoreWebView2Color

            r, g, b = _effective_page_rgb()
            c = CoreWebView2Color()
            c.A = 255
            c.R = r
            c.G = g
            c.B = b
            core.DefaultBackgroundColor = c
        except Exception as e:
            _LOG.debug("CoreWebView2Color chroma: %s", e)
            try:
                core.DefaultBackgroundColor = opaque
            except Exception as e2:
                _LOG.warning("CoreWebView2 chroma bg: %s", e2)
    except Exception as e:
        _LOG.warning("WebView2 chroma bg: %s", e)


def inject_page_chroma_background(wv: Any) -> None:
    from .avatar_config import effective_page_chroma_hex

    core = getattr(wv, "CoreWebView2", None)
    if core is None:
        return
    script = _page_bg_script(effective_page_chroma_hex())
    wid = id(core)
    if wid not in _chroma_script_added:
        try:
            core.AddScriptToExecuteOnDocumentCreatedAsync(script)
            _chroma_script_added.add(wid)
        except Exception as e:
            _LOG.debug("AddScriptToExecuteOnDocumentCreated: %s", e)
    try:
        core.ExecuteScriptAsync(script)
    except Exception as e:
        _LOG.debug("ExecuteScript chroma bg: %s", e)


def _schedule_avatar_shape_poll(form: Any) -> None:
    """Пока картинка догружается, повторяем обрезку. Останавливаемся на стабильном кадре."""
    gen = int(getattr(form, "_ltts_shape_gen", 0)) + 1
    form._ltts_shape_gen = gen
    import threading

    from System import Action

    def _kick() -> None:
        last: str | int | None = None
        stable = 0
        for _ in range(150):
            if int(getattr(form, "_ltts_shape_gen", 0)) != gen:
                return
            threading.Event().wait(0.2)
            done = threading.Event()
            box: dict[str, Any] = {}

            def _ui(box: dict[str, Any] = box, done: threading.Event = done) -> None:
                try:
                    box["mask"] = refresh_avatar_shape(form)
                except Exception as e:
                    _LOG.warning("avatar shape: %s", e)
                    box["mask"] = "fail"
                finally:
                    done.set()

            try:
                form.BeginInvoke(Action(_ui))
            except Exception as e:
                _LOG.warning("avatar shape poll: %s", e)
                return
            if not done.wait(2.5):
                return
            mask = box.get("mask")
            if isinstance(mask, int) and mask == last:
                stable += 1
                if stable >= 2:
                    return
            else:
                stable = 0
            last = mask if isinstance(mask, (int, str)) else None

    threading.Thread(target=_kick, name="ltts-avatar-shape", daemon=True).start()


def tune_avatar_form(form: Any, owner: Any = None, *, transparency: bool = True) -> None:
    try:
        form.ShowInTaskbar = False
    except Exception:
        pass
    if owner is not None:
        try:
            form.Owner = owner
        except Exception:
            pass
    if transparency:
        wv = getattr(form, "webview", None)
        if wv is not None:
            set_webview2_chroma_background(wv)
            inject_page_chroma_background(wv)
        enable_native_drag(form)
        try:
            refresh_avatar_shape(form)
        except Exception as e:
            _LOG.warning("avatar shape: %s", e)
        _schedule_avatar_shape_poll(form)
    hwnd = _hwnd(form)
    if hwnd:
        clear_dwm_backdrop(hwnd)
        exclude_from_taskbar(hwnd)


def set_main_taskbar_visible(form: Any, visible: bool) -> None:
    try:
        form.ShowInTaskbar = bool(visible)
    except Exception:
        pass

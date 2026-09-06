"""Windows-only reference capture. Sends input only to a named DOSBox window."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import time
from pathlib import Path
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    parser.add_argument('--keys', default='')
    args = parser.parse_args()
    user = c.WinDLL('user32', use_last_error=True)
    user.SetProcessDPIAware()
    gdi = c.WinDLL('gdi32', use_last_error=True)
    user.GetDC.restype = w.HDC
    user.GetDC.argtypes = [w.HWND]
    gdi.CreateCompatibleDC.restype = w.HDC
    gdi.CreateCompatibleDC.argtypes = [w.HDC]
    gdi.CreateCompatibleBitmap.restype = w.HBITMAP
    gdi.CreateCompatibleBitmap.argtypes = [w.HDC, c.c_int, c.c_int]
    gdi.SelectObject.restype = w.HANDLE
    gdi.SelectObject.argtypes = [w.HDC, w.HANDLE]
    gdi.GetBitmapBits.argtypes = [w.HBITMAP, c.c_long, c.c_void_p]
    gdi.DeleteObject.argtypes = [w.HANDLE]
    gdi.DeleteDC.argtypes = [w.HDC]
    user.ReleaseDC.argtypes = [w.HWND, w.HDC]
    user.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
    found = []
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def callback(hwnd, _):
        title = c.create_unicode_buffer(512)
        user.GetWindowTextW(hwnd, title, 512)
        if 'DOSBox-X' in title.value:
            found.append((hwnd, title.value))
        return True
    user.EnumWindows(callback, 0)
    if not found:
        raise SystemExit('DOSBox-X window not found')
    hwnd, title = found[0]
    print(title)
    if args.keys:
        user.PostMessageW(hwnd, 0x1c, 1, 0)
        user.PostMessageW(hwnd, 0x6, 1, 0)
        user.PostMessageW(hwnd, 0x7, 0, 0)
        time.sleep(.1)
    for key in args.keys.split(','):
        if not key:
            continue
        vk = {'space':32, 'enter':13, 'esc':27, 'f9':120, 'left':37, 'up':38, 'right':39, 'down':40}.get(key, ord(key.upper()) if len(key) == 1 else 0)
        if not vk:
            raise ValueError(key)
        scan = user.MapVirtualKeyW(vk, 0)
        user.PostMessageW(hwnd, 0x100, vk, 1 | (scan << 16))
        time.sleep(.06)
        user.PostMessageW(hwnd, 0x101, vk, 1 | (scan << 16) | (3 << 30))
        time.sleep(.12)
    time.sleep(.3)
    rect = w.RECT()
    user.GetClientRect(hwnd, c.byref(rect))
    width, height = rect.right, rect.bottom
    dc = user.GetDC(hwnd)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
    previous = gdi.SelectObject(memory, bitmap)
    user.PrintWindow(hwnd, memory, 1)
    pixels = c.create_string_buffer(width * height * 4)
    gdi.GetBitmapBits(bitmap, len(pixels), pixels)
    Image.frombuffer('RGB', (width, height), pixels.raw, 'raw', 'BGRX', 0, 1).save(Path(args.output))
    gdi.SelectObject(memory, previous)
    gdi.DeleteObject(bitmap)
    gdi.DeleteDC(memory)
    user.ReleaseDC(hwnd, dc)


if __name__ == '__main__':
    main()

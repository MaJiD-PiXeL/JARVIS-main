"""Resolve the user's Windows folders, including folders redirected to OneDrive."""
import ctypes
from pathlib import Path
import sys
from uuid import UUID


FOLDERS = {
    "desktop": ("دسکتاپ", "B4BFCC3A-DB2C-424C-B029-7FE99A87C641", "Desktop"),
    "documents": ("اسناد", "FDD39AD0-238F-46AF-ADB4-6C85480369C7", "Documents"),
    "downloads": ("دانلودها", "374DE290-123F-4565-9164-39C4925E467B", "Downloads"),
    "pictures": ("تصاویر", "33E28130-4E1E-4676-835A-98395C3BC3BB", "Pictures"),
    "music": ("موسیقی", "4BD8D571-6D19-48D3-BE97-422220080E43", "Music"),
    "videos": ("ویدیوها", "18989B1D-99B5-455B-841C-AB7C74E4DDFC", "Videos"),
}


def known_folder(name):
    label, guid, fallback = FOLDERS[name]
    if sys.platform != "win32":
        return Path.home() / fallback
    folder_id = ctypes.create_string_buffer(UUID(guid).bytes_le)
    result = ctypes.c_wchar_p()
    try:
        status = ctypes.windll.shell32.SHGetKnownFolderPath(folder_id, 0, None, ctypes.byref(result))
        if status != 0 or not result.value:
            raise OSError(f"مسیر پوشهٔ {label} در ویندوز پیدا نشد.")
        return Path(result.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(result)

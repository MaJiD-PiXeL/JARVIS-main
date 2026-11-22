import os
from core.tts import speak
from core.tasks import open_app as _open_app, open_folder as _open_folder


def open_explorer(*args, **kwargs):
    return _open_app("explorer")


#  ---


def open_settings(*args, **kwargs):
    return _open_app("settings")


def open_control_panel(*args, **kwargs):
    speak("کنترل پنل را باز می کنم.")
    os.system("start control")


def open_task_manager(*args, **kwargs):
    speak("مدیریت وظایف را باز می کنم.")
    os.system("start taskmgr")


def open_cmd(*args, **kwargs):
    speak("خط فرمان را باز می کنم.")
    os.system("start cmd")


def open_powershell(*args, **kwargs):
    speak("پاورشل را باز می کنم.")
    os.system("start powershell")


def open_notepad(*args, **kwargs):
    return _open_app("notepad")


def open_calculator(*args, **kwargs):
    return _open_app("calculator")


def open_paint(*args, **kwargs):
    return _open_app("paint")


def open_snipping_tool(*args, **kwargs):
    speak("ابزار عکس از صفحه را باز می کنم.")
    os.system("start snippingtool")


def open_camera(*args, **kwargs):
    return _open_app("camera")


def open_downloads(*args, **kwargs):
    return _open_folder("downloads")


def open_documents(*args, **kwargs):
    return _open_folder("documents")


def open_desktop_folder():
    return _open_folder("desktop")


def open_pictures(*args, **kwargs):
    return _open_folder("pictures")


def open_music(*args, **kwargs):
    return _open_folder("music")


def open_videos(*args, **kwargs):
    return _open_folder("videos")


def open_run_dialog(*args, **kwargs):
    speak("پنجره اجرا را باز می کنم.")
    os.system("explorer.exe shell:::{2559a1f3-21d7-11d4-bdaf-00c04f60b9f0}")

from core.tasks import open_app as _open_app


def open_browser(*args, **kwargs):
    return _open_app("browser")


def open_youtube(*args, **kwargs):
    return _open_app("youtube")


def open_google(*args, **kwargs):
    return _open_app("browser")

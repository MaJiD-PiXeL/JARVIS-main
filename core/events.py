"""Small, optional bridge from the engine to a desktop event queue."""

_handler = None


def set_event_handler(handler):
    global _handler
    _handler = handler


def emit_event(kind, **data):
    if _handler is not None:
        _handler(kind, data)

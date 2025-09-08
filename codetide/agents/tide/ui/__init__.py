import os

if os.getenv("SKIP_AUTH"):
    pass
else:
    from .app import main

    __all__ = [
        "main"
    ]
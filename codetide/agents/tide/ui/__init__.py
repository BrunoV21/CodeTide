import os

if os.getenv("SKIP_AUTH"):
    from .app import main

    __all__ = [
        "main"
    ]
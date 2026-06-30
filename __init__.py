"""Expose the inner PyQCSNU package when importing from the workspace parent."""

from importlib import import_module
import sys

_real_package = import_module(".pyqcsnu", __name__)

from .pyqcsnu import *  # noqa: E402,F401,F403
from .pyqcsnu import __all__, __version__  # noqa: E402

__path__ = _real_package.__path__

for _submodule in ("backend", "client", "exceptions", "models"):
    sys.modules[f"{__name__}.{_submodule}"] = import_module(
        f".pyqcsnu.{_submodule}",
        __name__,
    )

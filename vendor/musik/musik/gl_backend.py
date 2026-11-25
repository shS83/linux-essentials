"""Choose Qt's desktop OpenGL platform before QApplication is constructed."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo


BACKEND_LABELS = {
    "auto": "Automatic (use launch environment)",
    "wayland_egl": "Wayland / EGL",
    "x11_glx": "X11 / GLX",
    "x11_egl": "X11 / EGL",
    "software_glx": "X11 / GLX (Mesa software)",
}


def available_backends(plugin_root=None, environ=None):
    """Offer installed desktop integrations that can connect to this session."""
    environ = os.environ if environ is None else environ
    root = Path(plugin_root or QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    choices = [("auto", BACKEND_LABELS["auto"])]
    if sys.platform != "linux":
        return choices
    if environ.get("WAYLAND_DISPLAY") and (root / "platforms/libqwayland.so").is_file():
        choices.append(("wayland_egl", BACKEND_LABELS["wayland_egl"]))
    if environ.get("DISPLAY") and (root / "platforms/libqxcb.so").is_file():
        integrations = root / "xcbglintegrations"
        if (integrations / "libqxcb-glx-integration.so").is_file():
            choices.append(("x11_glx", BACKEND_LABELS["x11_glx"]))
            if Path("/usr/lib/dri/swrast_dri.so").is_file() or Path("/usr/lib64/dri/swrast_dri.so").is_file():
                choices.append(("software_glx", BACKEND_LABELS["software_glx"]))
        if (integrations / "libqxcb-egl-integration.so").is_file():
            choices.append(("x11_egl", BACKEND_LABELS["x11_egl"]))
    return choices


def apply_backend(key, environ=None):
    """Set Qt's platform hints before creating QApplication; auto keeps caller hints."""
    environ = os.environ if environ is None else environ
    if key == "auto":
        return
    if key == "wayland_egl":
        environ["QT_QPA_PLATFORM"] = "wayland"
        environ.pop("QT_XCB_GL_INTEGRATION", None)
    elif key in ("x11_glx", "x11_egl", "software_glx"):
        environ["QT_QPA_PLATFORM"] = "xcb"
        environ["QT_XCB_GL_INTEGRATION"] = "xcb_egl" if key == "x11_egl" else "xcb_glx"
    else:
        return
    if key == "software_glx":
        environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    else:
        environ.pop("LIBGL_ALWAYS_SOFTWARE", None)


def apply_saved_backend(key, environ=None):
    """An explicit XCB integration in the launcher is a recovery override."""
    environ = os.environ if environ is None else environ
    if "QT_XCB_GL_INTEGRATION" not in environ:
        apply_backend(key, environ)

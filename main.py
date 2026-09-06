import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QIcon

from manual_studio.main_window import MainWindow


def resource_path(*parts):
    """Resolve recursos no fonte, PyInstaller e cx_Freeze."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    elif getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)



def register_preview_scheme():
    """Registra o esquema usado pela prévia HTML antes de criar o QApplication."""
    try:
        from PyQt5.QtWebEngineCore import QWebEngineUrlScheme
        scheme = QWebEngineUrlScheme(b"manualpreview")
        syntax_group = getattr(QWebEngineUrlScheme, "Syntax", None)
        host_syntax = getattr(syntax_group, "HostAndPort", None) if syntax_group is not None else None
        if host_syntax is None:
            host_syntax = getattr(QWebEngineUrlScheme, "HostAndPort", None)
        if host_syntax is not None:
            scheme.setSyntax(host_syntax)
        flag_values = [getattr(QWebEngineUrlScheme, name, None) for name in ("SecureScheme", "LocalScheme", "LocalAccessAllowed")]
        flag_values = [value for value in flag_values if value is not None]
        if flag_values:
            flags = flag_values[0]
            for value in flag_values[1:]:
                flags = flags | value
            scheme.setFlags(flags)
        QWebEngineUrlScheme.registerScheme(scheme)
    except Exception:
        pass

def main():
    register_preview_scheme()
    QCoreApplication.setOrganizationName("ManualStudio")
    QCoreApplication.setApplicationName("Manual Studio Qt5")
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Manual Studio Qt5")

    icon_path = resource_path("assets", "manual_studio.ico")
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    win = MainWindow()
    if not app_icon.isNull():
        win.setWindowIcon(app_icon)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

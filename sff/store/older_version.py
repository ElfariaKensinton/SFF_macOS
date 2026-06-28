# SteaMidra - Steam game setup and manifest tool (SFF)
# Copyright (c) 2025-2026 Midrag (https://github.com/Midrags)
#
# This file is part of SteaMidra.
#
# SteaMidra is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SteaMidra is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SteaMidra.  If not, see <https://www.gnu.org/licenses/>.
import logging

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


def open_older_version_browser(parent: QWidget, app_id: str, quiet: bool = False) -> None:
    window = QWidget(parent)
    window.setWindowTitle(f"SteamDB — {app_id}")
    window.resize(1000, 750)

    layout = QVBoxLayout(window)
    browser = QWebEngineView(window)

    if not quiet:
        from sff.storage.settings import get_setting
        from sff.structs import Settings
        quiet = str(get_setting(Settings.OLDER_VERSION_QUIET) or "").lower() in ("true", "1", "yes")

    timeout = QTimer(window)
    timeout.setSingleShot(True)
    timeout.setInterval(60000)

    def cleanup():
        try:
            timeout.stop()
        except Exception:
            pass
        browser.stop()
        browser.page().deleteLater()
        window.close()

    def _on_timeout():
        if not quiet:
            QMessageBox.warning(
                window,
                "SteamDB timed out",
                "The SteamDB browser session exceeded 60 seconds and was closed.",
            )
        cleanup()

    timeout.timeout.connect(_on_timeout)
    timeout.start()

    layout.addWidget(browser)
    window.setLayout(layout)

    url = QUrl(f"https://steamdb.info/app/{app_id}/depots/")
    browser.setUrl(url)

    from sff.gui.main_window import SFFMainWindow
    p = parent
    while p is not None:
        if isinstance(p, SFFMainWindow):
            if not hasattr(p, "_older_version_windows"):
                p._older_version_windows = []
            p._older_version_windows.append(window)
            break
        p = p.parent()

    window.show()

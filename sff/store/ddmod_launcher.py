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
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class DdmodLauncher(QObject):
    finished = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self, exe_path: Path, *args: str) -> tuple[int, str, str]:
        cmd = [str(exe_path), *args]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            stdout, stderr = proc.communicate()
            rc = proc.wait()
            return rc, stdout, stderr
        except FileNotFoundError:
            return -1, "", f"Executable not found: {exe_path}"
        except Exception as exc:
            return -1, "", str(exc)

    def run_and_report(self, parent_widget, exe_path: Path, *args: str) -> None:
        rc, stdout, stderr = self.run(exe_path, *args)
        if rc == 0:
            body = stdout.strip() or "Done."
            QMessageBox.information(parent_widget, "DDMod success", body)
        else:
            body = (stderr.strip() or stdout.strip() or "(no output)")
            QMessageBox.critical(parent_widget, f"DDMod failed", f"Exit {rc}\n\n{body}")
        self.finished.emit(stdout, stderr)

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

"""A9 startup self-update popup.

Shown by Main_gui.py when update_available() reports a newer release. The
release notes come from updater.fetch_release_notes() as Markdown. Three
buttons emit signals so the caller can run the existing update flow,
persist a skip, or just dismiss.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


class SelfUpdateDialog(QDialog):
    download_now = pyqtSignal()
    skip_this_version = pyqtSignal()
    remind_later = pyqtSignal()

    def __init__(self, parent, version, release_notes_markdown):
        super().__init__(parent)
        self.setWindowTitle("SteaMidra Update Available")
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)

        header = QLabel(f"A new version is available: <b>{version}</b>")
        header.setTextFormat(1)  # Qt::RichText
        layout.addWidget(header)

        notes = QTextBrowser(self)
        notes.setOpenExternalLinks(True)
        # QTextBrowser renders Markdown natively. Empty body falls back to a
        # plain "no notes" line so the dialog still has content.
        if release_notes_markdown:
            notes.setMarkdown(release_notes_markdown)
        else:
            notes.setPlainText("No release notes were available.")
        layout.addWidget(notes, stretch=1)

        button_row = QHBoxLayout()
        download_btn = QPushButton("Download Now", self)
        skip_btn = QPushButton("Skip This Version", self)
        remind_btn = QPushButton("Remind Later", self)
        button_row.addWidget(download_btn)
        button_row.addStretch(1)
        button_row.addWidget(skip_btn)
        button_row.addWidget(remind_btn)
        layout.addLayout(button_row)

        download_btn.clicked.connect(self._on_download)
        skip_btn.clicked.connect(self._on_skip)
        remind_btn.clicked.connect(self._on_remind)

    def _on_download(self):
        self.download_now.emit()
        self.accept()

    def _on_skip(self):
        self.skip_this_version.emit()
        self.accept()

    def _on_remind(self):
        self.remind_later.emit()
        self.reject()

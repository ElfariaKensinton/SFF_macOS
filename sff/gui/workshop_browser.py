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

"""Embedded Workshop browser with persistent Steam session."""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sff.utils import root_folder


_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Module-level singletons. The profile owns persistent storage and cookies for
# the Workshop sign-in session and must outlive every dialog so a second open
# does not rebuild the QtWebEngine surface from scratch (the source of the
# white-box bug). The dialog reference is cleared on close via destroyed().
_WORKSHOP_PROFILE: Optional[QWebEngineProfile] = None
_WORKSHOP_DIALOG: Optional[QDialog] = None


def _get_workshop_profile() -> QWebEngineProfile:
    global _WORKSHOP_PROFILE
    if _WORKSHOP_PROFILE is not None:
        return _WORKSHOP_PROFILE
    app = QApplication.instance()
    profile = QWebEngineProfile("SteaMidraWorkshop", app)
    base_path = root_folder(outside_internal=True) / "webengine_profile"
    storage_path = base_path / "storage"
    cache_path = base_path / "cache"
    storage_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)
    profile.setPersistentStoragePath(str(storage_path))
    profile.setCachePath(str(cache_path))
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    )
    profile.setHttpUserAgent(_CHROME_UA)
    _WORKSHOP_PROFILE = profile
    return profile


def open_workshop_browser(app_id, parent=None):
    global _WORKSHOP_DIALOG

    if _WORKSHOP_DIALOG is not None and _WORKSHOP_DIALOG.isVisible():
        _WORKSHOP_DIALOG.raise_()
        _WORKSHOP_DIALOG.activateWindow()
        return

    profile = _get_workshop_profile()
    page = QWebEnginePage(profile)
    view = QWebEngineView()
    view.setPage(page)
    view.hide()

    workshop_url = f"https://steamcommunity.com/app/{app_id}/workshop/" if app_id else "https://steamcommunity.com/workshop/"

    dialog = QDialog(parent)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.setWindowTitle(f"Steam Workshop - App {app_id}")
    dialog.resize(900, 700)

    root_layout = QVBoxLayout(dialog)
    tabs = QTabWidget()
    root_layout.addWidget(tabs)

    # ── Browse tab (the existing dialog body) ────────────────────
    browse_tab = QWidget()
    layout = QVBoxLayout(browse_tab)

    url_bar = QLineEdit()
    url_bar.setPlaceholderText("URL")
    url_bar.setReadOnly(False)

    def navigate_from_bar():
        text = url_bar.text().strip()
        if text:
            if not text.startswith(("http://", "https://")):
                text = "https://" + text
            view.setUrl(QUrl(text))

    def update_url_bar(qurl):
        url_str = qurl.toString()
        if url_str and url_bar.text() != url_str:
            url_bar.blockSignals(True)
            url_bar.setText(url_str)
            url_bar.blockSignals(False)

    view.urlChanged.connect(update_url_bar)
    url_bar.returnPressed.connect(navigate_from_bar)
    layout.addWidget(url_bar)

    btn_layout = QHBoxLayout()
    login_btn = QPushButton("Login to Steam")
    login_btn.clicked.connect(
        lambda: view.setUrl(QUrl("https://store.steampowered.com/login/"))
    )
    workshop_btn = QPushButton("Workshop")
    workshop_btn.clicked.connect(lambda: view.setUrl(QUrl(
        f"https://steamcommunity.com/app/{app_id}/workshop/" if app_id else "https://steamcommunity.com/workshop/"
    )))
    copy_btn = QPushButton("Copy Workshop link")
    def copy_current_url():
        clipboard = QApplication.clipboard()
        url = view.url().toString()
        clipboard.setText(url if url else "")

    copy_btn.clicked.connect(copy_current_url)

    dl_btn = QPushButton("Download Item")
    dl_btn.setToolTip(
        "Download the currently viewed workshop item (tries SteamWebAPI, GGNetwork, SteamCMD)"
    )

    status_label = QLabel("")
    status_label.setStyleSheet("font-size:11px;opacity:0.7;")

    _dl_thread = [None]

    class _DlWorker(QThread):
        log_msg = pyqtSignal(str)
        finished = pyqtSignal(bool, str)

        def __init__(self, item_id, game_id, out_dir):
            super().__init__()
            self._item_id = item_id
            self._game_id = game_id
            self._out_dir = out_dir

        def run(self):
            from sff.manifest.workshop_dl import download_workshop_item
            from sff.storage.settings import get_setting
            from sff.structs import Settings
            user = get_setting(Settings.STEAM_USER) or "anonymous"
            pwd = get_setting(Settings.STEAM_PASS) or ""
            result = download_workshop_item(
                self._item_id,
                self._game_id,
                self._out_dir,
                steam_username=user,
                steam_password=pwd,
                log=self.log_msg.emit,
            )
            self.finished.emit(result["success"], result.get("path") or result.get("error") or "")

    def start_download():
        from sff.manifest.workshop_dl import parse_workshop_item_id
        from sff.utils import sff_data_dir
        current_url = url_bar.text().strip()
        item_id = parse_workshop_item_id(current_url)
        if not item_id:
            status_label.setText("No item ID found in the current URL")
            return
        out_dir = sff_data_dir() / "downloaded_files" / "workshop" / item_id
        status_label.setText(f"Downloading item {item_id}...")
        dl_btn.setEnabled(False)
        worker = _DlWorker(item_id, str(app_id) if app_id else "0", out_dir)
        _dl_thread[0] = worker

        def on_log(msg):
            status_label.setText(msg[:120])

        def on_done(success, path_or_err):
            dl_btn.setEnabled(True)
            if success:
                status_label.setText(f"[OK] Saved to: {path_or_err}")
            else:
                status_label.setText(f"[!] {path_or_err}")

        worker.log_msg.connect(on_log)
        worker.finished.connect(on_done)
        worker.start()

    dl_btn.clicked.connect(start_download)

    btn_layout.addWidget(login_btn)
    btn_layout.addWidget(workshop_btn)
    btn_layout.addWidget(copy_btn)
    btn_layout.addWidget(dl_btn)
    btn_layout.addStretch()
    layout.addLayout(btn_layout)
    layout.addWidget(status_label)

    loading_label = QLabel("Loading Steam Workshop...")
    loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    loading_label.setStyleSheet("font-size:14px;color:#888;padding:80px;")
    layout.addWidget(loading_label)
    layout.addWidget(view)

    def on_page_loaded(ok):
        if ok:
            loading_label.hide()
            view.show()

    page.loadFinished.connect(on_page_loaded)
    view.setUrl(QUrl(workshop_url))

    tabs.addTab(browse_tab, "Browse")

    # ── Bypass download tab ──────────────────────────────────────
    bypass_tab = QWidget()
    bypass_layout = QVBoxLayout(bypass_tab)

    bypass_help = QLabel(
        "Paste a Workshop item URL, a Workshop collection URL, "
        "or a newline-separated list. The bypass path uses "
        "IPublishedFileService and the UGC CDN, no Steam session cookies."
    )
    bypass_help.setWordWrap(True)
    bypass_help.setStyleSheet("font-size:11px;opacity:0.75;")
    bypass_layout.addWidget(bypass_help)

    bypass_input = QPlainTextEdit()
    bypass_input.setPlaceholderText(
        "https://steamcommunity.com/sharedfiles/filedetails/?id=...\n"
        "https://steamcommunity.com/workshop/filedetails/?id=...   (collection)\n"
        "1234567890\n"
        "..."
    )
    bypass_layout.addWidget(bypass_input, 1)

    key_row = QHBoxLayout()
    key_label = QLabel("Web API key (optional override):")
    key_label.setStyleSheet("font-size:11px;")
    bypass_key = QLineEdit()
    bypass_key.setPlaceholderText("Leave blank to use Settings → Steam Web API Key")
    bypass_key.setEchoMode(QLineEdit.EchoMode.Password)
    key_row.addWidget(key_label)
    key_row.addWidget(bypass_key, 1)
    bypass_layout.addLayout(key_row)

    bypass_action_row = QHBoxLayout()
    bypass_btn = QPushButton("Download (bypass)")
    bypass_status = QLabel("")
    bypass_status.setStyleSheet("font-size:11px;opacity:0.7;")
    bypass_action_row.addWidget(bypass_btn)
    bypass_action_row.addStretch()
    bypass_action_row.addWidget(bypass_status)
    bypass_layout.addLayout(bypass_action_row)

    bypass_results = QListWidget()
    bypass_layout.addWidget(bypass_results, 2)

    _bypass_thread = [None]

    class _BypassWorker(QThread):
        progress = pyqtSignal(dict)
        finished_payload = pyqtSignal(dict)

        def __init__(self, raw_input: str, api_key: str, out_dir: Path):
            super().__init__()
            self._raw = raw_input
            self._key = api_key
            self._out = out_dir

        def run(self):
            from sff.manifest.workshop_dl import run_bypass_batch

            def _emit(payload):
                self.progress.emit(payload)

            def _log(msg):
                self.progress.emit({"task": "workshop_bypass", "log": str(msg)})

            try:
                summary = run_bypass_batch(
                    self._raw, self._out, self._key, _emit, log=_log
                )
            except Exception as e:
                summary = {"success": False, "error": str(e)}
            self.finished_payload.emit(summary)

    def _resolve_api_key() -> str:
        override = bypass_key.text().strip()
        if override:
            return override
        try:
            from sff.storage.settings import get_setting
            from sff.structs import Settings
            from sff.strings import STEAM_WEB_API_KEY as _DEFAULT_KEY

            saved = get_setting(Settings.STEAM_WEB_API_KEY)
            if isinstance(saved, str) and saved.strip():
                return saved.strip()
            return _DEFAULT_KEY
        except Exception:
            return ""

    def _start_bypass():
        raw = bypass_input.toPlainText()
        api_key = _resolve_api_key()
        if not api_key:
            bypass_status.setText("[!] no Web API key available")
            return
        bypass_results.clear()
        bypass_btn.setEnabled(False)
        bypass_status.setText("Resolving items and downloading...")
        from sff.utils import sff_data_dir
        out_dir = sff_data_dir() / "downloaded_files" / "workshop"
        worker = _BypassWorker(raw, api_key, out_dir)
        _bypass_thread[0] = worker

        def _on_progress(payload):
            if not isinstance(payload, dict):
                return
            if payload.get("reason") == "no items to process":
                bypass_results.addItem("(no items to process)")
                return
            if "log" in payload:
                bypass_results.addItem(str(payload["log"])[:200])
                return
            pid = payload.get("item_id") or "?"
            if payload.get("success"):
                bypass_results.addItem(f"[OK] {pid} -> {payload.get('path', '')}")
            else:
                bypass_results.addItem(f"[!] {pid}: {payload.get('error', 'failed')}")

        def _on_done(summary):
            bypass_btn.setEnabled(True)
            if not isinstance(summary, dict):
                bypass_status.setText("[!] bypass batch crashed")
                return
            if not summary.get("success", True) and summary.get("error"):
                bypass_status.setText(f"[!] {summary['error']}")
                return
            added = int(summary.get("added") or 0)
            failed = int(summary.get("failed") or 0)
            bypass_status.setText(f"Done: {added} added, {failed} failed")

        worker.progress.connect(_on_progress)
        worker.finished_payload.connect(_on_done)
        worker.start()

    bypass_btn.clicked.connect(_start_bypass)

    tabs.addTab(bypass_tab, "Bypass download")

    def _on_destroyed(_obj=None):
        global _WORKSHOP_DIALOG
        _WORKSHOP_DIALOG = None

    dialog.destroyed.connect(_on_destroyed)
    _WORKSHOP_DIALOG = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()

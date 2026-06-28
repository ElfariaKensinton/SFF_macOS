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

"""
Single-instance guard for SteaMidra.

Uses QLocalServer / QLocalSocket so only one process runs at a time.
A second launch sends a SHOW message to the existing instance and exits.
"""

import logging
from typing import Callable, Optional

from PyQt6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

_SERVER_NAME = "SteaMidra-v1"
_CONNECT_TIMEOUT_MS = 1000


class SingleInstanceGuard:
    """
    Call try_activate_existing() first. If it returns True, exit immediately.
    Otherwise call start_server(callback) to handle show requests from future instances.
    """

    def __init__(self):
        self._server: Optional[QLocalServer] = None

    def try_activate_existing(self, message: str = "SHOW") -> bool:
        """
        Try to connect to an already-running SteaMidra instance.
        Sends *message* and returns True if one was found.
        """
        sock = QLocalSocket()
        sock.connectToServer(_SERVER_NAME)
        if sock.waitForConnected(_CONNECT_TIMEOUT_MS):
            sock.write(message.encode("utf-8"))
            sock.flush()
            sock.waitForBytesWritten(500)
            sock.disconnectFromServer()
            logger.info("Existing SteaMidra instance found — forwarding %s request", message)
            return True
        return False

    def start_server(self, on_show: Callable[[], None], on_file: Optional[Callable[[str], None]] = None) -> None:
        """
        Start the IPC server. Calls on_show() whenever a second instance connects.
        Calls on_file(path) when the message starts with 'FILE:'.
        Removes any stale server socket left from a previous crash first.
        """
        QLocalServer.removeServer(_SERVER_NAME)
        self._server = QLocalServer()
        self._server.newConnection.connect(lambda: self._handle_connection(on_show, on_file))
        if not self._server.listen(_SERVER_NAME):
            logger.debug("SingleInstanceGuard: could not start server — %s", self._server.errorString())
        else:
            logger.debug("SingleInstanceGuard: listening on %s", _SERVER_NAME)

    def _handle_connection(self, on_show: Callable[[], None], on_file: Optional[Callable[[str], None]] = None) -> None:
        conn = self._server.nextPendingConnection()
        if conn is None:
            return
        def _on_ready():
            msg = bytes(conn.readAll()).decode("utf-8", errors="replace").strip()
            if msg.startswith("FILE:") and on_file:
                on_file(msg[5:])
            else:
                on_show()
            conn.deleteLater()
        conn.readyRead.connect(_on_ready)

    def cleanup(self) -> None:
        if self._server:
            self._server.close()
            QLocalServer.removeServer(_SERVER_NAME)
            self._server = None

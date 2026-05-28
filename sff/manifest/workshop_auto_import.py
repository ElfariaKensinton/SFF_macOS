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

"""Workshop subscribed-mods auto-import.

Scans `<steam>/steamapps/workshop/content/<app_id>/` for numeric Workshop
item IDs and feeds the not-yet-downloaded ones into the existing workshop
downloader. Already-completed downloads (presence of a manifest under
`<sff_data>/downloaded_files/workshop/<workshop_id>/`) are skipped.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Protocol

logger = logging.getLogger(__name__)


class _Downloader(Protocol):
    def enqueue(self, app_id: int, workshop_id: str) -> None: ...


def scan_subscribed_workshop_ids(steam_path: Path, app_id: int) -> list[str]:
    """Return numeric workshop subdir names under
    `<steam>/steamapps/workshop/content/<app_id>/`, sorted ascending.

    Non-numeric subdirs and any files at that path are ignored.
    """
    base = Path(steam_path) / "steamapps" / "workshop" / "content" / str(app_id)
    if not base.exists() or not base.is_dir():
        return []
    out: list[str] = []
    try:
        for child in base.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            if not name.isdigit():
                continue
            out.append(name)
    except OSError as exc:
        logger.warning("scan_subscribed_workshop_ids: iterdir failed for %s: %s", base, exc)
        return []
    return sorted(out, key=int)


def _has_complete_manifest(sff_data: Path, workshop_id: str) -> bool:
    """A workshop ID counts as already-downloaded when its target dir
    holds at least one file. Empty dirs are treated as incomplete and
    get re-enqueued."""
    target = sff_data / "downloaded_files" / "workshop" / workshop_id
    if not target.is_dir():
        return False
    try:
        return any(target.iterdir())
    except OSError:
        return False


def workshop_auto_import(
    steam_path: Path,
    app_id: int,
    downloader: _Downloader,
    log: Callable[[str], None],
) -> dict:
    """Scan, dedupe, enqueue. Returns a UI summary dict.

    Successful runs return
    `{success: True, added: [...], skipped: [...], found: [...]}`.
    Errors return `{success: False, error: "..."}` after logging.
    """
    try:
        from sff.utils import sff_data_dir
        sff_data = sff_data_dir()

        found = scan_subscribed_workshop_ids(steam_path, app_id)
        added: list[str] = []
        skipped: list[str] = []

        for wid in found:
            if _has_complete_manifest(sff_data, wid):
                skipped.append(wid)
                continue
            try:
                downloader.enqueue(app_id, wid)
            except Exception as enqueue_err:
                logger.warning(
                    "workshop_auto_import: enqueue failed for %s/%s: %s",
                    app_id, wid, enqueue_err,
                )
                continue
            added.append(wid)

        log(
            f"workshop_auto_import: app_id={app_id} found={len(found)} "
            f"added={len(added)} skipped={len(skipped)}"
        )
        return {
            "success": True,
            "added": added,
            "skipped": skipped,
            "found": found,
        }
    except Exception as e:
        logger.exception("workshop_auto_import failed for app_id=%s", app_id)
        return {"success": False, "error": str(e)}

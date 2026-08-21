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

r"""Repair of 6.6.5-broken Linux downloads (flat backslash filenames).

The native CDN downloader used to join manifest filenames containing
Windows backslash separators directly onto the game folder. On Linux a
backslash is a legal filename character, so every file landed flat in
the game root with a literal name like ``Some\File\Name.exe`` and the
game could not launch. This module moves those files back into the
proper subdirectories — slowly, in the background, at most once a day.
"""

import logging
import shutil
import sys
import time
from pathlib import Path

from sff.core.utils import sff_data_dir

logger = logging.getLogger(__name__)

_STAMP_FILE = sff_data_dir() / "flat_file_repair_last_check"
_CHECK_INTERVAL_S = 24 * 60 * 60
_MOVE_PAUSE_S = 0.02


def _needs_check() -> bool:
    try:
        if not _STAMP_FILE.exists():
            return True
        last = float(_STAMP_FILE.read_text(encoding="utf-8").strip() or "0")
        return (time.time() - last) >= _CHECK_INTERVAL_S
    except Exception:
        return True


def _mark_checked() -> None:
    try:
        _STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STAMP_FILE.write_text(str(time.time()), encoding="utf-8")
    except Exception as e:
        logger.debug("flat-file repair stamp write failed: %s", e)


def _game_dirs(steam_path) -> list[Path]:
    from sff.core.storage.vdf import get_steam_libs
    try:
        libs = list(get_steam_libs(steam_path))
    except Exception:
        libs = []
    libs.append(Path(steam_path))
    out = []
    seen = set()
    for lib in libs:
        try:
            common = Path(lib) / "steamapps" / "common"
            if not common.is_dir():
                continue
            for child in common.iterdir():
                if child.is_dir():
                    key = str(child.resolve())
                    if key not in seen:
                        seen.add(key)
                        out.append(child)
        except OSError:
            continue
    return out


def repair_flat_files(steam_path) -> dict:
    """Move root-level files whose names contain backslashes into the
    proper subdirectories. Linux only. Returns a summary dict."""
    summary = {"scanned_games": 0, "repaired": 0, "failed": 0, "skipped": 0}
    if sys.platform == "win32":
        return summary
    if not steam_path:
        return summary
    if not _needs_check():
        return summary
    try:
        for game_dir in _game_dirs(steam_path):
            summary["scanned_games"] += 1
            try:
                entries = list(game_dir.iterdir())
            except OSError:
                continue
            for entry in entries:
                try:
                    if not entry.is_file():
                        continue
                    name = entry.name
                    if "\\" not in name:
                        continue
                    relative = name.replace("\\", "/")
                    if ".." in relative.split("/"):
                        summary["failed"] += 1
                        continue
                    dest = game_dir / relative
                    if dest.exists():
                        summary["skipped"] += 1
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(entry), str(dest))
                    summary["repaired"] += 1
                    time.sleep(_MOVE_PAUSE_S)
                except OSError as e:
                    logger.debug("flat-file repair failed for %s: %s", entry, e)
                    summary["failed"] += 1
    finally:
        _mark_checked()
    if summary["repaired"] or summary["failed"]:
        logger.info(
            "flat-file repair: %d repaired, %d skipped, %d failed across %d games",
            summary["repaired"], summary["skipped"], summary["failed"],
            summary["scanned_games"],
        )
    return summary

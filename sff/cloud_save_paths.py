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

"""Resolve per-game save-file paths using the Ludusavi manifest database.

The bundled manifest.yaml covers ~22k games with filesystem save paths
(not just Steam cloud). This module indexes it by Steam App ID and
resolves placeholder tags (<base>, <root>, <winDocuments>, etc.) into
real paths on the user's machine.

Only save-tagged paths matching the current platform are returned.
Registry, config-only, and non-matching OS/store entries are skipped.
"""

import logging
import os
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_MANIFEST: dict | None = None
_STEAM_INDEX: dict[str, dict] | None = None


def _manifest_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "manifest.yaml"


def _load_manifest() -> dict:
    global _MANIFEST, _STEAM_INDEX
    if _MANIFEST is not None:
        return _MANIFEST
    p = _manifest_path()
    if not p.is_file():
        logger.debug("manifest.yaml not found at %s", p)
        _MANIFEST = {}
        _STEAM_INDEX = {}
        return _MANIFEST
    try:
        with p.open("r", encoding="utf-8") as f:
            _MANIFEST = yaml.safe_load(f) or {}
        _STEAM_INDEX = {}
        for name, entry in _MANIFEST.items():
            if not isinstance(entry, dict):
                continue
            steam = entry.get("steam") or {}
            sid = str(steam.get("id", "")) if isinstance(steam, dict) else ""
            if sid:
                _STEAM_INDEX[sid] = entry
        logger.debug("Loaded save-path manifest: %d games, %d with steam ids",
                     len(_MANIFEST), len(_STEAM_INDEX))
    except Exception:
        logger.warning("Failed to load manifest.yaml", exc_info=True)
        _MANIFEST = {}
        _STEAM_INDEX = {}
    return _MANIFEST


def _game_by_steam_id(app_id: int) -> dict | None:
    _load_manifest()
    return (_STEAM_INDEX or {}).get(str(app_id))


def _matches_when(meta: dict) -> bool:
    conditions = meta.get("when") or []
    if not conditions:
        return True
    is_win = sys.platform == "win32"
    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        cond_os = str(cond.get("os", "")).lower()
        cond_store = str(cond.get("store", "")).lower()
        if cond_os and ((cond_os == "windows") != is_win):
            return False
        if cond_store and cond_store != "steam":
            return False
    return True


def _resolve_placeholder(path: str, base: str, root: str) -> list[str]:
    home = str(Path.home())
    p = path.replace("<base>", base).replace("<root>", root).replace("<home>", home)
    if sys.platform == "win32":
        p = p.replace("<winDocuments>", str(Path.home() / "Documents"))
        p = p.replace("<winAppData>", os.environ.get("APPDATA", ""))
        p = p.replace("<winLocalAppData>", os.environ.get("LOCALAPPDATA", ""))
        p = p.replace("<winLocalAppDataLow>",
                      os.path.join(os.environ.get("LOCALAPPDATA", ""), "..", "LocalLow"))
        p = p.replace("<winProgramData>", os.environ.get("PROGRAMDATA", ""))
    else:
        p = p.replace("<xdgData>", os.path.join(home, ".local", "share"))
        p = p.replace("<xdgConfig>", os.path.join(home, ".config"))
    p = p.replace("<storeUserId>", "*")
    p = p.replace("<storeGameId>", "*")
    p = p.replace("<osUserName>", os.environ.get("USERNAME", os.environ.get("USER", "")))
    return [p]


def get_save_paths(app_id: int, game_base_dir: str) -> list[str]:
    entry = _game_by_steam_id(app_id)
    if entry is None:
        return []
    files = entry.get("files") or {}
    base = str(Path(game_base_dir))
    root = str(Path(game_base_dir).parent)
    paths: list[str] = []
    for raw_path, meta in files.items():
        if not isinstance(meta, dict):
            continue
        tags = meta.get("tags") or []
        if "save" not in tags:
            continue
        if not _matches_when(meta):
            continue
        resolved = _resolve_placeholder(raw_path, base, root)
        paths.extend(resolved)
    if paths:
        logger.debug("Resolved %d custom save path(s) for app_id=%d", len(paths), app_id)
    return paths


def get_install_dir_candidates(app_id: int) -> list[str]:
    entry = _game_by_steam_id(app_id)
    if entry is None:
        return []
    install_dir = entry.get("installDir") or {}
    return list(install_dir.keys())

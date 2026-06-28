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


"""Miscellaneous stuff used across various files"""


import logging
import os
import sys

from pathlib import Path


import vdf  # type: ignore


logger = logging.getLogger(__name__)


def sff_data_dir() -> Path:
    """Return a writable directory for SteaMidra user data (logs, settings, cache).

    Always returns the directory containing the running script or exe.
    On a frozen build this is the exe's parent (e.g. %LOCALAPPDATA%\\SteaMidra\\
    when installed via the NSIS installer). When running from source it is the
    project root next to Main_gui.py. settings.bin, debug.log, and cache files
    are always written beside the entry-point, never in a platform-specific dir.
    """
    return root_folder(outside_internal=True)


def root_folder(outside_internal = False):
    bundled = getattr(sys, "frozen", False)

    if bundled:
        if outside_internal:
            ai = os.environ.get('APPIMAGE')
            if ai:
                return Path(ai).resolve().parent
            return Path(sys.executable).resolve().parent

        internal_path = getattr(sys, '_MEIPASS', None)
        if internal_path:
            return Path(internal_path).resolve()
        return Path(sys.executable).resolve().parent

    script_root = Path(__file__).resolve().parent.parent
    if outside_internal:
        return script_root
    return script_root


def manifests_staging_dir() -> Path:
    """Canonical staging directory for downloaded .manifest files.

    Used by:
      * sff.zip — extracts manifests from provider ZIPs into here
      * sff.manifest.downloader — refreshes depotcache from here, prefers
        these over stale depotcache copies
      * sff.linux.linux_download — collects manifests for DDMod forwarding

    Cannot use Path.cwd() because cwd flips between repo root (dev),
    AppImage mount point (frozen Linux build), and arbitrary launch
    directory (when invoked from the Web UI). The result is a quiet
    "no manifests found, fall through to anonymous CDN fetch" failure
    that ends in a 401 inside DDMod.

    Returns the writable user-data root + "manifests/", creating it.
    """
    out = root_folder(outside_internal=True) / "manifests"
    out.mkdir(parents=True, exist_ok=True)
    return out


def enter_path(

    obj,

    *paths,

    mutate = False,

    ignore_case = False,

    default = None,

):

    """

    Walks or creates nested dicts in a VDFDict/dict.

    Returns an empty dict-like if not found.

    `default` key only works when `mutate` is False.

    """

    current = obj

    for key in paths:

        if isinstance(key, int):
            try:
                current = current[key]  # pyright: ignore[reportUnknownVariableType]
            except IndexError:
                return type(current)()
            continue
        original_key = key
        if ignore_case:
            key = key.lower()
        key_map = {}
        for x in current:  # pyright: ignore[reportUnknownVariableType]
            if ignore_case and isinstance(x, str):
                key_map[x.lower()] = x
            else:
                key_map[x] = x
        if key in key_map:
            current = current[  # pyright: ignore[reportUnknownVariableType]
                key_map[key]
            ]
        else:
            if not mutate:
                return default if default else type(current)()
            # create a new key that's the same type as current
            new_node = type(current)()
            current[original_key] = new_node
            current = new_node

    return current  # pyright: ignore[reportUnknownVariableType]

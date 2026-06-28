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

import json
from pathlib import Path

from sff.http_utils import get_game_name
from sff.structs import NamedIDs


def _id_cache_path(folder: Path) -> Path:
    return folder / "names.json"


def _blank_registry() -> NamedIDs:
    return NamedIDs({})


def _read_registry_file(cache_file: Path):
    if not cache_file.is_file():
        return _blank_registry()
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        return _blank_registry()
    return payload if isinstance(payload, dict) else _blank_registry()


def _write_registry_file(cache_file: Path, payload):
    cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _scan_saved_lua_ids(folder: Path) -> list[str]:
    return [lua_path.stem for lua_path in folder.glob("*.lua")]


def _backfill_unknown_names(registry, disk_ids) -> bool:
    dirty = False
    for disk_id in disk_ids:
        if disk_id in registry:
            continue
        registry[disk_id] = get_game_name(disk_id)
        dirty = True
    return dirty


def get_named_ids(folder):
    if not folder.is_dir():
        folder.mkdir()
        return NamedIDs({})

    cache_file = _id_cache_path(folder)
    registry = _read_registry_file(cache_file)

    if _backfill_unknown_names(registry, _scan_saved_lua_ids(folder)):
        _write_registry_file(cache_file, registry)
    return registry

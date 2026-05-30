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

"""Per-game "Show update available" toggle.

Drops a 00_LetUpdate_override.lua file into the game's stplug-in folder
when the user flips the per-game toggle in the context menu. The override
chains through LumaCore's setManifestid binding via the _originals table
so the user-supplied manifest gid feeds Steam's depot resolver while still
letting Steam see the depot is "out of date" and surface the Update button
in the library card.

Settings storage: GAME_UPDATE_OVERRIDE (json string, dict[str_appid -> bool]).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# the override script body. small enough to inline; bigger templates went
# in their own .lua.tpl historically and got out of sync, plain string is
# easier to grep and easier for users to read.
_SCRIPT_BODY = """-- LumaCore per-game LetUpdate override (managed by SteaMidra)
-- Wraps setManifestid so the user-supplied gid still lands but Steam keeps
-- treating the depot as updatable. Lets the library "Update" button stay
-- visible for games yall want to track.
local original_setManifestid = _originals and _originals.setManifestid or setManifestid
local original_setmanifestid = _originals and _originals.setmanifestid or setmanifestid

local function _route(depotId, gidStr, sizeArg)
    local fn = original_setManifestid or original_setmanifestid
    if fn then
        return fn(depotId, gidStr, sizeArg)
    end
end

function setManifestid(depotId, gidStr, sizeArg)
    return _route(depotId, gidStr, sizeArg)
end

function setmanifestid(depotId, gidStr, sizeArg)
    return _route(depotId, gidStr, sizeArg)
end
"""


def _override_path(steam_path: Path, app_id: int) -> Path:
    return Path(steam_path) / "config" / "stplug-in" / str(app_id) / "00_LetUpdate_override.lua"


def _legacy_override_path(steam_path: Path, app_id: int) -> Path:
    # older builds dropped the override straight into stplug-in/ named after
    # the appid. handle removal on toggle-off so we don't leave both behind.
    return Path(steam_path) / "config" / "stplug-in" / f"{app_id}_LetUpdate_override.lua"


def write_override(steam_path, app_id) -> bool:
    if not steam_path:
        return False
    try:
        target = _override_path(Path(steam_path), int(app_id))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_SCRIPT_BODY, encoding="utf-8")
        return True
    except Exception as e:
        logger.warning("write_override(%s) failed: %s", app_id, e)
        return False


def remove_override(steam_path, app_id) -> bool:
    if not steam_path:
        return False
    ok = True
    for p in (_override_path(Path(steam_path), int(app_id)),
              _legacy_override_path(Path(steam_path), int(app_id))):
        try:
            if p.exists():
                p.unlink()
        except Exception as e:
            ok = False
            logger.warning("remove_override(%s) failed: %s", p, e)
    return ok


def load_overrides() -> dict:
    from sff.storage.settings import get_setting
    from sff.structs import Settings
    raw = get_setting(Settings.GAME_UPDATE_OVERRIDE) or "{}"
    if not isinstance(raw, str):
        return {}
    try:
        d = json.loads(raw)
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def save_overrides(d: dict) -> None:
    from sff.storage.settings import set_setting
    from sff.structs import Settings
    try:
        set_setting(Settings.GAME_UPDATE_OVERRIDE, json.dumps(d))
    except Exception as e:
        logger.warning("save_overrides failed: %s", e)


def is_enabled(app_id) -> bool:
    return bool(load_overrides().get(str(app_id), False))


def set_enabled(steam_path, app_id, enabled: bool) -> bool:
    """Flip the toggle and write/remove the override file."""
    overrides = load_overrides()
    key = str(app_id)
    if enabled:
        overrides[key] = True
        ok = write_override(steam_path, app_id)
    else:
        overrides.pop(key, None)
        ok = remove_override(steam_path, app_id)
    save_overrides(overrides)
    return ok

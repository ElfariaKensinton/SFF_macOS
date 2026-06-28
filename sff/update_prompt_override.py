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
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 00_ prefix forces this to load before any per-game .lua, which matters
# because the wrapper has to capture the C-bound setManifestid into its
# upvalue BEFORE the game .lua starts calling setManifestid for its own
# depots. Filename is also a clear marker for support sweeps.
OVERRIDE_FILENAME = "00_LetUpdate_override.lua"

def _render_override_body(excluded_depots=()) -> str:
    depot_ids = sorted({int(x) for x in (excluded_depots or []) if str(x).isdigit()})
    depot_json = json.dumps(depot_ids, separators=(",", ":"))
    depot_lines = "\n".join(f"    [{depot}] = true," for depot in depot_ids)
    if not depot_lines:
        depot_lines = "    -- empty means every setManifestid call is skipped"
    return f"""\
-- 00_LetUpdate_override.lua
-- Lets games show the "Update" prompt in the Steam library when Steam
-- pushes a newer manifest than the one our .lua pinned.
--
-- STEAMIDRA_EXCLUDED_DEPOTS: {depot_json}
--
-- Managed by SteaMidra. Toggle "Show in-Steam 'Update available' prompts"
-- in Settings to remove this file. Editing it by hand is fine but the
-- toggle will rewrite or delete it on next change.

local original_setManifestid = _originals and (_originals.setManifestid or _originals.setmanifestid) or setManifestid

local pinned_depots = {{
{depot_lines}
}}

local function should_keep_pin(depot_id)
    local numeric_id = tonumber(depot_id)
    return numeric_id ~= nil and pinned_depots[numeric_id] == true
end

local function route_set_manifest(depot_id, manifest_id, size)
    if should_keep_pin(depot_id) and original_setManifestid then
        return original_setManifestid(depot_id, manifest_id, size)
    end
    return nil
end

function setManifestid(depot_id, manifest_id, size)
    return route_set_manifest(depot_id, manifest_id, size)
end

function setmanifestid(depot_id, manifest_id, size)
    return route_set_manifest(depot_id, manifest_id, size)
end
"""


def _stplugin_dir(steam_path: Path) -> Path:
    return steam_path / "config" / "stplug-in"


def _override_path(steam_path: Path) -> Path:
    return _stplugin_dir(Path(steam_path)) / OVERRIDE_FILENAME


def install(steam_path: Path) -> bool:
    """Drop the override .lua into stplug-in. Idempotent. Returns True
    on success, False on any IO failure (already logged)."""
    return install_with_exclusions(steam_path, ())


def install_with_exclusions(steam_path: Path, excluded_depots=()) -> bool:
    """Install the global LetUpdate override.

    Depots in *excluded_depots* keep their setManifestid pins. Every other
    depot skips setManifestid, which lets Steam resolve the latest manifest.
    """
    if steam_path is None:
        logger.warning("update_prompt_override.install: no steam_path")
        return False
    target_dir = _stplugin_dir(Path(steam_path))
    target = _override_path(Path(steam_path))
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(_render_override_body(excluded_depots), encoding="utf-8")
        logger.info("update_prompt_override: installed %s", target)
        return True
    except OSError as e:
        logger.error("update_prompt_override.install failed: %s", e)
        return False


def remove(steam_path: Path) -> bool:
    """Delete the override .lua if present. Idempotent. Returns True
    when the file is gone after the call (already absent counts), False
    only on a real IO error."""
    if steam_path is None:
        return True
    target = _override_path(Path(steam_path))
    try:
        target.unlink(missing_ok=True)
        logger.info("update_prompt_override: removed %s", target)
        return True
    except OSError as e:
        logger.error("update_prompt_override.remove failed: %s", e)
        return False


def apply_setting(steam_path: Path, enabled: bool) -> bool:
    """Wire the SHOW_UPDATE_PROMPTS toggle to the on-disk file. The
    Settings UI calls this after a successful set_setting, so the .lua
    matches the new value within one event-loop tick."""
    if enabled:
        return install(steam_path)
    return remove(steam_path)


def get_excluded_depots(steam_path: Path) -> set[str]:
    """Read the managed exclusion list from the global override file."""
    if steam_path is None:
        return set()
    target = _override_path(Path(steam_path))
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return set()
    for line in text.splitlines():
        if "STEAMIDRA_EXCLUDED_DEPOTS:" not in line:
            continue
        raw = line.split("STEAMIDRA_EXCLUDED_DEPOTS:", 1)[1].strip()
        try:
            values = json.loads(raw)
        except Exception:
            return set()
        if isinstance(values, list):
            return {str(x) for x in values if str(x).isdigit()}
        return set()
    return set()

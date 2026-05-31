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

# Small helper that drops a setManifestid override .lua into stplug-in
# so games render the "Update available" prompt in Steam. DarkH2o was
# pasting this manually into stplug-in for a while and it works because
# LumaCore's LuaState already exposes _originals.setManifestid, so the
# wrapper can chain through to the C handler. The override stays loaded
# alongside the game .lua files; LumaCore's hot-reload picks it up.

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 00_ prefix forces this to load before any per-game .lua, which matters
# because the wrapper has to capture the C-bound setManifestid into its
# upvalue BEFORE the game .lua starts calling setManifestid for its own
# depots. Filename is also a clear marker for support sweeps.
OVERRIDE_FILENAME = "00_LetUpdate_override.lua"

OVERRIDE_BODY = """\
-- 00_LetUpdate_override.lua
-- Lets games show the "Update" prompt in the Steam library when Steam
-- pushes a newer manifest than the one our .lua pinned.
--
-- Managed by SteaMidra. Toggle "Show in-Steam 'Update available' prompts"
-- in Settings to remove this file. Editing it by hand is fine but the
-- toggle will rewrite or delete it on next change.

local original_setManifestid = setManifestid
function setManifestid(depot_id, manifest_id, size)
    return original_setManifestid(depot_id, manifest_id, size)
end
"""


def _stplugin_dir(steam_path: Path) -> Path:
    return steam_path / "config" / "stplug-in"


def install(steam_path: Path) -> bool:
    """Drop the override .lua into stplug-in. Idempotent. Returns True
    on success, False on any IO failure (already logged)."""
    if steam_path is None:
        logger.warning("update_prompt_override.install: no steam_path")
        return False
    target_dir = _stplugin_dir(Path(steam_path))
    target = target_dir / OVERRIDE_FILENAME
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(OVERRIDE_BODY, encoding="utf-8")
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
    target = _stplugin_dir(Path(steam_path)) / OVERRIDE_FILENAME
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

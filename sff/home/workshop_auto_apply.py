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
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run_auto_apply(steam_path: Path, app_id: str, apply_func) -> dict:
    content_dir = steam_path / "steamapps" / "workshop" / "content" / app_id
    if not content_dir.is_dir():
        return {"added": 0, "skipped": 0, "found": 0}
    subscribed = _get_subscribed_ids(steam_path, app_id)
    installed = set()
    for p in content_dir.iterdir():
        if p.is_dir() and p.name.isdigit():
            installed.add(p.name)
    missing = subscribed - installed
    added = 0
    for wid in sorted(missing, key=int):
        try:
            apply_func(wid)
            added += 1
        except Exception as exc:
            logger.warning("workshop auto-apply: id %s failed: %s", wid, exc)
    return {"added": added, "skipped": len(missing) - added, "found": len(subscribed)}


def _get_subscribed_ids(steam_path: Path, app_id: str) -> set:
    workshop_vdf = steam_path / "steamapps" / "workshop" / f"appworkshop_{app_id}.acf"
    if not workshop_vdf.is_file():
        return set()
    ids = set()
    try:
        text = workshop_vdf.read_text(encoding="utf-8", errors="replace")
        import re
        for m in re.finditer(r'"(\d+)"\s*$', text, re.MULTILINE):
            ids.add(m.group(1))
    except Exception as exc:
        logger.warning("failed to parse subscribed workshop IDs for %s: %s", app_id, exc)
    return ids

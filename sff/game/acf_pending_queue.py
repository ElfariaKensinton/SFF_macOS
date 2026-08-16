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

"""Persistent queue for deferred ACF edits (downgrade build IDs).

Steam only creates ``appmanifest_*.acf`` once a game is being
downloaded, and while it downloads Steam may hold the file. When the
Download Older Version flow cannot write the build ID / manifest IDs
yet, the edit is queued here and retried every 30 seconds until the
ACF exists, the game is fully installed (StateFlags bit 4), and the
write actually sticks. The queue survives restarts.
"""

import json
import logging
import time

from sff.core.utils import sff_data_dir

logger = logging.getLogger(__name__)

_QUEUE_FILE = sff_data_dir() / "acf_pending_queue.json"
_MAX_AGE_DAYS = 7


def _load():
    try:
        if not _QUEUE_FILE.exists():
            return []
        data = json.loads(_QUEUE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [e for e in data if isinstance(e, dict)]
    except Exception as e:
        logger.debug("acf queue load failed: %s", e)
        return []


def _save(entries):
    try:
        _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _QUEUE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        tmp.replace(_QUEUE_FILE)
    except Exception as e:
        logger.debug("acf queue save failed: %s", e)


def enqueue_acf_edit(app_id, build_id, pins):
    """Queue (or refresh) a pending ACF edit for a downgraded game."""
    app_id = str(app_id).strip()
    build_id = str(build_id).strip()
    if not app_id.isdigit() or not build_id.isdigit():
        return
    pins = {str(k): str(v) for k, v in (pins or {}).items()}
    entries = _load()
    for e in entries:
        if str(e.get("app_id", "")) == app_id and str(e.get("build_id", "")) == build_id:
            e["pins"] = pins
            e["queued_at"] = time.time()
            _save(entries)
            logger.info("acf queue: refreshed pending edit for app %s (build %s)", app_id, build_id)
            return
    entries.append({
        "app_id": app_id,
        "build_id": build_id,
        "pins": pins,
        "queued_at": time.time(),
        "attempts": 0,
    })
    _save(entries)
    logger.info("acf queue: queued build %s edit for app %s", build_id, app_id)


def process_pending_acf_edits(steam_path, on_applied=None):
    """Try to apply every queued ACF edit. Entries that still cannot be
    applied (no ACF yet, game still downloading, Steam holding the file)
    stay queued. Returns the list of applied app ids."""
    entries = _load()
    if not entries or not steam_path:
        return []
    from sff.core.storage.vdf import vdf_load
    from sff.gui.bridges.download_bridge import (
        _find_app_manifest_acf,
        _sync_acf_downgrade,
    )

    now = time.time()
    remaining = []
    applied = []
    for e in entries:
        app_id = str(e.get("app_id", "") or "")
        build_id = str(e.get("build_id", "") or "")
        pins = {str(k): str(v) for k, v in (e.get("pins") or {}).items()}
        if not app_id.isdigit() or not build_id.isdigit():
            continue
        try:
            age = now - float(e.get("queued_at") or now)
        except Exception:
            age = 0.0
        if age > _MAX_AGE_DAYS * 86400:
            logger.warning(
                "acf queue: dropping stale edit for app %s (build %s) after %s days",
                app_id, build_id, _MAX_AGE_DAYS,
            )
            continue
        try:
            acf_path = _find_app_manifest_acf(steam_path, app_id)
            if acf_path is None:
                remaining.append(e)
                continue
            data = vdf_load(acf_path)
            try:
                flags = int(str((data.get("AppState", {}) or {}).get("StateFlags", "0") or "0") or 0)
            except Exception:
                flags = 0
            if not (flags & 4):
                # Game not fully installed yet — keep waiting.
                remaining.append(e)
                continue
            e["attempts"] = int(e.get("attempts") or 0) + 1
            if _sync_acf_downgrade(acf_path, build_id, pins):
                applied.append(app_id)
                logger.info("acf queue: applied build %s to app %s", build_id, app_id)
                if on_applied:
                    try:
                        on_applied(app_id, build_id)
                    except Exception:
                        pass
            else:
                remaining.append(e)
        except Exception as exc:
            logger.debug("acf queue: edit failed for app %s: %s", app_id, exc)
            e["attempts"] = int(e.get("attempts") or 0) + 1
            remaining.append(e)
    _save(remaining)
    return applied

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

"""
Cloud saves domain bridge functions extracted from web_bridge.py.

Each ``_bridge_*`` function takes a ``WebBridge`` instance as its first
parameter (named ``bridge``) in place of ``self``.
"""

import concurrent.futures as _concurrent
import json
import logging
import shutil
import string
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def _format_size(size_bytes):
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _bridge_scan_cloud_games(bridge, steam_path, steam32_id):
    """Scan userdata for cloud saves."""
    def _do():
        from sff.cloud.cloud_saves import CloudSaves
        pairs = CloudSaves.list_steam_games(steam_path, steam32_id)
        games = []
        for app_id, game_name in pairs:
            remote_dir = Path(steam_path) / "userdata" / steam32_id / str(app_id) / "remote"
            size = 0
            if remote_dir.exists():
                try:
                    size = sum(f.stat().st_size for f in remote_dir.rglob("*") if f.is_file())
                except Exception:
                    pass
            games.append({
                "app_id": str(app_id),
                "name": game_name,
                "size": _format_size(size),
            })
        return games

    def _on_done(games):
        bridge._emit_task_result("scan_cloud_games", True, "", games=games or [])

    bridge._run_async(_do, on_done=_on_done)

def _bridge_backup_cloud_save(bridge, config_json):
    """Backup cloud saves for a game."""
    def _do():
        config = json.loads(config_json)
        app_id = str(config.get("app_id", "")).strip()
        dest_path = config.get("dest_path", "").strip()
        steam_path = config.get("steam_path", "").strip()
        steam32_id = str(config.get("steam32_id", "")).strip()
        game_name = config.get("game_name", f"App {app_id}").strip() or f"App {app_id}"
        if not app_id or not dest_path or not steam_path or not steam32_id:
            return (False, "", "Missing required parameters for backup")
        from sff.cloud.cloud_saves import CloudSaves
        log_lines = []
        result = CloudSaves().backup_steam_save(
            steam_path, steam32_id, int(app_id), game_name, dest_path,
            log_func=log_lines.append,
        )
        log_text = "\n".join(log_lines)
        if result:
            return (True, log_text, f"Saves backed up for {game_name}")
        return (False, log_text, "Backup failed — check log")

    def _on_done(result):
        if isinstance(result, tuple):
            ok, log_text, msg = result
            bridge._emit_task_result("backup_cloud_save", ok, msg, log=log_text)
        else:
            bridge._emit_task_result("backup_cloud_save", False, "Backup failed")

    bridge._run_async(_do, on_done=_on_done)

def _bridge_restore_cloud_save(bridge, config_json):
    """Restore cloud saves from backup."""
    def _do():
        config = json.loads(config_json)
        backup_path = config.get("backup_path", "").strip()
        app_id = str(config.get("app_id", "")).strip()
        steam_path = config.get("steam_path", "").strip()
        steam32_id = str(config.get("steam32_id", "")).strip()
        if not backup_path or not app_id or not steam_path or not steam32_id:
            return (False, "", "Missing required parameters for restore")
        from sff.cloud.cloud_saves import CloudSaves
        log_lines = []
        ok = CloudSaves().restore_steam_save(
            backup_path, steam_path, steam32_id, int(app_id),
            log_func=log_lines.append,
        )
        log_text = "\n".join(log_lines)
        if ok:
            return (True, log_text, "Saves restored successfully")
        return (False, log_text, "Restore failed — check log")

    def _on_done(result):
        if isinstance(result, tuple):
            ok, log_text, msg = result
            bridge._emit_task_result("restore_cloud_save", ok, msg, log=log_text)
        else:
            bridge._emit_task_result("restore_cloud_save", False, "Restore failed")

    bridge._run_async(_do, on_done=_on_done)

# ── Bundled tool resolution ───────────────────────────────────

def _bridge_rclone_backup_save(bridge, config_json):
    """Upload a game's Steam userdata saves to an rclone remote."""
    def _do():
        import subprocess
        import tempfile
        config = json.loads(config_json)
        app_id = str(config.get("app_id", "")).strip()
        rclone_exe = config.get("rclone_exe", "").strip()
        remote_dest = config.get("remote_dest", "").strip()
        steam_path = config.get("steam_path", "").strip()
        steam32_id = str(config.get("steam32_id", "")).strip()
        game_name = config.get("game_name", f"App {app_id}").strip() or f"App {app_id}"
        if not rclone_exe:
            bundled = bridge._get_bundled_tool_path("rclone")
            if bundled:
                rclone_exe = str(bundled)
        if not app_id or not rclone_exe or not remote_dest or not steam_path or not steam32_id:
            return (False, "", "Missing rclone configuration")
        if not Path(rclone_exe).exists():
            return (False, "", f"rclone executable not found: {rclone_exe}")
        from sff.cloud.cloud_saves import CloudSaves
        log_lines = []
        tmp = Path(tempfile.mkdtemp(prefix="steamidra_rclone_"))
        try:
            result = CloudSaves().backup_steam_save(
                steam_path, steam32_id, int(app_id), game_name, str(tmp),
                log_func=log_lines.append,
            )
            if not result:
                return (False, "\n".join(log_lines), "Local backup step failed")
            local_dir = Path(result)
            remote_path = remote_dest.rstrip("/") + "/" + local_dir.name
            _no_win = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
            proc = subprocess.run(
                [
                    rclone_exe, "copy", str(local_dir), remote_path,
                    "--update",
                    "--transfers", "10", "--checkers", "20",
                    "--create-empty-src-dirs",
                    "--fast-list",
                ],
                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300, **_no_win,
            )
            log_lines.append(proc.stdout)
            if proc.returncode == 0:
                return (True, "\n".join(log_lines), f"Uploaded to {remote_path}")
            log_lines.append(proc.stderr)
            return (False, "\n".join(log_lines), f"rclone failed (exit {proc.returncode})")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _on_done(result):
        if isinstance(result, tuple):
            ok, log_text, msg = result
            bridge._emit_task_result("rclone_backup_save", ok, msg, log=log_text)
        else:
            bridge._emit_task_result("rclone_backup_save", False, "Upload failed")

    bridge._run_async(_do, on_done=_on_done)

def _bridge_rclone_list_remotes(bridge, rclone_exe_json):
    """Run rclone listremotes --long and return JSON list of configured remote names."""
    def _do():
        import subprocess
        try:
            rclone_exe = json.loads(rclone_exe_json).get("rclone_exe", "").strip()
        except Exception:
            rclone_exe = ""
        if not rclone_exe:
            bundled = bridge._get_bundled_tool_path("rclone")
            rclone_exe = str(bundled) if bundled else ""
        if not rclone_exe or not Path(rclone_exe).exists():
            return json.dumps({"ok": False, "error": "rclone executable not found"})
        _no_win = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
        try:
            proc = subprocess.run(
                [rclone_exe, "listremotes", "--long"],
                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=15, **_no_win,
            )
            if proc.returncode != 0:
                return json.dumps({"ok": False, "error": proc.stderr.strip()[:300]})
            remotes = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line:
                    name = line.split()[0]
                    remotes.append(name)
            return json.dumps({"ok": True, "remotes": remotes})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def _on_done(result):
        try:
            parsed = json.loads(result or "{}")
        except Exception:
            parsed = {}
        if parsed.get("ok"):
            bridge._emit_task_result("rclone_list_remotes", True, "", remotes=parsed.get("remotes", []))
        else:
            bridge._emit_task_result("rclone_list_remotes", False, "", error=parsed.get("error", "Failed to list remotes"))

    bridge._run_async(_do, on_done=_on_done)

def _bridge_rclone_test_remote(bridge, config_json):
    """Test an rclone remote by running lsd with a short timeout. Returns JSON ok/error."""
    def _do():
        import subprocess
        config = json.loads(config_json)
        rclone_exe = config.get("rclone_exe", "").strip()
        remote = config.get("remote", "").strip()
        if not rclone_exe:
            bundled = bridge._get_bundled_tool_path("rclone")
            rclone_exe = str(bundled) if bundled else ""
        if not rclone_exe or not Path(rclone_exe).exists():
            return json.dumps({"ok": False, "error": "rclone executable not found"})
        if not remote:
            return json.dumps({"ok": False, "error": "No remote specified"})
        # Test only the remote root — the backup subfolder may not exist yet
        remote_root = remote.split(":")[0] + ":" if ":" in remote else remote + ":"
        _no_win = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
        try:
            proc = subprocess.run(
                [rclone_exe, "lsd", remote_root, "--max-depth", "1", "--timeout", "15s"],
                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=20, **_no_win,
            )
            if proc.returncode == 0:
                return json.dumps({"ok": True})
            return json.dumps({"ok": False, "error": proc.stderr.strip()[:300]})
        except subprocess.TimeoutExpired:
            return json.dumps({"ok": False, "error": "Timed out after 20s"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def _on_done(result):
        try:
            parsed = json.loads(result or "{}")
        except Exception:
            parsed = {}
        if parsed.get("ok"):
            bridge._emit_task_result("rclone_test_remote", True, "")
        else:
            bridge._emit_task_result("rclone_test_remote", False, "", error=parsed.get("error", "Remote test failed")[:300])

    bridge._run_async(_do, on_done=_on_done)

def _bridge_rclone_open_config(bridge, rclone_exe_json):
    """Open rclone config in a new terminal window so the user can add or edit remotes."""
    import sys
    import subprocess
    try:
        rclone_exe = json.loads(rclone_exe_json).get("rclone_exe", "").strip()
    except Exception:
        rclone_exe = ""
    if not rclone_exe:
        bundled = bridge._get_bundled_tool_path("rclone")
        rclone_exe = str(bundled) if bundled else ""
    if not rclone_exe or not Path(rclone_exe).exists():
        bridge._emit_task_result("rclone_open_config", False, "", error="rclone executable not found")
        return
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/k", rclone_exe, "config"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            cmd = [rclone_exe, "config"]
            launched = False
            for term, args in [
                ("x-terminal-emulator", ["-e"]),
                ("gnome-terminal", ["--"]),
                ("xterm", ["-e"]),
                ("konsole", ["-e"]),
                ("xfce4-terminal", ["-e"]),
            ]:
                try:
                    subprocess.Popen([term] + args + cmd)
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            if not launched:
                bridge._emit_task_result("rclone_open_config", False, "", error="No terminal emulator found. Open a terminal and run: rclone config")
                return
        bridge._emit_task_result("rclone_open_config", True, "")
    except Exception as e:
        bridge._emit_task_result("rclone_open_config", False, "", error=str(e))

def _bridge_gdrive_authorize(bridge):
    """Start the Google Drive OAuth flow in a background thread."""
    def _do():
        from sff.cloud.google_drive import authorize, is_available
        if not is_available():
            return (False, "Google Drive is not available in this build.")
        log_lines = []
        ok = authorize(log_func=log_lines.append)
        return (ok, "\n".join(log_lines))

    def _on_done(result):
        if isinstance(result, tuple):
            ok, msg = result
            if ok:
                from sff.cloud.google_drive import get_service, get_user_email
                svc = get_service()
                email = get_user_email(svc) if svc else ""
                bridge._emit_task_result("gdrive_authorize", True, msg, email=email)
            else:
                bridge._emit_task_result("gdrive_authorize", False, msg)
        else:
            bridge._emit_task_result("gdrive_authorize", False, "Authorization failed")

    bridge._run_async(_do, on_done=_on_done)

def _bridge_gdrive_status(bridge):
    """Return GDrive connection status as JSON (synchronous)."""
    from sff.cloud.google_drive import is_available, is_authenticated, get_service, get_user_email
    if not is_available():
        return json.dumps({"available": False, "connected": False, "email": ""})
    if not is_authenticated():
        return json.dumps({"available": True, "connected": False, "email": ""})
    svc = get_service()
    email = get_user_email(svc) if svc else ""
    return json.dumps({"available": True, "connected": bool(svc), "email": email})

# ── All Save Locations ────────────────────────────────────────

def _bridge_get_custom_save_paths(bridge):
    """Returns user-defined per-game save paths as JSON {"<app_id>": "<path>"}."""
    try:
        from sff.core.storage.settings import get_setting
        from sff.core.structs import Settings
        raw = get_setting(Settings.CLOUD_CUSTOM_SAVE_PATHS) or ""
        if not raw:
            return "{}"
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return json.dumps(parsed)
        except Exception:
            pass
        return "{}"
    except Exception as exc:
        logger.warning("get_custom_save_paths failed: %s", exc)
        return "{}"

def _bridge_set_custom_save_path(bridge, app_id, path):
    """Add / update a custom save path for an app id. Empty path removes."""
    try:
        from sff.core.storage.settings import get_setting, set_setting
        from sff.core.structs import Settings
        raw = get_setting(Settings.CLOUD_CUSTOM_SAVE_PATHS) or ""
        mapping: dict = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    mapping = parsed
            except Exception:
                mapping = {}
        app_id_str = str(app_id or "").strip()
        if not app_id_str:
            return json.dumps({"ok": False, "error": "missing app_id"})
        new_path = (path or "").strip()
        if not new_path:
            mapping.pop(app_id_str, None)
        else:
            mapping[app_id_str] = new_path
        set_setting(Settings.CLOUD_CUSTOM_SAVE_PATHS, json.dumps(mapping))
        return json.dumps({"ok": True, "paths": mapping})
    except Exception as exc:
        logger.warning("set_custom_save_path failed: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})

def _bridge_scan_all_save_locations(bridge, config_json):
    """Scan all emu save locations + Steam userdata. Emits task_finished with results list."""
    def _do():
        config = json.loads(config_json)
        steam_path = config.get("steam_path", "").strip()
        steam32_id = str(config.get("steam32_id", "")).strip()
        from sff.cloud.cloud_saves import scan_all_save_locations as _scan
        entries = _scan(
            steam_path=steam_path or None,
            steam32_id=steam32_id or None,
        )
        return entries

    def _on_done(entries):
        if entries is None:
            entries = []
        bridge._emit_task_result("scan_all_save_locations", True, f"Found {len(entries)} save folder(s)", entries=entries)

    bridge._run_async(_do, on_done=_on_done)

def _bridge_backup_all_save_locations(bridge, config_json):
    """Backup all (or selected) save location entries using the configured provider."""
    def _do():
        config = json.loads(config_json)
        entries = config.get("entries", [])
        provider = config.get("provider", "local").lower()
        dest_path = config.get("dest_path", "").strip()
        rclone_exe = config.get("rclone_exe", "").strip()
        remote_dest = config.get("remote_dest", "").strip()

        if not entries:
            return (False, "No entries to back up.", [])

        from sff.cloud.cloud_saves import (
            backup_save_location_local,
            backup_save_location_rclone,
            backup_save_location_gdrive,
        )

        log_lines = []
        succeeded = 0
        failed = 0
        total = len(entries)
        done = 0

        def _emit_backup_progress(label, s, f):
            bridge.download_progress.emit(json.dumps({
                "task": "backup_progress",
                "done": done, "total": total,
                "percent": int(done / total * 100) if total > 0 else 0,
                "current_label": label,
                "succeeded": s, "failed": f,
            }))

        _emit_backup_progress("Starting...", 0, 0)

        if provider in ("local", "gdrive_sync"):
            if not dest_path:
                return (False, "Destination folder not set.", [])
            for entry in entries:
                result = backup_save_location_local(entry, dest_path, log_func=log_lines.append)
                if result:
                    succeeded += 1
                else:
                    failed += 1
                done += 1
                _emit_backup_progress(entry.get("label", ""), succeeded, failed)

        elif provider == "rclone":
            import threading
            import subprocess
            from concurrent.futures import ThreadPoolExecutor, as_completed
            if not rclone_exe:
                bundled = bridge._get_bundled_tool_path("rclone")
                rclone_exe = str(bundled) if bundled else ""
            if not rclone_exe or not remote_dest:
                return (False, "rclone exe or remote destination not set.", [])
            lock = threading.Lock()
            _rclone_exe = rclone_exe
            _remote_dest = remote_dest

            import sys as _sys
            _no_window = {"creationflags": 0x08000000} if _sys.platform == "win32" else {}
            def _backup_one_rclone(entry):
                thread_log = []
                ok = backup_save_location_rclone(
                    entry, _rclone_exe, _remote_dest, log_func=thread_log.append
                )
                with lock:
                    log_lines.extend(thread_log)
                return ok

            with ThreadPoolExecutor(max_workers=10) as ex:
                futures = {ex.submit(_backup_one_rclone, e): e for e in entries}
                for fut in as_completed(futures):
                    e = futures[fut]
                    try:
                        ok = fut.result()
                    except Exception as exc:
                        ok = False
                        with lock:
                            log_lines.append(f"[FAIL] {e.get('label', '?')}: {exc}")
                    with lock:
                        if ok:
                            succeeded += 1
                        else:
                            failed += 1
                    done += 1
                    _emit_backup_progress(e.get("label", ""), succeeded, failed)

            subprocess.run(
                [_rclone_exe, "dedupe", "--dedupe-mode", "newest",
                 _remote_dest.rstrip("/") + "/SteaMidraAllSaves"],
                capture_output=True, stdin=subprocess.DEVNULL, timeout=180, **_no_window,
            )

        elif provider == "gdrive_api":
            import threading
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from sff.cloud.google_drive import (
                get_service, get_backup_root, is_authenticated,
            )
            if not is_authenticated():
                return (False, "Google Drive not connected. Use Connect button first.", [])
            svc = get_service()
            if not svc:
                return (False, "Could not connect to Google Drive.", [])
            root_id = get_backup_root(svc)
            if not root_id:
                return (False, "Could not create backup root on Google Drive.", [])
            from pathlib import Path as _Path
            valid_entries = []
            for e in entries:
                sources = e.get("sources") if isinstance(e.get("sources"), list) else []
                paths = [s.get("source_path") for s in sources if isinstance(s, dict)] or [e.get("source_path")]
                if any(p and _Path(p).exists() for p in paths):
                    valid_entries.append(e)
                else:
                    failed += 1
                    log_lines.append(
                        f"[SKIP] Source not found: {e.get('label', '?')} ({e.get('source_path', '?')})"
                    )

            folder_cache = {}
            lock = threading.Lock()

            def _backup_one_gdrive(entry):
                thread_log = []
                thread_svc = get_service()
                if not thread_svc:
                    with lock:
                        log_lines.append(
                            f"[FAIL] {entry.get('label', '?')}: could not connect to Drive"
                        )
                    return False
                thread_cache = dict(folder_cache)
                ok = backup_save_location_gdrive(
                    entry, thread_svc, root_id,
                    log_func=thread_log.append,
                    folder_cache=thread_cache,
                )
                with lock:
                    log_lines.extend(thread_log)
                return ok

            with ThreadPoolExecutor(max_workers=10) as ex:
                futures = {ex.submit(_backup_one_gdrive, e): e for e in valid_entries}
                for fut in as_completed(futures):
                    e = futures[fut]
                    try:
                        ok = fut.result()
                    except Exception as exc:
                        ok = False
                        with lock:
                            log_lines.append(f"[FAIL] {e.get('label', '?')}: {exc}")
                    with lock:
                        if ok:
                            succeeded += 1
                        else:
                            failed += 1
                    done += 1
                    _emit_backup_progress(e.get("label", ""), succeeded, failed)
        else:
            return (False, f"Provider '{provider}' not supported for all-saves backup.", [])

        ok = failed == 0
        msg = f"Backup complete: {succeeded} succeeded, {failed} failed"
        return (ok, msg, log_lines, provider, dest_path, rclone_exe, remote_dest)

    def _on_done(result):
        if isinstance(result, tuple) and len(result) >= 3:
            ok, msg, log_lines = result[0], result[1], result[2]
            bridge._emit_task_result("backup_all_save_locations", ok, msg, log="\n".join(log_lines))
            if ok and len(result) == 7:
                _prov, _dest, _rclone_exe, _remote_dest = result[3], result[4], result[5], result[6]
                import json as _json
                from sff.core.storage.settings import set_setting as _set
                from sff.core.structs import Settings as _S
                if _prov in ('local', 'gdrive_sync'):
                    _cfg = {'provider': 'local', 'dest_path': _dest}
                elif _prov == 'rclone':
                    _cfg = {'provider': 'rclone', 'rclone_exe': _rclone_exe, 'remote_dest': _remote_dest}
                elif _prov == 'gdrive_api':
                    _cfg = {'provider': 'gdrive_api'}
                else:
                    _cfg = None
                if _cfg:
                    _set(_S.LAST_BACKUP_PROVIDER_CONFIG, _json.dumps(_cfg))
        else:
            bridge._emit_task_result("backup_all_save_locations", False, "Backup failed")

    bridge._run_async(_do, on_done=_on_done)

def _bridge_scan_backup_root(bridge, config_json):
    """Scan a backup root (local or GDrive) and return location/game tree."""
    def _do():
        config = json.loads(config_json)
        provider = config.get("provider", "local").lower()
        backup_root = config.get("backup_root", "").strip()

        if provider == "gdrive_api":
            from sff.cloud.google_drive import get_service, list_backup_locations, is_authenticated
            if not is_authenticated():
                return (False, "Google Drive not connected.", {})
            svc = get_service()
            if not svc:
                return (False, "Could not connect to Google Drive.", {})
            locations = list_backup_locations(svc)
            return (True, "", locations)
        elif provider == "rclone":
            rclone_exe = config.get("rclone_exe", "").strip()
            remote_dest = config.get("remote_dest", "").strip()
            if not rclone_exe:
                bundled = bridge._get_bundled_tool_path("rclone")
                rclone_exe = str(bundled) if bundled else ""
            if not rclone_exe or not remote_dest:
                return (False, "rclone exe or remote destination not set.", {})
            from sff.cloud.cloud_saves import scan_backup_root_rclone
            locations = scan_backup_root_rclone(rclone_exe, remote_dest)
            return (True, "", locations)
        else:
            if not backup_root:
                return (False, "Backup root folder not set.", {})
            from sff.cloud.cloud_saves import scan_backup_root_local
            locations = scan_backup_root_local(backup_root)
            return (True, "", locations)

    def _on_done(result):
        if isinstance(result, tuple):
            ok, msg, locations = result
            bridge._emit_task_result("scan_backup_root", ok, msg, locations=locations)
        else:
            bridge._emit_task_result("scan_backup_root", False, "Scan failed", locations={})

    bridge._run_async(_do, on_done=_on_done)

def _bridge_restore_save_location(bridge, game_entry_json):
    """Restore a single game's saves from backup to its original source_path."""
    def _do():
        game_entry = json.loads(game_entry_json)
        log_lines = []
        from sff.cloud.cloud_saves import restore_save_entry
        result = restore_save_entry(game_entry, log_func=log_lines.append)
        if isinstance(result, dict):
            ok = bool(result.get("ok"))
            msg = result.get("message") or ("Restore complete" if ok else "Restore failed")
            return (ok, msg, log_lines, result.get("results", []))
        ok = bool(result)
        msg = "Restore complete" if ok else "Restore failed - check log"
        return (ok, msg, log_lines, [])

    def _on_done(result):
        if isinstance(result, tuple):
            ok, msg, log_lines = result[0], result[1], result[2]
            results = result[3] if len(result) > 3 else []
            bridge._emit_task_result("restore_save_location", ok, msg, log="\n".join(log_lines), results=results)
        else:
            bridge._emit_task_result("restore_save_location", False, "Restore failed")

    bridge._run_async(_do, on_done=_on_done)


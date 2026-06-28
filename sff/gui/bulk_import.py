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

"""A12 Bulk Import Queue.

Wraps the existing per-platform single-file registration pipeline that the
classic `import_lua_file` / `import_manifest_file` flows already use. The
queue itself only adds three things: a thread-safe FIFO drain, a cancel
signal, and aggregate progress accounting. Every parser, writer, and
registration helper is borrowed from the existing modules verbatim so the
single-file paths and the Bulk Import Queue cannot drift.

The queue is invisible until the user engages a bulk surface (Folder Scan,
Drop Zone, Quick Start drop). Single-file imports never instantiate it.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional


logger = logging.getLogger(__name__)


# Manifest filenames look like "<depot_id>_<manifest_id>.manifest". The
# existing single-file manifest import path (sff/zip.py + ManifestDownloader)
# uses this exact regex when scanning depotcache.
_MANIFEST_NAME_RE = re.compile(r"^(?P<depot>\d+)_(?P<manifest>[0-9a-fA-F]+)\.manifest$")

_HASH_BUFFER_SIZE = 64 * 1024


# Skip-reason strings (must match the i18n keys added to webui_*.json).
SKIP_REASON_LUA_PARSE = "lua parse error"
SKIP_REASON_MANIFEST_INVALID = "manifest invalid"
SKIP_REASON_DUPLICATE = "duplicate of {other}"
SKIP_REASON_UNSUPPORTED = "unsupported file type"


@dataclass
class FileResult:
    """Outcome for one file in the batch."""

    path: Path
    app_id: Optional[str] = None
    ok: bool = False
    skipped: bool = False
    reason: str = ""
    failing_step: str = ""


@dataclass
class QueueItem:
    """One file enqueued for processing."""

    path: Path
    kind: str  # "lua" or "manifest"
    parsed_lua: object = None  # LuaParsedInfo when kind == "lua"
    manifest_depot_id: Optional[str] = None
    manifest_id: Optional[str] = None
    content_hash: Optional[str] = None


@dataclass
class BatchSummary:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list = field(default_factory=list)


def _hash_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(_HASH_BUFFER_SIZE), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        logger.debug("hash failed for %s: %s", path, exc)
        return None


def validate_lua_file(path: Path):
    """Reuse the existing single-file lua parser used by import_lua_file.

    Returns ``(parsed_lua_or_None, reason_or_None)``. Parsing goes through
    `sff.lua.manager.parse_lua_contents`, the same function `process_lua_full`
    and `process_lua_minimal` call on every single-file import today.
    """

    try:
        from sff.lua.manager import parse_lua_contents
    except Exception as exc:
        logger.exception("parse_lua_contents import failed: %s", exc)
        return None, str(exc)

    try:
        if path.suffix.lower() in (".zip", ".rar", ".7z"):
            from sff.zip import read_lua_from_zip

            text = read_lua_from_zip(path, decode=True)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return None, f"{SKIP_REASON_LUA_PARSE}: {exc}"

    if not text:
        return None, SKIP_REASON_LUA_PARSE

    parsed = parse_lua_contents(text, path)
    if parsed is None:
        return None, SKIP_REASON_LUA_PARSE
    return parsed, None


def validate_manifest_file(path: Path):
    """Mirror the validation `import_manifest_file` uses on the single-file
    path: filename must match `<depot>_<manifest>.manifest` and the file
    must be non-empty. Returns `(is_valid, reason_or_None)`. On success the
    caller can read `_MANIFEST_NAME_RE.match(path.name)` to recover the
    depot/manifest pair.
    """

    if path.suffix.lower() != ".manifest":
        return False, SKIP_REASON_MANIFEST_INVALID
    m = _MANIFEST_NAME_RE.match(path.name)
    if not m:
        return False, SKIP_REASON_MANIFEST_INVALID
    try:
        if path.stat().st_size <= 0:
            return False, SKIP_REASON_MANIFEST_INVALID
    except Exception as exc:
        return False, f"{SKIP_REASON_MANIFEST_INVALID}: {exc}"
    return True, None


def dedupe_against_in_flight(
    files: Iterable[Path],
    seen_paths: set,
    seen_hashes: set,
):
    """Return ``(unique, duplicates)``. Duplicate detection runs on absolute
    path first (cheap) and content hash second. Both sets are mutated in
    place so a single batch can be deduped across multiple drops.
    """

    unique: list[Path] = []
    duplicates: list[tuple[Path, str]] = []
    for raw in files:
        try:
            path = Path(raw).resolve()
        except Exception:
            continue
        path_key = str(path)
        if path_key in seen_paths:
            duplicates.append((path, SKIP_REASON_DUPLICATE.format(other=path_key)))
            continue
        digest = _hash_file(path) if path.is_file() else None
        if digest and digest in seen_hashes:
            duplicates.append((path, SKIP_REASON_DUPLICATE.format(other=digest[:12])))
            continue
        seen_paths.add(path_key)
        if digest:
            seen_hashes.add(digest)
        unique.append(path)
    return unique, duplicates


class BulkImportQueue:
    """Sequential drain over a thread-safe FIFO of validated files.

    Per-file work delegates to `_process_lua_item` / `_process_manifest_item`
    which only call existing helpers (`install_lua_to_steam`,
    `add_decryption_keys_to_config`, `set_stats_and_achievements`,
    `app_list_man.add_ids` / `sls_man.add_ids`, `ACFWriter.write_acf`,
    `ACFWriter.patch_workshop_acf`, `ensure_library_has_app`). The queue
    never re-implements parsing or registration.
    """

    def __init__(
        self,
        ui,
        steam_path: Optional[Path],
        active_library: Optional[Path],
        progress_cb: Callable[[dict], None],
    ):
        self._ui = ui
        self._steam_path = Path(steam_path) if steam_path else None
        self._active_library = Path(active_library) if active_library else self._steam_path
        self._progress_cb = progress_cb

        self._lock = threading.Lock()
        self._queue: deque[QueueItem] = deque()
        self._cancel = threading.Event()
        self._draining = False
        self._processed = 0
        self._total = 0
        self._results: list[FileResult] = []
        self._seen_paths: set[str] = set()
        self._seen_hashes: set[str] = set()
        # Track which appids have a companion .lua in this batch so a
        # bare .manifest file can decide whether to skip the lua-specific
        # steps.
        self._lua_appids_in_batch: set[str] = set()

    # ── Enqueue API ──────────────────────────────────────────────

    def enqueue_files(self, paths: Iterable[Path]) -> list[FileResult]:
        """Validate each file, dedupe against the in-flight set, and add
        passing entries to the FIFO. Returns the results recorded for
        skipped/invalid entries so the caller can render them.
        """

        skipped_records: list[FileResult] = []
        unique, duplicates = dedupe_against_in_flight(
            paths, self._seen_paths, self._seen_hashes
        )
        for dup_path, reason in duplicates:
            skipped_records.append(FileResult(path=dup_path, skipped=True, reason=reason))

        for path in unique:
            ext = path.suffix.lower()
            if ext in (".lua", ".zip", ".rar", ".7z"):
                parsed, reason = validate_lua_file(path)
                if parsed is None:
                    skipped_records.append(
                        FileResult(path=path, skipped=True, reason=reason or SKIP_REASON_LUA_PARSE)
                    )
                    continue
                item = QueueItem(
                    path=path,
                    kind="lua",
                    parsed_lua=parsed,
                    content_hash=_hash_file(path),
                )
                with self._lock:
                    self._queue.append(item)
                    self._total += 1
                    self._lua_appids_in_batch.add(str(parsed.app_id))
            elif ext == ".manifest":
                ok, reason = validate_manifest_file(path)
                if not ok:
                    skipped_records.append(
                        FileResult(path=path, skipped=True, reason=reason or SKIP_REASON_MANIFEST_INVALID)
                    )
                    continue
                m = _MANIFEST_NAME_RE.match(path.name)
                item = QueueItem(
                    path=path,
                    kind="manifest",
                    manifest_depot_id=m.group("depot") if m else None,
                    manifest_id=m.group("manifest") if m else None,
                    content_hash=_hash_file(path),
                )
                with self._lock:
                    self._queue.append(item)
                    self._total += 1
            else:
                skipped_records.append(
                    FileResult(path=path, skipped=True, reason=SKIP_REASON_UNSUPPORTED)
                )

        with self._lock:
            self._results.extend(skipped_records)
        return skipped_records

    # ── Cancel ───────────────────────────────────────────────────

    def cancel(self) -> None:
        self._cancel.set()
        with self._lock:
            self._queue.clear()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    # ── Drain ────────────────────────────────────────────────────

    def drain(self) -> BatchSummary:
        """Process every queued file sequentially. Safe to call once per
        batch. The caller (web bridge) typically runs this on a worker
        thread so the UI thread stays responsive.
        """

        with self._lock:
            if self._draining:
                logger.debug("BulkImportQueue.drain re-entered; ignoring")
                return self._summary_locked()
            self._draining = True

        try:
            while True:
                with self._lock:
                    if self._cancel.is_set() or not self._queue:
                        break
                    item = self._queue.popleft()
                self._dispatch_one(item)
        finally:
            with self._lock:
                self._draining = False
                summary = self._summary_locked()
        return summary

    # ── Per-file dispatch ────────────────────────────────────────

    def _dispatch_one(self, item: QueueItem) -> None:
        try:
            if item.kind == "lua":
                result = self._process_lua_item(item)
            elif item.kind == "manifest":
                result = self._process_manifest_item(item)
            else:
                result = FileResult(
                    path=item.path,
                    skipped=True,
                    reason=SKIP_REASON_UNSUPPORTED,
                )
        except Exception as exc:
            logger.exception("Bulk dispatch failed for %s: %s", item.path, exc)
            result = FileResult(
                path=item.path,
                ok=False,
                reason=str(exc),
                failing_step="dispatch",
            )

        with self._lock:
            self._results.append(result)
            self._processed += 1
            processed = self._processed
            total = self._total
        self._emit_progress(item, "done", processed, total, result=result)

    def _process_lua_item(self, item: QueueItem) -> FileResult:
        parsed = item.parsed_lua
        app_id = str(parsed.app_id) if parsed is not None else ""
        steam_path = self._steam_path
        lib_path = self._active_library or steam_path
        if steam_path is None or lib_path is None:
            return FileResult(
                path=item.path,
                app_id=app_id,
                ok=False,
                reason="No Steam library selected",
                failing_step="library",
            )

        result = FileResult(path=item.path, app_id=app_id, ok=True)

        # All registration helpers are imported from the existing modules
        # so the single-file path and the bulk path stay byte-identical.
        from sff.lua.writer import ACFWriter, ConfigVDFWriter
        from sff.storage.vdf import ensure_library_has_app

        if sys.platform == "win32":
            from sff.steam_tools_compat import install_lua_to_steam
            from sff.registry_access import set_stats_and_achievements

            self._emit_progress(item, "Installing Lua to Steam")
            try:
                install_lua_to_steam(steam_path, app_id, item.path)
            except Exception as exc:
                logger.warning("install_lua_to_steam failed: %s", exc)
                result.ok = False
                result.failing_step = "install_lua_to_steam"
                result.reason = str(exc)
                return result

            self._emit_progress(item, "Adding decryption keys")
            try:
                ConfigVDFWriter(steam_path).add_decryption_keys_to_config(parsed)
            except Exception as exc:
                logger.warning("add_decryption_keys_to_config failed: %s", exc)
                result.ok = False
                result.failing_step = "add_decryption_keys_to_config"
                result.reason = str(exc)
                return result

            self._emit_progress(item, "Setting stats and achievements")
            try:
                set_stats_and_achievements(int(app_id) if app_id.isdigit() else app_id)
            except Exception as exc:
                logger.warning("set_stats_and_achievements failed: %s", exc)

            self._emit_progress(item, "Registering app ID with LumaCore")
            app_list_man = getattr(self._ui, "app_list_man", None)
            if app_list_man is not None:
                try:
                    app_list_man.add_ids(parsed)
                except Exception as exc:
                    logger.warning("app_list_man.add_ids failed: %s", exc)
                    result.ok = False
                    result.failing_step = "app_list_man.add_ids"
                    result.reason = str(exc)
                    return result
        else:
            # Linux: never call install_lua_to_steam (LumaCore is Windows-only).
            self._emit_progress(item, "Registering app ID with SLSSteam")
            sls_man = getattr(self._ui, "sls_man", None)
            if sls_man is not None:
                try:
                    sls_man.add_ids(parsed)
                except Exception as exc:
                    logger.warning("sls_man.add_ids failed: %s", exc)
                    result.ok = False
                    result.failing_step = "sls_man.add_ids"
                    result.reason = str(exc)
                    return result

        # Shared ACF + library entry steps run on every platform.
        self._emit_progress(item, "Writing ACF")
        acf = ACFWriter(lib_path)
        try:
            acf.write_acf(parsed)
        except Exception as exc:
            logger.warning("ACFWriter.write_acf failed: %s", exc)
            result.ok = False
            result.failing_step = "ACFWriter.write_acf"
            result.reason = str(exc)
            return result

        self._emit_progress(item, "Patching workshop ACF")
        try:
            acf.patch_workshop_acf(parsed)
        except Exception as exc:
            logger.warning("ACFWriter.patch_workshop_acf failed: %s", exc)

        self._emit_progress(item, "Registering library entry")
        try:
            ensure_library_has_app(steam_path, lib_path, app_id)
        except Exception as exc:
            logger.warning("ensure_library_has_app failed: %s", exc)
            result.ok = False
            result.failing_step = "ensure_library_has_app"
            result.reason = str(exc)
            return result

        return result

    def _process_manifest_item(self, item: QueueItem) -> FileResult:
        """Manifest-only file: the design says skip the lua/decryption/stats
        steps and run only the three ACF + library-entry steps. We still
        copy the manifest into Steam's depotcache so the depot fetch can
        find it later.
        """

        from sff.lua.writer import ACFWriter
        from sff.storage.vdf import ensure_library_has_app
        from sff.structs import DepotKeyPair, LuaParsedInfo

        steam_path = self._steam_path
        lib_path = self._active_library or steam_path
        if steam_path is None or lib_path is None:
            return FileResult(
                path=item.path,
                ok=False,
                reason="No Steam library selected",
                failing_step="library",
            )

        depot_id = item.manifest_depot_id or ""
        manifest_id = item.manifest_id or ""

        # Step 1: copy the manifest file into Steam's depotcache so Steam
        # does not have to download it again.
        self._emit_progress(item, "Staging manifest in depotcache")
        depotcache = steam_path / "depotcache"
        try:
            depotcache.mkdir(parents=True, exist_ok=True)
            dest = depotcache / item.path.name
            if dest.resolve() != item.path.resolve():
                import shutil as _shutil

                _shutil.copy2(item.path, dest)
        except Exception as exc:
            logger.warning("manifest copy to depotcache failed: %s", exc)

        # Build a minimal LuaParsedInfo so the ACF writer has something to
        # consume. The depot id doubles as the app id when no companion
        # .lua is present in the batch — Steam's appmanifest_<id>.acf
        # naming uses the appid, so we use the depot id as a best-effort
        # placeholder. If a user wants strict appid handling they should
        # drop the matching .lua as well.
        app_id = depot_id
        parsed = LuaParsedInfo(
            path=item.path,
            contents="",
            app_id=app_id,
            depots=[DepotKeyPair(depot_id=depot_id, decryption_key="")],
            manifest_overrides={depot_id: manifest_id} if depot_id and manifest_id else {},
        )

        result = FileResult(path=item.path, app_id=app_id, ok=True)

        # If a companion .lua for this appid is in the same batch the lua
        # path will run the full pipeline. Skip the manifest-only writes
        # so we do not stomp the lua-driven ACF.
        if app_id and app_id in self._lua_appids_in_batch:
            result.reason = f"covered by companion lua for app {app_id}"
            return result

        self._emit_progress(item, "Writing ACF")
        acf = ACFWriter(lib_path)
        try:
            acf.write_acf(parsed)
        except Exception as exc:
            logger.warning("ACFWriter.write_acf failed: %s", exc)
            result.ok = False
            result.failing_step = "ACFWriter.write_acf"
            result.reason = str(exc)
            return result

        self._emit_progress(item, "Patching workshop ACF")
        try:
            acf.patch_workshop_acf(parsed)
        except Exception as exc:
            logger.warning("ACFWriter.patch_workshop_acf failed: %s", exc)

        self._emit_progress(item, "Registering library entry")
        try:
            ensure_library_has_app(steam_path, lib_path, app_id)
        except Exception as exc:
            logger.warning("ensure_library_has_app failed: %s", exc)
            result.ok = False
            result.failing_step = "ensure_library_has_app"
            result.reason = str(exc)
            return result

        return result

    # ── Progress + summary helpers ───────────────────────────────

    def _emit_progress(
        self,
        item: QueueItem,
        step: str,
        processed: Optional[int] = None,
        total: Optional[int] = None,
        result: Optional[FileResult] = None,
    ) -> None:
        if self._progress_cb is None:
            return
        with self._lock:
            if processed is None:
                processed = self._processed
            if total is None:
                total = self._total
        payload = {
            "task": "bulk_import",
            "file": str(item.path),
            "kind": item.kind,
            "status": step,
            "processed": processed,
            "total": total,
            "progress": int(round(100 * processed / total)) if total else 0,
        }
        if item.kind == "lua" and item.parsed_lua is not None:
            payload["app_id"] = str(item.parsed_lua.app_id)
        elif item.manifest_depot_id:
            payload["app_id"] = item.manifest_depot_id
        if result is not None:
            payload["ok"] = bool(result.ok)
            if result.reason:
                payload["reason"] = result.reason
            if result.failing_step:
                payload["failing_step"] = result.failing_step
        try:
            self._progress_cb(payload)
        except Exception as exc:
            logger.debug("bulk progress callback failed: %s", exc)

    def _summary_locked(self) -> BatchSummary:
        succeeded = sum(1 for r in self._results if r.ok and not r.skipped)
        failed = sum(1 for r in self._results if not r.ok and not r.skipped)
        skipped = sum(1 for r in self._results if r.skipped)
        return BatchSummary(
            total=self._total,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            results=list(self._results),
        )

    def summary(self) -> BatchSummary:
        with self._lock:
            return self._summary_locked()

    # ── Folder scan helper ───────────────────────────────────────

    @staticmethod
    def collect_from_folder(folder: Path) -> list[Path]:
        """Walk `folder` recursively and collect every `.lua`, `.zip`, and
        `.manifest` file. Validation runs later via `enqueue_files`.
        """

        if folder is None or not folder.exists() or not folder.is_dir():
            return []
        collected: list[Path] = []
        try:
            for p in folder.rglob("*"):
                if not p.is_file():
                    continue
                ext = p.suffix.lower()
                if ext in (".lua", ".zip", ".manifest"):
                    collected.append(p)
        except Exception as exc:
            logger.warning("folder scan failed for %s: %s", folder, exc)
        return collected

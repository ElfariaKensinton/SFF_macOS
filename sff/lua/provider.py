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

from __future__ import annotations

import json
import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Iterable

import httpx

from sff.strings import VERSION
from sff.utils import sff_data_dir

logger = logging.getLogger(__name__)

PROVIDER_URLS = [
    "https://raw.githubusercontent.com/KoriaPolis/Steam-Depot/main/fallback_depotkeys.json",
    "https://pub-d3ba7941fdf24c2c84da530b93221e1c.r2.dev/fallback_depotkeys.json",
]
SUBMIT_URL = "https://stea-provider-api.steamidra.workers.dev/submit"
ALLOWED_FIELDS = {"id", "key", "name", "kind", "parent_appid", "parent_name"}
ALLOWED_KINDS = {"game", "software", "dlc", "depot", "dlc_depot", "unknown"}
MAX_ITEMS_PER_REQUEST = 1000
MAX_BODY_BYTES = 200_000

_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ID_RE = re.compile(r"^\d+$")
_ADDAPPID_KEY_RE = re.compile(
    r"addappid\s*\(\s*(\d+)\s*,\s*[01]\s*,\s*[\"']([0-9a-fA-F]{64})[\"']\s*\)"
)
_ADDAPPID_KEY_LINE_RE = re.compile(
    r"addappid\s*\(\s*(\d+)\s*,\s*[01]\s*,\s*[\"']([0-9a-fA-F]{64})[\"']\s*\)"
    r"\s*(?:--\s*(.*))?$",
    re.IGNORECASE,
)
_ADDAPPID_PLAIN_LINE_RE = re.compile(
    r"addappid\s*\(\s*(\d+)\s*\)\s*(?:--\s*(.*))?$",
    re.IGNORECASE,
)


def bundled_provider_path() -> Path:
    return Path(__file__).resolve().parent / "fallback_depotkeys.json"


def installed_provider_path() -> Path:
    """Persistent bundled-provider path beside a frozen one-dir EXE.

    In source/dev this points at <repo>/_internal/... and usually does not
    exist. In a PyInstaller one-dir build it points at:
      <exe_dir>/_internal/sff/lua/fallback_depotkeys.json
    """
    return sff_data_dir() / "_internal" / "sff" / "lua" / "fallback_depotkeys.json"


def provider_file_candidates() -> list[Path]:
    paths: list[Path] = []
    for path in (bundled_provider_path(), installed_provider_path(), cache_path()):
        if path not in paths:
            paths.append(path)
    return paths


def cache_dir() -> Path:
    return bundled_provider_path().parent


def cache_path() -> Path:
    return cache_dir() / "fallback_depotkeys.json"


def state_path() -> Path:
    return cache_dir() / "contributor_state.json"


def is_valid_id(value) -> bool:
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


def is_valid_key(value) -> bool:
    return isinstance(value, str) and bool(_HEX64_RE.fullmatch(value))


def _clean_text(value) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:160]


def normalize_entry(item_id: str, value) -> dict | None:
    if not is_valid_id(str(item_id)):
        return None
    if isinstance(value, str):
        value = {"key": value}
    if not isinstance(value, dict):
        return None
    kind = str(value.get("kind") or "unknown").strip().lower()
    if kind not in ALLOWED_KINDS:
        kind = "unknown"
    out = {
        "id": str(item_id),
        "key": str(value.get("key") or "").strip().lower(),
        "name": _clean_text(value.get("name")),
        "kind": kind,
        "parent_appid": str(value.get("parent_appid") or "").strip(),
        "parent_name": _clean_text(value.get("parent_name")),
    }
    if out["parent_appid"] and not is_valid_id(out["parent_appid"]):
        out["parent_appid"] = ""
    return out


def validate_provider_data(data) -> dict[str, dict]:
    if not isinstance(data, dict):
        raise ValueError("provider root must be an object")
    cleaned: dict[str, dict] = {}
    for item_id, value in data.items():
        entry = normalize_entry(str(item_id), value)
        if entry is None:
            continue
        out = {k: entry[k] for k in ("key", "name", "kind")}
        if entry.get("parent_appid"):
            out["parent_appid"] = entry["parent_appid"]
        if entry.get("parent_name"):
            out["parent_name"] = entry["parent_name"]
        cleaned[entry["id"]] = out
    return dict(sorted(cleaned.items(), key=lambda kv: int(kv[0])))


def load_provider_file(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_provider_data(data)


def load_provider() -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path in provider_file_candidates():
        if not path.exists():
            continue
        try:
            data = load_provider_file(path)
        except Exception as exc:
            logger.warning("provider load failed for %s: %s", path, exc)
            continue
        merged.update(data)
    return dict(sorted(merged.items(), key=lambda kv: int(kv[0])))


def get_key(item_id: str) -> str:
    entry = load_provider().get(str(item_id))
    if not isinstance(entry, dict):
        return ""
    key = str(entry.get("key") or "")
    return key if is_valid_key(key) else ""


def get_entry(item_id: str) -> dict:
    entry = load_provider().get(str(item_id))
    return dict(entry) if isinstance(entry, dict) else {}


def atomic_save_provider(data: dict[str, dict], path: Path | None = None) -> Path:
    path = path or cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = validate_provider_data(data)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
            f.write("\n")
        tmp_path.replace(path)
        return path
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def _writable_provider_update_targets() -> list[Path]:
    targets = [cache_path()]
    for path in (bundled_provider_path(), installed_provider_path()):
        if path in targets:
            continue
        if path.exists() or path.parent.exists():
            targets.append(path)
    return targets


def download_provider_update(urls: Iterable[str] = PROVIDER_URLS, timeout: float = 20.0) -> dict:
    errors: list[str] = []
    for url in urls:
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            if resp.status_code != 200:
                errors.append(f"{url}: HTTP {resp.status_code}")
                continue
            data = validate_provider_data(resp.json())
            saved_paths: list[str] = []
            save_errors: list[str] = []
            for target in _writable_provider_update_targets():
                try:
                    atomic_save_provider(data, target)
                    saved_paths.append(str(target))
                except Exception as exc:
                    save_errors.append(f"{target}: {exc}")
            if not saved_paths:
                errors.extend(save_errors)
                continue
            return {
                "ok": True,
                "url": url,
                "count": len(data),
                "paths": saved_paths,
                "save_errors": save_errors,
                "errors": errors,
            }
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    return {"ok": False, "errors": errors}


def update_cache_from_lua_bytes(lua_bytes: bytes, app_id: str = "", app_name: str = "") -> int:
    text = lua_bytes.decode("utf-8", errors="ignore")
    pairs = _ADDAPPID_KEY_RE.findall(text)
    if not pairs:
        return 0
    data = load_provider()
    added = 0
    for depot_id, key in pairs:
        if not is_valid_key(key):
            continue
        existing = data.get(depot_id) or {}
        if existing.get("key"):
            continue
        data[depot_id] = {
            "key": key.lower(),
            "name": existing.get("name") or f"Depot {depot_id}",
            "kind": existing.get("kind") or "depot",
            "parent_appid": existing.get("parent_appid") or str(app_id or ""),
            "parent_name": existing.get("parent_name") or _clean_text(app_name),
        }
        added += 1
    if added:
        atomic_save_provider(data)
    return added


def _entry_fingerprint(entry: dict) -> str:
    return f"{entry.get('id', '')}:{entry.get('key', '')}".lower()


def _sent_fingerprints() -> set[str]:
    state = read_contributor_state()
    sent = state.get("sent_items") or []
    if not isinstance(sent, list):
        return set()
    return {str(x).lower() for x in sent if str(x).strip()}


def _mark_fingerprints_sent(items: list[dict]) -> None:
    if not items:
        return
    state = read_contributor_state()
    sent = set(str(x).lower() for x in (state.get("sent_items") or []) if str(x).strip())
    before = len(sent)
    for item in items:
        fp = _entry_fingerprint(item)
        if fp != ":":
            sent.add(fp)
    if len(sent) == before:
        return
    state["sent_items"] = sorted(sent)
    write_contributor_state(state)


def collect_submit_candidates(steam_path: Path | None = None) -> dict:
    entries: list[dict] = []
    invalid = 0
    duplicates = 0
    sent_skipped = 0
    seen: set[tuple[str, str]] = set()
    sent = _sent_fingerprints()

    def add(entry: dict | None) -> None:
        nonlocal invalid, duplicates, sent_skipped
        if not entry:
            invalid += 1
            return
        item = {k: entry.get(k, "") for k in ALLOWED_FIELDS}
        item["id"] = str(item.get("id") or "").strip()
        item["key"] = str(item.get("key") or "").strip().lower()
        item["kind"] = str(item.get("kind") or "unknown").strip().lower()
        if item["kind"] not in ALLOWED_KINDS:
            item["kind"] = "unknown"
        if not is_valid_id(item["id"]) or not is_valid_key(item["key"]):
            invalid += 1
            return
        if not item.get("parent_appid"):
            item.pop("parent_appid", None)
        if not item.get("parent_name"):
            item.pop("parent_name", None)
        key = (item["id"], item["key"])
        if key in seen:
            duplicates += 1
            return
        if _entry_fingerprint(item) in sent:
            sent_skipped += 1
            return
        seen.add(key)
        entries.append(item)

    def scan_lua_file(path: Path) -> None:
        parent_appid = ""
        parent_name = ""
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as exc:
            logger.debug("provider lua scan failed for %s: %s", path, exc)
            return

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("--"):
                continue

            plain = _ADDAPPID_PLAIN_LINE_RE.search(line)
            if plain and not parent_appid:
                parent_appid = plain.group(1)
                parent_name = _clean_text(plain.group(2))
                continue

            keyed = _ADDAPPID_KEY_LINE_RE.search(line)
            if not keyed:
                continue
            depot_id, key, comment = keyed.groups()
            add({
                "id": depot_id,
                "key": key,
                "name": _clean_text(comment) or f"Depot {depot_id}",
                "kind": "depot",
                "parent_appid": parent_appid,
                "parent_name": parent_name,
            })

    saved_lua_root = Path.cwd() / "saved_lua"
    if saved_lua_root.exists():
        for lua_path in sorted(saved_lua_root.glob("*.lua")):
            scan_lua_file(lua_path)

    if steam_path:
        stplugin_root = Path(steam_path) / "config" / "stplug-in"
        if stplugin_root.exists():
            for lua_path in sorted(stplugin_root.glob("*.lua")):
                scan_lua_file(lua_path)

        cfg_dir = Path(steam_path) / "config"
        for cfg in (cfg_dir / "config.vdf", cfg_dir / "config.vdf.backup"):
            if not cfg.exists():
                continue
            try:
                from sff.tools.vdf_key_extractor import VdfKeyExtractor

                for key in VdfKeyExtractor().extract_keys(str(cfg)).keys:
                    add({
                        "id": str(key.depot_id),
                        "key": key.key,
                        "name": f"Depot {key.depot_id}",
                        "kind": "depot",
                        "parent_appid": "",
                        "parent_name": "",
                    })
            except Exception as exc:
                logger.debug("provider config scan failed for %s: %s", cfg, exc)

    return {
        "items": entries,
        "valid": len(entries),
        "invalid": invalid,
        "duplicates": duplicates,
        "already_submitted": sent_skipped,
    }


def _generic_depot_name(value: str, item_id: str) -> bool:
    text = str(value or "").strip().lower()
    return not text or text == f"depot {item_id}" or text == item_id


def enrich_submit_items_with_steam_appinfo(items: list[dict], max_parents: int = 120) -> dict:
    """Fill missing submit metadata from Steam appinfo for known parents.

    This is intentionally bounded. It only looks at parent_appid values already
    present in the clean candidate items, then fills allowed metadata fields.
    """
    all_parent_ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        parent = str(item.get("parent_appid") or "").strip()
        if parent and parent not in seen and is_valid_id(parent):
            seen.add(parent)
            all_parent_ids.append(parent)
    parent_ids = all_parent_ids[:max_parents]

    stats = {
        "enabled": True,
        "parents_checked": 0,
        "items_enriched": 0,
        "errors": 0,
        "error_samples": [],
        "limited": len(all_parent_ids) > len(parent_ids),
    }
    if not parent_ids or not items:
        return stats

    by_id = {str(item.get("id")): item for item in items if is_valid_id(str(item.get("id") or ""))}
    try:
        from sff.steam_client import create_provider_for_current_thread
        provider = create_provider_for_current_thread()
    except Exception as exc:
        stats["errors"] += 1
        stats["error_samples"].append(f"Steam provider unavailable: {exc}")
        return stats

    for parent in parent_ids:
        try:
            info = provider.get_single_app_info(int(parent))
            stats["parents_checked"] += 1
        except Exception as exc:
            stats["errors"] += 1
            if len(stats["error_samples"]) < 5:
                stats["error_samples"].append(f"{parent}: {exc}")
            continue
        if not isinstance(info, dict):
            continue
        common = info.get("common") if isinstance(info.get("common"), dict) else {}
        parent_name = _clean_text(common.get("name"))
        depots = info.get("depots") if isinstance(info.get("depots"), dict) else {}
        for depot_id, depot_data in depots.items():
            item = by_id.get(str(depot_id))
            if not item or not isinstance(depot_data, dict):
                continue
            changed = False
            depot_name = _clean_text(depot_data.get("name"))
            if _generic_depot_name(item.get("name", ""), str(depot_id)) and depot_name:
                item["name"] = depot_name
                changed = True
            if not item.get("parent_appid"):
                item["parent_appid"] = parent
                changed = True
            if parent_name and not item.get("parent_name"):
                item["parent_name"] = parent_name
                changed = True
            target_kind = "dlc_depot" if str(depot_data.get("dlcappid") or "").strip().isdigit() else "depot"
            if item.get("kind") in ("", "unknown", "depot") and item.get("kind") != target_kind:
                item["kind"] = target_kind
                changed = True
            if changed:
                stats["items_enriched"] += 1
    return stats


def chunk_submit_items(items: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    for item in items:
        clean = {k: v for k, v in item.items() if k not in ("parent_appid", "parent_name") or v}
        probe = cur + [clean]
        body = {"tool_version": VERSION, "type": "tool_keys", "items": probe}
        too_many = len(probe) > MAX_ITEMS_PER_REQUEST
        too_big = len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > MAX_BODY_BYTES
        if cur and (too_many or too_big):
            chunks.append(cur)
            cur = [clean]
        else:
            cur = probe
    if cur:
        chunks.append(cur)
    return chunks


def submit_items(items: list[dict]) -> dict:
    accepted = 0
    duplicate = False
    submission_ids: list[str] = []
    chunks = chunk_submit_items(items)

    for chunk in chunks:
        body = {"tool_version": VERSION, "type": "tool_keys", "items": chunk}

        try:
            resp = httpx.post(SUBMIT_URL, json=body, timeout=30)

            if resp.status_code == 409:
                try:
                    data = resp.json()
                except Exception:
                    data = {}

                if data.get("duplicate") is True or data.get("error") == "duplicate_submission":
                    duplicate = True
                    _mark_fingerprints_sent(chunk)
                    continue

                return {"ok": False, "error": f"HTTP 409: {resp.text[:300]}"}

            if resp.status_code >= 400:
                return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}"}

            accepted += len(chunk)
            _mark_fingerprints_sent(chunk)

            try:
                data = resp.json()
                sid = str(data.get("id") or data.get("submission_id") or "")
                if sid:
                    submission_ids.append(sid)
            except Exception:
                pass

        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "accepted": accepted,
        "already_submitted": duplicate and accepted == 0,
        "submission_ids": submission_ids,
        "chunks": len(chunks),
    }


def read_contributor_state() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_contributor_state(state: dict) -> None:
    state_path().parent.mkdir(parents=True, exist_ok=True)
    state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")


def contributor_due() -> bool:
    state = read_contributor_state()
    last = float(state.get("last_submit_at") or 0)
    return time.time() - last >= 24 * 60 * 60


def mark_contributor_run() -> None:
    state = read_contributor_state()
    state["last_submit_at"] = time.time()
    write_contributor_state(state)

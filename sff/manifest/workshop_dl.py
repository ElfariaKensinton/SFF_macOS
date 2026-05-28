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

"""Workshop item file downloader.

Two paths live here side by side. The 4-method cascade
(`download_workshop_item`) covers normal subscribe-eligible workshop items.
The bypass path (`download_with_bypass`) covers ownership-gated items where
Steam itself returns "No internet connection" on Subscribe; it goes through
`IPublishedFileService/GetDetails` plus the UGC CDN with the user's Web API
key only and never carries Steam session cookies.
"""

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, List, Optional

import httpx

logger = logging.getLogger(__name__)

_STEAMAPI_DETAILS_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)
_GGNETWORK_URL = "https://api.ggntw.com/steam.request"
_STEAMCMD_DL_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"

# Bypass-path endpoints. `IPublishedFileService` requires a Web API key and
# returns the canonical `file_url` plus `hcontent_file`; the UGC CDN serves the
# blob with no auth context.
_PFS_GET_DETAILS_URL = (
    "https://api.steampowered.com/IPublishedFileService/GetDetails/v1/"
)
_PFS_GET_COLLECTION_URL = (
    "https://api.steampowered.com/IPublishedFileService/GetCollectionDetails/v1/"
)
_UGC_CDN_BASE = "https://steamusercontent-a.akamaihd.net/ugc"
_BYPASS_CONCURRENCY = 4
_BYPASS_TIMEOUT = 120

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _steamcmd_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    return base / "SteaMidra" / "steamcmd"


def _steamcmd_exe() -> Path:
    d = _steamcmd_dir()
    return d / ("steamcmd.exe" if sys.platform == "win32" else "steamcmd.sh")


def ensure_steamcmd(log: Callable[[str], None] = print) -> Optional[Path]:
    """Download and extract SteamCMD if not present. Returns path or None."""
    exe = _steamcmd_exe()
    if exe.exists():
        return exe
    log("SteamCMD not found — downloading...")
    d = _steamcmd_dir()
    d.mkdir(parents=True, exist_ok=True)
    try:
        resp = httpx.get(_STEAMCMD_DL_URL, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        zip_path = d / "steamcmd.zip"
        zip_path.write_bytes(resp.content)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(d)
        zip_path.unlink(missing_ok=True)
        if exe.exists():
            log(f"SteamCMD ready at {exe}")
            return exe
        log("[!] SteamCMD extraction failed — exe not found after extract")
        return None
    except Exception as e:
        log(f"[!] SteamCMD download failed: {e}")
        return None


def _get_workshop_file_url(item_id: str) -> Optional[str]:
    """SteamWebAPI: fetch file_url from published file details."""
    try:
        resp = httpx.post(
            _STEAMAPI_DETAILS_URL,
            data={"itemcount": "1", "publishedfileids[0]": item_id},
            headers={"User-Agent": _CHROME_UA},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            details = (
                data.get("response", {})
                .get("publishedfiledetails", [{}])[0]
            )
            url = details.get("file_url", "")
            return url if url else None
    except Exception as e:
        logger.debug("SteamWebAPI file_url fetch failed: %s", e)
    return None


def _ggnetwork_download_url(item_id: str) -> Optional[str]:
    """GGNetwork API: returns a time-limited direct download URL."""
    item_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={item_id}"
    try:
        resp = httpx.post(
            _GGNETWORK_URL,
            json={"url": item_url},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://ggntw.com",
                "Referer": "https://ggntw.com/",
                "User-Agent": _CHROME_UA,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            dl = (
                data.get("download_url")
                or data.get("url")
                or data.get("link")
                or data.get("file")
                or data.get("download")
            )
            if not dl and isinstance(data.get("data"), dict):
                dl = (
                    data["data"].get("download_url")
                    or data["data"].get("url")
                    or data["data"].get("link")
                    or data["data"].get("file")
                )
            return dl if dl else None
        logger.debug("GGNetwork returned HTTP %s: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.debug("GGNetwork request failed: %s", e)
    return None


def _download_file(url: str, dest: Path, log: Callable[[str], None]) -> bool:
    """Stream-download url to dest. Returns True on success."""
    try:
        with httpx.stream(
            "GET",
            url,
            headers={"User-Agent": _CHROME_UA},
            timeout=120,
            follow_redirects=True,
        ) as resp:
            if resp.status_code != 200:
                log(f"[!] HTTP {resp.status_code} downloading from {url}")
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as fh:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    fh.write(chunk)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as e:
        log(f"[!] Download error: {e}")
        return False


def _run_steamcmd(
    game_id: str,
    item_id: str,
    output_dir: Path,
    username: str = "anonymous",
    password: str = "",
    log: Callable[[str], None] = print,
) -> bool:
    """Run SteamCMD to download a workshop item. Returns True if output dir has files."""
    steamcmd = ensure_steamcmd(log)
    if steamcmd is None:
        return False
    output_dir.mkdir(parents=True, exist_ok=True)
    if username.lower() == "anonymous":
        login_args = ["+login", "anonymous"]
    else:
        login_args = ["+login", username, password] if password else ["+login", username]
    cmd = (
        [str(steamcmd)]
        + login_args
        + [
            "+force_install_dir", str(output_dir),
            "+workshop_download_item", str(game_id), str(item_id), "validate",
            "+quit",
        ]
    )
    log(f"Running SteamCMD: {' '.join(cmd[:5])} ...")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=False,
            timeout=300,
            cwd=str(_steamcmd_dir()),
        )
        item_dir = (
            output_dir
            / "steamapps"
            / "workshop"
            / "content"
            / str(game_id)
            / str(item_id)
        )
        if item_dir.exists() and any(item_dir.iterdir()):
            log(f"[OK] SteamCMD download complete: {item_dir}")
            return True
        log(f"[!] SteamCMD exited {proc.returncode} — output dir empty")
        return False
    except subprocess.TimeoutExpired:
        log("[!] SteamCMD timed out after 5 minutes")
        return False
    except Exception as e:
        log(f"[!] SteamCMD error: {e}")
        return False


def download_workshop_item(
    item_id: str,
    game_id: str,
    output_dir: Path,
    steam_username: str = "anonymous",
    steam_password: str = "",
    log: Callable[[str], None] = print,
) -> dict:
    """Try all 4 methods to download a workshop item.

    Returns {
        "success": bool,
        "method": str,
        "path": str | None,
        "error": str | None,
    }
    """
    result = {"success": False, "method": "", "path": None, "error": None}

    # Method 1: SteamWebAPI direct file_url
    log("Method 1: SteamWebAPI direct download...")
    file_url = _get_workshop_file_url(item_id)
    if file_url:
        dest = output_dir / f"{item_id}_direct{Path(file_url.split('?')[0]).suffix or '.zip'}"
        if _download_file(file_url, dest, log):
            log(f"[OK] Method 1 succeeded: {dest.name}")
            result.update({"success": True, "method": "SteamWebAPI", "path": str(dest)})
            return result
        log("[!] Method 1: download failed")
    else:
        log("Method 1: no direct file_url (not a legacy item)")

    # Method 2: GGNetwork API
    log("Method 2: GGNetwork API...")
    gg_url = _ggnetwork_download_url(item_id)
    if gg_url:
        dest = output_dir / f"{item_id}_ggnetwork.zip"
        if _download_file(gg_url, dest, log):
            log(f"[OK] Method 2 succeeded: {dest.name}")
            result.update({"success": True, "method": "GGNetwork", "path": str(dest)})
            return result
        log("[!] Method 2: GGNetwork URL expired or download failed")
    else:
        log("[!] Method 2: GGNetwork did not return a download URL (item not cached)")

    # Method 3: SteamCMD anonymous
    log("Method 3: SteamCMD anonymous...")
    steamcmd_out = output_dir / "steamcmd_content"
    if _run_steamcmd(game_id, item_id, steamcmd_out, "anonymous", "", log):
        item_dir = (
            steamcmd_out
            / "steamapps"
            / "workshop"
            / "content"
            / str(game_id)
            / str(item_id)
        )
        result.update({"success": True, "method": "SteamCMD (anonymous)", "path": str(item_dir)})
        return result

    # Method 4: SteamCMD authenticated
    if steam_username and steam_username.lower() != "anonymous":
        log("Method 4: SteamCMD authenticated...")
        if _run_steamcmd(game_id, item_id, steamcmd_out, steam_username, steam_password, log):
            item_dir = (
                steamcmd_out
                / "steamapps"
                / "workshop"
                / "content"
                / str(game_id)
                / str(item_id)
            )
            result.update(
                {"success": True, "method": "SteamCMD (authenticated)", "path": str(item_dir)}
            )
            return result
    else:
        log("Method 4: skipped (no Steam username configured)")

    result["error"] = (
        "All 4 methods failed. "
        "The item may require authentication or may not be publicly available."
    )
    log(f"[!] {result['error']}")
    return result


def parse_workshop_item_id(url_or_id: str) -> Optional[str]:
    """Extract item ID from a Steam Workshop URL or bare ID string."""
    match = re.search(r"(?:id=|filedetails/\?id=|workshopdetails/\?id=)(\d+)", url_or_id)
    if match:
        return match.group(1)
    if url_or_id.strip().isdigit():
        return url_or_id.strip()
    return None


# ── Bypass path (ownership-gated workshop items) ────────────────

_COLLECTION_URL_RE = re.compile(
    r"steamcommunity\.com/(?:sharedfiles|workshop)/filedetails/\?id=(\d+)",
    re.IGNORECASE,
)


def _is_collection_url(url_or_id: str) -> bool:
    text = url_or_id.lower()
    return "workshop_collection" in text or "collection" in text and "filedetails" in text


def _http_get_binary(url: str, log: Callable[[str], None]) -> Optional[bytes]:
    """Fetch a UGC blob over HTTPS GET with no Steam session cookies.

    The bypass path uses the user-supplied Web API key on the GetDetails
    call; the CDN GET below carries no auth at all. We still pass an empty
    cookie jar to make sure no ambient session leaks through.
    """
    try:
        with httpx.Client(
            timeout=_BYPASS_TIMEOUT,
            follow_redirects=True,
            cookies=httpx.Cookies(),
        ) as client:
            resp = client.get(url, headers={"User-Agent": _CHROME_UA})
        if resp.status_code == 200:
            return resp.content
        log(f"[!] CDN HTTP {resp.status_code} for {url}")
    except httpx.HTTPError as e:
        log(f"[!] CDN error: {e}")
    except Exception as e:
        log(f"[!] CDN fetch crashed: {e}")
    return None


def _get_published_file_details(
    item_id: str,
    web_api_key: str,
    log: Callable[[str], None],
) -> Optional[dict]:
    """`IPublishedFileService/GetDetails` returns one record per id.

    Sends only the API key plus the published-file id. No cookies, no Steam
    session header. Returns the first detail dict, or None on any failure.
    """
    if not web_api_key:
        log("[!] bypass: missing Web API key")
        return None
    try:
        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            cookies=httpx.Cookies(),
        ) as client:
            resp = client.post(
                _PFS_GET_DETAILS_URL,
                data={
                    "key": web_api_key,
                    "publishedfileids[0]": str(item_id),
                    "includetags": "false",
                    "includeadditionalpreviews": "false",
                    "includechildren": "false",
                    "includekvtags": "false",
                    "includevotes": "false",
                    "short_description": "true",
                    "includeforsaledata": "false",
                    "includemetadata": "false",
                    "strip_description_bbcode": "false",
                },
                headers={"User-Agent": _CHROME_UA},
            )
        if resp.status_code != 200:
            log(f"[!] GetDetails HTTP {resp.status_code} for {item_id}")
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        log(f"[!] GetDetails request failed for {item_id}: {e}")
        return None
    try:
        details_list = data.get("response", {}).get("publishedfiledetails", [])
        if not details_list:
            return None
        return details_list[0]
    except (KeyError, TypeError, AttributeError) as e:
        log(f"[!] GetDetails parse failed for {item_id}: {e}")
        return None


def _get_collection_children_pfs(
    collection_id: str,
    web_api_key: str,
    log: Callable[[str], None],
) -> List[str]:
    """`IPublishedFileService/GetCollectionDetails` returns the member ids."""
    if not web_api_key:
        log("[!] bypass: missing Web API key for collection lookup")
        return []
    try:
        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            cookies=httpx.Cookies(),
        ) as client:
            resp = client.post(
                _PFS_GET_COLLECTION_URL,
                data={
                    "key": web_api_key,
                    "collectioncount": "1",
                    "publishedfileids[0]": str(collection_id),
                },
                headers={"User-Agent": _CHROME_UA},
            )
        if resp.status_code != 200:
            log(f"[!] GetCollectionDetails HTTP {resp.status_code} for {collection_id}")
            return []
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        log(f"[!] GetCollectionDetails request failed: {e}")
        return []
    try:
        details = data.get("response", {}).get("collectiondetails", [])
        if not details:
            return []
        children = details[0].get("children", [])
        out: List[str] = []
        for child in children:
            pid = child.get("publishedfileid")
            if pid is None:
                continue
            try:
                out.append(str(int(pid)))
            except (TypeError, ValueError):
                continue
        return out
    except (KeyError, TypeError, AttributeError) as e:
        log(f"[!] GetCollectionDetails parse failed: {e}")
        return []


def _ugc_url(hcontent_file) -> str:
    return f"{_UGC_CDN_BASE}/{hcontent_file}/"


def _safe_filename(item_id: str, raw: Optional[str]) -> str:
    if raw:
        # Strip path components from the API-supplied filename so a
        # malicious entry can't escape `<out_dir>/<item_id>/`.
        base = Path(str(raw)).name.strip()
        if base:
            return base
    return f"{item_id}.bin"


def download_with_bypass(
    item_id: str,
    out_dir: Path,
    web_api_key: str,
    log: Callable[[str], None] = print,
) -> dict:
    """Ownership-bypass workshop download for a single published-file id.

    Returns one row: ``{"success": bool, "item_id": str, ...}``. Never writes
    a partial file: a CDN size mismatch discards the body before any disk
    write. The path uses the supplied Web API key on the GetDetails call and
    no cookies anywhere.
    """
    row = {"success": False, "item_id": str(item_id), "path": None, "error": None}
    item_id = str(item_id).strip()
    if not item_id.isdigit():
        row["error"] = f"invalid item id: {item_id!r}"
        log(f"[!] bypass {item_id}: {row['error']}")
        return row

    details = _get_published_file_details(item_id, web_api_key, log)
    if not details:
        row["error"] = "GetDetails empty"
        return row

    file_url = details.get("file_url") or ""
    hcontent_file = details.get("hcontent_file") or ""
    if not file_url and hcontent_file:
        file_url = _ugc_url(hcontent_file)
    if not file_url:
        row["error"] = "no file_url or hcontent_file"
        log(f"[!] bypass {item_id}: {row['error']}")
        return row

    body = _http_get_binary(file_url, log)
    if body is None:
        row["error"] = "download failed"
        return row

    expected = details.get("file_size")
    if expected not in (None, "", 0, "0"):
        try:
            expected_int = int(expected)
        except (TypeError, ValueError):
            expected_int = -1
        if expected_int >= 0 and len(body) != expected_int:
            row["error"] = f"size mismatch {len(body)} != {expected_int}"
            log(f"[!] bypass {item_id}: {row['error']}")
            return row

    filename = _safe_filename(item_id, details.get("filename"))
    item_dir = Path(out_dir) / item_id
    try:
        item_dir.mkdir(parents=True, exist_ok=True)
        out_path = item_dir / filename
        out_path.write_bytes(body)
    except OSError as e:
        row["error"] = f"write failed: {e}"
        log(f"[!] bypass {item_id}: {row['error']}")
        return row

    log(f"[OK] bypass {item_id} -> {out_path}")
    row.update({"success": True, "path": str(out_path)})
    return row


def _classify_input_token(token: str) -> Optional[dict]:
    """Tag a single line as item, collection, or unknown.

    Returns ``{"kind": "item"|"collection", "id": "..."}`` or None when the
    line yields no usable id. Collection URLs carry an explicit
    ``workshop_collection`` marker; everything else is treated as an item.
    """
    text = token.strip()
    if not text:
        return None
    is_collection = (
        "workshop_collection" in text.lower()
        or "/collections/" in text.lower()
    )
    match = re.search(r"(?:id=|filedetails/\?id=)(\d+)", text)
    pid = match.group(1) if match else (text if text.isdigit() else None)
    if not pid:
        return None
    return {"kind": "collection" if is_collection else "item", "id": pid}


def _expand_input_to_item_ids(
    raw: str,
    web_api_key: str,
    log: Callable[[str], None],
) -> List[str]:
    """Resolve a paste-list / single URL / collection URL to item ids.

    Collection ids resolve through `IPublishedFileService/GetCollectionDetails`
    before any download starts so the driver knows the full work set up
    front. Order is preserved within each input line.
    """
    seen: set = set()
    out: List[str] = []

    def _push(pid: str) -> None:
        if pid and pid not in seen:
            seen.add(pid)
            out.append(pid)

    for line in raw.splitlines():
        token = _classify_input_token(line)
        if token is None:
            continue
        if token["kind"] == "collection":
            children = _get_collection_children_pfs(
                token["id"], web_api_key, log
            )
            for cid in children:
                _push(cid)
        else:
            _push(token["id"])
    return out


def run_bypass_batch(
    raw_input: str,
    out_dir: Path,
    web_api_key: str,
    on_progress: Callable[[dict], None],
    log: Callable[[str], None] = print,
) -> dict:
    """Drive the bypass download for a paste list / URL / collection URL.

    Emits one ``task_progress`` payload per input id via ``on_progress``. When
    the input expands to zero items (empty / all-invalid), emits a single
    sentinel payload with ``added=0, failed=0, reason="no items to process"``.
    A row that observes both completed and failed states ends up failed:
    failure takes precedence over success.
    """
    item_ids = _expand_input_to_item_ids(raw_input or "", web_api_key, log)

    if not item_ids:
        sentinel = {
            "task": "workshop_bypass",
            "added": 0,
            "failed": 0,
            "reason": "no items to process",
        }
        try:
            on_progress(sentinel)
        except Exception:
            logger.debug("bypass progress sentinel emit failed", exc_info=True)
        return {"success": True, "added": 0, "failed": 0, "rows": []}

    results: dict = {}
    results_lock = threading.Lock()

    def _record(row: dict) -> None:
        rid = row.get("item_id")
        if not rid:
            return
        with results_lock:
            prior = results.get(rid)
            # failure takes precedence over success
            if prior is None:
                results[rid] = row
            elif prior.get("success") and not row.get("success"):
                results[rid] = row

    semaphore = threading.Semaphore(_BYPASS_CONCURRENCY)

    def _one(pid: str) -> None:
        with semaphore:
            try:
                row = download_with_bypass(pid, out_dir, web_api_key, log)
            except Exception as e:
                row = {
                    "success": False,
                    "item_id": pid,
                    "path": None,
                    "error": f"crash: {e}",
                }
                logger.exception("bypass worker crashed for %s", pid)
            _record(row)
            payload = {
                "task": "workshop_bypass",
                "item_id": pid,
                "success": bool(row.get("success")),
                "path": row.get("path") or "",
                "error": row.get("error") or "",
            }
            try:
                on_progress(payload)
            except Exception:
                logger.debug("bypass progress emit failed", exc_info=True)

    with ThreadPoolExecutor(max_workers=_BYPASS_CONCURRENCY) as pool:
        for pid in item_ids:
            pool.submit(_one, pid)

    rows = list(results.values())
    added = sum(1 for r in rows if r.get("success"))
    failed = sum(1 for r in rows if not r.get("success"))
    return {"success": True, "added": added, "failed": failed, "rows": rows}

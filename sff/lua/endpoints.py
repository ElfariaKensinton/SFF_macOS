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

"""API endpoints are in here"""

import asyncio
import io
import json
import logging
import re
from pathlib import Path

import httpx

from colorama import Fore, Style

from sff.http_utils import download_to_tempfile, get_request
from sff.prompts import prompt_confirm, prompt_secret
from sff.storage.settings import get_setting, set_setting
from sff.structs import Settings
from sff.zip import read_lua_from_zip

logger = logging.getLogger(__name__)

_REVO_PATTERN = re.compile(
    r'addappid\(\s*(\d+)\s*,\s*[01]\s*,\s*["\']([0-9a-fA-F]{64})["\']\s*\)'
)


def _update_fallback_depotkeys(lua_bytes):
    try:
        text = lua_bytes.decode("utf-8", errors="ignore")
        new_pairs = dict(_REVO_PATTERN.findall(text))
        if not new_pairs:
            return
        local_db = Path(__file__).parent / "fallback_depotkeys.json"
        if not local_db.exists():
            return
        existing = json.loads(local_db.read_text(encoding="utf-8"))
        added = 0
        for depot_id, key in new_pairs.items():
            if depot_id not in existing:
                existing[depot_id] = key
                added += 1
        if added == 0:
            return
        sorted_data = dict(sorted(existing.items(), key=lambda x: int(x[0])))
        local_db.write_text(json.dumps(sorted_data, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_oureverday(dest, app_id):
    import json
    import httpx as _httpx
    from sff.steam_client import create_provider_for_current_thread

    if not app_id or not str(app_id).strip().isdigit():
        print(Fore.RED + f"Invalid App ID: '{app_id}'" + Style.RESET_ALL)
        return None

    # Step 1: Steam native query for depot IDs
    print(Fore.CYAN + f"[Step 1] Fetching depot list for {app_id} from Steam client..." + Style.RESET_ALL)
    try:
        # Build the SteamClient INSIDE the executor task. SteamClient binds
        # gevent's hub to whichever OS thread constructed it, so if we make
        # the client out here and then submit() get_single_app_info, the
        # executor thread has no hub for that client and gevent fires
        # "This operation would block forever". Building it inside keeps
        # the client + the hub on the same thread.
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FT
        def _fetch_app_info():
            from sff.steam_client import create_provider_for_current_thread as _mk
            _provider = _mk()
            return _provider.get_single_app_info(int(app_id))
        with ThreadPoolExecutor(max_workers=1) as _ex:
            _fut = _ex.submit(_fetch_app_info)
            try:
                app_info = _fut.result(timeout=30)
            except _FT:
                print(Fore.RED + f"Steam app-info timed out for {app_id} (CM probably down)." + Style.RESET_ALL)
                return None
        if not app_info:
            print(Fore.RED + f"Failed to query Steam App Info for {app_id}." + Style.RESET_ALL)
            return None
        depots = [d for d in app_info.get("depots", {}).keys() if d.isdigit()]
    except Exception as e:
        print(Fore.RED + f"Steam query failed while checking depots: {e}" + Style.RESET_ALL)
        return None

    if not depots:
        print(Fore.RED + f"No valid depots exist on Steam for this App ID." + Style.RESET_ALL)
        return None

    # Pull every DLC app id Steam reports for this game from extended.listofdlc.
    # These are DLCs with no depot of their own (cosmetic, soundtrack, in-game
    # currency, etc) — the keyed addappid(depot, 1, "key") lines won't cover
    # them because they have no depot_id. Adding plain addappid(<dlc_id>) lines
    # tells LumaCore to mark them as owned without any depot data.
    dlc_app_ids: list[str] = []
    try:
        listofdlc = (
            app_info.get("extended", {}).get("listofdlc", "")
            if isinstance(app_info.get("extended"), dict) else ""
        )
        if isinstance(listofdlc, str) and listofdlc.strip():
            dlc_app_ids = [
                x.strip()
                for x in listofdlc.split(",")
                if x.strip().isdigit()
            ]
    except Exception:
        dlc_app_ids = []

    # Step 2: Bundled local key database
    print(Fore.CYAN + f"[Step 2] Loading bundled key database..." + Style.RESET_ALL)
    keys_dict = {}
    local_db = Path(__file__).parent / "fallback_depotkeys.json"
    if local_db.exists():
        try:
            keys_dict = json.loads(local_db.read_text(encoding="utf-8"))
            print(Fore.GREEN + f"[OK] Loaded bundled key database ({len(keys_dict):,} entries)." + Style.RESET_ALL)
        except Exception as e:
            print(Fore.YELLOW + f"Failed to load bundled key database ({e})." + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + f"Bundled key database not found." + Style.RESET_ALL)

    # Generate the Lua File Dynamically
    lua_lines = [f"addappid({app_id})"]
    found = 0
    for d in depots:
        if d in keys_dict:
            # SteamAutoCrack uses addappid(depot_id, 1, "key") format
            lua_lines.append(f"addappid({d}, 1, \"{keys_dict[d]}\")")
            found += 1

    if found == 0:
        print(Fore.RED + f"No known keys found in any database for {app_id}." + Style.RESET_ALL)
        # Step 3: revobd.club — parse keys and inject into keys_dict (last resort)
        print(Fore.CYAN + f"[Step 3] Trying revobd.club pre-built Lua archive..." + Style.RESET_ALL)
        # _REVO_PATTERN is defined at module level
        try:
            revo_resp = _httpx.get(
                f"https://api.luagen.revobd.club/{app_id}.zip",
                timeout=20,
                follow_redirects=True,
            )
            if revo_resp.status_code == 200 and revo_resp.content:
                lua_bytes = read_lua_from_zip(io.BytesIO(revo_resp.content), decode=False)
                if lua_bytes:
                    revo_keys = dict(_REVO_PATTERN.findall(lua_bytes.decode("utf-8", errors="ignore")))
                    injected = 0
                    for d in depots:
                        if d not in keys_dict and d in revo_keys:
                            keys_dict[d] = revo_keys[d]
                            injected += 1
                    if injected > 0:
                        print(Fore.GREEN + f"\u2705 revobd.club: Injected {injected} key(s) for {app_id}" + Style.RESET_ALL)
                        lua_lines = [f"addappid({app_id})"]
                        found = 0
                        for d in depots:
                            if keys_dict.get(d):
                                lua_lines.append(f"addappid({d}, 1, \"{keys_dict[d]}\")")
                                found += 1
                        if found > 0:
                            # Append every depotless DLC the game declares so
                            # LumaCore marks them as owned alongside the keyed
                            # depots above.
                            for dlc_id in dlc_app_ids:
                                if dlc_id != str(app_id) and dlc_id not in depots:
                                    lua_lines.append(f"addappid({dlc_id})")
                            lua_path = dest / f"{app_id}.lua"
                            lua_path.write_text("\n".join(lua_lines), encoding="utf-8")
                            print(Fore.GREEN + f"\u2705 Built Lua for {app_id} using revobd.club keys ({found} depot(s))" + Style.RESET_ALL)
                            return lua_path
            print(Fore.YELLOW + f"revobd.club: No usable keys for {app_id} (HTTP {revo_resp.status_code})." + Style.RESET_ALL)
        except Exception as e:
            print(Fore.YELLOW + f"revobd.club unreachable ({e})." + Style.RESET_ALL)
        return None

    # Append every depotless DLC the game declares so LumaCore marks them as
    # owned alongside the keyed depots above. Skipping the base appid and any
    # id that already appears as a depot avoids duplicates.
    appended_dlcs = 0
    for dlc_id in dlc_app_ids:
        if dlc_id == str(app_id) or dlc_id in depots:
            continue
        lua_lines.append(f"addappid({dlc_id})")
        appended_dlcs += 1

    lua_path = dest / f"{app_id}.lua"
    with lua_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lua_lines))

    if appended_dlcs:
        print(Fore.GREEN + f"[OK] Built custom Lua for {app_id} (Resolved {found} keys natively, +{appended_dlcs} DLC appid(s))" + Style.RESET_ALL)
    else:
        print(Fore.GREEN + f"[OK] Built custom Lua for {app_id} (Resolved {found} keys natively)" + Style.RESET_ALL)
    return lua_path


def get_hubcap(dest, app_id, depotcache = None):
    if not app_id or not str(app_id).strip().isdigit():
        print(Fore.RED + f"Invalid App ID: '{app_id}'" + Style.RESET_ALL)
        return None
    url = f"https://hubcapmanifest.com/api/v1/manifest/{app_id}"

    # Loop to allow retry with new API key
    while True:
        if not (hubcap_key := get_setting(Settings.HUBCAP_KEY)):
            hubcap_key = prompt_secret(
                "Paste your Hubcap API key here: ",
                lambda x: x.startswith("smm"),
                "That's not a Hubcap API key!",
                long_instruction=(
                    "Go to the Hubcap Manifest website and request an API key. It's free."
                ),
            ).strip()
            set_setting(Settings.HUBCAP_KEY, hubcap_key)
        headers = {
            "Authorization": f"Bearer {hubcap_key}",
        }
        try:
            stats_resp = httpx.get(
                "https://hubcapmanifest.com/api/v1/user/stats",
                headers=headers,
                timeout=15,
                follow_redirects=True,
            )
        except httpx.ConnectError:
            print(
                Fore.RED
                + "\nNetwork error: Cannot reach Hubcap Manifest API."
                  " Check your internet connection."
                + Style.RESET_ALL
            )
            return None
        except httpx.RequestError as e:
            print(Fore.RED + f"\nNetwork error connecting to Hubcap Manifest: {e}" + Style.RESET_ALL)
            return None
        if stats_resp.status_code == 401:
            print(Fore.RED + "\nHubcap API key is invalid or expired." + Style.RESET_ALL)
            if prompt_confirm("Do you want to enter a new API key?"):
                set_setting(Settings.HUBCAP_KEY, "")
                continue
            else:
                print(Fore.YELLOW + "\nYou can update your API key in Settings later." + Style.RESET_ALL)
                return None
        elif stats_resp.status_code != 200:
            detail = ""
            try:
                detail = stats_resp.json().get("detail", "")
            except Exception:
                pass
            if detail:
                print(Fore.RED + f"\nHubcap error: {detail}" + Style.RESET_ALL)
                if "discord" in detail.lower():
                    print(
                        Fore.YELLOW
                        + "You must be a member of the Hubcap Discord server to use this API.\n"
                          "Join at: https://discord.gg/hubcap — then re-authenticate to get a valid key."
                        + Style.RESET_ALL
                    )
                elif "state" in detail.lower():
                    print(
                        Fore.YELLOW
                        + "OAuth state error — your authentication session expired or was already used.\n"
                          "Go to https://hubcapmanifest.com and log in again to get a fresh API key."
                        + Style.RESET_ALL
                    )
            else:
                print(
                    Fore.RED
                    + f"\nHubcap Manifest API returned HTTP {stats_resp.status_code}."
                    + Style.RESET_ALL
                )
            return None
        data = stats_resp.json()
        break

    usage = data.get("daily_usage")
    limit = data.get("daily_limit")
    state = data.get("can_make_requests")

    if not state:
        print(
            Fore.RED
            + f"Daily limit exceeded! You used {usage}/{limit}"
            + Style.RESET_ALL
        )
        return None
    else:
        logger.debug(f"Downloading lua files from {url}")
        lua_bytes = b''
        while True:
            with download_to_tempfile(url, headers) as tf:
                if tf is None:
                    if prompt_confirm("Try again?"):
                        continue
                    break
                data = tf.read()
                print(
                    Fore.GREEN
                    + f"Hubcap Daily Limit: {usage+1}/{limit}"
                    + Style.RESET_ALL
                )
                lua_bytes = read_lua_from_zip(io.BytesIO(data), decode=False, depotcache=depotcache)
                if lua_bytes is None:
                    # Try to decode server response for a useful error message.
                    # Hubcap sometimes returns an HTML 404 page (or Cloudflare
                    # interstitial) wrapped in HTTP 200. Detect that shape
                    # specifically so users get a clear "not on Hubcap" line
                    # instead of a wall of HTML in the log.
                    try:
                        decoded = data.decode("utf-8", errors="replace")
                    except Exception:
                        decoded = repr(data[:200])
                    stripped = decoded.lstrip().lower()
                    looks_html = stripped.startswith("<!doctype") or stripped.startswith("<html")
                    if looks_html:
                        if "page not found" in decoded.lower() or "page-not-found" in decoded.lower():
                            print(
                                Fore.RED
                                + f"Hubcap: app {app_id} is not in the Hubcap database. "
                                "Try Ryuu or oureveryday for this game."
                                + Style.RESET_ALL
                            )
                        else:
                            print(
                                Fore.RED
                                + "Hubcap returned an HTML page instead of a Lua zip "
                                "(rate limit, Cloudflare challenge, or service down). "
                                "Try again in a minute or pick a different provider."
                                + Style.RESET_ALL
                            )
                        break
                    try:
                        parsed = json.loads(decoded)
                        print(
                            Fore.RED
                            + json.dumps(parsed, indent=2)
                            + Style.RESET_ALL
                        )
                    except json.JSONDecodeError:
                        print(
                            "Did not receive a ZIP file or JSON:\n"
                            + decoded[:500]
                        )
            break
        lua_path = dest / f"{app_id}.lua"
        if lua_bytes:
            with lua_path.open("wb") as f:
                f.write(lua_bytes)
            _update_fallback_depotkeys(lua_bytes)
            try:
                from sff.lua.dlc_appid_enricher import append_depotless_dlcs
                appended = append_depotless_dlcs(lua_path, app_id)
                if appended:
                    logger.debug(
                        "hubcap: appended %d depotless dlc line(s) for %s",
                        appended, app_id,
                    )
            except Exception as e:
                logger.debug("hubcap: dlc enricher raised for %s: %s", app_id, e)
            return lua_path
        return None


def get_ryuu(dest, app_id, depotcache=None, request_update=None):
    if not app_id or not str(app_id).strip().isdigit():
        print(Fore.RED + f"Invalid App ID: '{app_id}'" + Style.RESET_ALL)
        return None
    if request_update is None:
        request_update = prompt_confirm(
            "[Optional] Request an update from Ryuu before downloading?\n"
            "  (This can be slow and may fail — skip to get the current version.)"
        )

    max_attempts = 3
    attempt = 0
    while attempt < max_attempts:
        if not (ryuu_key := get_setting(Settings.RYUU_KEY)):
            ryuu_key = prompt_secret(
                "Paste your Ryuu API key: ",
                lambda x: bool(x.strip()),
                "API key cannot be empty.",
                long_instruction="Contact Ryuu staff to get an API key.",
            ).strip()
            set_setting(Settings.RYUU_KEY, ryuu_key)

        if request_update:
            try:
                upd_resp = httpx.get(
                    f"https://generator.ryuu.lol/resellerrequestupdate"
                    f"?appid={app_id}&auth_code={ryuu_key}",
                    timeout=30,
                    follow_redirects=True,
                )
                if upd_resp.status_code == 200:
                    msg = upd_resp.json().get("message", "OK")
                    print(Fore.GREEN + f"Ryuu update: {msg}" + Style.RESET_ALL)
                elif upd_resp.status_code == 400:
                    body = (upd_resp.text or "")[:4096]
                    print(
                        Fore.YELLOW
                        + f"ryuu rejected update: 400 (appid not in db) {body}"
                        + Style.RESET_ALL
                    )
                else:
                    body = (upd_resp.text or "")[:4096]
                    print(
                        Fore.YELLOW
                        + f"ryuu rejected update: {upd_resp.status_code} {body}"
                        + Style.RESET_ALL
                    )
            except Exception as e:
                print(Fore.YELLOW + f"Ryuu update request failed ({e}). Continuing with download..." + Style.RESET_ALL)
            request_update = False

        try:
            resp = httpx.get(
                f"https://generator.ryuu.lol/secure_download"
                f"?appid={app_id}&auth_code={ryuu_key}",
                timeout=60,
                follow_redirects=True,
            )
        except httpx.ConnectError:
            print(
                Fore.RED
                + "\nNetwork error: Cannot reach Ryuu API."
                  " Check your internet connection."
                + Style.RESET_ALL
            )
            return None
        except httpx.RequestError as e:
            print(Fore.RED + f"\nNetwork error connecting to Ryuu: {e}" + Style.RESET_ALL)
            return None

        if resp.status_code == 404:
            body = (resp.text or "")[:4096]
            print(
                Fore.RED
                + f"ryuu rejected: 404 (App ID {app_id} not found) {body}"
                + Style.RESET_ALL
            )
            return None

        if resp.status_code == 403:
            attempt += 1
            body = (resp.text or "")[:4096]
            print(
                Fore.RED
                + f"ryuu rejected: 403 — API key rejected or subscription expired."
                  f" {body} (Attempt {attempt}/{max_attempts})"
                + Style.RESET_ALL
            )
            if attempt >= max_attempts:
                print(Fore.RED + "Ryuu: Max attempts reached. Check your API key in Settings." + Style.RESET_ALL)
                return None
            if prompt_confirm("Do you want to enter a new API key?"):
                set_setting(Settings.RYUU_KEY, "")
                continue
            return None

        if resp.status_code != 200:
            body = (resp.text or "")[:4096]
            print(
                Fore.RED
                + f"ryuu rejected: {resp.status_code} {body}"
                + Style.RESET_ALL
            )
            return None

        lua_bytes = read_lua_from_zip(io.BytesIO(resp.content), decode=False, depotcache=depotcache)
        if lua_bytes is None:
            print(Fore.RED + "Ryuu: ZIP downloaded but no .lua file found inside." + Style.RESET_ALL)
            return None

        lua_path = dest / f"{app_id}.lua"
        with lua_path.open("wb") as f:
            f.write(lua_bytes)
        _update_fallback_depotkeys(lua_bytes)
        try:
            from sff.lua.dlc_appid_enricher import append_depotless_dlcs
            appended = append_depotless_dlcs(lua_path, app_id)
            if appended:
                logger.debug(
                    "ryuu: appended %d depotless dlc line(s) for %s",
                    appended, app_id,
                )
        except Exception as e:
            logger.debug("ryuu: dlc enricher raised for %s: %s", app_id, e)
        print(Fore.GREEN + f"[OK] Ryuu: Downloaded Lua for {app_id}" + Style.RESET_ALL)
        return lua_path
    return None

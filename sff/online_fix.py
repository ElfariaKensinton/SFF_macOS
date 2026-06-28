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
Online-fix.me integration — search + open browser.
The old automatic download system has been removed.
SteaMidra now only helps you find the right page; you follow their guide manually.
"""

import logging
import os
import re
import shutil
import tempfile
from urllib.parse import quote, unquote, urlparse, urljoin

import httpx
from colorama import Fore, Style

from sff.storage.settings import get_setting, set_setting, Settings

logger = logging.getLogger(__name__)

ONLINE_FIX_BASE_URL = "https://online-fix.me"
ONLINE_FIX_DISCORD = "https://discord.gg/ZJx6seG"

# ── Shared utility functions (kept for hv_fix.py and other callers) ──


def _detect_archiver():
    """Find a working archive extractor for the current platform."""
    import shutil as sh
    if os.name == "nt":
        for p in [sh.which("winrar"), r"C:\Program Files\WinRAR\winrar.exe", r"C:\Program Files (x86)\WinRAR\winrar.exe"]:
            if p and os.path.exists(p): return ("winrar", p)
        for p in [sh.which("7z"), r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"]:
            if p and os.path.exists(p): return ("7z", p)
        return (None, None)
    for name in ("7z", "7zz", "7zip"):
        p = sh.which(name)
        if p: return ("7z", p)
    p = sh.which("unrar")
    if p: return ("winrar", p)
    return (None, None)


def _run_extraction_with_timeout(cmd, timeout=300):
    import subprocess
    try:
        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            popen_kwargs["startupinfo"] = startupinfo
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen(cmd, **popen_kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return (process.returncode == 0, stdout, stderr, None)
        except subprocess.TimeoutExpired:
            process.kill()
            return (False, None, None, "Timeout")
    except Exception as e:
        return (False, None, None, str(e))


def _extract_archive_with_backup(archive, target, atype, apath, game_name, pwd="online-fix.me"):
    backed_up = []
    try:
        temp_dir = tempfile.mkdtemp(prefix='sff_ext_final_')
        cmd = [apath, "x", f"-p{pwd}", "-y", archive, temp_dir + os.sep] if atype == "winrar" else [apath, "x", f"-p{pwd}", "-y", f"-o{temp_dir}", archive]
        success, stdout, stderr, err = _run_extraction_with_timeout(cmd)
        if not success:
            detail = err
            if not detail and stderr:
                try:
                    detail = stderr.decode(errors="replace").strip().splitlines()[-1] if stderr else ""
                except Exception:
                    detail = "extraction failed"
            print(f"{Fore.RED}\u2717 Extraction failed via {atype} ({apath}): {detail or 'unknown error'}{Style.RESET_ALL}")
            return False
        extracted = {}
        for root, _, files in os.walk(temp_dir):
            for f in files:
                ft = os.path.join(root, f); rel = os.path.relpath(ft, temp_dir)
                extracted[rel] = ft
        for rel in extracted:
            gp = os.path.join(target, rel)
            if os.path.isfile(gp):
                bk = gp + ".bak"
                try:
                    if os.path.exists(bk): os.remove(bk)
                    os.rename(gp, bk); backed_up.append((gp, bk))
                except Exception:
                    pass
        for rel, src in extracted.items():
            dest = os.path.join(target, rel); os.makedirs(os.path.dirname(dest), exist_ok=True); shutil.move(src, dest)
        print(f"{Fore.GREEN}\u2713 Fix applied successfully!{Style.RESET_ALL}"); return True
    except Exception as e:
        print(f"{Fore.RED}\u2717 Installation error: {e}. Recovering...{Style.RESET_ALL}")
        for o, b in backed_up:
            try:
                if os.path.exists(o): os.remove(o)
                os.rename(b, o)
            except Exception:
                pass
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _show_new_system_message():
    if get_setting(Settings.ONLINE_FIX_NEW_SYSTEM_SHOWN):
        return
    print()
    print(Fore.YELLOW + "=" * 60 + Style.RESET_ALL)
    print(Fore.YELLOW + " Online-Fix system changed" + Style.RESET_ALL)
    print(Fore.YELLOW + "=" * 60 + Style.RESET_ALL)
    print()
    print("The old automatic Online-Fix download system has been removed. This")
    print("does NOT mean LC Online-Fix was removed or broken.")
    print()
    print("You should always try LC Online-Fix first.")
    print()
    print("How to use this now:")
    print()
    print("1. Select or search for your game in SteaMidra.")
    print("2. Try LC Online-Fix on the game first.")
    print("3. If LC Online-Fix does not work for that game, SteaMidra can help")
    print("   search/open the correct Online-Fix page for you.")
    print("4. After the Online-Fix page opens, read and follow their official")
    print("   guide manually.")
    print("5. Make sure your game version and platform match what the Online-Fix")
    print("   guide says.")
    print()
    print("This change was made because I do not want SteaMidra to automatically")
    print("download Online-Fix files or cause extra problems for Online-Fix.")
    print("SteaMidra will only help you find/open the page, then you follow their")
    print("guide yourself.")
    print()
    print(f"Official Online-Fix website:")
    print(f"  {ONLINE_FIX_BASE_URL}")
    print()
    print(f"Online-Fix Discord:")
    print(f"  {ONLINE_FIX_DISCORD}")
    print()
    print(Fore.YELLOW + "This message is only shown once." + Style.RESET_ALL)
    print()
    set_setting(Settings.ONLINE_FIX_NEW_SYSTEM_SHOWN, True)


def _online_fix_game_url(url):
    if not url:
        return ""
    url = url.strip()
    if url.startswith("/url?"):
        from urllib.parse import parse_qs
        query = parse_qs(urlparse(url).query)
        url = (query.get("q") or [""])[0]
    url = unquote(url)
    if "online-fix.me/games/" not in url.lower():
        return ""
    url = url.split("&sa=")[0].split("&ved=")[0]
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.lower().endswith("online-fix.me") and parsed.path.startswith("/games/"):
        return f"{parsed.scheme or 'https'}://{parsed.netloc}{parsed.path}"
    return ""


def _extract_search_urls(html):
    urls = []
    for raw in re.findall(r'href=["\']([^"\']+)["\']', html or "", flags=re.IGNORECASE):
        url = _online_fix_game_url(raw)
        if url and url not in urls:
            urls.append(url)
    return urls


def _norm_title(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _score_result(game_name, text, href):
    from difflib import SequenceMatcher
    want = _norm_title(game_name)
    hay = _norm_title(f"{text} {unquote(href or '')}")
    if not want or not hay:
        return 0.0
    tokens = [t for t in want.split() if len(t) > 1]
    token_hits = sum(1 for t in tokens if t in hay)
    ratio = SequenceMatcher(None, want, hay).ratio()
    coverage = token_hits / max(1, len(tokens))
    compact_want = want.replace(" ", "")
    compact_hay = hay.replace(" ", "")
    compact_hit = 1.0 if compact_want and compact_want in compact_hay else 0.0
    return max(ratio, coverage, compact_hit)


def _discover_online_fix_page(game_name):
    query = f'{game_name} online fix me'
    urls = [
        f"https://www.google.com/search?q={quote('site:online-fix.me/games ' + query)}",
        f"https://www.bing.com/search?q={quote('site:online-fix.me/games ' + query)}",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    best_url = ""
    best_score = 0.0
    for url in urls:
        try:
            resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=12)
            if resp.status_code >= 400:
                continue
            for candidate in _extract_search_urls(resp.text):
                score = _score_result(game_name, candidate, candidate)
                if score > best_score:
                    best_score = score
                    best_url = candidate
        except Exception as exc:
            logger.debug("online-fix external search failed for %s: %s", url, exc)
    if best_url and best_score >= 0.6:
        return best_url
    return ""


def _search_online_fix_direct(game_name):
    """Search online-fix.me directly and return the best matching URL."""
    from difflib import SequenceMatcher
    search_url = f"{ONLINE_FIX_BASE_URL}/index.php?do=search&subaction=search&story={quote(game_name)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        ),
    }
    try:
        resp = httpx.get(search_url, headers=headers, follow_redirects=True, timeout=15)
        if resp.status_code >= 400:
            return ""
        # Look for game links in the response
        urls = _extract_search_urls(resp.text)
        best_url = ""
        best_score = 0.0
        for url in urls:
            score = _score_result(game_name, url, url)
            if score > best_score:
                best_score = score
                best_url = url
        if best_url and best_score >= 0.6:
            return best_url
    except Exception as exc:
        logger.debug("online-fix.me direct search failed: %s", exc)
    return ""


def _open_browser(url):
    """Open the given URL in the default browser."""
    import webbrowser
    print(Fore.CYAN + f"Opening: {url}" + Style.RESET_ALL)
    webbrowser.open(url)


def apply_multiplayer_fix(game_name, game_folder):
    """
    Search online-fix.me for a game and open the page in the browser.
    No automatic download — the user follows the Online-Fix guide manually.
    """
    _show_new_system_message()

    print()
    print(Fore.CYAN + "Multiplayer Fix (online-fix.me)" + Style.RESET_ALL)
    print(f"Game: {Fore.YELLOW}{game_name}{Style.RESET_ALL}")
    print()

    # Step 1: try direct search on online-fix.me
    print("Searching online-fix.me for the game...")
    url = _search_online_fix_direct(game_name)
    if url:
        print(Fore.GREEN + f"Found: {url}" + Style.RESET_ALL)
        _open_browser(url)
        return True

    # Step 2: fallback to search engine discovery
    print("Trying search engine fallback...")
    url = _discover_online_fix_page(game_name)
    if url:
        print(Fore.GREEN + f"Found: {url}" + Style.RESET_ALL)
        _open_browser(url)
        return True

    # Step 3: just open the main site
    print(Fore.YELLOW + "Could not find a specific page. Opening the main site..." + Style.RESET_ALL)
    print("Browse to the correct game page manually.")
    _open_browser(ONLINE_FIX_BASE_URL)
    print()
    print(Fore.CYAN + "Tips:" + Style.RESET_ALL)
    print(f"  1. Use the search on {ONLINE_FIX_BASE_URL} to find your game")
    print("  2. Read and follow their official guide manually")
    print(f"  3. Join their Discord for help: {ONLINE_FIX_DISCORD}")
    return True

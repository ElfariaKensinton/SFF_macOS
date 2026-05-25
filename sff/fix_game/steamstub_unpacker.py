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
SteamStub DRM unpacker.

Scans game directories for SteamStub-protected executables and
unpacks them using Steamless (existing in third_party/).

Tries Steamless against every .exe in the game directory; the tool
internally selects the matching unpacker variant for the wrapper
version (V10x86, V20x86, V21x86, V30x86, V30x64, V31x86, V31x64).
"""

import os
import sys
import shutil
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Steamless exe name — should be in third_party/
STEAMLESS_EXE = "Steamless.CLI.exe"

# files to skip when scanning for executables
SKIP_PATTERNS = [
    "unins", "setup", "install", "redist", "vcredist", "dxsetup",
    "dotnet", "directx", "vc_", "crashhandler", "crashreport",
    "update", "patch", "launcher", "UnityCrash",
]

# Directory names we never want to recurse into when scanning for
# executables to unpack. These are SteaMidra's own backup / staging
# folders — touching them produces noise like "File not Packed/Other
# Protector" warnings against backup copies of already-processed exes.
SKIP_DIR_NAMES = {
    ".steamidra_exe_backups",  # created by sff/steamauto.py
    ".steamlocked.bak",        # legacy Library-tab Steamless backup
    "saved_lua",
    "manifests",
}


class SteamStubUnpacker:
    """
    Unpacks SteamStub DRM from executables using Steamless.

    For each .exe found in the game directory:
    1. Backs up as {name}.steamstub.bak
    2. Runs Steamless against it
    3. If SteamStub was found and unpacked, replaces original
    4. If no SteamStub, restores backup
    """

    def __init__(self, steamless_path = None):
        self.steamless_path = steamless_path or self._find_steamless()

    @staticmethod
    def _find_steamless():
        """try to find Steamless in third_party/ dirs"""
        candidates = [
            Path(__file__).parent.parent.parent / "third_party" / STEAMLESS_EXE,
            Path(__file__).parent.parent.parent / "third_party" / "Steamless" / STEAMLESS_EXE,
        ]
        # APPDATA path is Windows-only
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                candidates.append(Path(appdata) / "SteaMidra" / "tools" / STEAMLESS_EXE)
        for p in candidates:
            if p.exists():
                return str(p)
        # also check third_party subfolders
        tp_dir = Path(__file__).parent.parent.parent / "third_party"
        if tp_dir.exists():
            for f in tp_dir.rglob(STEAMLESS_EXE):
                return str(f)
            # also try the regular Steamless.exe (non-CLI)
            for f in tp_dir.rglob("Steamless.exe"):
                return str(f)
        return None

    @staticmethod
    def _wine_available():
        """check if wine is available in PATH (Linux only)"""
        return shutil.which("wine") is not None

    def is_available(self):
        """check if Steamless is available.
        On Linux, also requires wine to run the .exe.
        """
        if self.steamless_path is None or not Path(self.steamless_path).exists():
            return False
        if sys.platform != "win32":
            return self._wine_available()
        return True

    def _should_skip(self, exe_path):
        """Skip installers, redistributables, and SteaMidra backup folders."""
        # Walk up the parent chain and bail if any segment is a known
        # backup/staging folder. Cheaper than rebuilding the rglob iterator.
        for part in exe_path.parts:
            if part in SKIP_DIR_NAMES:
                return True
        # Also skip our own *.steamstub.bak / *.unpacked.exe artefacts that
        # rglob sometimes returns alongside live exes during retries.
        name_lower = exe_path.name.lower()
        if name_lower.endswith(".steamstub.bak") or name_lower.endswith(".unpacked.exe"):
            return True
        return any(skip in name_lower for skip in SKIP_PATTERNS)

    def unpack_directory(self, directory, log_func=None, use_experimental=True):
        """
        Scan a directory recursively and unpack any SteamStub-protected .exe files.
        Returns the number of successfully unpacked files.
        """
        def log(msg):
            if log_func:
                log_func(msg)
            logger.info(msg)
        if not self.is_available():
            log("Steamless not found — cannot unpack SteamStub")
            return 0
        game_dir = Path(directory)
        if not game_dir.exists():
            log(f"Directory not found: {directory}")
            return 0
        # find all .exe files
        exe_files = [f for f in game_dir.rglob("*.exe") if not self._should_skip(f)]
        # 6.2.4: drop UE5 sub-bundle binaries that ship inside engine
        # subfolders (CrashReportClient, EpicWebHelper, EOSOverlay, etc).
        # They're never SteamStub-protected and the noise from
        # "All unpackers failed" buried the real game-exe failure in
        # the user log. Keep only exes one or two levels deep, plus the
        # game's main launch exe even when nested under Binaries/Win64.
        prioritized: list[Path] = []
        for f in exe_files:
            try:
                rel_parts = f.relative_to(game_dir).parts
            except ValueError:
                rel_parts = f.parts
            depth = len(rel_parts)
            # Skip UE5 / Unity nested redistributables / crash handlers
            # by directory name.
            engine_markers = (
                "Engine", "ThirdParty", "Redist", "Redistributable",
                "EOSOverlayRenderer", "EpicWebHelper", "CrashReportClient",
                "_CommonRedist", "Plugins",
            )
            if any(p in engine_markers for p in rel_parts[:-1]):
                continue
            # Drop tiny exes that are almost certainly stub launchers,
            # uninstallers, or activation prompts. SteamStub-protected
            # executables are typically >= 2 MB even on small games.
            try:
                if f.stat().st_size < 2 * 1024 * 1024 and depth > 2:
                    continue
            except OSError:
                continue
            prioritized.append(f)
        # Common UE5 layout: <GameRoot>/<GameName>/Binaries/Win64/<Game>-Win64-Shipping.exe
        # is the actual SteamStub-wrapped binary. Sort by size descending so
        # the main exe lands first; success on it short-circuits the rest.
        prioritized.sort(
            key=lambda p: p.stat().st_size if p.exists() else 0,
            reverse=True,
        )
        log(f"Found {len(exe_files)} executable(s); {len(prioritized)} eligible for SteamStub scan")
        unpacked_count = 0
        for exe_path in prioritized:
            result = self.unpack_file(str(exe_path), log_func, use_experimental=use_experimental)
            if result:
                unpacked_count += 1
        log(f"Unpacked {unpacked_count} SteamStub-protected file(s)")
        return unpacked_count

    def unpack_file(self, file_path, log_func=None, use_experimental=True):
        """
        Try to unpack a single executable.
        Returns True if SteamStub was detected and removed.
        """
        def log(msg):
            if log_func:
                log_func(msg)
            logger.info(msg)
        exe_path = Path(file_path)
        if not exe_path.exists():
            return False
        # create backup
        backup_path = exe_path.with_suffix(exe_path.suffix + ".steamstub.bak")
        try:
            # Steamless outputs to {name}.unpacked.exe by default
            unpacked_path = exe_path.with_name(exe_path.stem + ".unpacked.exe")
            # run Steamless (via wine on Linux)
            #
            # Flag set chosen to maximise success rate on modern UE5 / x64
            # titles. atom0s ships --realign and --recalcchecksum as part
            # of the v3.0.0.13+ kit and SteamAutoCrack invokes them too.
            # --exp turns on experimental variants for newer wrapper
            # revisions that haven't been promoted to the main code path.
            cmd = [self.steamless_path]
            if use_experimental:
                cmd.append("--exp")
            cmd.extend(["--realign", "--recalcchecksum", str(exe_path)])
            if sys.platform != "win32":
                cmd = ["wine"] + cmd
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(Path(self.steamless_path).parent),
            )
            # Surface Steamless output on failure so users can see which
            # variant tried and why. Without this every failed unpack
            # looked identical regardless of root cause.
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            # check if unpacked file was created
            if unpacked_path.exists():
                # SteamStub was found and unpacked
                log(f"✓ Unpacked SteamStub from {exe_path.name}")
                # backup original
                shutil.copy2(exe_path, backup_path)
                # replace with unpacked version
                shutil.move(str(unpacked_path), str(exe_path))
                return True
            # Steamless ran without producing output. Two cases:
            #   - "File has no SteamStub": expected, the exe isn't packed
            #   - "All unpackers failed to unpack file": real failure on a
            #     packed exe (header mismatch, unsupported variant, or a
            #     file the user actually wants to know about).
            failure_marker = "all unpackers failed"
            no_stub_markers = ("not packed", "no .bind section", "is not packed")
            looks_like_real_failure = (
                failure_marker in stdout.lower()
                or any(m in stdout.lower() for m in [
                    "failed to unpack", "decryption failed", "unsupported header"
                ])
            )
            looks_unprotected = any(m in stdout.lower() for m in no_stub_markers)
            if looks_like_real_failure and not looks_unprotected:
                log(f"× SteamStub unpack failed on {exe_path.name}")
                if stdout:
                    log(stdout[-1500:])
                if stderr:
                    log(stderr[-500:])
            else:
                logger.debug(
                    "No SteamStub detected in %s (rc=%s)",
                    exe_path.name, result.returncode,
                )
            return False
        except subprocess.TimeoutExpired:
            log(f"Steamless timed out on {exe_path.name}")
            return False
        except Exception as e:
            logger.warning("Failed to unpack %s: %s", exe_path.name, e)
            return False

    def restore_file(self, file_path):
        """restore an exe from its .steamstub.bak backup"""
        exe_path = Path(file_path)
        backup_path = exe_path.with_suffix(exe_path.suffix + ".steamstub.bak")
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, exe_path)
                backup_path.unlink()
                logger.info("Restored %s from backup", exe_path.name)
                return True
            except Exception as e:
                logger.error("Failed to restore %s: %s", exe_path.name, e)
        return False

    def restore_directory(self, directory, log_func=None):
        """Restore all .steamstub.bak files in a directory.

        Returns the count of files restored. Skips SteaMidra's own
        backup folders (`.steamidra_exe_backups/`, `.steamlocked.bak/`,
        `saved_lua/`, `manifests/`) so revert doesn't process stale
        backups that were never paired with a live exe.
        """
        def log(msg):
            if log_func:
                log_func(msg)
            logger.info(msg)
        game_dir = Path(directory)
        restored = 0
        for bak in game_dir.rglob("*.steamstub.bak"):
            if any(part in SKIP_DIR_NAMES for part in bak.parts):
                continue
            # Strip the .steamstub.bak suffix to recover the original .exe path.
            original_name = bak.name.replace(".steamstub.bak", "")
            original_path = bak.parent / original_name
            try:
                shutil.copy2(bak, original_path)
                bak.unlink()
                restored += 1
                log(f"Restored {original_name}")
            except Exception as e:
                log(f"Failed to restore {original_name}: {e}")
        log(f"Restored {restored} SteamStub backup(s)")
        return restored

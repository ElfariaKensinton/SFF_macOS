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

import shutil
import subprocess

from sff.structs import OSType
from sff.utils import root_folder


def _build_choices_text(choices) -> str:
    if isinstance(choices, list):
        return "\n".join(str(choice) for choice in choices)
    raw = choices.read_text(encoding="utf-8")
    return raw


def _resolve_fzf_binary(os_type):
    if os_type == OSType.LINUX:
        exe = shutil.which("fzf")
        if exe is None:
            print("You don't have fzf installed. Please install it and try this again.")
            return None
        return [str(exe)]
    if os_type == OSType.WINDOWS:
        bundled = root_folder() / "third_party/fzf/fzf.exe"
        if not bundled.is_file():
            print(f"fzf.exe not found at {bundled}.\nPlease re-extract the release zip to ensure third_party/fzf/ is present,\nor enter the App ID directly instead of using game search.")
            return None
        return [str(bundled)]
    return None


def run_fzf(choices, os_type):
    argv = _resolve_fzf_binary(os_type)
    if not argv:
        return None
    stdin_text = _build_choices_text(choices)
    try:
        result = subprocess.run(argv, input=stdin_text, capture_output=True, encoding="utf-8")
        return result.stdout.strip("\n")
    except (FileNotFoundError, OSError) as e:
        print(f"Failed to run fzf: {e}")
        return None

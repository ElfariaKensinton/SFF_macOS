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

import sys
import winreg
from pathlib import Path

from colorama import Fore, Style

from sff.utils import root_folder


def _read_registry_value(hive, key_path, value_name):
    with winreg.OpenKey(hive, key_path) as key:
        return winreg.QueryValueEx(key, value_name)[0]


def _drop_hkcu_key(path) -> bool:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        return True
    except FileNotFoundError:
        return True
    except OSError as e:
        print(Fore.RED + f"Error deleting {path}: {e}" + Style.RESET_ALL)
        return False


def find_steam_path_from_registry():
    lookup = (
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    )
    for hive, kp, val in lookup:
        try:
            return Path(_read_registry_value(hive, kp, val))
        except FileNotFoundError:
            continue
    return None


def key_exists(hive, key_path):
    try:
        h = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
        winreg.CloseKey(h)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        print(f"An OS error occurred: {e}")
        return False


def read_subkey(hive, key_path, sub_key_name):
    try:
        return _read_registry_value(hive, key_path, sub_key_name)
    except FileNotFoundError:
        return


def set_stats_and_achievements(app_id):
    return False


def install_context_menu():
    frozen = getattr(sys, "frozen", False)
    interpreter = sys.executable

    if not frozen:
        root_dir = root_folder()
        icon_path = str((root_dir / "sff.ico").resolve())
        cmd = f'"{interpreter}" "{root_dir / "main.py"}" -f "%V"'
        how = "Venv"
    else:
        icon_path = interpreter
        cmd = f'"{interpreter}" -f "%V"'
        how = "Executable"

    shell_root = r"SOFTWARE\Classes\*\shell\SteaMidra"
    shell_cmd = shell_root + r"\command"
    hkcu = winreg.HKEY_CURRENT_USER

    try:
        with winreg.CreateKey(hkcu, shell_root) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Add to SteaMidra")
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_path)
        with winreg.CreateKey(hkcu, shell_cmd) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
        print(Fore.GREEN + f"Success! Context menu added via {how}.\nYou can now right click .lua/.zip files and click \"Add to SteaMidra\"" + Style.RESET_ALL)
    except Exception as e:
        print(f"Failed to update registry: {e}")


def uninstall_context_menu():
    keys_to_delete = [
        r"SOFTWARE\Classes\*\shell\SteaMidra\command",
        r"SOFTWARE\Classes\*\shell\SteaMidra",
        r"SOFTWARE\Classes\*\shell\SFF\command",
        r"SOFTWARE\Classes\*\shell\SFF",
    ]

    try:
        for subkey in keys_to_delete:
            if not _drop_hkcu_key(subkey):
                return
        print(Fore.GREEN + "Success! Context menu removed." + Style.RESET_ALL)

    except Exception as e:
        print(f"Error during uninstall: {e}")

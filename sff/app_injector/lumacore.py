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

"""LumaCore injection manager for Windows."""

import logging
from pathlib import Path
from typing import Union

from colorama import Fore, Style

from sff.app_injector.base import AppInjectionManager
from sff.steam_client import SteamInfoProvider
from sff.structs import LuaParsedInfo

logger = logging.getLogger(__name__)


class LumaCoreManager(AppInjectionManager):
    """Manages app ID injection via LumaCore's stplug-in Lua files on Windows."""

    def __init__(self, steam_path: Path, provider: SteamInfoProvider):
        self.steam_path = steam_path
        self.provider = provider

    @property
    def stplug_in(self) -> Path:
        return self.steam_path / "config" / "stplug-in"

    def get_local_ids(self) -> set:
        ids = set()
        folder = self.stplug_in
        if not folder.exists():
            return ids
        for f in folder.glob("*.lua"):
            try:
                ids.add(int(f.stem))
            except ValueError:
                pass
        return ids

    def add_ids(
        self, data: Union[int, list, LuaParsedInfo], skip_check: bool = False
    ):
        raise NotImplementedError("LumaCore add_ids is not yet implemented")

    def dlc_check(self, provider, base_id, auto_add_depot_dlcs: bool = False):
        from sff.steam_store import get_dlc_list_from_store, get_dlc_names_from_store
        from sff.structs import MainReturnCode

        print(Fore.CYAN + f"\nFetching DLC list for App ID {base_id}..." + Style.RESET_ALL)
        try:
            result = get_dlc_list_from_store(base_id)
        except Exception as e:
            print(Fore.RED + f"Failed to fetch DLC list: {e}" + Style.RESET_ALL)
            return MainReturnCode.LOOP_NO_PROMPT

        if not result:
            print(Fore.YELLOW + "Could not load DLC list from Steam Store." + Style.RESET_ALL)
            return MainReturnCode.LOOP_NO_PROMPT

        _base_name, dlc_ids = result
        if not dlc_ids:
            print(Fore.YELLOW + "No DLCs found for this game." + Style.RESET_ALL)
            return MainReturnCode.LOOP_NO_PROMPT

        # Pull all names in one batch instead of one-by-one inside the table loop.
        try:
            names = get_dlc_names_from_store(dlc_ids)
        except Exception:
            names = {}

        local_ids = self.get_local_ids()

        rows: list[tuple[str, str, str]] = []
        missing: list[int] = []
        for dlc_id in dlc_ids:
            owned = dlc_id in local_ids
            status = "Unlocked" if owned else "Missing"
            rows.append((status, str(dlc_id), names.get(dlc_id, f"DLC {dlc_id}")))
            if not owned:
                missing.append(dlc_id)

        width_status = max(len("Status"), max((len(r[0]) for r in rows), default=6))
        width_id = max(len("DLC ID"), max((len(r[1]) for r in rows), default=6))
        width_name = max(len("Name"), max((len(r[2]) for r in rows), default=4))

        print(f"\nDLC List - App {base_id}")
        print(f"{'Status':<{width_status}}  {'DLC ID':<{width_id}}  {'Name':<{width_name}}")
        print(f"{'-' * width_status}  {'-' * width_id}  {'-' * width_name}")
        for status, dlc_id, name in rows:
            print(f"{status:<{width_status}}  {dlc_id:<{width_id}}  {name:<{width_name}}")

        if missing:
            print(
                Fore.YELLOW
                + f"{len(missing)} DLC(s) not unlocked. "
                  "Re-download the game's Lua via Download Games to add them."
                + Style.RESET_ALL
            )
        else:
            print(Fore.GREEN + "All DLCs are unlocked." + Style.RESET_ALL)
        return MainReturnCode.LOOP_NO_PROMPT

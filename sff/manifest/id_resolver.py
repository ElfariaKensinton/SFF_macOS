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

from dataclasses import dataclass
from typing import Any, Protocol, Union

from colorama import Fore, Style

from sff.prompts import prompt_text
from sff.steam_client import SteamInfoProvider
from sff.utils import enter_path


def _dlc_ids_from_app_data(app_data: dict[str, Any]) -> list[int]:
    raw = app_data.get("extended", {}).get("listofdlc", "")
    if not raw:
        return []
    return [int(x) for x in raw.split(",") if x.strip()]


def _iter_dlc_payloads(ctx: "ManifestContext"):
    return ctx.dlc_data.values()


def _manifest_from_depot_record(depot_data):
    return enter_path(depot_data, "manifests", "public").get("gid")


@dataclass
class ManifestContext:
    app_id: int
    "The base app ID"
    app_data: dict[str, Any]
    "get_product_info data for app id"
    provider: SteamInfoProvider
    auto: bool = True
    "whether the user chose to automatically get IDs or not"
    _dlc_data = None
    "Lazy-loaded DLC data"

    @property
    def dlc_data(self):
        if self._dlc_data is None:
            dlc_ids = _dlc_ids_from_app_data(self.app_data)
            self._dlc_data = self.provider.get_app_info(dlc_ids) if dlc_ids else {}
        return self._dlc_data


class IManifestStrategy(Protocol):
    @property
    def name(self):
        ...

    def get_manifest_id(self, ctx, depot_id):
        ...


def _public_manifest_from(app_data: dict[str, Any], depot_id: Union[str, int]):
    return enter_path(app_data, "depots", str(depot_id), "manifests", "public").get(
        "gid"
    )


def _gui_prompting_disabled() -> bool:
    try:
        from sff.prompts import _gui_backend
    except Exception:
        return False
    return _gui_backend is not None


class StandardManifestStrategy(IManifestStrategy):

    @property
    def name(self):
        return "Steam appinfo"

    def get_manifest_id(
        self, ctx: ManifestContext, depot_id: Union[str, int]
    ):
        return _public_manifest_from(ctx.app_data, depot_id)


class SharedDepotManifestStrategy(IManifestStrategy):

    @property
    def name(self):
        return "Shared app depot"

    def get_manifest_id(
        self, ctx: ManifestContext, depot_id: Union[str, int]
    ):
        depot_data = enter_path(ctx.app_data, "depots", str(depot_id))
        target_app_id = depot_data.get("depotfromapp")
        if not target_app_id:
            return None
        target_data = ctx.provider.get_single_app_info(int(target_app_id))
        return _public_manifest_from(target_data, depot_id)


class InnerDepotManifestStrategy(IManifestStrategy):

    @property
    def name(self):
        return "DLC depot appinfo"

    def get_manifest_id(self, ctx, depot_id):
        depot_key = str(depot_id)
        for dlc_data in _iter_dlc_payloads(ctx):
            depot_data = dlc_data.get("depots", {}).get(depot_key)
            if depot_data is not None:
                return _manifest_from_depot_record(depot_data)
        return None


class ManualManifestStrategy(IManifestStrategy):
    @property
    def name(self):
        return "Typed manifest GID"

    def get_manifest_id(self, ctx, depot_id):
        if ctx.app_id == int(depot_id):
            print(
                Fore.YELLOW
                + "The base app ID had a decryption key, and manifest ID could not be"
                " found. Skipping..."
                + Style.RESET_ALL
            )
            return ""
        # GUI mode: don't loop the user through 100 separate "Depot N: "
        # prompts. Ivanchick reported clicking OK/Cancel on every depot and
        # the next one would just pop up. The auto strategies ABOVE this
        # already extracted what they could; whatever's left has no public
        # gid in the steam appinfo and asking the user to type a manifest
        # GID for it is fantasy. Skip silently and let the caller handle
        # the missing gid (manifest fetch will skip the depot too).
        if _gui_prompting_disabled():
            print(
                Fore.YELLOW
                + f"Depot {depot_id}: no manifest GID in steam appinfo, "
                "skipping (GUI mode does not prompt)."
                + Style.RESET_ALL
            )
            return ""
        if ctx.auto:
            print(
                "All auto methods failed. Type the manifest ID manually here, "
                "enter a blank to skip downloading it."
            )
        return prompt_text(f"Depot {depot_id}: ")


class ManifestIDResolver:
    def __init__(self, strategies):
        self.strategies = tuple(strategies)

    def resolve(self, ctx, depot_id):
        for strategy in self.strategies:
            manifest = strategy.get_manifest_id(ctx, depot_id)
            if manifest is not None:
                return manifest, strategy.name
        raise LookupError(f"Unable to resolve manifest for depot {depot_id}")

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

from pathlib import Path
from typing import Callable

from configupdater import ConfigUpdater


def _read_ini_document(path: Path) -> ConfigUpdater:
    document = ConfigUpdater()
    document.read(path)  # pyright: ignore[reportUnknownMemberType]
    return document


def _read_option(document: ConfigUpdater, section: str, option: str) -> str | None:
    try:
        return document[section][option].value
    except KeyError:
        return None


def _write_option(document: ConfigUpdater, section: str, option: str, value: str) -> None:
    document[section][option].value = value


def edit_ini_option(
    ini_file: Path, section: str, option: str, converter: Callable[[str], str]
):
    document = _read_ini_document(ini_file)
    current_value = _read_option(document, section, option)
    if current_value is None:
        return

    converted_value = converter(current_value)
    _write_option(document, section, option, converted_value)
    document.update_file()
    return converted_value

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

from io import BytesIO
import zipfile
from pathlib import Path

from colorama import Fore, Style
from typing import Literal, Union, overload


@overload
def read_lua_from_zip(path): ...


@overload
def read_lua_from_zip(
    path: Union[Path, BytesIO], decode: Literal[True]
): ...


@overload
def read_lua_from_zip(
    path: Union[Path, BytesIO], decode: Literal[False]
): ...


def read_lua_from_zip(
    path: Union[Path, BytesIO],
    decode = True,
    depotcache = None,
):
    # Read a lua file from a ZIP. Also extracts any .manifest files found in
    # the ZIP — directly into depotcache if provided, otherwise ./manifests/.
    # Having manifests in depotcache before Steam starts the download is the
    # key fix for the 'no internet connection' error during downloads.
    lua_contents = None

    def _handle_member(name, data):
        nonlocal lua_contents
        lower = name.lower()
        if lower.endswith(".lua"):
            print(f".lua found in archive: {name}")
            if lua_contents is None:
                lua_contents = data
        elif lower.endswith(".manifest"):
            filename = Path(name).name
            from sff.utils import manifests_staging_dir
            manifests_dir = manifests_staging_dir()
            (manifests_dir / filename).write_bytes(data)
            if depotcache is not None:
                depotcache.mkdir(parents=True, exist_ok=True)
                dest = depotcache / filename
                already = dest.exists()
                dest.write_bytes(data)
                print(
                    Fore.GREEN
                    + f"  Manifest {'refreshed in' if already else 'seeded to'} depotcache: {filename}"
                    + Style.RESET_ALL
                )
            else:
                print(f"Manifest found in archive: {filename}")

    try:
        suffix = Path(path).suffix.lower() if isinstance(path, Path) else ".zip"
        if suffix == ".7z":
            import py7zr
            with py7zr.SevenZipFile(path, mode="r") as archive:
                for name, bio in archive.readall().items():
                    _handle_member(name, bio.read())
        elif suffix == ".rar":
            import rarfile
            with rarfile.RarFile(str(path), "r") as archive:
                for name in archive.namelist():
                    if name.lower().endswith((".lua", ".manifest")):
                        _handle_member(name, archive.read(name))
        else:
            with zipfile.ZipFile(path) as f:
                for file in f.filelist:
                    if file.filename.lower().endswith((".lua", ".manifest")):
                        _handle_member(file.filename, f.read(file))
        if lua_contents is None:
            print(Fore.RED + "Could not find the lua in the archive" + Style.RESET_ALL)
    except Exception:
        return
    if decode and lua_contents:
        lua_contents = lua_contents.decode(encoding="utf-8")
    return lua_contents


def extract_manifests_from_zip_bytes(
    data = None,
    depotcache: Path = None,
    staging: Path = None,
):
    # Extract all .manifest files from ZIP bytes directly into depotcache.
    # This is the core function that ensures manifests land in the right place
    # before Steam starts a download, so they're already available locally.
    written = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            for info in zf.filelist:
                if not info.filename.endswith(".manifest"):
                    continue
                filename = Path(info.filename).name
                mf_data = zf.read(info)
                # Always write to depotcache — fresh data wins over stale
                depotcache.mkdir(parents=True, exist_ok=True)
                dest = depotcache / filename
                dest.write_bytes(mf_data)
                written.append(filename)
                # Also stage in ./manifests/ for backward compat
                if staging is not None:
                    staging.mkdir(exist_ok=True)
                    (staging / filename).write_bytes(mf_data)
    except zipfile.BadZipFile:
        pass
    return written


def read_file_from_zip_bytes(filename, bytes):
    try:
        with zipfile.ZipFile(BytesIO(bytes)) as f:
            return BytesIO(f.read(filename))
    except zipfile.BadZipFile:
        return


def read_nth_file_from_zip_bytes(nth, bytes):
    try:
        with zipfile.ZipFile(BytesIO(bytes)) as f:
            return BytesIO(f.read(f.filelist[nth].filename))
    except zipfile.BadZipFile:
        return


def zip_folder(folder_path, output_path):
    tmp = BytesIO()
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in folder_path.rglob('*'):
            if file.is_file():
                zipf.write(file, arcname=file.relative_to(folder_path))
    tmp.seek(0)
    with output_path.open("wb") as f:
        f.write(tmp.read())

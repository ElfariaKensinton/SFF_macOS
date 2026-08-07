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


import gc
from enum import Enum
from pathlib import Path


_gui_backend = None


def set_gui_backend(backend):
    global _gui_backend
    _gui_backend = backend


def convert_to_path(x):
    return Path(x.strip("\"' "))


def _try_gui_dispatch(method_name, *args, **kwargs):
    if not _gui_backend:
        return None, False
    impl = getattr(_gui_backend, method_name)
    return impl(*args, **kwargs), True


def _release_inquirer(prompt_obj):
    """Dark voodoo I cooked that actually works??? `prompt_select` leaks way less now"""
    from InquirerPy.base import BaseComplexPrompt, BaseListPrompt
    from InquirerPy.prompts.input import InputPrompt

    if isinstance(prompt_obj, BaseComplexPrompt):
        prompt_obj.application.reset()  # pyright: ignore[reportUnknownMemberType]
        prompt_obj.application = None  # type: ignore
    if isinstance(prompt_obj, BaseListPrompt):
        prompt_obj.content_control.reset()
        prompt_obj.content_control = None  # type: ignore
    del prompt_obj
    gc.collect()


def _normalize_choice(item, exclude):
    from InquirerPy.base.control import Choice

    if isinstance(item, Enum):
        if exclude and item in exclude:
            return None
        return Choice(value=item, name=item.value)
    if isinstance(item, Choice):
        return item
    if isinstance(item, tuple) and len(item) == 2:  # type: ignore
        return Choice(value=item[1], name=item[0])  # type: ignore
    return Choice(value=item, name=str(item))


def _build_choice_list(choices, *, cancellable=False, exclude=None):
    from InquirerPy.base.control import Choice

    result = []
    for c in choices:
        norm = _normalize_choice(c, exclude)
        if norm is not None:
            result.append(norm)
    if cancellable:
        result.append(Choice(value=None, name="[Back]"))
    return result


def prompt_select(
    msg: str,
    choices,
    default = None,
    fuzzy = False,
    cancellable = False,
    exclude = None,
    **kwargs,
):
    result, handled = _try_gui_dispatch(
        "prompt_select",
            msg, choices, default=default, fuzzy=fuzzy,
            cancellable=cancellable, exclude=exclude, **kwargs,
    )
    if handled:
        return result
    from InquirerPy import inquirer

    cmd = inquirer.fuzzy if fuzzy else inquirer.select  # type: ignore
    obj = cmd(
        message=msg,
        choices=_build_choice_list(choices, cancellable=cancellable, exclude=exclude),
        default=default,
        vi_mode=False if fuzzy else True,
        **kwargs,
    )
    result = obj.execute()
    _release_inquirer(obj)
    return result


def prompt_dir(
    msg: str,
    custom_check = None,
    custom_msg = None,
):
    result, handled = _try_gui_dispatch(
        "prompt_dir", msg, custom_check=custom_check, custom_msg=custom_msg
    )
    if handled:
        return result
    def validator(raw_input):
        path = convert_to_path(raw_input)
        if not (path.exists() and path.is_dir()):
            return False
        if custom_check and not custom_check(path):
            return False
        return True
    return prompt_text(
        msg,
        validator=validator,
        invalid_msg=custom_msg if custom_msg else "Doesn't exist or not a folder.",
        filter=convert_to_path,
    )


def prompt_file(msg, allow_blank = False, start_dir = None):
    if _gui_backend:
        # Forward start_dir if the backend supports it; older backends ignore the kwarg.
        try:
            return _gui_backend.prompt_file(msg, allow_blank=allow_blank, start_dir=start_dir)
        except TypeError:
            return _gui_backend.prompt_file(msg, allow_blank=allow_blank)
    is_file = lambda x: (
        convert_to_path(x).exists() and convert_to_path(x).is_file()
    ) or (True if allow_blank and x == "" else False)
    return prompt_text(
        msg,
        validator=is_file,
        invalid_msg="Doesn't exist or not a file.",
        filter=convert_to_path,
    )


def prompt_text(
    msg: str,
    validator = None,
    invalid_msg = "Invalid input",
    instruction = "",
    long_instruction = "",
    filter = None,
):
    result, handled = _try_gui_dispatch(
        "prompt_text",
            msg, validator=validator, invalid_msg=invalid_msg,
            instruction=instruction, long_instruction=long_instruction,
            filter=filter,
    )
    if handled:
        return result
    from InquirerPy import inquirer

    obj = inquirer.text(
        msg,
        validate=validator,
        invalid_message=invalid_msg,
        instruction=instruction,
        long_instruction=long_instruction,
        filter=filter,
    )
    res = obj.execute()
    _release_inquirer(obj)
    return res


def prompt_secret(
    msg: str,
    validator = None,
    invalid_msg = "Invalid input",
    instruction = "",
    long_instruction = "",
):
    result, handled = _try_gui_dispatch(
        "prompt_secret",
            msg, validator=validator, invalid_msg=invalid_msg,
            instruction=instruction, long_instruction=long_instruction,
    )
    if handled:
        return result
    from InquirerPy import inquirer

    obj = inquirer.secret(
        message=msg,
        transformer=lambda _: "[hidden]",
        validate=validator,
        invalid_message=invalid_msg,
        instruction=instruction,
        long_instruction=long_instruction,
    )
    res = obj.execute()
    _release_inquirer(obj)
    return res


def prompt_confirm(
    msg: str,
    true_msg = None,
    false_msg = None,
    default = True,
):
    result, handled = _try_gui_dispatch(
        "prompt_confirm",
        msg, true_msg=true_msg, false_msg=false_msg, default=default,
    )
    if handled:
        return result
    # inquirer.confirm exists but I prefer this
    return prompt_select(
        msg,
        [
            (true_msg if true_msg else "Yes", True),
            (false_msg if false_msg else "No", False),
        ],
        default=default
    )

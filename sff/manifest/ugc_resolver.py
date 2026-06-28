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

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Union

import gevent
from steam.client import SteamClient  # type: ignore
from steam.core.msg import MsgProto  # type: ignore
from steam.protobufs.steammessages_publishedfile_pb2 import (
    CPublishedFile_GetDetails_Response,
)

logger = logging.getLogger(__name__)

_WORKSHOP_DETAIL_FLAGS = {
    "includetags": False,
    "includeadditionalpreviews": False,
    "includechildren": False,
    "includekvtags": False,
    "includevotes": False,
    "short_description": True,
    "includeforsaledata": False,
    "includemetadata": False,
    "language": 0,
}


@dataclass
class WorkshopItemContext:
    client: SteamClient
    workshop_id: int
    "AKA PublishedFileId"
    timestamp: float = 0.0
    "When the request was initiated (epoch seconds)"


@dataclass
class HContentFile:
    ugc_id: int


@dataclass
class DirectDownloadUrl:
    url: str


WorkshopContent = Union[HContentFile, DirectDownloadUrl]


class IUgcIdStrategy(ABC):
    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def get_content(self, ctx):
        pass


class StandardUgcIdStrategy(IUgcIdStrategy):

    @property
    def name(self):
        return "SteamWorkshop_Default"

    def _build_request_payload(self, workshop_id):
        payload = {"publishedfileids": [workshop_id]}
        payload.update(_WORKSHOP_DETAIL_FLAGS)
        return payload

    def _parse_response(self, resp):
        if not isinstance(resp, MsgProto):
            return None
        body = resp.body  # pyright: ignore[reportUnknownMemberType]
        if not isinstance(body, CPublishedFile_GetDetails_Response):
            return None
        return body

    def _send_request(self, client, workshop_id):
        msg = self._build_request_payload(workshop_id)
        resp = client.send_um_and_wait("PublishedFile.GetDetails#1", msg, timeout=7)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
        body = self._parse_response(resp)
        return None if body is None else body.publishedfiledetails[0]

    _MAX_UGC_RETRIES = 3

    def _ensure_logged_on(self, client):
        if client.logged_on:
            return
        print("Logging in anonymously...", end="", flush=True)
        client.anonymous_login()
        print(" Done!")

    def _try_relogin(self, client):
        try:
            client.anonymous_login()
        except RuntimeError:
            pass

    def _handle_timeout(self, client, attempt):
        if attempt < self._MAX_UGC_RETRIES:
            print(f"Request timed out. Trying again ({attempt}/{self._MAX_UGC_RETRIES})...")
            self._try_relogin(client)
            time.sleep(2)
            return
        print(
            "Request timed out after several attempts. "
            "Check your internet connection and try again later."
        )

    def _get_workshop_items_details(self, ctx):
        self._ensure_logged_on(ctx.client)
        last_error = None
        for attempt in range(1, self._MAX_UGC_RETRIES + 1):
            try:
                return self._send_request(ctx.client, ctx.workshop_id)
            except gevent.Timeout as e:
                last_error = e
                self._handle_timeout(ctx.client, attempt)
                if attempt >= self._MAX_UGC_RETRIES:
                    raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected: no response and no error")

    def _content_from_details(self, details):
        if not details:
            return None
        if details.file_url:
            return DirectDownloadUrl(details.file_url)
        return HContentFile(details.hcontent_file)

    def get_content(self, ctx):
        details = self._get_workshop_items_details(ctx)
        return self._content_from_details(details)

    def get_content_and_details(
        self, ctx: WorkshopItemContext
    ):
        details = self._get_workshop_items_details(ctx)
        return self._content_from_details(details), details


class UgcIDResolver:
    def __init__(self, strategies):
        self.strategies = strategies

    def resolve(self, ctx):
        content, _method, _details = self.resolve_with_details(ctx)
        return content, _method

    def _try_strategy(self, strategy, ctx):
        if isinstance(strategy, StandardUgcIdStrategy):
            content, details = strategy.get_content_and_details(ctx)
            return content, details
        return strategy.get_content(ctx), None

    def resolve_with_details(
        self, ctx: WorkshopItemContext
    ):
        for strategy in self.strategies:
            content, details = self._try_strategy(strategy, ctx)
            if content is not None:
                return content, strategy.name, details
        raise Exception(f"Unable to resolve manifest for depot {ctx.workshop_id}")


def get_workshop_time_updated(ctx):
    strategy = StandardUgcIdStrategy()
    try:
        details = strategy._get_workshop_items_details(ctx)
        return getattr(details, "time_updated", None) if details else None
    except Exception:
        return None

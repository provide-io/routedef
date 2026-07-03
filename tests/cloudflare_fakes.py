# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TypeAlias

from routedef.adapters.cloudflare import CloudflareHeaders

ToPyArrayBufferBody: TypeAlias = bytes | bytearray


def request_headers(headers: CloudflareHeaders | None) -> CloudflareHeaders:
    return {} if headers is None else headers


class FakeCloudflareResponse:
    def __init__(self, body: bytes, *, status: int = 200, headers: Mapping[str, str] | None = None) -> None:
        self.body = body
        self.status = status
        self.headers = dict(headers or {})


class FakeIndexOnlyHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = {name.lower(): value for name, value in headers.items()}

    def __getitem__(self, name: str) -> str:
        return self._headers[name.lower()]


class FakeGetOnlyHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = {name.lower(): value for name, value in headers.items()}

    def get(self, name: str) -> str | None:
        return self._headers.get(name.lower())


class FakeItemsOnlyHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = dict(headers)

    def items(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._headers.items())


class FakeIterableHeaders:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = tuple(headers.items())

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._headers)


class FakeRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
        body: bytes = b"",
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)
        self.body = body
        self.array_buffer_reads = 0

    async def arrayBuffer(self) -> bytearray:
        self.array_buffer_reads += 1
        return bytearray(self.body)


class FakeToPyArrayBuffer:
    def __init__(self, body: ToPyArrayBufferBody) -> None:
        self._body = body

    def __bytes__(self) -> bytes:
        raise TypeError("direct bytes conversion is unavailable")

    def to_py(self) -> ToPyArrayBufferBody:
        return self._body


class FakeToPyArrayBufferRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
        body: ToPyArrayBufferBody = b"",
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)
        self.body = body

    async def arrayBuffer(self) -> FakeToPyArrayBuffer:
        return FakeToPyArrayBuffer(self.body)


class FakeTextRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
        body: str = "",
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)
        self.body = body
        self.text_reads = 0

    async def text(self) -> str:
        self.text_reads += 1
        return self.body


class FakeEmptyRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: CloudflareHeaders | None = None,
    ) -> None:
        self.url = url
        self.method = method
        self.headers = request_headers(headers)

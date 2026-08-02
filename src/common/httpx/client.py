#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : client.py.                                                                          #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Shared HTTPX client wrapper - TLS, proxy, timeouts, bounded async concurrency.      #
# Dependencies  : httpx.                                                                              #
# Modifications : 2026-08-02 Shane Reddy - initial.                                                   #
#                                                                                                     #
# Contact       : shanevreddy@gmail.com.                                                              #
#                                                                                                     #
# ----------------------------------------------------------------------------------------------------#
#
#


# ----------------------------------------------------------------------------------------------------#
# Imports.                                                                                            #
# ----------------------------------------------------------------------------------------------------#

import sys

sys.dont_write_bytecode = True

# External imports

import asyncio
import ssl
from typing import (
    Any,
    Self,
)

import httpx

# Internal imports

from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"

DEFAULT_CONCURRENCY_LIMIT: int = 20
DEFAULT_TIMEOUT_SECONDS: float = 30.0


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class HTTPXClient:

    """
    HTTPXClient class: shared HTTP client wrapper used for every outbound call. Centralizes TLS
    verification (CA bundle or explicit skip), proxy configuration, timeouts, and a semaphore
    that bounds concurrent async requests.
    """

    def __init__(
            self,
            ca_certificate_path: str | None = None,
            verify_ssl: bool = True,
            concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT,
            timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
            proxy_url: str | None = None,
    ) -> None:

        """
        Initializes the client wrapper and its shared configuration.

        :param ca_certificate_path: path to a CA bundle used to verify server certificates.
        :type ca_certificate_path: str | None
        :param verify_ssl: whether to verify server certificates at all.
        :type verify_ssl: bool
        :param concurrency_limit: maximum number of concurrent async requests.
        :type concurrency_limit: int
        :param timeout_seconds: per-request timeout in seconds.
        :type timeout_seconds: float
        :param proxy_url: optional proxy URL for outbound traffic.
        :type proxy_url: str | None
        :return: None.
        :rtype: None
        :raises ValueError: if concurrency_limit is not positive.
        """

        if concurrency_limit <= 0:
            raise ValueError("concurrency_limit must be positive")

        # endIf

        self._verify: ssl.SSLContext | bool = self._build_verify(ca_certificate_path, verify_ssl)
        self._timeout: float = timeout_seconds
        self._proxy_url: str | None = proxy_url
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(concurrency_limit)
        self._async_client: httpx.AsyncClient | None = None

    # endDef

    @staticmethod
    def _build_verify(
            ca_certificate_path: str | None,
            verify_ssl: bool,
    ) -> ssl.SSLContext | bool:

        """
        Builds the TLS verification setting for the underlying httpx clients.

        :param ca_certificate_path: path to a CA bundle, when one is provided.
        :type ca_certificate_path: str | None
        :param verify_ssl: whether to verify server certificates at all.
        :type verify_ssl: bool
        :return: an SSL context bound to the CA bundle, or a plain verify flag.
        :rtype: ssl.SSLContext | bool
        """

        if not verify_ssl:
            logger.warning("TLS verification is disabled for outbound HTTP calls")
            return False

        # endIf

        if ca_certificate_path:
            return ssl.create_default_context(cafile=ca_certificate_path)

        # endIf

        return True

    # endDef

    async def __aenter__(self) -> Self:

        """
        Opens the shared async client.

        :return: this wrapper, ready for async calls.
        :rtype: Self
        """

        self._async_client = httpx.AsyncClient(
            verify=self._verify,
            timeout=self._timeout,
            proxy=self._proxy_url,
        )
        return self

    # endAsyncDef

    async def __aexit__(self, *_exc: object) -> None:

        """
        Closes the shared async client.

        :param _exc: exception details from the context, unused.
        :type _exc: object
        :return: None.
        :rtype: None
        """

        await self.aclose()

    # endAsyncDef

    async def aclose(self) -> None:

        """
        Closes the shared async client if it is open.

        :return: None.
        :rtype: None
        """

        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

        # endIf

    # endAsyncDef

    async def call_async(
            self,
            method: str,
            url: str,
            headers: dict[str, str] | None = None,
            params: dict[str, str] | None = None,
            json_payload: Any | None = None,
            follow_redirects: bool = False,
    ) -> httpx.Response:

        """
        Executes one async HTTP request through the shared client, bounded by the semaphore.

        :param method: HTTP method, e.g. GET or POST.
        :type method: str
        :param url: absolute request URL.
        :type url: str
        :param headers: optional request headers.
        :type headers: dict[str, str] | None
        :param params: optional query parameters.
        :type params: dict[str, str] | None
        :param json_payload: optional JSON body.
        :type json_payload: Any | None
        :param follow_redirects: whether to follow HTTP redirects.
        :type follow_redirects: bool
        :return: the HTTP response.
        :rtype: httpx.Response
        :raises RuntimeError: if the wrapper is used outside its async context.
        """

        if self._async_client is None:
            raise RuntimeError("Use HTTPXClient as an async context manager before calling call_async")

        # endIf

        async with self._semaphore:
            return await self._async_client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_payload,
                follow_redirects=follow_redirects,
            )

        # endAsyncWith

    # endAsyncDef

    def call_sync(
            self,
            method: str,
            url: str,
            headers: dict[str, str] | None = None,
            params: dict[str, str] | None = None,
            json_payload: Any | None = None,
            follow_redirects: bool = False,
    ) -> httpx.Response:

        """
        Executes one synchronous HTTP request with the same TLS, proxy and timeout settings.
        Reserved for the rare paths where async is not practical; never call from async code.

        :param method: HTTP method, e.g. GET or POST.
        :type method: str
        :param url: absolute request URL.
        :type url: str
        :param headers: optional request headers.
        :type headers: dict[str, str] | None
        :param params: optional query parameters.
        :type params: dict[str, str] | None
        :param json_payload: optional JSON body.
        :type json_payload: Any | None
        :param follow_redirects: whether to follow HTTP redirects.
        :type follow_redirects: bool
        :return: the HTTP response.
        :rtype: httpx.Response
        """

        with httpx.Client(verify=self._verify, timeout=self._timeout, proxy=self._proxy_url) as client:
            return client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_payload,
                follow_redirects=follow_redirects,
            )

        # endWith

    # endDef

# endClass


# end_client.py

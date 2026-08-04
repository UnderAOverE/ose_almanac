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
# Explanation   : Shared HTTPX client wrapper - TLS, proxy, timeouts, fresh client per call.          #
# Dependencies  : httpx, src.common.constants, src.common.logger.                                     #
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
import threading
from typing import Any

import httpx

# Internal imports

from src.common.constants import (
    CONTENT_TYPE,
    HTTPX_CONCURRENCY_LIMIT,
)
from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class HTTPXClient:

    """
    HTTPXClient class: shared HTTP client wrapper used for every outbound call. It holds TLS,
    proxy and timeout configuration, opens a fresh httpx client per request, and reports every
    failure as a returned string instead of raising. It has no open/close lifecycle and is not
    a context manager - construct it once and call it. The dict-or-string return convention is
    the process boundary; callers classify string returns to decide retryability.
    """

    def __init__(
            self,
            ca_certificate_path: str | None = None,
            client_certificate_path: str | None = None,
            client_key_path: str | None = None,
            check_hostname: bool = False,
            connect_timeout: int = 5,
            proxy_url: str | None = None,
            timeout: int = 30,
            verify_ssl: bool = False,
            verify_mode: bool = False,
            concurrency_limit: int | None = None,
    ) -> None:

        """
        Initializes the wrapper with SSL context, proxy settings, timeouts and the request
        concurrency limit.

        :param ca_certificate_path: path to a CA bundle used to verify server certificates.
        :type ca_certificate_path: str | None
        :param client_certificate_path: path to a client certificate for mutual TLS.
        :type client_certificate_path: str | None
        :param client_key_path: path to the private key belonging to the client certificate.
        :type client_key_path: str | None
        :param check_hostname: whether the server hostname must match its certificate.
        :type check_hostname: bool
        :param connect_timeout: connection timeout in seconds.
        :type connect_timeout: int
        :param proxy_url: optional proxy URL for outbound traffic.
        :type proxy_url: str | None
        :param timeout: overall per-request timeout in seconds.
        :type timeout: int
        :param verify_ssl: whether to verify server certificates at all.
        :type verify_ssl: bool
        :param verify_mode: whether server certificates are required rather than optional.
        :type verify_mode: bool
        :param concurrency_limit: maximum concurrent requests; None takes the shared default.
        :type concurrency_limit: int | None
        :return: None.
        :rtype: None
        """

        self.concurrency_limit: int = (
            concurrency_limit if concurrency_limit is not None else HTTPX_CONCURRENCY_LIMIT
        )

        client_ssl_verify: ssl.SSLContext | None = self._create_ssl_context(
            verify_ssl=verify_ssl,
            ca_certificate_path=ca_certificate_path,
            client_certificate_path=client_certificate_path,
            client_key_path=client_key_path,
            check_hostname=check_hostname,
            verify_mode=verify_mode,
        )

        self.client_configurations: dict[str, Any] = {
            "proxy": proxy_url,
            "timeout": httpx.Timeout(timeout=timeout, connect=connect_timeout),
        }

        if client_ssl_verify is not None:
            self.client_configurations["verify"] = client_ssl_verify

        # endIf

    # endDef

    @staticmethod
    def _create_ssl_context(
            verify_ssl: bool,
            ca_certificate_path: str | None,
            client_certificate_path: str | None,
            client_key_path: str | None,
            check_hostname: bool = False,
            verify_mode: bool = False,
    ) -> ssl.SSLContext | None:

        """
        Builds the SSL context for the underlying httpx clients.

        :param verify_ssl: whether to verify server certificates at all.
        :type verify_ssl: bool
        :param ca_certificate_path: path to a CA bundle, when one is provided.
        :type ca_certificate_path: str | None
        :param client_certificate_path: path to a client certificate for mutual TLS.
        :type client_certificate_path: str | None
        :param client_key_path: path to the private key belonging to the client certificate.
        :type client_key_path: str | None
        :param check_hostname: whether the server hostname must match its certificate.
        :type check_hostname: bool
        :param verify_mode: whether server certificates are required rather than optional.
        :type verify_mode: bool
        :return: the configured SSL context, or None when building it failed.
        :rtype: ssl.SSLContext | None
        """

        try:
            ssl_context = ssl.create_default_context()

            if not verify_ssl:
                logger.warning("TLS verification is disabled for outbound HTTP calls")
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                return ssl_context

            # endIf

            ssl_context.check_hostname = check_hostname
            ssl_context.verify_mode = ssl.CERT_REQUIRED if verify_mode else ssl.CERT_OPTIONAL

            if ca_certificate_path:
                ssl_context.load_verify_locations(cafile=ca_certificate_path)

            # endIf

            if client_certificate_path and client_key_path:
                ssl_context.load_cert_chain(certfile=client_certificate_path, keyfile=client_key_path)

            # endIf

            return ssl_context

        except Exception as generic_exception:
            logger.error("Error creating SSL context: %r", generic_exception)
            return None

        # endTryExcept

    # endDef

    @staticmethod
    def _prepare_headers(
            headers: dict[str, str] | None,
            bearer_token: str | None,
    ) -> dict[str, str]:

        """
        Assembles the headers for one request, attaching the bearer token when one is
        supplied.

        :param headers: request headers, or None for an empty set.
        :type headers: dict[str, str] | None
        :param bearer_token: bearer token to send as the Authorization header.
        :type bearer_token: str | None
        :return: the finished request headers.
        :rtype: dict[str, str]
        """

        if headers is None:
            headers = {}

        # endIf

        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        # endIf

        return headers

    # endDef

    @staticmethod
    def _interpret_response(
            url: str,
            response: httpx.Response,
            expected_status: int,
            expected_content_type: str | None,
            response_headers: bool,
    ) -> dict[str, Any] | str:

        """
        Turns one HTTP response into the wrapper's return value: JSON bodies come back as a
        dict, non-JSON responses come back as headers or text, and a wrong status or content
        type comes back as a plain error string.

        :param url: the requested URL, echoed into error strings.
        :type url: str
        :param response: the HTTP response to interpret.
        :type response: httpx.Response
        :param expected_status: the only status code treated as success.
        :type expected_status: int
        :param expected_content_type: substring the Content-Type must contain; falsy skips the check.
        :type expected_content_type: str | None
        :param response_headers: whether non-JSON success returns headers instead of body text.
        :type response_headers: bool
        :return: the decoded JSON object, the response headers, the body text, or an error string.
        :rtype: dict[str, Any] | str
        """

        if response.status_code != expected_status:
            return f"Error: {url} returned status {response.status_code}, expected {expected_status}"

        # endIf

        content_type = response.headers.get("Content-Type", "")

        if expected_content_type and expected_content_type not in content_type:
            return f"Error: {url} returned content type '{content_type}', expected '{expected_content_type}'"

        # endIf

        if CONTENT_TYPE in content_type:
            json_body: dict[str, Any] = response.json()
            return json_body

        # endIf

        return dict(response.headers) if response_headers else response.text

    # endDef

    def call_sync(
            self,
            url: str,
            method: str = "GET",
            headers: dict[str, str] | None = None,
            bearer_token: str | None = None,
            params: dict[str, str] | None = None,
            data: Any | None = None,
            json_data: Any | None = None,
            expected_status: int = 200,
            expected_content_type: str | None = CONTENT_TYPE,
            response_headers: bool = False,
    ) -> dict[str, Any] | str:

        """
        Synchronously requests a URL with the shared TLS, proxy and timeout settings.
        Reserved for the rare paths where async is not practical; never call from async code.

        Request bodies are arbitrary JSON, hence the Any-typed body parameters.

        :param url: absolute request URL.
        :type url: str
        :param method: HTTP method, e.g. GET or POST.
        :type method: str
        :param headers: optional request headers.
        :type headers: dict[str, str] | None
        :param bearer_token: bearer token attached as the Authorization header.
        :type bearer_token: str | None
        :param params: optional query parameters.
        :type params: dict[str, str] | None
        :param data: optional form body.
        :type data: Any | None
        :param json_data: optional JSON body.
        :type json_data: Any | None
        :param expected_status: the only status code treated as success.
        :type expected_status: int
        :param expected_content_type: substring the Content-Type must contain; falsy skips the check.
        :type expected_content_type: str | None
        :param response_headers: whether non-JSON success returns headers instead of body text.
        :type response_headers: bool
        :return: the decoded JSON object, the response headers, the body text, or an error string.
        :rtype: dict[str, Any] | str
        """

        semaphore = threading.Semaphore(self.concurrency_limit)

        with semaphore:
            try:
                with httpx.Client(**self.client_configurations) as client:
                    response = client.request(
                        method=method,
                        url=url,
                        headers=self._prepare_headers(headers, bearer_token),
                        params=params,
                        data=data,
                        json=json_data,
                    )

                    return self._interpret_response(
                        url=url,
                        response=response,
                        expected_status=expected_status,
                        expected_content_type=expected_content_type,
                        response_headers=response_headers,
                    )

                # endWith

            except httpx.HTTPStatusError as http_status_error:
                return f"HTTP error for {http_status_error.request.url}: {http_status_error}"

            except httpx.RequestError as request_error:
                return f"An error occurred while requesting {request_error.request.url}: {request_error}"

            except Exception as generic_exception:
                return f"An unexpected error occurred: {generic_exception!r}"

            # endTryExcept

        # endWith

    # endDef

    async def call_async(
            self,
            url: str,
            method: str = "GET",
            headers: dict[str, str] | None = None,
            bearer_token: str | None = None,
            params: dict[str, str] | None = None,
            data: Any | None = None,
            json_data: Any | None = None,
            expected_status: int = 200,
            expected_content_type: str | None = CONTENT_TYPE,
            response_headers: bool = False,
    ) -> dict[str, Any] | str:

        """
        Asynchronously requests a URL with the shared TLS, proxy and timeout settings.

        Failures never raise: a wrong status, wrong content type or transport problem comes
        back as a plain string, so callers must classify string returns before trusting the
        result. Request bodies are arbitrary JSON, hence the Any-typed body parameters.

        :param url: absolute request URL.
        :type url: str
        :param method: HTTP method, e.g. GET or POST.
        :type method: str
        :param headers: optional request headers.
        :type headers: dict[str, str] | None
        :param bearer_token: bearer token attached as the Authorization header.
        :type bearer_token: str | None
        :param params: optional query parameters.
        :type params: dict[str, str] | None
        :param data: optional form body.
        :type data: Any | None
        :param json_data: optional JSON body.
        :type json_data: Any | None
        :param expected_status: the only status code treated as success.
        :type expected_status: int
        :param expected_content_type: substring the Content-Type must contain; falsy skips the check.
        :type expected_content_type: str | None
        :param response_headers: whether non-JSON success returns headers instead of body text.
        :type response_headers: bool
        :return: the decoded JSON object, the response headers, the body text, or an error string.
        :rtype: dict[str, Any] | str
        """

        semaphore = asyncio.Semaphore(self.concurrency_limit)

        async with semaphore:
            try:
                async with httpx.AsyncClient(**self.client_configurations) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self._prepare_headers(headers, bearer_token),
                        params=params,
                        data=data,
                        json=json_data,
                    )

                    return self._interpret_response(
                        url=url,
                        response=response,
                        expected_status=expected_status,
                        expected_content_type=expected_content_type,
                        response_headers=response_headers,
                    )

                # endAsyncWith

            except httpx.HTTPStatusError as http_status_error:
                return f"HTTP error for {http_status_error.request.url}: {http_status_error}"

            except httpx.RequestError as request_error:
                return f"An error occurred while requesting {request_error.request.url}: {request_error}"

            except Exception as generic_exception:
                return f"An unexpected error occurred: {generic_exception!r}"

            # endTryExcept

        # endAsyncWith

    # endAsyncDef

# endClass


# end_client.py

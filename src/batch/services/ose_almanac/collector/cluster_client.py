#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : cluster_client.py.                                                                  #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Read-only OpenShift API adapter - paginated namespace and ConfigMap listing.        #
# Dependencies  : httpx via HTTPXClient, tenacity, auth service, cluster_registry model.              #
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

from typing import Any

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Internal imports

from src.batch.config.basesettings.ose_almanac import OSEAlmanacSettings
from src.batch.models.ose_almanac.cluster_registry import ClusterRegistryModel
from src.batch.services.ose_almanac.collector.auth import OSEAuthService
from src.batch.services.ose_almanac.collector.http_errors import (
    is_retryable_status,
    is_transport_error,
    status_code_of,
)
from src.common.httpx.client import HTTPXClient
from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"

NAMESPACES_PATH: str = "/api/v1/namespaces"
CONFIGMAPS_PATH_TEMPLATE: str = "/api/v1/namespaces/{namespace}/configmaps"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class ApiError(Exception):

    """Non-retryable API failure (auth, forbidden, malformed request)."""

    def __init__(
            self,
            status_code: int,
            message: str,
    ) -> None:

        """
        Initializes the error with the HTTP status and detail.

        :param status_code: HTTP status code returned by the API server.
        :type status_code: int
        :param message: response detail, truncated by the caller.
        :type message: str
        :return: None.
        :rtype: None
        """

        self.status_code = status_code
        super().__init__(f"[{status_code}] {message}")

    # endDef

# endClass


class RetryableApiError(ApiError):

    """Throttling or server-side failure worth retrying with backoff."""

# endClass


class OpenShiftClusterClient:

    """
    OpenShiftClusterClient class: the only component that talks to live clusters, and it only
    ever reads. Every call is paginated (limit/continue) and wrapped in exponential-backoff
    retries with an explicit stop condition, because an estate-wide sweep must be a polite
    API citizen.
    """

    def __init__(
            self,
            http_client: HTTPXClient,
            auth_service: OSEAuthService,
            settings: OSEAlmanacSettings,
    ) -> None:

        """
        OpenShiftClusterClient constructor.

        :param http_client: shared HTTP client wrapper.
        :type http_client: HTTPXClient
        :param auth_service: cluster authentication service.
        :type auth_service: OSEAuthService
        :param settings: collector settings.
        :type settings: OSEAlmanacSettings
        :return: None.
        :rtype: None
        """

        self._http_client = http_client
        self._auth_service = auth_service
        self._settings = settings

    # endDef

    def _retrying(self) -> AsyncRetrying:

        """
        Builds the retry policy for one API call from settings.

        :return: the configured retry controller.
        :rtype: AsyncRetrying
        """

        return AsyncRetrying(
            stop=stop_after_attempt(self._settings.retry_attempts),
            wait=wait_exponential(
                min=self._settings.retry_wait_min_seconds,
                max=self._settings.retry_wait_max_seconds,
            ),
            retry=retry_if_exception_type(RetryableApiError),
            reraise=True,
        )

    # endDef

    async def _get(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            username: str,
            password: str,
            path: str,
            params: dict[str, str] | None = None,
    ) -> dict[str, Any]:

        """
        GETs one API path with auth, retry and backoff.

        :param registry: registry document for URL construction.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster to call.
        :type cluster_name: str
        :param username: FID username.
        :type username: str
        :param password: FID password.
        :type password: str
        :param path: API path beginning with '/'.
        :type path: str
        :param params: query parameters.
        :type params: dict[str, str] | None
        :return: the decoded JSON object.
        :rtype: dict[str, Any]
        :raises ApiError: on non-retryable failures after retries are exhausted.
        """

        api_url = registry.api_url(cluster_name)

        async for attempt in self._retrying():
            with attempt:
                token = await self._auth_service.get_token(cluster_name, api_url, username, password)

                result = await self._http_client.call_async(
                    url=f"{api_url}{path}",
                    headers={"Accept": "application/json"},
                    bearer_token=token,
                    params=params,
                )

                # The shared client reports failures as strings, never exceptions, so the
                # status has to be recovered from the text to pick the retry behavior.
                if isinstance(result, str):
                    status_code = status_code_of(result)

                    if status_code in (401, 403):
                        # Force a fresh login on the next call - the cached token may be stale.
                        self._auth_service.invalidate(cluster_name)
                        raise ApiError(status_code or 0, f"Not authorized for {path}")

                    # endIf

                    if is_transport_error(result) or is_retryable_status(status_code):
                        raise RetryableApiError(status_code or 0, result[:300])

                    # endIf

                    raise ApiError(status_code or 0, result[:300])

                # endIf

                return result

            # endWith

        # endAsyncFor

        raise ApiError(0, f"Retries exhausted for {path}")

    # endAsyncDef

    async def _list_paginated(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            username: str,
            password: str,
            path: str,
    ) -> list[dict[str, Any]]:

        """
        Lists a collection resource page by page until the continue token runs out. Result
        sets are never materialized unbounded on the server side - the limit parameter caps
        every page.

        :param registry: registry document for URL construction.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster to call.
        :type cluster_name: str
        :param username: FID username.
        :type username: str
        :param password: FID password.
        :type password: str
        :param path: list API path.
        :type path: str
        :return: all items across pages.
        :rtype: list[dict[str, Any]]
        """

        items: list[dict[str, Any]] = []
        continue_token: str | None = None

        while True:
            params = {"limit": str(self._settings.page_size)}

            if continue_token:
                params["continue"] = continue_token

            # endIf

            page = await self._get(registry, cluster_name, username, password, path, params)
            items.extend(page.get("items", []))
            continue_token = (page.get("metadata") or {}).get("continue")

            if not continue_token:
                return items

            # endIf

        # endWhile

    # endAsyncDef

    async def list_namespaces(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            username: str,
            password: str,
    ) -> list[str]:

        """
        Lists the namespaces in scope for the sweep - only those matching the registry's
        namespace prefixes.

        :param registry: registry document with the namespace scope.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster to enumerate.
        :type cluster_name: str
        :param username: FID username.
        :type username: str
        :param password: FID password.
        :type password: str
        :return: in-scope namespace names, sorted.
        :rtype: list[str]
        """

        items = await self._list_paginated(registry, cluster_name, username, password, NAMESPACES_PATH)
        prefixes = tuple(registry.namespace_prefixes)

        names = sorted(
            name
            for item in items
            if (name := (item.get("metadata") or {}).get("name", "")) and name.startswith(prefixes)
        )

        logger.info("namespaces_in_scope cluster=%s count=%d", cluster_name, len(names))
        return names

    # endAsyncDef

    async def list_configmaps(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            namespace: str,
            username: str,
            password: str,
    ) -> list[dict[str, Any]]:

        """
        Lists every ConfigMap in one namespace, paginated.

        :param registry: registry document for URL construction.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster to call.
        :type cluster_name: str
        :param namespace: namespace to list.
        :type namespace: str
        :param username: FID username.
        :type username: str
        :param password: FID password.
        :type password: str
        :return: raw ConfigMap objects as returned by the API.
        :rtype: list[dict[str, Any]]
        """

        path = CONFIGMAPS_PATH_TEMPLATE.format(namespace=namespace)
        return await self._list_paginated(registry, cluster_name, username, password, path)

    # endAsyncDef

# endClass


# end_cluster_client.py

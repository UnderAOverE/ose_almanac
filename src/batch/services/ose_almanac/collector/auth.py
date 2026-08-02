#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : auth.py.                                                                            #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Cluster authentication - OAuth challenge flow with per-cluster token caching.       #
# Dependencies  : httpx via HTTPXClient, CryptoTransformer, cluster_registry model.                   #
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

import base64
import os
import time
from dataclasses import dataclass
from urllib.parse import (
    parse_qs,
    urlparse,
)

# Internal imports

from src.batch.config.basesettings.ose_almanac import OSEAlmanacSettings
from src.batch.constants import MASTER_KEY_ENV_VAR
from src.batch.models.ose_almanac.cluster_registry import FIDDetails
from src.common.httpx.client import HTTPXClient
from src.common.logger import logger
from src.common.security.secure_data_transformer import CryptoTransformer

# Internal constants

module_version: str = "1.0.0v"

OAUTH_METADATA_PATH: str = "/.well-known/oauth-authorization-server"
OAUTH_CLIENT_ID: str = "openshift-challenging-client"
DEFAULT_TOKEN_LIFETIME_SECONDS: int = 86400


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class AuthenticationError(Exception):

    """Raised when the OAuth server rejects the credentials or returns no token."""

# endClass


@dataclass
class _CachedToken:

    """One bearer token with its refresh-early expiry."""

    value: str
    expires_at: float

    @property
    def valid(self) -> bool:

        """
        Tells whether the token is still usable.

        :return: True while the token has not reached its skewed expiry.
        :rtype: bool
        """

        return time.time() < self.expires_at

    # endDef

# endClass


class OSEAuthService:

    """
    OSEAuthService class: authenticates the FID against each cluster's OAuth server using the
    same challenge flow oc login uses under the hood, and caches the resulting bearer token per
    cluster for the duration of the run. Tokens last roughly 24 hours; they are refreshed early
    by the configured skew.
    """

    def __init__(
            self,
            http_client: HTTPXClient,
            settings: OSEAlmanacSettings,
    ) -> None:

        """
        OSEAuthService constructor.

        :param http_client: shared HTTP client wrapper.
        :type http_client: HTTPXClient
        :param settings: collector settings.
        :type settings: OSEAlmanacSettings
        :return: None.
        :rtype: None
        """

        self._http_client = http_client
        self._settings = settings
        self._tokens: dict[str, _CachedToken] = {}

    # endDef

    @staticmethod
    def resolve_credentials(
            fid_details: FIDDetails,
    ) -> tuple[str, str]:

        """
        Decrypts the FID password from the registry document. The master pre_data is read from
        the environment here, at the single point of use - the sanctioned exception to the
        no-os.environ rule - and the plaintext never persists anywhere.

        :param fid_details: FID name and encrypted secret from the cluster registry.
        :type fid_details: FIDDetails
        :return: (username, plaintext password).
        :rtype: tuple[str, str]
        :raises AuthenticationError: when the master pre_data is missing from the environment.
        """

        master_key = os.getenv(MASTER_KEY_ENV_VAR, "")

        if not master_key:
            raise AuthenticationError(f"{MASTER_KEY_ENV_VAR} is not set - cannot decrypt FID credentials")

        # endIf

        transformer = CryptoTransformer(master_key)
        password = transformer.decrypt(fid_details.geheimer_schlussel.get_secret_value())
        return fid_details.name, password

    # endDef

    async def get_token(
            self,
            cluster_name: str,
            api_url: str,
            username: str,
            password: str,
    ) -> str:

        """
        Returns a bearer token for one cluster, logging in only when the cached token is
        missing or about to expire.

        :param cluster_name: cluster the token is for (cache key).
        :type cluster_name: str
        :param api_url: API server base URL of the cluster.
        :type api_url: str
        :param username: FID username.
        :type username: str
        :param password: FID password, already decrypted.
        :type password: str
        :return: the bearer token.
        :rtype: str
        :raises AuthenticationError: when login fails.
        """

        cached = self._tokens.get(cluster_name)

        if cached and cached.valid:
            return cached.value

        # endIf

        token, expires_in = await self._login(api_url, username, password)

        self._tokens[cluster_name] = _CachedToken(
            value=token,
            expires_at=time.time() + max(expires_in - self._settings.token_skew_seconds, 60),
        )

        logger.info("openshift_login_ok cluster=%s user=%s", cluster_name, username)
        return token

    # endAsyncDef

    def invalidate(
            self,
            cluster_name: str,
    ) -> None:

        """
        Drops the cached token for one cluster so the next call re-authenticates.

        :param cluster_name: cluster whose token should be discarded.
        :type cluster_name: str
        :return: None.
        :rtype: None
        """

        self._tokens.pop(cluster_name, None)

    # endDef

    async def _authorization_endpoint(
            self,
            api_url: str,
    ) -> str:

        """
        Discovers the OAuth authorize endpoint from the API server metadata.

        :param api_url: API server base URL.
        :type api_url: str
        :return: the authorization endpoint URL.
        :rtype: str
        :raises AuthenticationError: when the metadata cannot be read.
        """

        response = await self._http_client.call_async("GET", f"{api_url}{OAUTH_METADATA_PATH}")

        if response.status_code != 200:
            raise AuthenticationError(
                f"Could not read OAuth metadata from {api_url} (HTTP {response.status_code})"
            )

        # endIf

        endpoint = response.json().get("authorization_endpoint")

        if not endpoint:
            raise AuthenticationError(f"No authorization_endpoint in OAuth metadata from {api_url}")

        # endIf

        return str(endpoint)

    # endAsyncDef

    async def _login(
            self,
            api_url: str,
            username: str,
            password: str,
    ) -> tuple[str, int]:

        """
        Runs the OAuth challenge flow: Basic auth against the authorize endpoint with the
        challenging client id, token read from the fragment of the 302 redirect.

        :param api_url: API server base URL.
        :type api_url: str
        :param username: FID username.
        :type username: str
        :param password: FID password.
        :type password: str
        :return: (access token, lifetime in seconds).
        :rtype: tuple[str, int]
        :raises AuthenticationError: when the credentials are rejected or no token is returned.
        """

        authorize_url = await self._authorization_endpoint(api_url)
        basic = base64.b64encode(f"{username}:{password}".encode()).decode()

        response = await self._http_client.call_async(
            "GET",
            authorize_url,
            params={"client_id": OAUTH_CLIENT_ID, "response_type": "token"},
            headers={"Authorization": f"Basic {basic}", "X-CSRF-Token": "1"},
            follow_redirects=False,
        )

        if response.status_code == 401:
            raise AuthenticationError(
                f"OAuth server rejected credentials for {username!r} (401). "
                "Check the FID, password, and that it is not locked or expired."
            )

        # endIf

        if response.status_code not in (302, 303):
            raise AuthenticationError(f"Unexpected login response (HTTP {response.status_code})")

        # endIf

        fragment = parse_qs(urlparse(response.headers.get("location", "")).fragment)
        token = (fragment.get("access_token") or [None])[0]

        if not token:
            error = (fragment.get("error_description") or fragment.get("error") or ["no token"])[0]
            raise AuthenticationError(f"Login failed: {error}")

        # endIf

        expires_in = int((fragment.get("expires_in") or [str(DEFAULT_TOKEN_LIFETIME_SECONDS)])[0])
        return token, expires_in

    # endAsyncDef

# endClass


# end_auth.py

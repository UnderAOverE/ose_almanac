#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : api_client.py.                                                                      #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Thin cached HTTP client for the read-only API - every page fetches through here.    #
# Dependencies  : streamlit, requests.                                                                #
# Modifications : 2026-08-05 Shane Reddy - initial.                                                   #
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

import os
from typing import Any

import requests
import streamlit as st

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

# The dashboards subtree is self-contained (no settings layer to import), so the API base
# URL comes straight from the environment with a local-development default.
API_BASE_URL: str = os.getenv("OSE_ALMANAC_DASHBOARDS_API_URL", "http://127.0.0.1:8000")

CACHE_TTL_SECONDS: int = 60
REQUEST_TIMEOUT_SECONDS: float = 10.0


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def api_get(
        path: str,
        params: tuple[tuple[str, str], ...] = (),
) -> tuple[int, Any]:

    """
    Executes one GET against the read-only API and caches the parsed result briefly, so a
    page rerun does not hammer the API. Params arrive as a tuple of pairs because cache
    keys must be hashable.

    :param path: API path beginning with '/'.
    :type path: str
    :param params: query parameters as (name, value) pairs.
    :type params: tuple[tuple[str, str], ...]
    :return: (status code, parsed JSON body); status 0 with the error text when unreachable.
    :rtype: tuple[int, Any]
    """

    try:
        response = requests.get(
            f"{API_BASE_URL}{path}",
            params=dict(params),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    except requests.RequestException as request_error:
        return 0, str(request_error)

    # endTryExcept

    try:
        body = response.json()

    except ValueError:
        body = response.text

    # endTryExcept

    return response.status_code, body

# endDef


def build_params(**values: Any) -> tuple[tuple[str, str], ...]:

    """
    Builds the hashable params tuple, dropping empty values so untouched filter widgets
    never reach the API.

    :param values: query parameter values by name.
    :type values: Any
    :return: (name, value) pairs for every non-empty value.
    :rtype: tuple[tuple[str, str], ...]
    """

    return tuple(
        (name, str(value))
        for name, value in values.items()
        if value not in (None, "", False)
    )

# endDef


# end_api_client.py

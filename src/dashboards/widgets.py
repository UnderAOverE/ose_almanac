#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : widgets.py.                                                                         #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Shared render helpers - page header, data-freshness banner, restart wording.        #
# Dependencies  : streamlit, src.dashboards.api_client.                                               #
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

from typing import Any

import streamlit as st

# Internal imports

from src.dashboards.api_client import (
    api_get,
    build_params,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

def render_page_header(
        title: str,
        caption: str,
) -> None:

    """
    Renders the standard page header.

    :param title: page title.
    :type title: str
    :param caption: one-line explanation under the title.
    :type caption: str
    :return: None.
    :rtype: None
    """

    st.title(title)
    st.caption(caption)
    st.divider()

# endDef


def render_freshness_banner(
        environment: str,
        sector: str,
) -> None:

    """
    Renders the data-freshness banner from the latest sweep - every page shows how old and
    how complete the data is before showing the data itself.

    :param environment: environment filter, may be empty.
    :type environment: str
    :param sector: sector filter, may be empty.
    :type sector: str
    :return: None.
    :rtype: None
    """

    status, sweep = api_get("/sweeps/latest", build_params(environment=environment, sector=sector))

    if status == 0:
        st.error(f"API unreachable at the configured base URL: {sweep}")
        return

    # endIf

    if status == 404:
        st.warning("No sweep has run for this scope yet - there is no data to show.")
        return

    # endIf

    if status != 200 or not isinstance(sweep, dict):
        st.error(f"Unexpected API response for /sweeps/latest (HTTP {status}).")
        return

    # endIf

    summary = (
        f"Data from sweep started {sweep.get('started_at', '?')} - outcome {sweep.get('outcome', '?')} - "
        f"{sweep.get('namespaces_swept', 0)} namespaces, {sweep.get('namespaces_failed', 0)} failed, "
        f"{sweep.get('namespaces_with_workload_gaps', 0)} with workload coverage gaps"
    )

    if sweep.get("outcome") == "success" and not sweep.get("namespaces_with_workload_gaps"):
        st.success(summary)

    elif sweep.get("outcome") == "failed":
        st.error(summary)

    else:
        st.warning(summary)

    # endIfElifElse

# endDef


def restart_wording(
        reference: dict[str, Any],
) -> str:

    """
    Turns one workload reference into the operational sentence support actually needs.

    :param reference: one reference object from the blast-radius endpoint.
    :type reference: dict[str, Any]
    :return: plain-language delivery behavior for a config change.
    :rtype: str
    """

    if reference.get("restart_required"):
        if reference.get("sub_path_used"):
            return "RESTART REQUIRED (subPath mount - file frozen until pod restart)"

        # endIf

        return "RESTART REQUIRED (env vars never refresh in a running pod)"

    # endIf

    if reference.get("container_name") is None:
        return "declared but not mounted by any container"

    # endIf

    return "live refresh (mounted file updates in the running pod)"

# endDef


# end_widgets.py

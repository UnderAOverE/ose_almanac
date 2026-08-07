#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : 01_Change_Feed.py.                                                                  #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Change Feed - what changed, where, when, by which tool. Page two of the story:      #
#                 the incident-bridge query is namespace + time window, answered at key level with    #
#                 the editing tool attributed. Everything arrives through the read-only API.          #
# Dependencies  : streamlit, src.dashboards.api_client, src.dashboards.widgets.                       #
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

from pathlib import Path

import streamlit as st

# Streamlit executes pages as standalone scripts, so the repo root is pinned onto sys.path
# before the src.-prefixed internal imports resolve.
_REPO_ROOT = str(Path(__file__).resolve().parents[3])

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# endIf

# Internal imports

from src.dashboards.api_client import (
    api_get,
    build_params,
)
from src.dashboards.widgets import (
    render_freshness_banner,
    render_page_header,
)

# Internal constants

module_version: str = "1.0.0v"

# Deployment tooling stores its release history in ConfigMaps with this name prefix; they
# churn on every deploy and drown out human edits, so the feed hides them by default.
TOOLING_NAME_PREFIX: str = "release-"


# ----------------------------------------------------------------------------------------------------#
# Page setup and filters.                                                                             #
# ----------------------------------------------------------------------------------------------------#

st.set_page_config(page_title="Change Feed - OpenShift ConfigMap Intelligence Platform", layout="wide")

render_page_header(
    "Change Feed",
    "Every recorded ConfigMap change, newest first. The incident question - what changed in "
    "this namespace during this window - is one filter row away.",
)

with st.sidebar:
    st.header("Scope")
    filter_environment = st.text_input("Environment", value="", placeholder="production")
    filter_sector = st.text_input("Sector", value="", placeholder="sector name")
    filter_cluster = st.text_input("Cluster", value="")
    filter_namespace = st.text_input("Namespace", value="")
    filter_configmap = st.text_input("ConfigMap name", value="")

    st.header("Event filters")
    filter_change_type = st.selectbox("Change type", ["any", "created", "modified"])
    filter_credential_only = st.checkbox("Credential changes only")
    filter_hide_tooling = st.checkbox(
        f"Hide deployment tooling ({TOOLING_NAME_PREFIX}*)",
        value=True,
        help=(
            "Deployment tooling rewrites its release-history ConfigMaps on every deploy. "
            "Those events stay recorded; this only hides them from the feed. The exact "
            "ConfigMap name filter above overrides this."
        ),
    )
    filter_since = st.date_input("Since", value=None)
    filter_until = st.date_input("Until", value=None)

# endWith

render_freshness_banner(filter_environment, filter_sector)


# ----------------------------------------------------------------------------------------------------#
# Feed.                                                                                               #
# ----------------------------------------------------------------------------------------------------#

page_number = st.number_input("Page", min_value=1, value=1, step=1)

status, payload = api_get(
    "/changes",
    build_params(
        environment=filter_environment,
        sector=filter_sector,
        cluster=filter_cluster,
        namespace=filter_namespace,
        configmap=filter_configmap,
        exclude_name_prefix=TOOLING_NAME_PREFIX if filter_hide_tooling else "",
        change_type=filter_change_type if filter_change_type != "any" else "",
        credential_only=filter_credential_only,
        since=f"{filter_since}T00:00:00Z" if filter_since else "",
        until=f"{filter_until}T23:59:59Z" if filter_until else "",
        page=int(page_number),
    ),
)

if status != 200 or not isinstance(payload, dict):
    st.error(f"Feed fetch failed (HTTP {status}). Is the API running and reachable?")
    st.stop()

# endIf

events = payload.get("items", [])
st.caption(
    f"{payload.get('total', 0)} events match - page {payload.get('page', 1)}. Deletion events "
    "do not exist yet by design: absence is only trustworthy after several proven sweeps."
)

if not events:
    st.info("No change events match the current filters.")
    st.stop()

# endIf

st.dataframe(
    [
        {
            "observed": event.get("observed_at"),
            "cluster": event.get("cluster_name"),
            "namespace": event.get("namespace"),
            "configmap": event.get("configmap_name"),
            "type": event.get("change_type"),
            "changed keys": ", ".join(event.get("changed_keys", [])),
            "added": len(event.get("added_keys", [])),
            "removed": len(event.get("removed_keys", [])),
            "credential": event.get("credential_change", False),
            "touched by": event.get("manager") or "unknown",
        }
        for event in events
    ],
    width="stretch",
    hide_index=True,
)


# ----------------------------------------------------------------------------------------------------#
# Event detail.                                                                                       #
# ----------------------------------------------------------------------------------------------------#

event_labels = [
    f"{event.get('observed_at')} - {event.get('namespace')}/{event.get('configmap_name')} ({event.get('change_type')})"
    for event in events
]
selected_label = st.selectbox("Open an event", event_labels)
event = events[event_labels.index(selected_label)]

left, right = st.columns(2)

with left:
    st.subheader("What changed")
    st.markdown(f"- Changed keys: {', '.join(event.get('changed_keys', [])) or 'none'}")
    st.markdown(f"- Added keys: {', '.join(event.get('added_keys', [])) or 'none'}")
    st.markdown(f"- Removed keys: {', '.join(event.get('removed_keys', [])) or 'none'}")

    if event.get("credential_change"):
        st.warning("A credential-bearing key changed in this event - a secret was rotated or added.")

    # endIf

# endWith

with right:
    st.subheader("Provenance")
    st.markdown(f"- Observed by sweep: {event.get('observed_at')}")
    st.markdown(f"- Last touched by: {event.get('manager') or 'unknown'} at {event.get('manager_operation_time') or '?'}")
    st.markdown(f"- Version transition: {str(event.get('previous_content_hash') or 'none')[:16]} to {str(event.get('new_content_hash', ''))[:16]}")
    st.caption(
        "A manager of kubectl or kubectl-client-side-apply means a human edited this by "
        "hand, outside any pipeline. Open the ConfigMap Explorer page with this name to see "
        "the full detail and blast radius."
    )

# endWith


# end_01_Change_Feed.py

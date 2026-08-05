#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : home.py.                                                                            #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : ConfigMap Explorer - search the estate, open a ConfigMap, walk its versions, see    #
#                 its blast radius. Page one of the two-page story; everything on it arrives through  #
#                 the read-only API, exactly as the React UI would fetch it.                          #
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
_REPO_ROOT = str(Path(__file__).resolve().parents[2])

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
    restart_wording,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Page setup and filters.                                                                             #
# ----------------------------------------------------------------------------------------------------#

st.set_page_config(page_title="OpenShift ConfigMap Intelligence Platform", layout="wide")

render_page_header(
    "ConfigMap Explorer",
    "Search the collected estate, open a ConfigMap, walk its versions, and see exactly "
    "which workloads a change would reach. All values shown were redacted before storage.",
)

with st.sidebar:
    st.header("Scope")
    filter_environment = st.text_input("Environment", value="", placeholder="production")
    filter_sector = st.text_input("Sector", value="", placeholder="sector name")
    filter_cluster = st.text_input("Cluster", value="")
    filter_namespace = st.text_input("Namespace", value="")

# endWith

render_freshness_banner(filter_environment, filter_sector)


# ----------------------------------------------------------------------------------------------------#
# Search.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

search_column, page_column = st.columns([4, 1])

with search_column:
    query_text = st.text_input("Search by ConfigMap name", value="", placeholder="ess-activator")

# endWith

with page_column:
    page_number = st.number_input("Page", min_value=1, value=1, step=1)

# endWith

status, payload = api_get(
    "/configmaps",
    build_params(
        environment=filter_environment,
        sector=filter_sector,
        cluster=filter_cluster,
        namespace=filter_namespace,
        q=query_text,
        page=int(page_number),
    ),
)

if status != 200 or not isinstance(payload, dict):
    st.error(f"Search failed (HTTP {status}). Is the API running and reachable?")
    st.stop()

# endIf

results = payload.get("items", [])
st.caption(f"{payload.get('total', 0)} ConfigMaps match - page {payload.get('page', 1)}")

if not results:
    st.info("No ConfigMaps match the current filters.")
    st.stop()

# endIf

st.dataframe(
    [
        {
            "cluster": row.get("cluster_name"),
            "namespace": row.get("namespace"),
            "name": row.get("name"),
            "keys": len(row.get("keys", [])),
            "redactions": row.get("redaction_count", 0),
            "last seen": row.get("last_seen"),
            "seen count": row.get("seen_count"),
        }
        for row in results
    ],
    width="stretch",
    hide_index=True,
)


# ----------------------------------------------------------------------------------------------------#
# Selection and detail tabs.                                                                          #
# ----------------------------------------------------------------------------------------------------#

identity_labels = [
    f"{row.get('cluster_name')} / {row.get('namespace')} / {row.get('name')}" for row in results
]
selected_label = st.selectbox("Open a ConfigMap", identity_labels)
selected = results[identity_labels.index(selected_label)]

cluster = selected.get("cluster_name", "")
namespace = selected.get("namespace", "")
name = selected.get("name", "")
base_path = f"/configmaps/{cluster}/{namespace}/{name}"

detail_tab, versions_tab, blast_tab = st.tabs(["Detail", "Versions", "Blast radius"])

with detail_tab:
    detail_status, detail = api_get(base_path)

    if detail_status != 200 or not isinstance(detail, dict):
        st.error(f"Detail fetch failed (HTTP {detail_status}).")

    else:
        left, middle, right = st.columns(3)
        left.metric("Keys", len(detail.get("key_hashes", {})))
        middle.metric("Redacted credentials", len(detail.get("redactions", [])))
        right.metric("Times seen unchanged", detail.get("seen_count", 1))

        st.caption(
            f"Content hash {detail.get('content_hash', '')[:16]}... - "
            f"first seen {detail.get('first_seen')} - created on cluster {detail.get('creation_timestamp')}"
        )

        for key, value in sorted(detail.get("data", {}).items()):
            with st.expander(f"data: {key}"):
                st.code(value)

            # endWith

        # endFor

        if detail.get("redactions"):
            st.subheader("Redaction receipts")
            st.caption(
                "Each receipt proves a credential existed and lets analytics tell whether it "
                "changed - the credential itself is unrecoverable by design."
            )
            st.dataframe(detail["redactions"], width="stretch", hide_index=True)

        # endIf

        if detail.get("annotations"):
            with st.expander("Annotations (redacted)"):
                st.json(detail["annotations"])

            # endWith

        # endIf

    # endIfElse

# endWith

with versions_tab:
    versions_status, versions = api_get(f"{base_path}/versions")

    if versions_status != 200 or not isinstance(versions, list):
        st.error(f"Versions fetch failed (HTTP {versions_status}).")

    else:
        st.caption(
            "One entry per distinct content, not per day - storage grows with change. "
            "Two entries differing in content hash differ in at least one key."
        )
        st.dataframe(
            [
                {
                    "current": version.get("is_current", False),
                    "content hash": str(version.get("content_hash", ""))[:16],
                    "keys": len(version.get("keys", [])),
                    "redactions": version.get("redaction_count", 0),
                    "first seen": version.get("first_seen"),
                    "last seen": version.get("last_seen"),
                    "seen count": version.get("seen_count"),
                }
                for version in versions
            ],
            width="stretch",
            hide_index=True,
        )

    # endIfElse

# endWith

with blast_tab:
    blast_status, blast = api_get(f"{base_path}/blast-radius")

    if blast_status == 404:
        st.info("No blast radius computed yet for this ConfigMap - run the analytics pipeline.")

    elif blast_status != 200 or not isinstance(blast, dict):
        st.error(f"Blast radius fetch failed (HTTP {blast_status}).")

    else:
        orphan_status = blast.get("orphan_status", "")

        if orphan_status == "referenced":
            st.success(f"Consumed by {len(blast.get('references', []))} reference(s) among collected workloads.")

        elif orphan_status == "no_pod_template_reference_found":
            st.warning(
                "No Deployment or StatefulSet pod-template reference found. This is NOT "
                "safe-to-delete: operators, CRDs and CLI flags consume ConfigMaps invisibly "
                "to this scan."
            )

        else:
            st.warning(
                "Indeterminate - workload listing was incomplete in this namespace, so "
                "absence of a reference proves nothing."
            )

        # endIfElifElse

        if not blast.get("coverage_complete", False):
            st.caption("Coverage note: at least one workload kind failed to list in this namespace.")

        # endIf

        references = blast.get("references", [])

        if references:
            st.dataframe(
                [
                    {
                        "workload": f"{ref.get('workload_kind')}/{ref.get('workload_name')}",
                        "container": ref.get("container_name") or "-",
                        "how": ref.get("reference_kind"),
                        "keys": ", ".join(ref.get("keys", [])) or "whole map",
                        "change delivery": restart_wording(ref),
                    }
                    for ref in references
                ],
                width="stretch",
                hide_index=True,
            )

        # endIf

    # endIfElifElse

# endWith


# end_home.py

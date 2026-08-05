#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : configmaps.py.                                                                      #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : /configmaps router - the support-story endpoints, in the order a person uses them:  #
#                                                                                                     #
#                   GET /configmaps                                        search + filters + paging  #
#                   GET /configmaps/{cluster}/{namespace}/{name}           full stored detail         #
#                   GET /configmaps/{cluster}/{namespace}/{name}/versions  version timeline           #
#                   GET /configmaps/{cluster}/{namespace}/{name}/blast-radius  who consumes it        #
#                                                                                                     #
#                 Every value served here was redacted before it was ever persisted.                  #
# Dependencies  : fastapi, pydantic, src.apis.dependencies, src.apis.services.configmaps_service.     #
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

from datetime import datetime
from typing import (
    Annotated,
    Any,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

# Internal imports

from src.apis.dependencies import get_configmaps_service
from src.apis.services.configmaps_service import ConfigMapsQueryService

# Internal constants

module_version: str = "1.0.0v"

VERSIONS_LIMIT: int = 50


# ----------------------------------------------------------------------------------------------------#
# Response models.                                                                                    #
# ----------------------------------------------------------------------------------------------------#

class RedactionView(BaseModel):

    """
    One credential that was irreversibly scrubbed before storage. The hash lets a caller
    tell that a credential existed and whether it changed between versions - never what
    it was.
    """

    model_config = ConfigDict(extra="ignore")

    key: str = Field(description="Data key, or annotation prefixed 'annotation:', the hit was found in.")
    rule: str = Field(description="Scanner rule that matched.")
    line_number: int = Field(description="1-based line number of the hit inside the value.")
    offset: int = Field(description="Character offset of the hit within its line.")
    original_sha256: str = Field(description="SHA-256 of the original secret - one-way, for change comparison only.")

# endClass


class ConfigMapSummary(BaseModel):

    """One search hit - enough to render a result row and link to the detail page."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "cluster_name": "cluster-a",
                "namespace": "team-namespace-1",
                "name": "app-config",
                "environment": "production",
                "sector": "sector-a",
                "content_hash": "7f85...",
                "keys": ["application.yaml"],
                "redaction_count": 3,
                "first_seen": "2026-08-04T18:21:30Z",
                "last_seen": "2026-08-05T02:04:11Z",
                "seen_count": 2,
            }
        },
    )

    cluster_name: str = Field(description="Cluster the ConfigMap lives on.")
    namespace: str = Field(description="Namespace the ConfigMap lives in.")
    name: str = Field(description="ConfigMap name.")
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")
    content_hash: str = Field(description="Fingerprint of the whole ConfigMap - changes when anything does.")
    keys: list[str] = Field(default_factory=list, description="Data and binary key names.")
    redaction_count: int = Field(default=0, description="How many credentials were scrubbed at collection time.")
    first_seen: datetime = Field(description="When this version was first observed (UTC).")
    last_seen: datetime = Field(description="When this version was last observed (UTC).")
    seen_count: int = Field(default=1, description="How many sweeps observed this version.")

# endClass


class ConfigMapSearchPage(BaseModel):

    """One page of search results with the total for pagination controls."""

    model_config = ConfigDict(extra="ignore")

    items: list[ConfigMapSummary] = Field(description="Results, sorted by cluster, namespace, name.")
    page: int = Field(description="1-based page number served.")
    page_size: int = Field(description="Effective page size after guard rails.")
    total: int = Field(description="Total ConfigMaps matching the filters.")

# endClass


class ConfigMapDetail(BaseModel):

    """
    The full stored record of one ConfigMap's current version. data values are exactly what
    the collector persisted: redacted, with markers where credentials used to be.
    """

    model_config = ConfigDict(extra="ignore")

    cluster_name: str = Field(description="Cluster the ConfigMap lives on.")
    namespace: str = Field(description="Namespace the ConfigMap lives in.")
    name: str = Field(description="ConfigMap name.")
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")
    content_hash: str = Field(description="Fingerprint of the whole ConfigMap.")
    data: dict[str, str] = Field(default_factory=dict, description="Redacted data values by key.")
    binary_data_keys: list[str] = Field(default_factory=list, description="binaryData key names (blobs not stored).")
    key_hashes: dict[str, str] = Field(default_factory=dict, description="Per-key fingerprints - which key changed.")
    redactions: list[RedactionView] = Field(default_factory=list, description="Scrub receipts.")
    labels: dict[str, str] = Field(default_factory=dict, description="metadata.labels.")
    annotations: dict[str, str] = Field(default_factory=dict, description="metadata.annotations, redacted.")
    resource_version: str | None = Field(default=None, description="Cluster's internal change counter.")
    creation_timestamp: datetime | None = Field(default=None, description="When the ConfigMap was created on cluster.")
    first_seen: datetime = Field(description="When this version was first observed (UTC).")
    last_seen: datetime = Field(description="When this version was last observed (UTC).")
    seen_count: int = Field(default=1, description="How many sweeps observed this version.")
    collector_version: str = Field(description="Collector build that wrote this document.")
    schema_version: int = Field(description="Document shape version.")

# endClass


class VersionView(BaseModel):

    """One entry in a ConfigMap's version timeline - current first, then superseded."""

    model_config = ConfigDict(extra="ignore")

    content_hash: str = Field(description="Fingerprint of this version.")
    is_current: bool = Field(description="True for the live version, False for superseded ones.")
    keys: list[str] = Field(default_factory=list, description="Key names in this version.")
    redaction_count: int = Field(default=0, description="Credentials scrubbed in this version.")
    first_seen: datetime = Field(description="First sweep that saw this version (UTC).")
    last_seen: datetime = Field(description="Last sweep that saw this version (UTC).")
    seen_count: int = Field(default=1, description="How many sweeps observed this version.")

# endClass


class WorkloadReferenceView(BaseModel):

    """
    One workload consuming the ConfigMap through one hookup point. restart_required is the
    field support cares about: env vars and subPath-mounted files never refresh in a running
    pod, so a config change only takes effect after a restart.
    """

    model_config = ConfigDict(extra="ignore")

    workload_kind: str = Field(description="Deployment or StatefulSet.")
    workload_name: str = Field(description="Consuming workload name.")
    container_name: str | None = Field(default=None, description="Container reached; null for an unmounted volume.")
    reference_kind: str = Field(description="volume, projected, env_from or env_key.")
    keys: list[str] = Field(default_factory=list, description="Specific keys consumed; empty means the whole map.")
    sub_path_used: bool = Field(default=False, description="True when mounted via subPath - frozen until restart.")
    optional_reference: bool = Field(default=False, description="True when the pod tolerates the map being absent.")
    restart_required: bool = Field(default=False, description="True when a change needs a pod restart to take effect.")

# endClass


class BlastRadiusView(BaseModel):

    """
    Who consumes this ConfigMap, per the latest analytics run. orphan_status is worded
    exactly as strongly as the evidence allows: no_pod_template_reference_found means no
    collected Deployment or StatefulSet references it - it never means safe to delete,
    because operators, CRDs and CLI flags consume ConfigMaps invisibly to this scan.
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "cluster_name": "cluster-a",
                "namespace": "team-namespace-1",
                "configmap_name": "app-config",
                "environment": "production",
                "sector": "sector-a",
                "references": [
                    {
                        "workload_kind": "Deployment",
                        "workload_name": "app",
                        "container_name": "app",
                        "reference_kind": "volume",
                        "keys": ["application.yaml"],
                        "sub_path_used": True,
                        "optional_reference": False,
                        "restart_required": True,
                    }
                ],
                "orphan_status": "referenced",
                "coverage_complete": True,
                "computed_at": "2026-08-05T03:00:00Z",
                "extractor_version": "1.0.0",
            }
        },
    )

    cluster_name: str = Field(description="Cluster the ConfigMap lives on.")
    namespace: str = Field(description="Namespace the ConfigMap lives in.")
    configmap_name: str = Field(description="ConfigMap name.")
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")
    references: list[WorkloadReferenceView] = Field(default_factory=list, description="Every consumer found.")
    orphan_status: str = Field(description="referenced, no_pod_template_reference_found or indeterminate.")
    coverage_complete: bool = Field(description="False when a workload kind failed to list in this namespace.")
    computed_at: datetime = Field(description="When analytics computed this document (UTC).")
    extractor_version: str = Field(description="Extractor build that wrote this document.")

# endClass


class ErrorBody(BaseModel):

    """Uniform error body for non-2xx responses, mirroring FastAPI's default shape."""

    detail: str = Field(description="Human-readable error message.")

# endClass


# ----------------------------------------------------------------------------------------------------#
# Projection helpers.                                                                                 #
# ----------------------------------------------------------------------------------------------------#

def _summarize(
        doc: dict[str, Any],
) -> dict[str, Any]:

    """
    Derives the summary-row fields a raw document does not carry directly.

    :param doc: one raw configmaps document.
    :type doc: dict[str, Any]
    :return: the document with keys and redaction_count added.
    :rtype: dict[str, Any]
    """

    doc["keys"] = sorted(doc.get("key_hashes") or {})
    doc["redaction_count"] = len(doc.get("redactions") or [])
    return doc

# endDef


# ----------------------------------------------------------------------------------------------------#
# Router.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

router = APIRouter(prefix="/configmaps", tags=["configmaps"])


@router.get(
    "",
    response_model=ConfigMapSearchPage,
    status_code=status.HTTP_200_OK,
    summary="Search ConfigMaps across the estate",
    response_description="One page of matching ConfigMaps, sorted by cluster, namespace, name.",
    description=(
        "Paged search over the current version of every collected ConfigMap. All filters AND "
        "together; q matches the ConfigMap name case-insensitively as a literal substring. "
        "This is the entry point of the UI story: search, open the detail, walk the versions, "
        "check the blast radius."
    ),
)
async def search_configmaps(
        environment: Annotated[str | None, Query(description="Exact environment filter (e.g. production).")] = None,
        sector: Annotated[str | None, Query(description="Exact sector filter.")] = None,
        cluster: Annotated[str | None, Query(description="Exact cluster name filter.")] = None,
        namespace: Annotated[str | None, Query(description="Exact namespace filter.")] = None,
        q: Annotated[str | None, Query(description="Case-insensitive substring of the ConfigMap name.")] = None,
        page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
        page_size: Annotated[int | None, Query(ge=1, description="Page size; capped by the server.")] = None,
        service: ConfigMapsQueryService = Depends(get_configmaps_service),
) -> ConfigMapSearchPage:

    """
    Runs the filtered, paged search and projects rows to summaries.

    :param environment: exact environment filter.
    :type environment: str | None
    :param sector: exact sector filter.
    :type sector: str | None
    :param cluster: exact cluster name filter.
    :type cluster: str | None
    :param namespace: exact namespace filter.
    :type namespace: str | None
    :param q: case-insensitive name substring.
    :type q: str | None
    :param page: 1-based page number.
    :type page: int
    :param page_size: requested page size.
    :type page_size: int | None
    :param service: the ConfigMaps query service.
    :type service: ConfigMapsQueryService
    :return: one page of summaries.
    :rtype: ConfigMapSearchPage
    """

    effective_page_size = service.clamp_page_size(page_size)

    docs, total = await service.search(
        environment=environment,
        sector=sector,
        cluster_name=cluster,
        namespace=namespace,
        name_contains=q,
        page=page,
        page_size=effective_page_size,
    )

    return ConfigMapSearchPage(
        items=[ConfigMapSummary.model_validate(_summarize(doc)) for doc in docs],
        page=page,
        page_size=effective_page_size,
        total=total,
    )

# endAsyncDef


@router.get(
    "/{cluster}/{namespace}/{name}",
    response_model=ConfigMapDetail,
    status_code=status.HTTP_200_OK,
    summary="Full stored detail of one ConfigMap",
    response_description="The current stored version, values redacted.",
    description=(
        "Returns everything the collector stored about the current version: redacted values, "
        "per-key fingerprints, scrub receipts, labels, annotations and observation window. "
        "Returns 404 when the ConfigMap was never collected."
    ),
    responses={
        404: {"model": ErrorBody, "description": "The ConfigMap was never collected."},
    },
)
async def get_configmap(
        cluster: str,
        namespace: str,
        name: str,
        service: ConfigMapsQueryService = Depends(get_configmaps_service),
) -> ConfigMapDetail:

    """
    Looks up one ConfigMap's current stored version.

    :param cluster: cluster the ConfigMap lives on.
    :type cluster: str
    :param namespace: namespace the ConfigMap lives in.
    :type namespace: str
    :param name: ConfigMap name.
    :type name: str
    :param service: the ConfigMaps query service.
    :type service: ConfigMapsQueryService
    :return: the full detail.
    :rtype: ConfigMapDetail
    :raises HTTPException: 404 when never collected.
    """

    doc = await service.detail(cluster, namespace, name)

    if doc is None:
        raise HTTPException(status_code=404, detail=f"ConfigMap {cluster}/{namespace}/{name} was never collected")

    # endIf

    return ConfigMapDetail.model_validate(doc)

# endAsyncDef


@router.get(
    "/{cluster}/{namespace}/{name}/versions",
    response_model=list[VersionView],
    status_code=status.HTTP_200_OK,
    summary="Version timeline of one ConfigMap",
    response_description="Current version first, then superseded versions newest-first.",
    description=(
        "The stored version history: one entry per distinct content, not per day - storage "
        "grows with change. Two timeline entries with different content_hash values diff at "
        "key level via their key fingerprints. Returns 404 when the ConfigMap was never "
        "collected."
    ),
    responses={
        404: {"model": ErrorBody, "description": "The ConfigMap was never collected."},
    },
)
async def get_versions(
        cluster: str,
        namespace: str,
        name: str,
        service: ConfigMapsQueryService = Depends(get_configmaps_service),
) -> list[VersionView]:

    """
    Returns the version timeline, newest first.

    :param cluster: cluster the ConfigMap lives on.
    :type cluster: str
    :param namespace: namespace the ConfigMap lives in.
    :type namespace: str
    :param name: ConfigMap name.
    :type name: str
    :param service: the ConfigMaps query service.
    :type service: ConfigMapsQueryService
    :return: the timeline.
    :rtype: list[VersionView]
    :raises HTTPException: 404 when never collected.
    """

    timeline = await service.versions(cluster, namespace, name, VERSIONS_LIMIT)

    if not timeline:
        raise HTTPException(status_code=404, detail=f"ConfigMap {cluster}/{namespace}/{name} was never collected")

    # endIf

    return [VersionView.model_validate(_summarize(doc)) for doc in timeline]

# endAsyncDef


@router.get(
    "/{cluster}/{namespace}/{name}/blast-radius",
    response_model=BlastRadiusView,
    status_code=status.HTTP_200_OK,
    summary="Who consumes this ConfigMap, and whether changes need a restart",
    response_description="The latest computed blast radius.",
    description=(
        "Every Deployment and StatefulSet consuming this ConfigMap, how each consumes it, and "
        "whether a change reaches the running container without a pod restart. Coverage is "
        "deployments and statefulsets by design; orphan wording never exceeds that evidence. "
        "Returns 404 when analytics has not yet computed this ConfigMap."
    ),
    responses={
        404: {"model": ErrorBody, "description": "Analytics has not computed this ConfigMap yet."},
    },
)
async def get_blast_radius(
        cluster: str,
        namespace: str,
        name: str,
        service: ConfigMapsQueryService = Depends(get_configmaps_service),
) -> BlastRadiusView:

    """
    Returns the computed blast radius for one ConfigMap.

    :param cluster: cluster the ConfigMap lives on.
    :type cluster: str
    :param namespace: namespace the ConfigMap lives in.
    :type namespace: str
    :param name: ConfigMap name.
    :type name: str
    :param service: the ConfigMaps query service.
    :type service: ConfigMapsQueryService
    :return: the blast radius.
    :rtype: BlastRadiusView
    :raises HTTPException: 404 when not yet computed.
    """

    doc = await service.blast_radius(cluster, namespace, name)

    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"No blast radius computed yet for {cluster}/{namespace}/{name} - run the analytics pipeline",
        )

    # endIf

    return BlastRadiusView.model_validate(doc)

# endAsyncDef


# end_configmaps.py

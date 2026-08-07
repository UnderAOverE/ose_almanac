#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : changes.py.                                                                         #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : /changes router - the incident-bridge feed, one endpoint:                           #
#                                                                                                     #
#                   GET /changes    paged change events, newest first, filterable by scope,           #
#                                   type, credential involvement and time window                      #
#                                                                                                     #
#                 The canonical incident query is namespace + since + until: everything that          #
#                 changed there, in that window, with the keys named and the editor attributed.       #
# Dependencies  : fastapi, pydantic, src.apis.dependencies, src.apis.services.changes_service.        #
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
from enum import StrEnum
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

# Internal imports

from src.apis.dependencies import get_changes_service
from src.apis.services.changes_service import ChangesQueryService

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Response models.                                                                                    #
# ----------------------------------------------------------------------------------------------------#

class ChangeTypeParam(StrEnum):

    """Change types the feed can filter on."""

    CREATED = "created"
    MODIFIED = "modified"

# endClass


class ChangeEventView(BaseModel):

    """
    One change event: a ConfigMap version transition at key granularity. changed/added/
    removed keys come from per-key hash comparison, so they exist even for values nobody
    has parsed. manager is the tool that last touched the object per the cluster's own
    bookkeeping - "kubectl" means a human edited it by hand.
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
                "change_type": "modified",
                "observed_at": "2026-08-05T02:04:11Z",
                "changed_keys": ["application.yaml"],
                "added_keys": [],
                "removed_keys": [],
                "credential_change": True,
                "manager": "kubectl-client-side-apply",
                "manager_operation_time": "2026-08-04T21:17:02Z",
                "previous_content_hash": "0f3a...",
                "new_content_hash": "7f85...",
            }
        },
    )

    cluster_name: str = Field(description="Cluster the ConfigMap lives on.")
    namespace: str = Field(description="Namespace the ConfigMap lives in.")
    configmap_name: str = Field(description="ConfigMap name.")
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")
    change_type: str = Field(description="created or modified.")
    observed_at: datetime = Field(description="When the sweep first saw the new version (UTC).")
    changed_keys: list[str] = Field(default_factory=list, description="Keys whose value changed.")
    added_keys: list[str] = Field(default_factory=list, description="Keys present only in the new version.")
    removed_keys: list[str] = Field(default_factory=list, description="Keys present only in the old version.")
    credential_change: bool = Field(
        default=False,
        description="True when a changed key carries a redaction marker - a credential rotated.",
    )
    manager: str | None = Field(default=None, description="Tool that last touched the object (managedFields).")
    manager_operation_time: datetime | None = Field(
        default=None,
        description="Timestamp of that manager's update, per the cluster.",
    )
    previous_content_hash: str | None = Field(default=None, description="Superseded version hash; null for created.")
    new_content_hash: str = Field(description="Hash of the version this event describes.")

# endClass


class ChangeFeedPage(BaseModel):

    """One page of the change feed, newest first, with the total for pagination controls."""

    model_config = ConfigDict(extra="ignore")

    items: list[ChangeEventView] = Field(description="Events on this page, observed_at descending.")
    page: int = Field(description="1-based page number served.")
    page_size: int = Field(description="Effective page size after guard rails.")
    total: int = Field(description="Total events matching the filters.")

# endClass


# ----------------------------------------------------------------------------------------------------#
# Router.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

router = APIRouter(prefix="/changes", tags=["changes"])


@router.get(
    "",
    response_model=ChangeFeedPage,
    status_code=status.HTTP_200_OK,
    summary="Change feed - what changed, where, when, by which tool",
    response_description="One page of change events, newest first.",
    description=(
        "Paged feed of ConfigMap change events derived from stored version pairs. All filters "
        "AND together. The incident-bridge query is namespace + since + until: everything that "
        "changed in that scope and window, with changed keys named and the editing tool "
        "attributed. Deletion events do not exist yet by design - absence of a ConfigMap is "
        "only trustworthy after several proven sweeps."
    ),
)
async def change_feed(
        environment: Annotated[str | None, Query(description="Exact environment filter (e.g. production).")] = None,
        sector: Annotated[str | None, Query(description="Exact sector filter.")] = None,
        cluster: Annotated[str | None, Query(description="Exact cluster name filter.")] = None,
        namespace: Annotated[str | None, Query(description="Exact namespace filter.")] = None,
        configmap: Annotated[str | None, Query(description="Exact ConfigMap name filter.")] = None,
        exclude_name_prefix: Annotated[
            str | None,
            Query(
                description=(
                    "Hide events whose ConfigMap name starts with this prefix - e.g. release- "
                    "to suppress deployment-tooling churn. Ignored when configmap is set. "
                    "Events stay stored in full; this narrows only the served view."
                ),
            ),
        ] = None,
        change_type: Annotated[ChangeTypeParam | None, Query(description="created or modified.")] = None,
        credential_only: Annotated[bool, Query(description="Only events where a credential-bearing key changed.")] = False,
        since: Annotated[datetime | None, Query(description="Earliest observed_at, inclusive (ISO 8601).")] = None,
        until: Annotated[datetime | None, Query(description="Latest observed_at, inclusive (ISO 8601).")] = None,
        page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
        page_size: Annotated[int | None, Query(ge=1, description="Page size; capped by the server.")] = None,
        service: ChangesQueryService = Depends(get_changes_service),
) -> ChangeFeedPage:

    """
    Runs the filtered, paged feed query and projects events to the view model.

    :param environment: exact environment filter.
    :type environment: str | None
    :param sector: exact sector filter.
    :type sector: str | None
    :param cluster: exact cluster name filter.
    :type cluster: str | None
    :param namespace: exact namespace filter.
    :type namespace: str | None
    :param configmap: exact ConfigMap name filter.
    :type configmap: str | None
    :param exclude_name_prefix: hide events whose ConfigMap name starts with this prefix.
    :type exclude_name_prefix: str | None
    :param change_type: created or modified.
    :type change_type: ChangeTypeParam | None
    :param credential_only: only credential-affecting events.
    :type credential_only: bool
    :param since: earliest observed_at, inclusive.
    :type since: datetime | None
    :param until: latest observed_at, inclusive.
    :type until: datetime | None
    :param page: 1-based page number.
    :type page: int
    :param page_size: requested page size.
    :type page_size: int | None
    :param service: the change-feed query service.
    :type service: ChangesQueryService
    :return: one page of events.
    :rtype: ChangeFeedPage
    """

    effective_page_size = service.clamp_page_size(page_size)

    docs, total = await service.feed(
        environment=environment,
        sector=sector,
        cluster_name=cluster,
        namespace=namespace,
        configmap_name=configmap,
        exclude_name_prefix=exclude_name_prefix,
        change_type=change_type.value if change_type else None,
        credential_only=credential_only,
        since=since,
        until=until,
        page=page,
        page_size=effective_page_size,
    )

    return ChangeFeedPage(
        items=[ChangeEventView.model_validate(doc) for doc in docs],
        page=page,
        page_size=effective_page_size,
        total=total,
    )

# endAsyncDef


# end_changes.py

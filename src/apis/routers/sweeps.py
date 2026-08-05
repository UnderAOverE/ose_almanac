#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : sweeps.py.                                                                          #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : /sweeps router - data freshness and completeness, one endpoint:                     #
#                                                                                                     #
#                   GET /sweeps/latest    latest run (?environment=, ?sector=)                        #
#                                                                                                     #
#                 Every UI banner starts here: how old is the data, and how complete was the run.     #
# Dependencies  : fastapi, pydantic, src.apis.dependencies, src.apis.services.sweeps_service.         #
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

from src.apis.dependencies import get_sweeps_service
from src.apis.services.sweeps_service import SweepsQueryService

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Response models.                                                                                    #
# ----------------------------------------------------------------------------------------------------#

class SweepView(BaseModel):

    """
    One collector run, summarized for a freshness banner: when it ran, whether it fully
    succeeded, and how much of the estate it proved anything about.
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "environment": "production",
                "sector": "sector-a",
                "started_at": "2026-08-05T02:00:04Z",
                "finished_at": "2026-08-05T02:19:41Z",
                "outcome": "success",
                "clusters_attempted": ["cluster-a", "cluster-b"],
                "configmaps_new": 12,
                "configmaps_changed": 3,
                "configmaps_unchanged": 4183,
                "workloads_collected": True,
                "namespaces_swept": 214,
                "namespaces_failed": 0,
                "namespaces_with_workload_gaps": 0,
                "errors": [],
            }
        },
    )

    environment: str = Field(description="Environment this run swept.")
    sector: str = Field(description="Sector this run swept.")
    started_at: datetime = Field(description="Run start (UTC).")
    finished_at: datetime | None = Field(default=None, description="Run end (UTC); null while running.")
    outcome: str = Field(description="success, partial or failed.")
    clusters_attempted: list[str] = Field(default_factory=list, description="Clusters targeted by the run.")
    configmaps_new: int = Field(default=0, description="New ConfigMap versions inserted.")
    configmaps_changed: int = Field(default=0, description="Versions superseded to historical.")
    configmaps_unchanged: int = Field(default=0, description="Versions seen unchanged.")
    workloads_collected: bool = Field(
        default=False,
        description="Whether this run collected workloads - blast radius is only trustworthy when true.",
    )
    namespaces_swept: int = Field(default=0, description="Namespaces the run attempted.")
    namespaces_failed: int = Field(default=0, description="Namespaces whose ConfigMap listing failed.")
    namespaces_with_workload_gaps: int = Field(
        default=0,
        description="Namespaces where at least one workload kind failed to list - orphan verdicts are suppressed there.",
    )
    errors: list[str] = Field(default_factory=list, description="Run-level errors.")

# endClass


class ErrorBody(BaseModel):

    """Uniform error body for non-2xx responses, mirroring FastAPI's default shape."""

    detail: str = Field(description="Human-readable error message.")

# endClass


# ----------------------------------------------------------------------------------------------------#
# Router.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

router = APIRouter(prefix="/sweeps", tags=["sweeps"])


@router.get(
    "/latest",
    response_model=SweepView,
    status_code=status.HTTP_200_OK,
    summary="Latest collector run - the data-freshness banner",
    response_description="The most recent sweep record, summarized.",
    description=(
        "Returns the most recent collector run, optionally narrowed to one environment and "
        "sector. UIs should render this as a banner before showing any other data: started_at "
        "answers how fresh the corpus is, and the failure counts answer how complete it is. "
        "Returns 404 when no sweep has ever run for the requested scope."
    ),
    responses={
        404: {"model": ErrorBody, "description": "No sweep record exists for the requested scope."},
    },
)
async def latest_sweep(
        environment: Annotated[str | None, Query(description="Exact environment filter (e.g. production).")] = None,
        sector: Annotated[str | None, Query(description="Exact sector filter.")] = None,
        service: SweepsQueryService = Depends(get_sweeps_service),
) -> SweepView:

    """
    Fetches the latest sweep record and folds its per-namespace results into counts.

    :param environment: exact environment filter.
    :type environment: str | None
    :param sector: exact sector filter.
    :type sector: str | None
    :param service: the sweeps query service.
    :type service: SweepsQueryService
    :return: the summarized sweep.
    :rtype: SweepView
    :raises HTTPException: 404 when no sweep record exists.
    """

    doc = await service.latest(environment, sector)

    if doc is None:
        raise HTTPException(status_code=404, detail="No sweep record exists for the requested scope")

    # endIf

    namespace_results: list[dict[str, Any]] = doc.get("namespace_results") or []
    doc["namespaces_swept"] = len(namespace_results)
    doc["namespaces_failed"] = sum(1 for result in namespace_results if not result.get("success"))
    doc["namespaces_with_workload_gaps"] = sum(
        1 for result in namespace_results if result.get("workload_kinds_failed")
    )

    return SweepView.model_validate(doc)

# endAsyncDef


# end_sweeps.py

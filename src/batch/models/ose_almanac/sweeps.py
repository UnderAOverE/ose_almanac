#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : sweeps.py.                                                                          #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Sweep outcome models - per-run record with per-namespace success and failure.       #
# Dependencies  : pydantic, src.batch.models.base, src.batch.constants.                               #
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

from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    Field,
)

# Internal imports

from src.batch.constants import (
    COLLECTOR_VERSION,
    SCHEMA_VERSION,
)
from src.batch.models.base import (
    PERSISTED_MODEL_CONFIG,
    PyObjectId,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Models.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

class SweepOutcome(StrEnum):

    """
    Overall outcome of one sweep run.
    """

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"

# endClass


class NamespaceSweepResult(BaseModel):

    """
    Outcome of sweeping one namespace on one cluster. Deletion may only ever be inferred for a
    namespace whose sweep succeeded - a failed namespace proves nothing about absence.
    """

    model_config = PERSISTED_MODEL_CONFIG

    cluster_name: str = Field(description="Cluster the namespace belongs to.")
    namespace: str = Field(description="Namespace that was swept.")
    success: bool = Field(description="Whether the namespace listing completed.")
    configmaps_seen: int = Field(default=0, ge=0, description="ConfigMaps observed.")
    error: str | None = Field(default=None, description="Failure detail when success is false.")

# endClass


class SweepModel(BaseModel):

    """
    SweepModel class: one document per collector run, carrying enough provenance to answer
    "how complete is the data from this day" without re-running anything.
    """

    model_config = PERSISTED_MODEL_CONFIG

    id_: PyObjectId | None = Field(default=None, alias="_id", description="MongoDB document id.")
    environment: str = Field(description="Environment this run swept.")
    sector: str = Field(description="Sector this run swept.")
    started_at: datetime = Field(description="Run start (UTC).")
    finished_at: datetime | None = Field(default=None, description="Run end (UTC).")
    outcome: SweepOutcome = Field(description="Overall run outcome.")
    clusters_attempted: list[str] = Field(default_factory=list, description="Clusters targeted.")
    namespace_results: list[NamespaceSweepResult] = Field(default_factory=list, description="Per-namespace outcomes.")
    configmaps_new: int = Field(default=0, ge=0, description="New ConfigMap versions inserted.")
    configmaps_changed: int = Field(default=0, ge=0, description="Versions superseded to historical.")
    configmaps_unchanged: int = Field(default=0, ge=0, description="Versions seen unchanged.")
    errors: list[str] = Field(default_factory=list, description="Run-level errors.")
    collector_version: str = Field(default=COLLECTOR_VERSION, description="Collector that ran.")
    schema_version: int = Field(default=SCHEMA_VERSION, description="Shape version of this document.")

# endClass


# end_sweeps.py

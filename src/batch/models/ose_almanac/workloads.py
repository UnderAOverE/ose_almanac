#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : workloads.py.                                                                       #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Workload record model - one stored deployment or statefulset pod-template subtree.  #
# Dependencies  : pydantic, src.batch.models.base, src.batch.constants.                               #
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
from typing import Any

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
from src.batch.models.ose_almanac.configmaps import RedactionRecord

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Models.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

class WorkloadKind(StrEnum):

    """
    Workload types the sweep collects. Deliberately scoped to the two kinds the FID holds
    list access for; blast-radius findings are always worded as covering exactly these kinds.
    """

    DEPLOYMENT = "Deployment"
    STATEFULSET = "StatefulSet"

# endClass


class WorkloadRecordModel(BaseModel):

    """
    WorkloadRecordModel class: one stored workload with the ConfigMap-relevant subtree of its
    pod template. Identity is cluster + namespace + kind + name; a matching content hash bumps
    last_seen, a differing hash replaces the record in place - workloads keep no historical
    twin because blast radius only ever asks what mounts a ConfigMap today.
    """

    model_config = PERSISTED_MODEL_CONFIG

    id_: PyObjectId | None = Field(default=None, alias="_id", description="MongoDB document id.")

    # Identity.
    cluster_name: str = Field(description="Cluster the workload was collected from.")
    namespace: str = Field(description="Namespace the workload lives in.")
    kind: WorkloadKind = Field(description="Workload type (Deployment or StatefulSet).")
    name: str = Field(description="Workload name.")
    content_hash: str = Field(description="SHA-256 over the stored pod-template subtree.")

    # Placement dimensions.
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")

    # The ConfigMap-relevant pod-template subtree, stored uninterpreted: volumes plus each
    # container's name, env, envFrom and volumeMounts. Literal env values are redacted like
    # ConfigMap data; everything else is verbatim so a reference-extraction fix never costs
    # a re-sweep.
    pod_template: dict[str, Any] = Field(default_factory=dict, description="Trimmed pod-template subtree.")
    redactions: list[RedactionRecord] = Field(default_factory=list, description="Redaction hits in env values.")

    # Cluster-side metadata.
    labels: dict[str, str] = Field(default_factory=dict, description="metadata.labels.")
    resource_version: str | None = Field(default=None, description="metadata.resourceVersion.")
    creation_timestamp: datetime | None = Field(default=None, description="metadata.creationTimestamp.")

    # Sweep provenance.
    first_seen: datetime = Field(description="When this version was first observed (UTC).")
    last_seen: datetime = Field(description="When this version was last observed (UTC).")
    seen_count: int = Field(default=1, ge=1, description="How many sweeps observed this version.")
    collector_version: str = Field(default=COLLECTOR_VERSION, description="Collector that wrote this.")
    schema_version: int = Field(default=SCHEMA_VERSION, description="Shape version of this document.")

# endClass


# end_workloads.py

#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : blast_radius.py.                                                                    #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Blast radius model - which workloads consume one ConfigMap, and how.                #
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

from pydantic import (
    BaseModel,
    Field,
)

# Internal imports

from src.batch.constants import (
    EXTRACTOR_VERSION,
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

class ReferenceKind(StrEnum):

    """
    The four declared ways a pod template can consume a ConfigMap. The kind decides whether a
    ConfigMap change reaches the running container without a restart: volume-mounted files
    refresh in place, while env vars and subPath mounts never refresh until the pod restarts.
    """

    VOLUME = "volume"
    PROJECTED = "projected"
    ENV_FROM = "env_from"
    ENV_KEY = "env_key"

# endClass


class OrphanStatus(StrEnum):

    """
    Whether anything is known to consume the ConfigMap. Absence of a reference is only ever
    reported as exactly that - a missing pod-template reference among the collected workload
    kinds - never as safe-to-delete: operators, CRDs, CLI flags and runtime API reads consume
    ConfigMaps invisibly to pod-template scanning.
    """

    REFERENCED = "referenced"
    NO_REFERENCE_FOUND = "no_pod_template_reference_found"
    INDETERMINATE = "indeterminate"

# endClass


class WorkloadReference(BaseModel):

    """
    One workload consuming one ConfigMap through one hookup point.
    """

    model_config = PERSISTED_MODEL_CONFIG

    workload_kind: str = Field(description="Consuming workload type (Deployment or StatefulSet).")
    workload_name: str = Field(description="Consuming workload name.")
    container_name: str | None = Field(
        default=None,
        description="Container the reference reaches; None for a declared volume no container mounts.",
    )
    reference_kind: ReferenceKind = Field(description="How the ConfigMap is consumed.")
    keys: list[str] = Field(
        default_factory=list,
        description="Specific keys consumed (volume items or the env key); empty means the whole map.",
    )
    sub_path_used: bool = Field(
        default=False,
        description="True when the mount uses subPath - the file never refreshes without a restart.",
    )
    optional_reference: bool = Field(
        default=False,
        description="True when the pod tolerates the ConfigMap being absent (optional: true).",
    )
    restart_required: bool = Field(
        default=False,
        description="True when a change needs a pod restart to take effect (env vars or subPath).",
    )

# endClass


class BlastRadiusModel(BaseModel):

    """
    BlastRadiusModel class: one document per stored ConfigMap, listing every workload that
    consumes it. Recomputed wholesale per environment + sector on every analytics run -
    derived data, safe to delete and rebuild.
    """

    model_config = PERSISTED_MODEL_CONFIG

    id_: PyObjectId | None = Field(default=None, alias="_id", description="MongoDB document id.")

    # Identity of the ConfigMap this document describes.
    cluster_name: str = Field(description="Cluster the ConfigMap lives on.")
    namespace: str = Field(description="Namespace the ConfigMap lives in.")
    configmap_name: str = Field(description="ConfigMap name.")

    # Placement dimensions.
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")

    references: list[WorkloadReference] = Field(
        default_factory=list,
        description="Every pod-template reference found among collected workloads.",
    )
    orphan_status: OrphanStatus = Field(description="Reference verdict, worded conservatively.")
    coverage_complete: bool = Field(
        description="Whether every collected workload kind listed successfully in this namespace.",
    )

    # Provenance.
    computed_at: datetime = Field(description="When this document was computed (UTC).")
    extractor_version: str = Field(default=EXTRACTOR_VERSION, description="Extractor that wrote this.")
    schema_version: int = Field(default=SCHEMA_VERSION, description="Shape version of this document.")

# endClass


# end_blast_radius.py

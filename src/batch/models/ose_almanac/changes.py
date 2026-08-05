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
# Explanation   : Change event model - one created or modified ConfigMap version, key-level.          #
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

class ChangeType(StrEnum):

    """
    What happened to the ConfigMap. Deletion events are deliberately absent: inferring
    deletion is where change tools lose credibility, and it only lands once several sweeps
    have proven the per-namespace success bookkeeping.
    """

    CREATED = "created"
    MODIFIED = "modified"

# endClass


class ChangeEventModel(BaseModel):

    """
    ChangeEventModel class: one change event per new ConfigMap version, at key granularity -
    which keys changed comes from comparing stored per-key hashes, so events exist without
    any value parsing. Identity is cluster + namespace + name + new_content_hash, which makes
    recomputes idempotent: re-running analytics upserts the same events, never duplicates.
    """

    model_config = PERSISTED_MODEL_CONFIG

    id_: PyObjectId | None = Field(default=None, alias="_id", description="MongoDB document id.")

    # Identity of the ConfigMap and the version transition.
    cluster_name: str = Field(description="Cluster the ConfigMap lives on.")
    namespace: str = Field(description="Namespace the ConfigMap lives in.")
    configmap_name: str = Field(description="ConfigMap name.")
    new_content_hash: str = Field(description="Content hash of the version this event describes.")
    previous_content_hash: str | None = Field(
        default=None,
        description="Content hash of the superseded version; None for created events.",
    )

    # Placement dimensions.
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")

    change_type: ChangeType = Field(description="created or modified.")
    observed_at: datetime = Field(description="When the sweep first saw this version (UTC).")

    # Key-level detail from per-key hash comparison.
    changed_keys: list[str] = Field(default_factory=list, description="Keys whose value changed.")
    added_keys: list[str] = Field(default_factory=list, description="Keys present only in the new version.")
    removed_keys: list[str] = Field(default_factory=list, description="Keys present only in the old version.")
    credential_change: bool = Field(
        default=False,
        description="True when a changed key carries a redaction marker in the new version - a credential rotated.",
    )

    # Attribution recovered from managedFields - the tool that last touched the object and
    # when. "kubectl" here means a human edited production by hand.
    manager: str | None = Field(default=None, description="Field manager of the most recent update.")
    manager_operation_time: datetime | None = Field(
        default=None,
        description="Timestamp of that manager's update, per the cluster.",
    )

    # Provenance.
    computed_at: datetime = Field(description="When this event was computed (UTC).")
    extractor_version: str = Field(default=EXTRACTOR_VERSION, description="Extractor that wrote this.")
    schema_version: int = Field(default=SCHEMA_VERSION, description="Shape version of this document.")

# endClass


# end_changes.py

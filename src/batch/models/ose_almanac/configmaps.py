#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : configmaps.py.                                                                      #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : ConfigMap record model - one stored, redacted version of one ConfigMap.             #
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

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Models.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

class RedactionRecord(BaseModel):

    """
    One credential hit that was irreversibly replaced at write time. The original hash lets
    analytics tell that a credential existed and whether it changed, without storing it.
    """

    model_config = PERSISTED_MODEL_CONFIG

    key: str = Field(description="ConfigMap data key the hit was found in.")
    rule: str = Field(description="Name of the scanner rule that matched.")
    line_number: int = Field(ge=1, description="1-based line number of the hit inside the value.")
    offset: int = Field(ge=0, description="Character offset of the hit within its line.")
    original_sha256: str = Field(description="SHA-256 of the original secret material.")

# endClass


class ConfigMapRecordModel(BaseModel):

    """
    ConfigMapRecordModel class: one stored version of one ConfigMap. Identity is cluster +
    namespace + name + content_hash; a matching hash bumps last_seen, a differing hash moves
    the current record to historical (historical is always written first) and inserts anew.
    """

    model_config = PERSISTED_MODEL_CONFIG

    id_: PyObjectId | None = Field(default=None, alias="_id", description="MongoDB document id.")

    # Identity.
    cluster_name: str = Field(description="Cluster the ConfigMap was collected from.")
    namespace: str = Field(description="Namespace the ConfigMap lives in.")
    name: str = Field(description="ConfigMap name.")
    content_hash: str = Field(description="SHA-256 over all key hashes - did anything change.")

    # Placement dimensions - environment is a field, never a collection, so cross-environment
    # comparison stays a $group instead of a join.
    environment: str = Field(description="Environment the cluster belongs to.")
    sector: str = Field(description="Sector the cluster belongs to.")

    # Contents. Values are stored redacted; redaction happened before persistence and cannot
    # be undone.
    data: dict[str, str] = Field(default_factory=dict, description="Redacted data values by key.")
    binary_data_keys: list[str] = Field(default_factory=list, description="binaryData key names.")
    key_hashes: dict[str, str] = Field(default_factory=dict, description="SHA-256 per key - which key changed.")
    redactions: list[RedactionRecord] = Field(default_factory=list, description="Redaction hits.")

    # Cluster-side metadata worth keeping. managedFields recovers part of the edit-and-revert
    # gap a daily sweep cannot see; it is stored verbatim, hence the loosely typed dicts.
    labels: dict[str, str] = Field(default_factory=dict, description="metadata.labels.")
    annotations: dict[str, str] = Field(default_factory=dict, description="metadata.annotations.")
    managed_fields: list[dict[str, Any]] = Field(default_factory=list, description="metadata.managedFields, verbatim.")
    resource_version: str | None = Field(default=None, description="metadata.resourceVersion.")
    creation_timestamp: datetime | None = Field(default=None, description="metadata.creationTimestamp.")

    # Sweep provenance.
    first_seen: datetime = Field(description="When this version was first observed (UTC).")
    last_seen: datetime = Field(description="When this version was last observed (UTC).")
    seen_count: int = Field(default=1, ge=1, description="How many sweeps observed this version.")
    collector_version: str = Field(default=COLLECTOR_VERSION, description="Collector that wrote this.")
    schema_version: int = Field(default=SCHEMA_VERSION, description="Shape version of this document.")

# endClass


# end_configmaps.py

#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : constants.py.                                                                       #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Batch-wide constants - database and collection names, version stamps.               #
# Dependencies  : stdlib enum.                                                                        #
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

from enum import StrEnum

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

# Stamped on every raw document the collector writes - says how good the DATA is.
COLLECTOR_VERSION: str = "1.0.0"

# Stamped on every derived document analytics writes - says how good the CONCLUSIONS are and
# enables targeted recompute when a parser improves.
EXTRACTOR_VERSION: str = "1.0.0"

# Bumped when a persisted document shape changes.
SCHEMA_VERSION: int = 1

# Environment variable carrying the CryptoTransformer master pre_data. Read only at the
# decryption call site, never from business code.
MASTER_KEY_ENV_VAR: str = "OSE_ALMANAC_MASTER_KEY"


# ----------------------------------------------------------------------------------------------------#
# Databases and collections.                                                                          #
# ----------------------------------------------------------------------------------------------------#

class DatabasesCollections(StrEnum):

    """
    Database and collection names owned by this project. Everything lives in the ose_almanac
    database; the OpenShift and CertificateManagement databases belong to other systems and are
    never touched from here.
    """

    OSE_ALMANAC_DATABASE = "ose_almanac"

    # Operator-managed sweep targets.
    OSE_ALMANAC_CLUSTER_REGISTRY_COLLECTION = "cluster_registry"

    # Collector output.
    OSE_ALMANAC_CONFIGMAPS_COLLECTION = "configmaps"
    OSE_ALMANAC_CONFIGMAPS_HISTORICAL_COLLECTION = "configmaps_historical"
    OSE_ALMANAC_WORKLOADS_COLLECTION = "workloads"
    OSE_ALMANAC_SWEEPS_COLLECTION = "sweeps"

    # Analytics output.
    OSE_ALMANAC_CM_BLAST_RADIUS_COLLECTION = "cm_blast_radius"
    OSE_ALMANAC_CM_ENDPOINTS_COLLECTION = "cm_endpoints"
    OSE_ALMANAC_CM_CERTIFICATES_COLLECTION = "cm_certificates"
    OSE_ALMANAC_CM_KEYSTORES_COLLECTION = "cm_keystores"
    OSE_ALMANAC_CM_RESILIENCE_COLLECTION = "cm_resilience"
    OSE_ALMANAC_CM_AUTHORIZATION_COLLECTION = "cm_authorization"
    OSE_ALMANAC_CM_MASKING_COLLECTION = "cm_masking"
    OSE_ALMANAC_CM_CHANGES_COLLECTION = "cm_changes"
    OSE_ALMANAC_CM_LINT_FINDINGS_COLLECTION = "cm_lint_findings"
    OSE_ALMANAC_SERVICE_GRAPH_COLLECTION = "service_graph"

# endClass


# end_constants.py

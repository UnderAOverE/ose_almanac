#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : cluster_registry.py.                                                                #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Cluster registry document model - sweep targets per sector and environment.         #
# Dependencies  : pydantic, src.batch.models.base.                                                    #
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

from pydantic import (
    BaseModel,
    Field,
    SecretStr,
)

# Internal imports

from src.batch.models.base import (
    PERSISTED_MODEL_CONFIG,
    PyObjectId,
)

# Internal constants

module_version: str = "1.0.0v"

DEFAULT_API_PORT: int = 6443


# ----------------------------------------------------------------------------------------------------#
# Models.                                                                                             #
# ----------------------------------------------------------------------------------------------------#

class RegistryDimensions(BaseModel):

    """
    The sector and environment a registry document applies to.
    """

    model_config = PERSISTED_MODEL_CONFIG

    sector: str = Field(description="Business sector the clusters belong to.")
    environment: str = Field(description="Environment the clusters belong to, e.g. development.")

# endClass


class FIDDetails(BaseModel):

    """
    Service account details used to authenticate against the clusters. The secret is stored
    encrypted (encrypted-data prefix) and is decrypted only at the point of use.
    """

    model_config = PERSISTED_MODEL_CONFIG

    name: str = Field(description="FID / service account username.")
    geheimer_schlussel: SecretStr = Field(description="Encrypted FID password.")

# endClass


class ClusterRegistryModel(BaseModel):

    """
    ClusterRegistryModel class: one operator-managed document per sector + environment, listing
    the clusters to sweep, the FID to authenticate with, and the namespace scope.
    """

    model_config = PERSISTED_MODEL_CONFIG

    id_: PyObjectId | None = Field(default=None, alias="_id", description="MongoDB document id.")
    comment: str | None = Field(default=None, alias="_comment", description="Operator note.")
    active: bool = Field(description="Whether this target group is swept.")
    dimensions: RegistryDimensions = Field(description="Sector and environment of the group.")
    clusters: list[str] = Field(description="Cluster names in this group.")
    fid_details: FIDDetails = Field(description="Auth material for the group.")
    namespace_prefixes: list[str] = Field(description="Namespace prefixes in scope for the sweep.")
    domain: str = Field(description="DNS domain used to build cluster API URLs.")
    api_port: int = Field(default=DEFAULT_API_PORT, ge=1, le=65535, description="API server port.")

    def api_url(
            self,
            cluster_name: str,
    ) -> str:

        """
        Builds the API server URL for one cluster in this group.

        :param cluster_name: the cluster name from the clusters list.
        :type cluster_name: str
        :return: the API server base URL.
        :rtype: str
        """

        return f"https://api.{cluster_name}.{self.domain}:{self.api_port}"

    # endDef

# endClass


# end_cluster_registry.py

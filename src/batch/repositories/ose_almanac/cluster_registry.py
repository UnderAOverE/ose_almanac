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
# Explanation   : Read repository for the cluster_registry collection.                                #
# Dependencies  : motor, src.common.db, src.batch.models.ose_almanac.cluster_registry.                #
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

from motor.motor_asyncio import AsyncIOMotorClient

# Internal imports

from src.batch.constants import DatabasesCollections
from src.batch.models.ose_almanac.cluster_registry import ClusterRegistryModel
from src.common.db.motor_repository import BaseReadMotorRepository

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Repository.                                                                                         #
# ----------------------------------------------------------------------------------------------------#

class ClusterRegistryMotorRepository(BaseReadMotorRepository[ClusterRegistryModel]):

    """
    ClusterRegistryMotorRepository class: read-only access to the operator-managed sweep
    targets. The collector never writes here.
    """

    _database_name = DatabasesCollections.OSE_ALMANAC_DATABASE.value
    _collection_name = DatabasesCollections.OSE_ALMANAC_CLUSTER_REGISTRY_COLLECTION.value

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
    ) -> None:

        """
        ClusterRegistryMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :return: None.
        :rtype: None
        """

        super().__init__(db_client=db_client, base_model=ClusterRegistryModel)

    # endDef

    async def find_active_by_environment_sector(
            self,
            environment: str,
            sector: str,
    ) -> ClusterRegistryModel | None:

        """
        Finds the active registry document for one environment + sector pair.

        :param environment: the environment to sweep, e.g. development.
        :type environment: str
        :param sector: the sector to sweep, e.g. pbwm_cgw.
        :type sector: str
        :return: the registry document, or None when no active group matches.
        :rtype: ClusterRegistryModel | None
        """

        doc = await self._execute_find_one(
            {
                "active": True,
                "dimensions.environment": environment,
                "dimensions.sector": sector,
            }
        )
        return self._read_map_to_model(doc) if doc else None

    # endAsyncDef

    async def find_all_active(self) -> list[ClusterRegistryModel]:

        """
        Finds every active registry document across all sectors and environments.

        :return: all active registry documents.
        :rtype: list[ClusterRegistryModel]
        """

        docs = await self._execute_find_many({"active": True})
        return [self._read_map_to_model(doc) for doc in docs]

    # endAsyncDef

# endClass


# end_cluster_registry.py

#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : configmaps_historical.py.                                                           #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Repository for the configmaps_historical collection - superseded versions.          #
# Dependencies  : motor, src.common.db, src.batch.models.ose_almanac.configmaps.                      #
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
from src.batch.models.ose_almanac.configmaps import ConfigMapRecordModel
from src.common.db.motor_repository import (
    BaseWriteMotorRepository,
    MongoDocument,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Repository.                                                                                         #
# ----------------------------------------------------------------------------------------------------#

class ConfigMapsHistoricalMotorRepository(BaseWriteMotorRepository[ConfigMapRecordModel]):

    """
    ConfigMapsHistoricalMotorRepository class: append-only store of superseded ConfigMap
    versions. Written FIRST when a version changes; duplicates here are harmless, gaps are not.
    """

    _database_name = DatabasesCollections.OSE_ALMANAC_DATABASE.value
    _collection_name = DatabasesCollections.OSE_ALMANAC_CONFIGMAPS_HISTORICAL_COLLECTION.value

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
    ) -> None:

        """
        ConfigMapsHistoricalMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :return: None.
        :rtype: None
        """

        super().__init__(db_client=db_client, base_model=ConfigMapRecordModel)

    # endDef

    async def find_latest_versions(
            self,
            environment: str,
            sector: str,
    ) -> list[ConfigMapRecordModel]:

        """
        Returns the most recently superseded version of every ConfigMap in one environment +
        sector - the predecessor each current version is diffed against. Runs as one
        aggregation instead of a lookup per ConfigMap, and projects the documents down to
        identity + hashes so an estate-wide run never materializes full historical values.

        :param environment: environment to read.
        :type environment: str
        :param sector: sector to read.
        :type sector: str
        :return: one trimmed record per ConfigMap identity with history.
        :rtype: list[ConfigMapRecordModel]
        """

        pipeline: list[MongoDocument] = [
            {"$match": {"environment": environment, "sector": sector}},
            {"$sort": {"last_seen": -1}},
            {
                "$group": {
                    "_id": {"cluster_name": "$cluster_name", "namespace": "$namespace", "name": "$name"},
                    "doc": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$doc"}},
            {
                "$project": {
                    "_id": 1,
                    "cluster_name": 1,
                    "namespace": 1,
                    "name": 1,
                    "content_hash": 1,
                    "environment": 1,
                    "sector": 1,
                    "key_hashes": 1,
                    "first_seen": 1,
                    "last_seen": 1,
                }
            },
        ]

        docs = await self._execute_pipeline(pipeline, allow_disk_use=True)
        return [self._write_map_to_model(doc) for doc in docs]

    # endAsyncDef

    async def create(
            self,
            entity: ConfigMapRecordModel,
    ) -> ConfigMapRecordModel:

        """
        Appends a superseded version. The document id is dropped so historical keeps every
        version under its own id.

        :param entity: the superseded record.
        :type entity: ConfigMapRecordModel
        :return: the appended record.
        :rtype: ConfigMapRecordModel
        """

        document = self._write_map_to_document(entity)
        document.pop("_id", None)
        await self._execute_insert_one(document)
        return entity

    # endAsyncDef

    async def create_many(
            self,
            entities: list[ConfigMapRecordModel],
    ) -> list[ConfigMapRecordModel]:

        """
        Appends multiple superseded versions.

        :param entities: the superseded records.
        :type entities: list[ConfigMapRecordModel]
        :return: the appended records.
        :rtype: list[ConfigMapRecordModel]
        """

        documents = []

        for entity in entities:
            document = self._write_map_to_document(entity)
            document.pop("_id", None)
            documents.append(document)

        # endFor

        await self._execute_insert_many(documents)
        return entities

    # endAsyncDef

    async def update_one(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> ConfigMapRecordModel | None:

        """
        Not supported - historical is append-only by design.

        :param filter_query: unused.
        :type filter_query: MongoDocument
        :param update_doc_payload: unused.
        :type update_doc_payload: MongoDocument
        :param upsert: unused.
        :type upsert: bool
        :return: never returns.
        :rtype: ConfigMapRecordModel | None
        :raises NotImplementedError: always - superseded versions are immutable.
        """

        raise NotImplementedError("configmaps_historical is append-only")

    # endAsyncDef

    async def update_many(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> int:

        """
        Not supported - historical is append-only by design.

        :param filter_query: unused.
        :type filter_query: MongoDocument
        :param update_doc_payload: unused.
        :type update_doc_payload: MongoDocument
        :param upsert: unused.
        :type upsert: bool
        :return: never returns.
        :rtype: int
        :raises NotImplementedError: always - superseded versions are immutable.
        """

        raise NotImplementedError("configmaps_historical is append-only")

    # endAsyncDef

# endClass


# end_configmaps_historical.py

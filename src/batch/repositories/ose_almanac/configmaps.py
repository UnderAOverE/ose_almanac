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
# Explanation   : Repository for the configmaps collection - current version of every ConfigMap.      #
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

from datetime import datetime

import bson
from motor.motor_asyncio import AsyncIOMotorClient

# Internal imports

from src.batch.constants import DatabasesCollections
from src.batch.models.ose_almanac.configmaps import (
    ConfigMapIdentityModel,
    ConfigMapRecordModel,
)
from src.common.db.motor_repository import (
    BaseWriteMotorRepository,
    MongoDocument,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Repository.                                                                                         #
# ----------------------------------------------------------------------------------------------------#

class ConfigMapsMotorRepository(BaseWriteMotorRepository[ConfigMapRecordModel]):

    """
    ConfigMapsMotorRepository class: the current version of every ConfigMap across the estate.
    Superseded versions move to configmaps_historical BEFORE this collection is touched - the
    service enforces that order; this class only provides the primitives.
    """

    _database_name = DatabasesCollections.OSE_ALMANAC_DATABASE.value
    _collection_name = DatabasesCollections.OSE_ALMANAC_CONFIGMAPS_COLLECTION.value

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
    ) -> None:

        """
        ConfigMapsMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :return: None.
        :rtype: None
        """

        super().__init__(db_client=db_client, base_model=ConfigMapRecordModel)

    # endDef

    @staticmethod
    def _identity_filter(
            cluster_name: str,
            namespace: str,
            name: str,
    ) -> MongoDocument:

        """
        Builds the identity filter for one ConfigMap's current record.

        :param cluster_name: cluster the ConfigMap was collected from.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param name: ConfigMap name.
        :type name: str
        :return: the filter document.
        :rtype: MongoDocument
        """

        return {"cluster_name": cluster_name, "namespace": namespace, "name": name}

    # endDef

    async def find_by_identity(
            self,
            cluster_name: str,
            namespace: str,
            name: str,
    ) -> ConfigMapRecordModel | None:

        """
        Finds the current record for one ConfigMap.

        :param cluster_name: cluster the ConfigMap was collected from.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param name: ConfigMap name.
        :type name: str
        :return: the current record, or None when the ConfigMap has never been stored.
        :rtype: ConfigMapRecordModel | None
        """

        # The write base offers no read helper; this stays inside the repository adapter layer.
        doc = await self._collection.find_one(self._identity_filter(cluster_name, namespace, name))
        return self._write_map_to_model(doc) if doc else None

    # endAsyncDef

    async def find_batch(
            self,
            environment: str,
            sector: str,
            after_id: str | None,
            limit: int,
    ) -> list[ConfigMapRecordModel]:

        """
        Reads one bounded page of current ConfigMaps for an environment + sector, ordered by
        document id so a caller can walk the whole scope without materializing it at once.

        :param environment: environment to read.
        :type environment: str
        :param sector: sector to read.
        :type sector: str
        :param after_id: last document id of the previous page, or None for the first page.
        :type after_id: str | None
        :param limit: page size.
        :type limit: int
        :return: up to limit records.
        :rtype: list[ConfigMapRecordModel]
        """

        filter_query: MongoDocument = {"environment": environment, "sector": sector}

        if after_id:
            filter_query["_id"] = {"$gt": bson.ObjectId(after_id)}

        # endIf

        # The write base offers no read helper; this stays inside the repository adapter layer.
        cursor = self._collection.find(filter_query).sort("_id", 1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self._write_map_to_model(doc) for doc in docs]

    # endAsyncDef

    async def find_identities_batch(
            self,
            environment: str,
            sector: str,
            after_id: str | None,
            limit: int,
    ) -> list[ConfigMapIdentityModel]:

        """
        Reads one bounded page of ConfigMap identities (id, cluster, namespace, name only) -
        the projection keeps blast-radius runs from materializing full documents just to know
        which ConfigMaps exist.

        :param environment: environment to read.
        :type environment: str
        :param sector: sector to read.
        :type sector: str
        :param after_id: last document id of the previous page, or None for the first page.
        :type after_id: str | None
        :param limit: page size.
        :type limit: int
        :return: up to limit identity projections.
        :rtype: list[ConfigMapIdentityModel]
        """

        filter_query: MongoDocument = {"environment": environment, "sector": sector}

        if after_id:
            filter_query["_id"] = {"$gt": bson.ObjectId(after_id)}

        # endIf

        projection = {"_id": 1, "cluster_name": 1, "namespace": 1, "name": 1}

        # The write base offers no read helper; this stays inside the repository adapter layer.
        cursor = self._collection.find(filter_query, projection).sort("_id", 1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [ConfigMapIdentityModel(**doc) for doc in docs]

    # endAsyncDef

    async def create(
            self,
            entity: ConfigMapRecordModel,
    ) -> ConfigMapRecordModel:

        """
        Inserts a new current record.

        :param entity: the record to insert.
        :type entity: ConfigMapRecordModel
        :return: the inserted record.
        :rtype: ConfigMapRecordModel
        """

        await self._execute_insert_one(self._write_map_to_document(entity))
        return entity

    # endAsyncDef

    async def create_many(
            self,
            entities: list[ConfigMapRecordModel],
    ) -> list[ConfigMapRecordModel]:

        """
        Inserts multiple current records.

        :param entities: the records to insert.
        :type entities: list[ConfigMapRecordModel]
        :return: the inserted records.
        :rtype: list[ConfigMapRecordModel]
        """

        await self._execute_insert_many([self._write_map_to_document(entity) for entity in entities])
        return entities

    # endAsyncDef

    async def update_one(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> ConfigMapRecordModel | None:

        """
        Updates a single record matching the filter query.

        :param filter_query: the filter query to find the record to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert a new record if nothing matches.
        :type upsert: bool
        :return: the updated record, or None when nothing matched.
        :rtype: ConfigMapRecordModel | None
        """

        result = await self._execute_update_one(filter_query, update_doc_payload, upsert=upsert)

        if result.matched_count == 0 and not upsert:
            return None

        # endIf

        doc = await self._collection.find_one(filter_query)
        return self._write_map_to_model(doc) if doc else None

    # endAsyncDef

    async def update_many(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> int:

        """
        Updates multiple records matching the filter query.

        :param filter_query: the filter query to find the records to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert new records if nothing matches.
        :type upsert: bool
        :return: the number of records updated.
        :rtype: int
        """

        result = await self._execute_update_many(filter_query, update_doc_payload, upsert=upsert)
        return result.modified_count

    # endAsyncDef

    async def mark_seen(
            self,
            cluster_name: str,
            namespace: str,
            name: str,
            seen_at: datetime,
    ) -> None:

        """
        Records that the current version was observed again unchanged.

        :param cluster_name: cluster the ConfigMap was collected from.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param name: ConfigMap name.
        :type name: str
        :param seen_at: observation time (UTC).
        :type seen_at: datetime
        :return: None.
        :rtype: None
        """

        await self._execute_update_one(
            self._identity_filter(cluster_name, namespace, name),
            {"$set": {"last_seen": seen_at}, "$inc": {"seen_count": 1}},
        )

    # endAsyncDef

    async def replace_current(
            self,
            entity: ConfigMapRecordModel,
    ) -> None:

        """
        Replaces the current record for one ConfigMap with a new version. The caller must have
        already written the superseded record to historical - a crash between the two writes
        must only ever produce a harmless duplicate there, never data loss here.

        :param entity: the new current record.
        :type entity: ConfigMapRecordModel
        :return: None.
        :rtype: None
        """

        document = self._write_map_to_document(entity)
        await self._execute_update_one(
            self._identity_filter(entity.cluster_name, entity.namespace, entity.name),
            {"$set": document},
            upsert=True,
        )

    # endAsyncDef

# endClass


# end_configmaps.py

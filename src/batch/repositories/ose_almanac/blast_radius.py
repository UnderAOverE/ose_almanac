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
# Explanation   : Repository for the cm_blast_radius collection - derived, rebuilt per run.           #
# Dependencies  : motor, src.common.db, src.batch.models.ose_almanac.blast_radius.                    #
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

from motor.motor_asyncio import AsyncIOMotorClient

# Internal imports

from src.batch.constants import DatabasesCollections
from src.batch.models.ose_almanac.blast_radius import BlastRadiusModel
from src.common.db.motor_repository import (
    BaseWriteMotorRepository,
    MongoDocument,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Repository.                                                                                         #
# ----------------------------------------------------------------------------------------------------#

class BlastRadiusMotorRepository(BaseWriteMotorRepository[BlastRadiusModel]):

    """
    BlastRadiusMotorRepository class: derived blast-radius documents. The extractor deletes
    one environment + sector scope and rebuilds it on every run - this data is a projection
    of workloads + configmaps and is always safe to recompute.
    """

    _database_name = DatabasesCollections.OSE_ALMANAC_DATABASE.value
    _collection_name = DatabasesCollections.OSE_ALMANAC_CM_BLAST_RADIUS_COLLECTION.value

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
    ) -> None:

        """
        BlastRadiusMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :return: None.
        :rtype: None
        """

        super().__init__(db_client=db_client, base_model=BlastRadiusModel)

    # endDef

    async def delete_scope(
            self,
            environment: str,
            sector: str,
    ) -> int:

        """
        Deletes every document for one environment + sector ahead of a rebuild.

        :param environment: environment scope to clear.
        :type environment: str
        :param sector: sector scope to clear.
        :type sector: str
        :return: the number of documents deleted.
        :rtype: int
        """

        # The write base offers no delete helper; this stays inside the repository adapter layer.
        result = await self._collection.delete_many({"environment": environment, "sector": sector})
        return result.deleted_count

    # endAsyncDef

    async def create(
            self,
            entity: BlastRadiusModel,
    ) -> BlastRadiusModel:

        """
        Inserts one blast-radius document.

        :param entity: the document to insert.
        :type entity: BlastRadiusModel
        :return: the inserted document.
        :rtype: BlastRadiusModel
        """

        await self._execute_insert_one(self._write_map_to_document(entity))
        return entity

    # endAsyncDef

    async def create_many(
            self,
            entities: list[BlastRadiusModel],
    ) -> list[BlastRadiusModel]:

        """
        Inserts a batch of blast-radius documents.

        :param entities: the documents to insert.
        :type entities: list[BlastRadiusModel]
        :return: the inserted documents.
        :rtype: list[BlastRadiusModel]
        """

        await self._execute_insert_many([self._write_map_to_document(entity) for entity in entities])
        return entities

    # endAsyncDef

    async def update_one(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> BlastRadiusModel | None:

        """
        Updates a single document matching the filter query.

        :param filter_query: the filter query to find the document to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert a new document if nothing matches.
        :type upsert: bool
        :return: the updated document, or None when nothing matched.
        :rtype: BlastRadiusModel | None
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
        Updates multiple documents matching the filter query.

        :param filter_query: the filter query to find the documents to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert new documents if nothing matches.
        :type upsert: bool
        :return: the number of documents updated.
        :rtype: int
        """

        result = await self._execute_update_many(filter_query, update_doc_payload, upsert=upsert)
        return result.modified_count

    # endAsyncDef

# endClass


# end_blast_radius.py

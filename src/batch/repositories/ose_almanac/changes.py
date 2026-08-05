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
# Explanation   : Repository for the cm_changes collection - idempotently upserted change events.     #
# Dependencies  : motor, pymongo, src.common.db, src.batch.models.ose_almanac.changes.                #
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
from pymongo import (
    UpdateMany,
    UpdateOne,
)

# Internal imports

from src.batch.constants import DatabasesCollections
from src.batch.models.ose_almanac.changes import ChangeEventModel
from src.common.db.motor_repository import (
    BaseWriteMotorRepository,
    MongoDocument,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Repository.                                                                                         #
# ----------------------------------------------------------------------------------------------------#

class ChangesMotorRepository(BaseWriteMotorRepository[ChangeEventModel]):

    """
    ChangesMotorRepository class: key-level change events. Events are upserted on the
    cluster + namespace + name + new_content_hash identity, so re-running the extractor
    refreshes existing events instead of duplicating them.
    """

    _database_name = DatabasesCollections.OSE_ALMANAC_DATABASE.value
    _collection_name = DatabasesCollections.OSE_ALMANAC_CM_CHANGES_COLLECTION.value

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
    ) -> None:

        """
        ChangesMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :return: None.
        :rtype: None
        """

        super().__init__(db_client=db_client, base_model=ChangeEventModel)

    # endDef

    @staticmethod
    def _event_filter(
            entity: ChangeEventModel,
    ) -> MongoDocument:

        """
        Builds the idempotency filter for one change event.

        :param entity: the event to build the filter from.
        :type entity: ChangeEventModel
        :return: the filter document.
        :rtype: MongoDocument
        """

        return {
            "cluster_name": entity.cluster_name,
            "namespace": entity.namespace,
            "configmap_name": entity.configmap_name,
            "new_content_hash": entity.new_content_hash,
        }

    # endDef

    async def upsert_events(
            self,
            entities: list[ChangeEventModel],
    ) -> int:

        """
        Upserts a batch of change events in one bulk write.

        :param entities: the events to upsert.
        :type entities: list[ChangeEventModel]
        :return: the number of newly inserted events.
        :rtype: int
        """

        if not entities:
            return 0

        # endIf

        operations: list[UpdateMany | UpdateOne] = [
            UpdateOne(
                self._event_filter(entity),
                {"$set": self._write_map_to_document(entity)},
                upsert=True,
            )
            for entity in entities
        ]

        result = await self._execute_bulk_updates(operations, ordered=False)
        return len(result.upserted_ids or {})

    # endAsyncDef

    async def create(
            self,
            entity: ChangeEventModel,
    ) -> ChangeEventModel:

        """
        Upserts one change event.

        :param entity: the event to upsert.
        :type entity: ChangeEventModel
        :return: the event.
        :rtype: ChangeEventModel
        """

        await self._execute_update_one(
            self._event_filter(entity),
            {"$set": self._write_map_to_document(entity)},
            upsert=True,
        )
        return entity

    # endAsyncDef

    async def create_many(
            self,
            entities: list[ChangeEventModel],
    ) -> list[ChangeEventModel]:

        """
        Upserts multiple change events.

        :param entities: the events to upsert.
        :type entities: list[ChangeEventModel]
        :return: the events.
        :rtype: list[ChangeEventModel]
        """

        await self.upsert_events(entities)
        return entities

    # endAsyncDef

    async def update_one(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> ChangeEventModel | None:

        """
        Updates a single event matching the filter query.

        :param filter_query: the filter query to find the event to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert a new event if nothing matches.
        :type upsert: bool
        :return: the updated event, or None when nothing matched.
        :rtype: ChangeEventModel | None
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
        Updates multiple events matching the filter query.

        :param filter_query: the filter query to find the events to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert new events if nothing matches.
        :type upsert: bool
        :return: the number of events updated.
        :rtype: int
        """

        result = await self._execute_update_many(filter_query, update_doc_payload, upsert=upsert)
        return result.modified_count

    # endAsyncDef

# endClass


# end_changes.py

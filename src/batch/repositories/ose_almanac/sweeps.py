#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : sweeps.py.                                                                          #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Repository for the sweeps collection - one record per collector run.                #
# Dependencies  : motor, src.common.db, src.batch.models.ose_almanac.sweeps.                          #
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
from src.batch.models.ose_almanac.sweeps import SweepModel
from src.common.db.motor_repository import (
    BaseWriteMotorRepository,
    MongoDocument,
)

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Repository.                                                                                         #
# ----------------------------------------------------------------------------------------------------#

class SweepsMotorRepository(BaseWriteMotorRepository[SweepModel]):

    """
    SweepsMotorRepository class: append-only record of collector runs.
    """

    _database_name = DatabasesCollections.OSE_ALMANAC_DATABASE.value
    _collection_name = DatabasesCollections.OSE_ALMANAC_SWEEPS_COLLECTION.value

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
    ) -> None:

        """
        SweepsMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :return: None.
        :rtype: None
        """

        super().__init__(db_client=db_client, base_model=SweepModel)

    # endDef

    async def create(
            self,
            entity: SweepModel,
    ) -> SweepModel:

        """
        Appends one sweep record.

        :param entity: the sweep record.
        :type entity: SweepModel
        :return: the appended record.
        :rtype: SweepModel
        """

        await self._execute_insert_one(self._write_map_to_document(entity))
        return entity

    # endAsyncDef

    async def create_many(
            self,
            entities: list[SweepModel],
    ) -> list[SweepModel]:

        """
        Appends multiple sweep records.

        :param entities: the sweep records.
        :type entities: list[SweepModel]
        :return: the appended records.
        :rtype: list[SweepModel]
        """

        await self._execute_insert_many([self._write_map_to_document(entity) for entity in entities])
        return entities

    # endAsyncDef

    async def update_one(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> SweepModel | None:

        """
        Not supported - sweep records are immutable once written.

        :param filter_query: unused.
        :type filter_query: MongoDocument
        :param update_doc_payload: unused.
        :type update_doc_payload: MongoDocument
        :param upsert: unused.
        :type upsert: bool
        :return: never returns.
        :rtype: SweepModel | None
        :raises NotImplementedError: always.
        """

        raise NotImplementedError("sweeps is append-only")

    # endAsyncDef

    async def update_many(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> int:

        """
        Not supported - sweep records are immutable once written.

        :param filter_query: unused.
        :type filter_query: MongoDocument
        :param update_doc_payload: unused.
        :type update_doc_payload: MongoDocument
        :param upsert: unused.
        :type upsert: bool
        :return: never returns.
        :rtype: int
        :raises NotImplementedError: always.
        """

        raise NotImplementedError("sweeps is append-only")

    # endAsyncDef

# endClass


# end_sweeps.py

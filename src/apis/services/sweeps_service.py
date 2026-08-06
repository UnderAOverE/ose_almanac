#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : sweeps_service.py.                                                                  #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Query service for sweep records - the data-freshness and trust signal.              #
# Dependencies  : pymongo, src.apis.db.                                                               #
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

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

# Internal imports

from src.apis.db import SWEEPS_COLLECTION

# Internal constants

module_version: str = "1.0.0v"

# Raw Mongo documents stay inside this service layer; routers validate them into typed
# response models at the process boundary.
type RawDocument = dict[str, Any]


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class SweepsQueryService:

    """
    SweepsQueryService class: exposes the latest sweep record so every UI can show how
    fresh and how complete the data is before anyone draws conclusions from it.
    """

    def __init__(
            self,
            database: AsyncDatabase,
    ) -> None:

        """
        SweepsQueryService constructor.

        :param database: corpus database handle.
        :type database: AsyncDatabase
        :return: None.
        :rtype: None
        """

        self._sweeps = database[SWEEPS_COLLECTION]

    # endDef

    async def latest(
            self,
            environment: str | None,
            sector: str | None,
    ) -> RawDocument | None:

        """
        Returns the most recent sweep record, optionally narrowed to one environment +
        sector.

        :param environment: exact environment filter.
        :type environment: str | None
        :param sector: exact sector filter.
        :type sector: str | None
        :return: the latest sweep record, or None when nothing has ever run.
        :rtype: RawDocument | None
        """

        filter_query: RawDocument = {}

        if environment:
            filter_query["environment"] = environment

        # endIf

        if sector:
            filter_query["sector"] = sector

        # endIf

        docs: list[RawDocument] = (
            await self._sweeps.find(filter_query).sort("started_at", -1).limit(1).to_list(length=1)
        )
        return docs[0] if docs else None

    # endAsyncDef

# endClass


# end_sweeps_service.py

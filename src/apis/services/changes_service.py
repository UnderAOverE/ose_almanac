#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : changes_service.py.                                                                 #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Query service for the change-event feed - the what-changed-when question.           #
# Dependencies  : motor, src.apis.db, src.apis.settings.                                              #
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

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

# Internal imports

from src.apis.db import CM_CHANGES_COLLECTION
from src.apis.settings import ApiSettings

# Internal constants

module_version: str = "1.0.0v"

# Raw Mongo documents stay inside this service layer; routers validate them into typed
# response models at the process boundary.
type RawDocument = dict[str, Any]


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class ChangesQueryService:

    """
    ChangesQueryService class: the incident-bridge query - everything that changed in a
    scope within a time window, newest first, filterable down to one namespace or one
    ConfigMap.
    """

    def __init__(
            self,
            database: AsyncIOMotorDatabase,
            settings: ApiSettings,
    ) -> None:

        """
        ChangesQueryService constructor.

        :param database: corpus database handle.
        :type database: AsyncIOMotorDatabase
        :param settings: API settings for pagination guard rails.
        :type settings: ApiSettings
        :return: None.
        :rtype: None
        """

        self._changes = database[CM_CHANGES_COLLECTION]
        self._settings = settings

    # endDef

    def clamp_page_size(
            self,
            page_size: int | None,
    ) -> int:

        """
        Applies the configured page-size guard rails.

        :param page_size: the caller-requested page size, when any.
        :type page_size: int | None
        :return: the effective page size.
        :rtype: int
        """

        if page_size is None:
            return self._settings.default_page_size

        # endIf

        return min(page_size, self._settings.max_page_size)

    # endDef

    async def feed(
            self,
            environment: str | None,
            sector: str | None,
            cluster_name: str | None,
            namespace: str | None,
            configmap_name: str | None,
            change_type: str | None,
            credential_only: bool,
            since: datetime | None,
            until: datetime | None,
            page: int,
            page_size: int,
    ) -> tuple[list[RawDocument], int]:

        """
        Returns one page of change events, newest first. All filters AND together; the time
        window bounds observed_at, which is when the sweep first saw the new version.

        :param environment: exact environment filter.
        :type environment: str | None
        :param sector: exact sector filter.
        :type sector: str | None
        :param cluster_name: exact cluster filter.
        :type cluster_name: str | None
        :param namespace: exact namespace filter.
        :type namespace: str | None
        :param configmap_name: exact ConfigMap name filter.
        :type configmap_name: str | None
        :param change_type: created or modified.
        :type change_type: str | None
        :param credential_only: when True, only events where a credential-bearing key changed.
        :type credential_only: bool
        :param since: earliest observed_at, inclusive.
        :type since: datetime | None
        :param until: latest observed_at, inclusive.
        :type until: datetime | None
        :param page: 1-based page number.
        :type page: int
        :param page_size: effective page size.
        :type page_size: int
        :return: (events for the page, total matching count).
        :rtype: tuple[list[RawDocument], int]
        """

        filter_query: RawDocument = {}

        if environment:
            filter_query["environment"] = environment

        # endIf

        if sector:
            filter_query["sector"] = sector

        # endIf

        if cluster_name:
            filter_query["cluster_name"] = cluster_name

        # endIf

        if namespace:
            filter_query["namespace"] = namespace

        # endIf

        if configmap_name:
            filter_query["configmap_name"] = configmap_name

        # endIf

        if change_type:
            filter_query["change_type"] = change_type

        # endIf

        if credential_only:
            filter_query["credential_change"] = True

        # endIf

        observed_window: RawDocument = {}

        if since:
            observed_window["$gte"] = since

        # endIf

        if until:
            observed_window["$lte"] = until

        # endIf

        if observed_window:
            filter_query["observed_at"] = observed_window

        # endIf

        total = await self._changes.count_documents(filter_query)
        cursor = (
            self._changes.find(filter_query)
            .sort("observed_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        docs: list[RawDocument] = await cursor.to_list(length=page_size)
        return docs, total

    # endAsyncDef

# endClass


# end_changes_service.py

#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : configmaps_service.py.                                                              #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Query service for ConfigMap search, detail, version history and blast radius.       #
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

import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

# Internal imports

from src.apis.db import (
    CM_BLAST_RADIUS_COLLECTION,
    CONFIGMAPS_COLLECTION,
    CONFIGMAPS_HISTORICAL_COLLECTION,
)
from src.apis.settings import ApiSettings

# Internal constants

module_version: str = "1.0.0v"

# Raw Mongo documents stay inside this service layer; routers validate them into typed
# response models at the process boundary.
type RawDocument = dict[str, Any]


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class ConfigMapsQueryService:

    """
    ConfigMapsQueryService class: read-only queries over the collected ConfigMap corpus.
    Every list query is filtered, sorted and paginated server-side - the corpus spans every
    environment and no endpoint may materialize it unbounded.
    """

    def __init__(
            self,
            database: AsyncIOMotorDatabase,
            settings: ApiSettings,
    ) -> None:

        """
        ConfigMapsQueryService constructor.

        :param database: corpus database handle.
        :type database: AsyncIOMotorDatabase
        :param settings: API settings for pagination guard rails.
        :type settings: ApiSettings
        :return: None.
        :rtype: None
        """

        self._configmaps = database[CONFIGMAPS_COLLECTION]
        self._historical = database[CONFIGMAPS_HISTORICAL_COLLECTION]
        self._blast_radius = database[CM_BLAST_RADIUS_COLLECTION]
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

    async def search(
            self,
            environment: str | None,
            sector: str | None,
            cluster_name: str | None,
            namespace: str | None,
            name_contains: str | None,
            page: int,
            page_size: int,
    ) -> tuple[list[RawDocument], int]:

        """
        Searches current ConfigMaps. All filters AND together; the free-text term matches
        the ConfigMap name case-insensitively with the term escaped, so user input can never
        become a regex operator.

        :param environment: exact environment filter.
        :type environment: str | None
        :param sector: exact sector filter.
        :type sector: str | None
        :param cluster_name: exact cluster filter.
        :type cluster_name: str | None
        :param namespace: exact namespace filter.
        :type namespace: str | None
        :param name_contains: case-insensitive substring of the ConfigMap name.
        :type name_contains: str | None
        :param page: 1-based page number.
        :type page: int
        :param page_size: effective page size.
        :type page_size: int
        :return: (documents for the page, total matching count).
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

        if name_contains:
            filter_query["name"] = {"$regex": re.escape(name_contains), "$options": "i"}

        # endIf

        total = await self._configmaps.count_documents(filter_query)
        cursor = (
            self._configmaps.find(filter_query)
            .sort([("cluster_name", 1), ("namespace", 1), ("name", 1)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        docs: list[RawDocument] = await cursor.to_list(length=page_size)
        return docs, total

    # endAsyncDef

    async def detail(
            self,
            cluster_name: str,
            namespace: str,
            name: str,
    ) -> RawDocument | None:

        """
        Returns the current stored version of one ConfigMap.

        :param cluster_name: cluster the ConfigMap lives on.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param name: ConfigMap name.
        :type name: str
        :return: the document, or None when it was never collected.
        :rtype: RawDocument | None
        """

        return await self._configmaps.find_one(
            {"cluster_name": cluster_name, "namespace": namespace, "name": name}
        )

    # endAsyncDef

    async def versions(
            self,
            cluster_name: str,
            namespace: str,
            name: str,
            limit: int,
    ) -> list[RawDocument]:

        """
        Returns the version timeline of one ConfigMap: the current version first, then
        superseded versions newest-first. Each document gains an is_current flag.

        :param cluster_name: cluster the ConfigMap lives on.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param name: ConfigMap name.
        :type name: str
        :param limit: maximum number of superseded versions returned.
        :type limit: int
        :return: the timeline, newest first.
        :rtype: list[RawDocument]
        """

        identity = {"cluster_name": cluster_name, "namespace": namespace, "name": name}
        timeline: list[RawDocument] = []

        current = await self._configmaps.find_one(identity)

        if current is not None:
            current["is_current"] = True
            timeline.append(current)

        # endIf

        cursor = self._historical.find(identity).sort("last_seen", -1).limit(limit)
        superseded: list[RawDocument] = await cursor.to_list(length=limit)

        for doc in superseded:
            doc["is_current"] = False
            timeline.append(doc)

        # endFor

        return timeline

    # endAsyncDef

    async def blast_radius(
            self,
            cluster_name: str,
            namespace: str,
            name: str,
    ) -> RawDocument | None:

        """
        Returns the computed blast radius for one ConfigMap.

        :param cluster_name: cluster the ConfigMap lives on.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param name: ConfigMap name.
        :type name: str
        :return: the blast-radius document, or None when analytics has not computed one.
        :rtype: RawDocument | None
        """

        return await self._blast_radius.find_one(
            {"cluster_name": cluster_name, "namespace": namespace, "configmap_name": name}
        )

    # endAsyncDef

# endClass


# end_configmaps_service.py

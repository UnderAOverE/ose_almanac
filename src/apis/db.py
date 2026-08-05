#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : db.py.                                                                              #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : The API process's own Mongo edge - client factory and collection names.             #
# Dependencies  : motor, src.apis.settings.                                                           #
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

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
)

# Internal imports

from src.apis.settings import ApiSettings

# Internal constants

module_version: str = "1.0.0v"

# Collection names duplicated from the batch constants on purpose: the API subtree is
# self-contained so it can deploy where the batch tree does not exist. These names are the
# stable public contract of the ose_almanac database.
CONFIGMAPS_COLLECTION: str = "configmaps"
CONFIGMAPS_HISTORICAL_COLLECTION: str = "configmaps_historical"
SWEEPS_COLLECTION: str = "sweeps"
CM_BLAST_RADIUS_COLLECTION: str = "cm_blast_radius"
CM_CHANGES_COLLECTION: str = "cm_changes"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

def build_mongo_client(
        settings: ApiSettings,
) -> AsyncIOMotorClient:

    """
    Builds the API process's Mongo client - one per process, opened in the app lifespan and
    closed on shutdown.

    :param settings: API settings carrying the connection string.
    :type settings: ApiSettings
    :return: the async Mongo client.
    :rtype: AsyncIOMotorClient
    """

    return AsyncIOMotorClient(settings.mongo_uri)

# endDef


def get_database(
        client: AsyncIOMotorClient,
        settings: ApiSettings,
) -> AsyncIOMotorDatabase:

    """
    Returns the configured corpus database handle.

    :param client: the process Mongo client.
    :type client: AsyncIOMotorClient
    :param settings: API settings carrying the database name.
    :type settings: ApiSettings
    :return: the database handle.
    :rtype: AsyncIOMotorDatabase
    """

    return client[settings.mongo_database]

# endDef


# end_db.py

#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : client.py.                                                                          #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Shared MongoDB client factory - one AsyncIOMotorClient per process.                 #
# Dependencies  : motor.                                                                              #
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

import os

from motor.motor_asyncio import AsyncIOMotorClient

# Internal imports

from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"

MONGO_URI_ENV_VAR: str = "MONGO_URI"
DEFAULT_MONGO_URI: str = "mongodb://localhost:27017"
SERVER_SELECTION_TIMEOUT_MS: int = 10000


# ----------------------------------------------------------------------------------------------------#
# Client factory.                                                                                     #
# ----------------------------------------------------------------------------------------------------#

async def get_mongo_client() -> AsyncIOMotorClient:

    """
    Builds the shared MongoDB client for the process.

    Connection details come from the environment; this placeholder reads a single connection
    URI, while the enterprise implementation resolves hosts, replica set, auth and TLS from its
    own configuration. Callers depend only on receiving a ready AsyncIOMotorClient.

    :return: a MongoDB client with tz-aware datetimes enabled.
    :rtype: AsyncIOMotorClient
    """

    mongo_uri = os.getenv(MONGO_URI_ENV_VAR, DEFAULT_MONGO_URI)

    client: AsyncIOMotorClient = AsyncIOMotorClient(
        mongo_uri,
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        tz_aware=True,
    )

    logger.info("mongo_client_ready")
    return client

# endAsyncDef


# end_client.py

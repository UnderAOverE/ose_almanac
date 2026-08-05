#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : registry.py.                                                                        #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Extractor registry - the pipeline iterates this map instead of hardcoding names.    #
# Dependencies  : motor (typing only), analytics extractor services.                                  #
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

from collections.abc import (
    Callable,
    Coroutine,
)
from typing import (
    Any,
    Protocol,
)

from motor.motor_asyncio import AsyncIOMotorClient

# Internal imports

from src.batch.services.ose_almanac.analytics.blast_radius import BlastRadiusExtractorService
from src.batch.services.ose_almanac.analytics.changes import DriftExtractorService

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class ConfigMapExtractor(Protocol):

    """
    What every extractor exposes to the pipeline. Extractors read stored data, never the
    live cluster, and know nothing of each other - adding one adds a registry entry and
    touches nothing that exists.
    """

    async def run(
            self,
            batch_environment: str,
            batch_sector: str,
    ) -> None:

        """
        Runs the extractor for one environment + sector.

        :param batch_environment: environment to compute.
        :type batch_environment: str
        :param batch_sector: sector to compute.
        :type batch_sector: str
        :return: None.
        :rtype: None
        """

        ...

    # endAsyncDef

# endClass


# One factory per extractor, keyed by the name that appears in run logs. Coroutine's first
# two type arguments are the conventional Any of the coroutine protocol, not data types.
EXTRACTOR_FACTORIES: dict[str, Callable[[AsyncIOMotorClient], Coroutine[Any, Any, ConfigMapExtractor]]] = {
    "blast_radius": BlastRadiusExtractorService.get_service,
    "changes": DriftExtractorService.get_service,
}


# end_registry.py

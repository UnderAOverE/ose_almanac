#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : ose_almanac_analytics_main.py.                                                      #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Entry point for the OpenShift ConfigMap Intelligence Platform analytics pipeline.   #
# Dependencies  : src.common.db.client, src.batch.services.ose_almanac.analytics.registry.            #
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

import asyncio

# Internal imports

from src.batch.services.ose_almanac.analytics.registry import EXTRACTOR_FACTORIES
from src.common.db.client import get_mongo_client
from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Main.                                                                                               #
# ----------------------------------------------------------------------------------------------------#

async def main(
        batch_environment: str,
        batch_sector: str,
) -> None:

    """
    Main function to run the analytics pipeline of the OpenShift ConfigMap Intelligence
    Platform for one environment + sector. Every registered extractor runs in registry
    order against stored data only; the pipeline is re-runnable at any time and never
    touches a live cluster.

    :param batch_environment: the environment to compute (e.g., "development", "production").
    :type batch_environment: str
    :param batch_sector: the sector to compute (e.g., "pbwm_cgw").
    :type batch_sector: str
    :return: None.
    :rtype: None
    """

    mongo_client = await get_mongo_client()

    for extractor_name, factory in EXTRACTOR_FACTORIES.items():
        extractor = await factory(mongo_client)
        await extractor.run(batch_environment=batch_environment, batch_sector=batch_sector)

        logger.info("extractor_finished name=%s", extractor_name)

    # endFor

# endAsyncDef


if __name__ == "__main__":
    len(sys.argv) == 3 or sys.exit(f"Usage: {sys.argv[0]} <environment> <sector>")
    asyncio.run(
        main(
            batch_environment=sys.argv[1],
            batch_sector=sys.argv[2],
        )
    )

# endIf


# end_ose_almanac_analytics_main.py

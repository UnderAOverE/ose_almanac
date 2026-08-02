#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : ose_almanac_collector_main.py.                                                      #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Entry point for the OpenShift ConfigMap Intelligence Platform collector sweep.      #
# Dependencies  : src.common.db.client, src.batch.services.ose_almanac.collector.sweep.               #
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

import asyncio

# Internal imports

from src.batch.services.ose_almanac.collector.sweep import OSEAlmanacCollectorService
from src.common.db.client import get_mongo_client

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
    Main function to run one collector sweep of the OpenShift ConfigMap Intelligence Platform.
    The scheduler launches this every 24 hours per environment + sector.

    :param batch_environment: the environment to sweep (e.g., "development", "production").
    :type batch_environment: str
    :param batch_sector: the sector to sweep (e.g., "pbwm_cgw").
    :type batch_sector: str
    :return: None.
    :rtype: None
    """

    mongo_client = await get_mongo_client()
    collector_service = await OSEAlmanacCollectorService.get_service(mongo_client)

    await collector_service.run_sweep(batch_environment=batch_environment, batch_sector=batch_sector)

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


# end_ose_almanac_collector_main.py

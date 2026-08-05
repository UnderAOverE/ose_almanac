#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : ose_almanac_api_main.py.                                                            #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Entry point for the OpenShift ConfigMap Intelligence Platform read-only API.        #
# Dependencies  : uvicorn, src.apis.settings.                                                         #
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

import uvicorn

# Internal imports

from src.apis.settings import ApiSettings

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Main.                                                                                               #
# ----------------------------------------------------------------------------------------------------#

if __name__ == "__main__":
    # uvicorn owns the event loop for the API process; host and port come from the same
    # environment-driven settings the app itself reads.
    settings = ApiSettings()
    uvicorn.run("src.apis.app:app", host=settings.host, port=settings.port)

# endIf


# end_ose_almanac_api_main.py

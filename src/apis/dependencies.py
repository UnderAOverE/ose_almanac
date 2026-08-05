#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : dependencies.py.                                                                    #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Shared FastAPI dependency providers - services built in the lifespan surface here.  #
# Dependencies  : fastapi, src.apis.services.                                                         #
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

from fastapi import Request

# Internal imports

from src.apis.services.changes_service import ChangesQueryService
from src.apis.services.configmaps_service import ConfigMapsQueryService
from src.apis.services.sweeps_service import SweepsQueryService

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

def get_configmaps_service(request: Request) -> ConfigMapsQueryService:

    """
    Returns the ConfigMaps query service stashed on app.state during lifespan startup.

    :param request: the incoming request.
    :type request: Request
    :return: the shared service instance.
    :rtype: ConfigMapsQueryService
    """

    service: ConfigMapsQueryService = request.app.state.configmaps_service
    return service

# endDef


def get_changes_service(request: Request) -> ChangesQueryService:

    """
    Returns the change-feed query service stashed on app.state during lifespan startup.

    :param request: the incoming request.
    :type request: Request
    :return: the shared service instance.
    :rtype: ChangesQueryService
    """

    service: ChangesQueryService = request.app.state.changes_service
    return service

# endDef


def get_sweeps_service(request: Request) -> SweepsQueryService:

    """
    Returns the sweeps query service stashed on app.state during lifespan startup.

    :param request: the incoming request.
    :type request: Request
    :return: the shared service instance.
    :rtype: SweepsQueryService
    """

    service: SweepsQueryService = request.app.state.sweeps_service
    return service

# endDef


# end_dependencies.py

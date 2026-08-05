#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : app.py.                                                                             #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : FastAPI app factory for the read-only ConfigMap intelligence API. The lifespan      #
#                 opens one Mongo client, builds the query services onto app.state, and closes on     #
#                 shutdown. Swagger at /playground, ReDoc at /documentation, schema at /openapi.json. #
# Dependencies  : fastapi, src.apis.{settings, db, dependencies, routers, services}.                  #
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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Internal imports

from src.apis.db import (
    build_mongo_client,
    get_database,
)
from src.apis.routers.changes import router as changes_router
from src.apis.routers.configmaps import router as configmaps_router
from src.apis.routers.sweeps import router as sweeps_router
from src.apis.services.changes_service import ChangesQueryService
from src.apis.services.configmaps_service import ConfigMapsQueryService
from src.apis.services.sweeps_service import SweepsQueryService
from src.apis.settings import ApiSettings

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:

    """
    Opens the Mongo client and builds the query services at startup, closes at shutdown.
    Services live on app.state so the dependency providers stay decoupled from construction.

    :param app: the FastAPI application.
    :type app: FastAPI
    :return: an async iterator yielding once the app is ready.
    :rtype: AsyncIterator[None]
    """

    settings = ApiSettings()
    mongo_client = build_mongo_client(settings)
    database = get_database(mongo_client, settings)

    app.state.mongo_client = mongo_client
    app.state.configmaps_service = ConfigMapsQueryService(database, settings)
    app.state.changes_service = ChangesQueryService(database, settings)
    app.state.sweeps_service = SweepsQueryService(database)

    try:
        yield

    finally:
        mongo_client.close()

    # endTryFinally

# endAsyncDef


def create_app() -> FastAPI:

    """
    Builds the FastAPI app: OpenAPI metadata from settings, CORS for browser clients, and
    one include_router line per resource so a future router only adds a line here.

    :return: the configured application.
    :rtype: FastAPI
    """

    settings = ApiSettings()

    app = FastAPI(
        title=settings.title,
        version=settings.version,
        description=settings.description,
        lifespan=_lifespan,
        # Operator-friendly doc paths.
        docs_url="/playground",
        redoc_url="/documentation",
        openapi_url="/openapi.json",
    )

    # Browser clients (the React UI) call this API cross-origin; the allowed origin list is
    # environment-driven and read-only methods are all this API has.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(configmaps_router)
    app.include_router(changes_router)
    app.include_router(sweeps_router)

    @app.get(
        "/health",
        tags=["meta"],
        summary="Liveness probe",
        response_description="Status object when the process is up.",
    )
    async def health() -> dict[str, str]:

        """
        Liveness probe for orchestrators. Does not touch Mongo - a Mongo-reachability
        problem surfaces as a 500 on any data endpoint instead.

        :return: a static status object.
        :rtype: dict[str, str]
        """

        return {"status": "ok"}

    # endAsyncDef

    return app

# endDef


# Module-level instance for `uvicorn src.apis.app:app` invocations.
app = create_app()


# end_app.py

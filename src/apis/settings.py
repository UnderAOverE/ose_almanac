#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : settings.py.                                                                        #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Environment-driven settings for the read-only API process.                          #
# Dependencies  : pydantic-settings.                                                                  #
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

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

ENV_PREFIX: str = "OSE_ALMANAC_API_"


# ----------------------------------------------------------------------------------------------------#
# Settings.                                                                                           #
# ----------------------------------------------------------------------------------------------------#

class ApiSettings(BaseSettings):

    """
    ApiSettings class: every operational knob for the API process, read from environment
    variables with the OSE_ALMANAC_API_ prefix. The API serves a corpus that maps the whole
    internal estate - deploy it behind the same access controls as cluster credentials.
    """

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        extra="ignore",
        str_strip_whitespace=True,
    )

    # OpenAPI metadata - what the React team sees on /playground and /documentation.
    title: str = Field(
        default="OpenShift ConfigMap Intelligence Platform API",
        description="OpenAPI title.",
    )
    version: str = Field(
        default="1.0.0",
        description="OpenAPI version string.",
    )
    description: str = Field(
        default=(
            "Read-only API over the collected ConfigMap corpus: search, detail, version "
            "history, blast radius and change events. All values are stored redacted; "
            "credentials never appear here."
        ),
        description="OpenAPI description.",
    )

    # Bind address for the local uvicorn entry point.
    host: str = Field(default="127.0.0.1", description="Bind host.")
    port: int = Field(default=8000, ge=1, le=65535, description="Bind port.")

    # Mongo connectivity - the API process owns its own client and reads the ose_almanac
    # database only.
    mongo_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection string.",
    )
    mongo_database: str = Field(
        default="ose_almanac",
        description="Database holding the collected corpus.",
    )

    # Browser clients. Wide-open is a local-development default; production deployments set
    # the explicit React origin list through the environment.
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins for browser clients.",
    )

    # Pagination guard rails - the corpus spans every environment, so no endpoint ever
    # returns an unbounded result set.
    default_page_size: int = Field(default=50, ge=1, description="Page size when the caller omits one.")
    max_page_size: int = Field(default=500, ge=1, description="Hard ceiling on requested page size.")

# endClass


# end_settings.py

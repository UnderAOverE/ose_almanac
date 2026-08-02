#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : ose_almanac.py.                                                                     #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Environment-driven settings for the ose_almanac collector and analytics.            #
# Dependencies  : pydantic-settings.                                                                  #
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

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

ENV_PREFIX: str = "OSE_ALMANAC_"


# ----------------------------------------------------------------------------------------------------#
# Settings.                                                                                           #
# ----------------------------------------------------------------------------------------------------#

class OSEAlmanacSettings(BaseSettings):

    """
    OSEAlmanacSettings class: every operational knob for the collector, read from environment
    variables with the OSE_ALMANAC_ prefix. The concurrency caps are an operational requirement,
    not a tuning knob - an estate-wide sweep including dev/UAT is heavy and the platform team
    should know its ceiling.
    """

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        extra="ignore",
        str_strip_whitespace=True,
    )

    # TLS towards cluster API servers.
    ca_certificate_path: str | None = Field(
        default=None,
        description="Path to the CA bundle used to verify cluster API server certificates.",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify cluster API server certificates.",
    )

    # Sweep shape.
    cluster_concurrency_limit: int = Field(
        default=3,
        ge=1,
        description="Maximum clusters swept concurrently.",
    )
    request_concurrency_limit: int = Field(
        default=20,
        ge=1,
        description="Maximum concurrent API requests per process.",
    )
    page_size: int = Field(
        default=500,
        ge=1,
        description="limit parameter for paginated cluster API list calls.",
    )
    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Per-request timeout towards cluster API servers.",
    )

    # Retry policy for cluster API calls.
    retry_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum attempts per cluster API call.",
    )
    retry_wait_min_seconds: float = Field(
        default=2.0,
        gt=0,
        description="Minimum exponential backoff wait between retries.",
    )
    retry_wait_max_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Maximum exponential backoff wait between retries.",
    )

    # Auth token handling.
    token_skew_seconds: int = Field(
        default=300,
        ge=0,
        description="Seconds subtracted from token lifetime so tokens refresh early.",
    )

    # Redaction rules are yaml so a scanner rule can be tuned without a code change.
    redaction_rules_path: str = Field(
        default="conf/redaction.yaml",
        description="Path to the secret-scanner rules and placeholder patterns.",
    )

# endClass


# end_ose_almanac.py

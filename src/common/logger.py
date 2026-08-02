#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : logger.py.                                                                          #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Shared structured logger - UTC timestamps, level from the environment.              #
# Dependencies  : stdlib logging.                                                                     #
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

import logging
import os
import time

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

LOG_LEVEL_ENV_VAR: str = "LOG_LEVEL"
DEFAULT_LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"
LOGGER_NAME: str = "batch"


# ----------------------------------------------------------------------------------------------------#
# Logger construction.                                                                                #
# ----------------------------------------------------------------------------------------------------#

def _build_logger() -> logging.Logger:

    """
    Builds the shared process logger exactly once.

    Reading the level from the environment here is the infrastructure exception to the
    no-os.environ rule: the logger must exist before any settings model is constructed.

    :return: the configured logger.
    :rtype: logging.Logger
    """

    built_logger = logging.getLogger(LOGGER_NAME)

    if not built_logger.handlers:
        level_name = os.getenv(LOG_LEVEL_ENV_VAR, DEFAULT_LOG_LEVEL).upper()
        formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        formatter.converter = time.gmtime  # all timestamps are UTC

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        built_logger.addHandler(handler)
        built_logger.setLevel(level_name)
        built_logger.propagate = False

    # endIf

    return built_logger

# endDef


logger: logging.Logger = _build_logger()


# end_logger.py

#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : http_errors.py.                                                                     #
# Date of birth : 2026-08-04.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Classifies the shared HTTP client's string-error returns for retry decisions.       #
# Dependencies  : stdlib re.                                                                          #
# Modifications : 2026-08-04 Shane Reddy - initial.                                                   #
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

import re

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

STATUS_CODE_PATTERN: re.Pattern[str] = re.compile(r"returned status (\d+)")
TRANSPORT_ERROR_PREFIX: str = "An error occurred while requesting"
SERVER_ERROR_THRESHOLD: int = 500
THROTTLING_STATUS: int = 429


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

def status_code_of(error_text: str) -> int | None:

    """
    Pulls the HTTP status code out of one of the shared client's error strings.

    The shared HTTP client reports an unexpected status as a string of the form
    "Error: <url> returned status <code>, expected <code>" instead of raising, so the
    numeric status has to be recovered from the text before a caller can decide how
    to react.

    :param error_text: the string returned by the shared client.
    :type error_text: str
    :return: the status code when the string carries one, otherwise None.
    :rtype: int | None
    """

    match = STATUS_CODE_PATTERN.search(error_text)
    return int(match.group(1)) if match else None

# endDef


def is_transport_error(error_text: str) -> bool:

    """
    Tells whether an error string reports a transport failure (DNS, connect, TLS, read),
    which the shared client catches internally and returns as text. Transport failures
    are transient by nature and always worth retrying.

    :param error_text: the string returned by the shared client.
    :type error_text: str
    :return: True when the string reports a transport failure.
    :rtype: bool
    """

    return error_text.startswith(TRANSPORT_ERROR_PREFIX)

# endDef


def is_retryable_status(status_code: int | None) -> bool:

    """
    Tells whether a status code is worth retrying with backoff: server-side failures and
    throttling only. Client errors (auth, forbidden, malformed request) are never retried
    because repeating them cannot change the outcome.

    :param status_code: the status code recovered from an error string, when any.
    :type status_code: int | None
    :return: True for 5xx and 429, False otherwise.
    :rtype: bool
    """

    if status_code is None:
        return False

    # endIf

    return status_code >= SERVER_ERROR_THRESHOLD or status_code == THROTTLING_STATUS

# endDef


# end_http_errors.py

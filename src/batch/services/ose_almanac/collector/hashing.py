#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : hashing.py.                                                                         #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Content fingerprints - per-key SHA-256 and a stable whole-ConfigMap hash.           #
# Dependencies  : stdlib hashlib.                                                                     #
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

import hashlib

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Fingerprint functions.                                                                              #
# ----------------------------------------------------------------------------------------------------#

def sha256_text(text: str) -> str:

    """
    Hashes a text value.

    :param text: the value to hash.
    :type text: str
    :return: the hex SHA-256 digest.
    :rtype: str
    """

    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# endDef


def fingerprint(
        data: dict[str, str],
        binary_data: dict[str, str],
) -> tuple[str, dict[str, str]]:

    """
    Fingerprints a ConfigMap's contents at two levels: per-key hashes say WHICH key changed
    (what makes reports readable), the combined hash says WHETHER anything changed at all.
    The combined digest is computed over sorted key=digest lines so key order never matters.

    :param data: the ConfigMap data map (values may already be redacted).
    :type data: dict[str, str]
    :param binary_data: the ConfigMap binaryData map, base64 values as delivered.
    :type binary_data: dict[str, str]
    :return: (whole-ConfigMap hash, per-key hashes).
    :rtype: tuple[str, dict[str, str]]
    """

    key_hashes = {key: sha256_text(value) for key, value in sorted(data.items())}
    key_hashes.update({key: sha256_text(value) for key, value in sorted(binary_data.items())})

    combined = "\n".join(f"{key}={digest}" for key, digest in sorted(key_hashes.items()))
    return sha256_text(combined), key_hashes

# endDef


# end_hashing.py

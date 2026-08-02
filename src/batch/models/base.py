#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : base.py.                                                                            #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Shared model building blocks - PyObjectId and the common model configuration.       #
# Dependencies  : pydantic, bson.                                                                     #
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

from typing import (
    Annotated,
    Any,
)

from pydantic import (
    BeforeValidator,
    ConfigDict,
)

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Shared building blocks.                                                                             #
# ----------------------------------------------------------------------------------------------------#

def _stringify_object_id(value: Any) -> Any:

    """
    Converts a bson ObjectId to its string form so models stay bson-agnostic.

    :param value: the raw _id value from a MongoDB document.
    :type value: Any
    :return: the string form when the value is not already a string.
    :rtype: Any
    """

    return str(value) if value is not None and not isinstance(value, str) else value

# endDef


# Models carry Mongo's _id as a plain string; the repository layer converts back to ObjectId at
# write time.
type PyObjectId = Annotated[str, BeforeValidator(_stringify_object_id)]

# One shared configuration for every persisted model: unknown fields are rejected loudly,
# aliases (like _id) populate by name, and string fields are whitespace-trimmed.
PERSISTED_MODEL_CONFIG: ConfigDict = ConfigDict(
    extra="forbid",
    populate_by_name=True,
    str_strip_whitespace=True,
)


# end_base.py

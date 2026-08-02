#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : constants.py.                                                                       #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Cross-cutting constants shared by every batch process.                              #
# Dependencies  : stdlib pathlib.                                                                     #
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

from datetime import timezone
from pathlib import Path

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

HOME_DIRECTORY: str = str(Path.home())
UTC: timezone = timezone.utc


# end_constants.py

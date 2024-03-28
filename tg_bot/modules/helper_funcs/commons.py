###############################################################################
# Imported modules
###############################################################################

# Logging Library
import logging

# Data Types Hints Library
from typing import Union


###############################################################################
# Logger Setup
###############################################################################

logger = logging.getLogger(__name__)

def is_int(element):
    '''
    Check if the string is an integer number.
    '''
    try:
        int(element)
        return True
    except ValueError:
        return False

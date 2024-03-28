# Error Traceback Library
from traceback import format_exc

from tg_bot import LOGGER

def add_lrm(str_to_modify: str):
    '''
    Add a Left to Right Mark (LRM) at provided string start.
    '''
    try:
        byte_array = bytearray(b"\xe2\x80\x8e")
        str_to_modify_bytes = str_to_modify.encode("utf-8")
        for char in str_to_modify_bytes:
            byte_array.append(char)
        str_to_modify = byte_array.decode("utf-8")
    except Exception:
        LOGGER.error(format_exc())
    return str_to_modify

def list_remove_element(the_list: list, the_element):
    '''
    Safe remove an element from a list.
    '''
    try:
        if the_element not in the_list:
            return False
        i = the_list.index(the_element)
        del the_list[i]
    except Exception:
        # The element could not be in the list
        LOGGER.error(format_exc())
        LOGGER.error("Can't remove element from a list")
        return False
    return True

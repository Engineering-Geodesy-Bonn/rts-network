from typing import Tuple

from dash import Input, Output, callback

from web.components import ids
from web.utils import validate_ip_address, validate_port


@callback(
    [Output(ids.API_HOST_INPUT, "valid"), Output(ids.API_HOST_INPUT, "invalid")],
    [
        Input(ids.API_HOST_INPUT, "value"),
    ],
)
def update_api_ip_form(text: str) -> Tuple[bool, bool]:
    """
    This callback is triggered when the input value of the IP address input field changes.

    Args:
        text (str): The value of the IP address input field.

    Returns:
        Tuple[bool, bool]: A tuple of two boolean values. The first value indicates if the
        input is valid, the second value indicates if the input is invalid.
    """
    if not text:
        return False, False

    valid = validate_ip_address(text)
    return valid, not valid


@callback(
    [
        Output(ids.API_PORT_INPUT, "valid"),
        Output(ids.API_PORT_INPUT, "invalid"),
    ],
    [
        Input(ids.API_PORT_INPUT, "value"),
    ],
)
def update_api_port_form(number: int) -> Tuple[bool, bool]:
    if not number:
        return False, False

    valid = validate_port(number)
    return valid, not valid

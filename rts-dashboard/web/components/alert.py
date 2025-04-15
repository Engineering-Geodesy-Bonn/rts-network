import dash_bootstrap_components as dbc
from dash import html


def invalid_input_alert(alert_id: str) -> html.Div:
    return html.Div(
        dbc.Alert(
            "Invalid input. Please try again.",
            color="danger",
            dismissable=True,
            is_open=False,
            id=alert_id,
            duration=4000,
        )
    )

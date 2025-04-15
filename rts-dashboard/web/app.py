import flask
from dash import Dash, set_props

from web.components import ids
from web.components.layout import create_layout
from web.utils import extract_error_info


def custom_error_handler(err):
    error_text = extract_error_info(err)
    set_props(ids.ALERT, dict(children=error_text, is_open=True))


server = flask.Flask(__name__)
app = Dash(
    server=server,
    update_title=None,
    suppress_callback_exceptions=True,
    on_error=custom_error_handler,
    serve_locally=True,
)
app.title = "RTS Dashboard"
app.layout = create_layout()
from web import callbacks

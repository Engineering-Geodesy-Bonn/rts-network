from dash import Input, Output, State, callback, html

from web.components import (
    alignment_tab,
    api_settings_tab,
    devices_tab,
    ids,
    intrinsic_delay_tab,
    jobs_tab,
    plot_tab,
    rts_tab,
)


def render_error_page():
    return html.Div(
        children=[
            html.Div(
                className="tab-header-group",
                children=[
                    html.P("Something went wrong. Try to refresh the page.", className="section-header"),
                ],
            ),
        ],
        className="tab",
    )


@callback(Output(ids.TAB_CONTENT, "children"), Input(ids.TABS, "active_tab"), State(ids.API_STORE, "data"))
def switch_tab(at, api_store):
    try:
        if at == ids.DEVICE_TAB:
            return devices_tab.render(api_store)
        elif at == ids.RTS_TAB:
            return rts_tab.render(api_store)
        elif at == ids.JOBS_TAB:
            return jobs_tab.render(api_store)
        elif at == ids.PLOT_TAB:
            return plot_tab.render(api_store)
        elif at == ids.SETTINGS_TAB:
            return api_settings_tab.render(api_store)
        elif at == ids.ALIGNMENT_TAB:
            return alignment_tab.render(api_store)
        elif at == ids.INTERNAL_DELAY_TAB:
            return intrinsic_delay_tab.render(api_store)
    except Exception:
        return render_error_page()

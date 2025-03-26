from dash import Dash, dcc, html, Input, Output  # pip install dash (version 2.0.0 or higher)
from dash_bootstrap_components.themes import BOOTSTRAP
import ids

#PI_List= ["Chris", "Tod", "Bill"]
PI_List = ["Canada", "China", "South Korea"]

def render(app: Dash) -> html.Div:
    @app.callback(
        Output(ids.PI_DROPDOWN, "value"),
        Input(ids.PI_SELECT_ALL_BUTTON, "n_clicks"),
        prevent_initial_call=True
    )
    def select_all(_: int) -> list[str]:
        """Callback to select all values in the dropdown when the button is clicked."""
        return PI_List 

    return html.Div(
        children=[
            html.H6("PIs"),
            dcc.Dropdown(id=ids.PI_DROPDOWN, options=[{"label": PI, "value": PI} for PI in PI_List], multi = True),
            html.Button(id=ids.PI_SELECT_ALL_BUTTON, className="dropdown-button", children=["Show All"])
        ]

    )
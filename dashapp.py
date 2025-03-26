from dash import Dash, dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import requests

PI_DROPDOWN = "pi-dropdown"
PI_SELECT_ALL_BUTTON = "pi-select-all"

# ==== CONFIG ====
FASTAPI_URL = "http://localhost:8000"  # your FastAPI base URL

# ==== APP INIT ====
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "PI Dashboard"

# ==== LAYOUT ====
app.layout = html.Div(
    className="app-container",
    children=[
        html.H1("PI Dashboard"),
        html.Hr(),

        # LOGIN FORM
        html.Div([
            dcc.Input(id="username-input", type="text", placeholder="Username", debounce=True),
            dcc.Input(id="password-input", type="password", placeholder="Password", debounce=True),
            html.Button("Login", id="login-button", n_clicks=0, className="btn btn-primary"),
            html.Button("Logout", id="logout-button", n_clicks=0, className="btn btn-secondary ms-2"),
            html.Div(id="login-status", className="mt-2"),
        ], className="mb-4"),

        # Hidden storage for token and admin flag
        dcc.Store(id="auth-token"),
        dcc.Store(id="is-admin"),

        # Chart controls and output:
        html.Div(
            id="bar-chart-controls",
            children=[
                # Placeholder for PI dropdown (even if it's empty initially)
                dcc.Dropdown(id="pi-dropdown", options=[], value=[]),
                html.Button("Show All", id="pi-select-all", n_clicks=0, className="btn btn-sm btn-secondary mt-2")
            ]
        ),
        html.Div(id="bar-chart")
    ]
)

# ==== LOGIN CALLBACK ====
@app.callback(
    Output("auth-token", "data"),
    Output("is-admin", "data"),
    Output("login-status", "children"),
    Input("login-button", "n_clicks"),
    State("username-input", "value"),
    State("password-input", "value"),
    prevent_initial_call=True
)
def login(n_clicks, username, password):
    if not username or not password:
        return None, False, "Please enter both username and password."

    try:
        response = requests.post(
            f"{FASTAPI_URL}/token",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data["access_token"], token_data["is_admin"], f"Logged in as {token_data['username']}"

    except requests.exceptions.RequestException as e:
        return None, False, f"Login failed: {str(e)}"


@app.callback(
    Output("bar-chart-controls", "children"),
    Input("is-admin", "data"),
    Input("auth-token", "data"),
    prevent_initial_call=True
)
def show_admin_controls(is_admin, token):
    if not is_admin or not token:
        return html.Div()  # regular users see nothing extra

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{FASTAPI_URL}/api/v2/admin/quotas/", headers=headers)
    response.raise_for_status()
    data = response.json()

    pi_options = [{"label": pi, "value": pi} for pi in data.keys()]

    return html.Div([
        html.H6("Select PI(s)"),
        dcc.Dropdown(
            id=PI_DROPDOWN,
            options=pi_options,
            multi=True
        ),
        html.Button("Show All", id=PI_SELECT_ALL_BUTTON, n_clicks=0, className="btn btn-sm btn-secondary mt-2")
    ])


@app.callback(
    Output(PI_DROPDOWN, "value"),
    Input(PI_SELECT_ALL_BUTTON, "n_clicks"),
    State(PI_DROPDOWN, "options"),
    prevent_initial_call=True
)
def select_all_pis(_, options):
    return [opt["value"] for opt in options]

# ==== LOGOUT CALLBACK ====
@app.callback(
    Output("auth-token", "clear_data"),
    Output("is-admin", "clear_data"), 
    Output("login-status", "children", allow_duplicate=True),
    Input("logout-button", "n_clicks"),
    prevent_initial_call=True
)
def logout(n_clicks):
    return True, True, "You have been logged out."


# ==== BAR CHART CALLBACK ====
@app.callback(
    Output("bar-chart", "children"),
    Input("auth-token", "data"),
    Input("is-admin", "data"),
    Input("pi-dropdown", "value"),
    prevent_initial_call=True
)
def load_barchart(token, is_admin, selected_pis):
    # Debug print (you can remove this later)
    print("Token:", token, "is_admin:", is_admin, "selected_pis:", selected_pis)
    
    # If no token is present, return a message.
    if not token:
        return html.Div("Please log in to view data.")

    headers = {"Authorization": f"Bearer {token}"}
    usage_data = []

    if is_admin:
        # Admin branch: get all quotas.
        response = requests.get(f"{FASTAPI_URL}/api/v2/admin/quotas/", headers=headers)
        response.raise_for_status()
        all_data = response.json()

        # If no PIs are selected, prompt the admin to select at least one.
        if not selected_pis:
            return html.Div("Please select at least one PI.")
        filtered_pis = selected_pis  # use the list of selected PIs

        for pi in filtered_pis:
            members = all_data.get(pi, {})
            for member, stats in members.items():
                usage_data.append({
                    "PI": pi,
                    "Lab Member": member,
                    "Usage": stats["usage"],
                    "Soft Limit": stats["soft"],
                    "Hard Limit": stats["hard"],
                    "Files": stats["files"]
                })

        summary = html.Div([
            html.H5("All PI Usage Summary"),
            html.P(f"Selected PIs: {len(filtered_pis)}"),
            html.P(f"Total Lab Members: {len(usage_data)}")
        ])
    else:
        # Non-admin branch: get data for the current PI.
        response = requests.get(f"{FASTAPI_URL}/api/v2/members/", headers=headers)
        response.raise_for_status()
        members_data = response.json()

        for member, stats in members_data["Users"].items():
            usage_data.append({
                "PI": members_data["PI Name"],
                "Lab Member": member,
                "Usage": stats["usage"],
                "Soft Limit": stats["soft"],
                "Hard Limit": stats["hard"],
                "Files": stats["files"]
            })

        # Get summary stats for the current PI.
        summary_resp = requests.get(f"{FASTAPI_URL}/api/v2/summary/", headers=headers)
        summary_resp.raise_for_status()
        summary_data = summary_resp.json()
        summary = html.Div([
            html.H5("PI Usage Summary"),
            html.Ul([
                html.Li(f"PI: {summary_data['PI']}"),
                html.Li(f"Number of Users: {summary_data['Number of Users']}"),
                html.Li(f"Total Usage: {summary_data['Total Usage']}"),
                html.Li(f"Average Usage: {round(summary_data['Usage Average'], 2)}"),
                html.Li(f"Max Individual Usage: {summary_data['Max Individual Usage']}")
            ])
        ], className="mb-4")

    if not usage_data:
        return html.Div("No usage data found.")

    fig = px.bar(
        usage_data,
        x="Lab Member",
        y="Usage",
        color="PI",
        hover_data=["Soft Limit", "Hard Limit", "Files"],
        title="Lab Member Usage by PI"
    )

    return html.Div([
        summary,
        dcc.Graph(figure=fig)
    ])

# ==== MAIN ====
if __name__ == "__main__":
    app.run(debug=True)
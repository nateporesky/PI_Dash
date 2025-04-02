from dash import Dash, dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
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
            html.H6("Select PI(s)", id="pi-label", style={"display": "none"}),
            dcc.Dropdown(
                id=PI_DROPDOWN,
                options=[],  # will be set later
                value=[],
                multi=True,
                style={"display": "none"}
            ),
            html.Button(
                "Show All",
                id=PI_SELECT_ALL_BUTTON,
                n_clicks=0,
                className="btn btn-sm btn-secondary mt-2",
                style={"display": "none"}
            )
        ]
    ),
        html.Div(id="bar-chart")
    ]
)

# ==== LOGIN CALLBACK ====
@app.callback(
    Output("auth-token", "data"),
    Output("is-admin", "data"),
    Output("login-status", "children", allow_duplicate=True),
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
        return (
            token_data["access_token"],
            token_data["is_admin"],
            f"Logged in as {token_data['username']}"
        )
    except requests.exceptions.RequestException as e:
        return None, False, f"Login failed: {str(e)}"

@app.callback(
    Output(PI_DROPDOWN, "options"),
    Output(PI_DROPDOWN, "style"),
    Output(PI_SELECT_ALL_BUTTON, "style"),
    Output("pi-label", "style"),
    Input("is-admin", "data"),
    Input("auth-token", "data"),
    prevent_initial_call=True
)
def show_admin_controls(is_admin, token):
    if not is_admin or not token:
        hidden = {"display": "none"}
        return [], hidden, hidden, hidden

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{FASTAPI_URL}/api/v2/admin/quotas/", headers=headers)
    response.raise_for_status()
    data = response.json()

    pi_options = [{"label": pi, "value": pi} for pi in data.keys()]
    visible = {"display": "block"}
    return pi_options, visible, visible, visible

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
    Output("bar-chart", "children", allow_duplicate=True),
    Input("logout-button", "n_clicks"),
    prevent_initial_call=True
)
def logout(n_clicks):
    return True, True, "You have been logged out.", None

# ==== BAR CHART CALLBACK ====
@app.callback(
    Output("bar-chart", "children"),
    Input("auth-token", "data"),
    Input("is-admin", "data"),
    Input("pi-dropdown", "value"),
    prevent_initial_call=True
)
def load_barchart(token, is_admin, selected_pis):
    if not token:
        return html.Div("Please log in to view data.")

    headers = {"Authorization": f"Bearer {token}"}
    usage_data = []
    warnings = []

    if is_admin:
        if not selected_pis:
            return html.Div("Please select at least one PI.")

        response = requests.get(f"{FASTAPI_URL}/api/v2/admin/quotas/", headers=headers)
        response.raise_for_status()
        all_data = response.json()

        pi_summaries = []

        for pi in selected_pis:
            members = all_data.get(pi, {})
            pi_usage = sum(stats["usage"] for stats in members.values())
            pi_soft_limit = sum(stats["soft"] for stats in members.values())
            pi_remaining = max(0, pi_soft_limit - pi_usage)
            usage_percent = (pi_usage / pi_soft_limit) * 100 if pi_soft_limit else 0

            color = "red" if usage_percent >= 95 else "blue"
            if usage_percent >= 95:
                warnings.append(f"PI '{pi}' is at {round(usage_percent)}% of their total soft limit.")

            pi_summaries.append({
                "PI": pi,
                "Usage": pi_usage,
                "Remaining": pi_remaining,
                "Color": color
            })

        if not pi_summaries:
            return html.Div("No usage data found.")

        fig = go.Figure()

        for pi in pi_summaries:
            fig.add_trace(go.Bar(
                x=[pi["PI"]],
                y=[pi["Usage"]],
                name="Usage",
                marker_color=pi["Color"],
                hovertext=f"{pi['PI']}: {pi['Usage']} GB used",
                hoverinfo="text+y"
            ))

            fig.add_trace(go.Bar(
                x=[pi["PI"]],
                y=[pi["Remaining"]],
                name="Remaining",
                marker_color="lightgray",
                hovertext=f"{pi['PI']}: {pi['Remaining']} GB remaining",
                hoverinfo="text+y"
            ))

        fig.update_layout(
            barmode="stack",
            title="PI Usage vs Soft Limit",
            xaxis_title="PI",
            yaxis_title="Total Usage (GB)",
            showlegend=False
        )

        total_usage = sum(pi["Usage"] for pi in pi_summaries)
        total_remaining = sum(pi["Remaining"] for pi in pi_summaries)
        avg_usage = round(total_usage / len(pi_summaries), 2) if pi_summaries else 0
        max_usage = max(pi["Usage"] for pi in pi_summaries) if pi_summaries else 0

        summary = html.Div([
            html.H5("Admin Summary for Selected PIs"),
            html.P(f"Number of PIs: {len(pi_summaries)}"),
            html.P(f"Total Usage: {round(total_usage)} GB"),
            html.P(f"Remaining Quota: {round(total_remaining)} GB"),
        ], className="mb-4")

    else:
        response = requests.get(f"{FASTAPI_URL}/api/v2/members/", headers=headers)
        response.raise_for_status()
        members_data = response.json()
        pi_name = members_data["PI Name"]
        members = members_data["Users"]

        total_usage = 0
        max_usage = 0

        for member, stats in members.items():
            usage = stats["usage"]
            soft = stats["soft"]
            usage_percent = (usage / soft) * 100 if soft > 0 else 0
            usage_data.append({
                "PI": pi_name,
                "Lab Member": member,
                "Usage": usage,
                "Remaining": max(0, soft - usage),
                "Color": "red" if usage_percent >= 95 else "blue",
                "Hover": f"PI: {pi_name}<br>Lab Member: {member}<br>Usage: {usage} GB<br>Soft Limit: {soft} GB<br>Hard Limit: {stats['hard']} GB<br>Files: {stats['files']}"
                })
            if usage_percent >= 95:
                warnings.append(f"{member} is at {round(usage_percent)}% of their soft limit.")

            total_usage += usage
            if usage > max_usage:
                max_usage = usage

        avg_usage = round(total_usage / len(members), 2) if members else 0

        summary = html.Div([
            html.H5("PI Usage Summary"),
            html.Ul([
                html.Li(f"PI: {pi_name}"),
                html.Li(f"Number of Users: {len(members)}"),
                html.Li(f"Total Usage: {total_usage} GB"),
                html.Li(f"Average Usage: {avg_usage} GB"),
                html.Li(f"Max Individual Usage: {max_usage} GB")
            ])
        ], className="mb-4")

        if not usage_data:
            return html.Div("No usage data found.")

        fig = go.Figure()

        for entry in usage_data:
            fig.add_trace(go.Bar(
                x=[entry["Lab Member"]],
                y=[entry["Usage"]],
                marker_color=entry["Color"],
                name="Usage",
                hovertext=entry["Hover"],
                hoverinfo="text"
            ))

            fig.add_trace(go.Bar(
                x=[entry["Lab Member"]],
                y=[entry["Remaining"]],
                marker_color="lightgray",
                name="Remaining",
                hovertext=f"{entry['Lab Member']}: {entry['Remaining']} GB remaining",
                hoverinfo="text"
            ))

        fig.update_layout(
            barmode="stack",
            title="Lab Member Usage vs Soft Limit",
            xaxis_title="Lab Member",
            yaxis_title="Usage (GB)",
            showlegend=False
        )

    warning_div = html.Div([
        html.H5("Warnings"),
        html.Ul([html.Li(w) for w in warnings])
    ], className="alert alert-warning") if warnings else html.Div()

    return html.Div([
        summary,
        warning_div,
        dcc.Graph(figure=fig)
    ])

# ==== MAIN ====
if __name__ == "__main__":
    app.run(debug=True)
from dash import Dash, dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import requests

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

        # Hidden storage for token
        dcc.Store(id="auth-token"),
        dcc.Store(id="is-admin"),

        # Dropdown for PI filtering (if needed in future)
        # html.Div([
        #     dcc.Dropdown(id="pi-dropdown", multi=True)
        # ]),

        # Chart output
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
    State("is-admin", "data"),
    prevent_initial_call=True
)
def load_barchart(token, is_admin):
    if not token:
        return html.Div("Please log in to view data.")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        usage_data = []

        if is_admin:
            # Admin: get all quotas grouped by PI
            response = requests.get(f"{FASTAPI_URL}/api/v2/admin/quotas/", headers=headers)
            response.raise_for_status()
            all_data = response.json()

            for pi_name, members in all_data.items():
                for member, stats in members.items():
                    usage_data.append({
                        "PI": pi_name,
                        "Lab Member": member,
                        "Usage": stats["usage"],
                        "Soft Limit": stats["soft"],
                        "Hard Limit": stats["hard"],
                        "Files": stats["files"]
                    })

            summary = html.Div([
                html.H5("All PI Usage Summary"),
                html.P(f"Total PIs: {len(all_data)}"),
                html.P(f"Total Lab Members: {len(usage_data)}")
            ])

        else:
            # Regular PI: get their own quota data
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

            # Optional: fetch and show PI summary stats
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
                    html.Li(f"Max Individual Usage: {summary_data['Max Individual Usage']}"),
                ])
            ], className="mb-4")

        # Build chart
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

    except Exception as e:
        return html.Div(f"Error loading data: {e}")

# ==== MAIN ====
if __name__ == "__main__":
    app.run(debug=True)
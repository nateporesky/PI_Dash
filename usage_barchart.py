from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px
import requests
import ids

API_URL = "http://localhost:8000/api/v2/members/"

def render(app: Dash) -> html.Div:
    @app.callback(
        Output(ids.BARCHART, "children"),
        Input(ids.PI_DROPDOWN, "value"),
        State("auth-token", "data"),
        prevent_initial_call=True
    )
    def update_barchart(PIs: list[str], token: str) -> html.Div:
        if not token:
            return html.Div("Please log in first.")

        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(API_URL, headers=headers)
            response.raise_for_status()
            data = response.json()

            all_data = []
            for student_name, stats in data["Users"].items():
                all_data.append({
                    "PI": data["PI Name"],
                    "Student": student_name,
                    "Usage": stats["usage"]
                })

            if not all_data:
                return html.Div("No data available for this PI.")

            fig = px.bar(
                all_data,
                x="Student",
                y="Usage",
                color="PI",
                title="Student Usage by PI"
            )
            return html.Div(dcc.Graph(figure=fig), id=ids.BARCHART)

        except Exception as e:
            return html.Div(f"Error: {str(e)}")

    return html.Div(id=ids.BARCHART)


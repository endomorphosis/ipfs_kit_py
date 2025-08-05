

import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import asyncio
import base64
import json
from ipfs_kit_py.mcp_client import MCPClient

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("IPFS-Kit Dashboard"),
    dcc.Tabs([
        dcc.Tab(label="Daemon", children=[
            html.H2("Daemon Control"),
            html.Button("Start Daemon", id="start-daemon-button"),
            html.Button("Stop Daemon", id="stop-daemon-button"),
            html.Button("Restart Daemon", id="restart-daemon-button"),
            html.Div(id="daemon-status"),
        ]),
        dcc.Tab(label="Backends", children=[
            html.H2("Backend Management"),
            html.Table(id="backend-table"),
            html.Button("Add Backend", id="add-backend-button"),
            html.Button("Remove Backend", id="remove-backend-button"),
        ]),
        dcc.Tab(label="Buckets", children=[
            html.H2("Bucket Management"),
            html.Table(id="bucket-table"),
            html.Button("Create Bucket", id="create-bucket-button"),
            html.Button("Remove Bucket", id="remove-bucket-button"),
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select Files')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=True
            ),
            html.Div(id='output-data-upload'),
            html.H2("Bucket Files"),
            html.Table(id="bucket-files-table"),
        ]),
        dcc.Tab(label="Pinning", children=[
            html.H2("Pinning Management"),
            html.Table(id="pin-table"),
            html.Button("Add Pin", id="add-pin-button"),
            html.Button("Remove Pin", id="remove-pin-button"),
        ]),
        dcc.Tab(label="Health", children=[
            html.H2("Health Monitoring"),
            html.Table(id="health-table"),
        ]),
        dcc.Tab(label="Metrics", children=[
            html.H2("Performance Metrics"),
            html.Table(id="metrics-table"),
        ]),
        dcc.Tab(label="Resources", children=[
            html.H2("Resource Monitoring"),
            html.Table(id="resource-table"),
        ]),
        dcc.Tab(label="Configuration", children=[
            html.H2("Configuration Management"),
            dcc.Textarea(
                id='config-textarea',
                style={'width': '100%', 'height': 300},
            ),
            html.Button("Save Configuration", id="save-config-button"),
        ]),
        dcc.Tab(label="Peer Management", children=[
            html.H2("Peer Management"),
            html.Table(id="peer-table"),
        ]),
        dcc.Tab(label="Logs", children=[
            html.H2("Log Viewer"),
            dcc.Textarea(
                id='log-textarea',
                style={'width': '100%', 'height': 300},
            ),
        ]),
    ])
])

@app.callback(
    Output("daemon-status", "children"),
    [Input("start-daemon-button", "n_clicks"),
     Input("stop-daemon-button", "n_clicks"),
     Input("restart-daemon-button", "n_clicks")]
)
def update_daemon_status(start_clicks, stop_clicks, restart_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Daemon status: Unknown"

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    if button_id == "start-daemon-button":
        loop.run_until_complete(mcp.send("daemon", ["start"]))
        return "Daemon status: Started"
    elif button_id == "stop-daemon-button":
        loop.run_until_complete(mcp.send("daemon", ["stop"]))
        return "Daemon status: Stopped"
    elif button_id == "restart-daemon-button":
        loop.run_until_complete(mcp.send("daemon", ["restart"]))
        return "Daemon status: Restarted"
    else:
        return "Daemon status: Unknown"

@app.callback(
    Output("backend-table", "children"),
    [Input("add-backend-button", "n_clicks"),
     Input("remove-backend-button", "n_clicks")]
)
def update_backend_table(add_clicks, remove_clicks):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    backends = loop.run_until_complete(mcp.send("backend", ["list"])
    
    header = [html.Tr([html.Th("Name"), html.Th("Type"), html.Th("Status")])]
    if backends:
        rows = [html.Tr([html.Td(b["name"]), html.Td(b["type"]), html.Td(b["status"])]) for b in backends]
    else:
        rows = []
    
    return header + rows

@app.callback(
    Output("bucket-table", "children"),
    [Input("create-bucket-button", "n_clicks"),
     Input("remove-bucket-button", "n_clicks")]
)
def update_bucket_table(create_clicks, remove_clicks):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    buckets = loop.run_until_complete(mcp.send("bucket", ["list"]))
    
    header = [html.Tr([html.Th("Name"), html.Th("Size"), html.Th("Files")])]
    if buckets:
        rows = [html.Tr([html.Td(b["name"]), html.Td(b["size"]), html.Td(b["files"])]) for b in buckets]
    else:
        rows = []
    
    return header + rows

@app.callback(Output('output-data-upload', 'children'),
              [Input('upload-data', 'contents')],
              [State('upload-data', 'filename'),
               State('upload-data', 'last_modified')])
def update_output(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is not None:
        children = [
            parse_contents(c, n, d) for c, n, d in
            zip(list_of_contents, list_of_names, list_of_dates)]
        return children

@app.callback(
    Output("bucket-files-table", "children"),
    [Input("bucket-table", "selected_rows")]
)
def update_bucket_files_table(selected_rows):
    if selected_rows:
        selected_bucket = selected_rows[0]
        loop = asyncio.get_event_loop()
        mcp = MCPClient()
        files = loop.run_until_complete(mcp.send("bucket", ["files", selected_bucket]))
        header = [html.Tr([html.Th("Name"), html.Th("Size")])]
        if files:
            rows = [html.Tr([html.Td(f["name"]), html.Td(f["size"])]) for f in files]
        else:
            rows = []
        return header + rows
    return []

def parse_contents(contents, filename, date):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    loop.run_until_complete(mcp.send("bucket", ["upload", filename, decoded]))
    return html.Div([
        html.Hr(),
        html.Div('File uploaded successfully'),
        html.Hr(),
    ])

@app.callback(
    Output("pin-table", "children"),
    [Input("add-pin-button", "n_clicks"),
     Input("remove-pin-button", "n_clicks")]
)
def update_pin_table(add_clicks, remove_clicks):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    pins = loop.run_until_complete(mcp.send("pin", ["list"]))
    
    header = [html.Tr([html.Th("CID"), html.Th("Name")])]
    if pins:
        rows = [html.Tr([html.Td(p["cid"]), html.Td(p["name"])]) for p in pins]
    else:
        rows = []
    
    return header + rows

@app.callback(
    Output("health-table", "children"),
    [Input("health-table", "n_intervals")]
)
def update_health_table(n):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    health = loop.run_until_complete(mcp.send("health", []))
    
    header = [html.Tr([html.Th("Component"), html.Th("Status")])]
    if health:
        rows = [html.Tr([html.Td(k), html.Td(v)]) for k, v in health.items()])
    else:
        rows = []
    
    return header + rows

@app.callback(
    Output("metrics-table", "children"),
    [Input("metrics-table", "n_intervals")]
)
def update_metrics_table(n):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    metrics = loop.run_until_complete(mcp.send("metrics", []))
    
    header = [html.Tr([html.Th("Metric"), html.Th("Value")])]
    if metrics:
        rows = [html.Tr([html.Td(k), html.Td(v)]) for k, v in metrics.items()])
    else:
        rows = []
    
    return header + rows

@app.callback(
    Output("resource-table", "children"),
    [Input("resource-table", "n_intervals")]
)
def update_resource_table(n):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    resources = loop.run_until_complete(mcp.send("resource", []))
    
    header = [html.Tr([html.Th("Resource"), html.Th("Usage")])]
    if resources:
        rows = [html.Tr([html.Td(k), html.Td(v)]) for k, v in resources.items()])
    else:
        rows = []
    
    return header + rows

@app.callback(
    Output("config-textarea", "value"),
    [Input("config-textarea", "n_intervals")]
)
def update_config_textarea(n):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    config = loop.run_until_complete(mcp.send("config", ["show"]))
    
    return json.dumps(config, indent=2)

@app.callback(
    Output("config-textarea", "value"),
    [Input("save-config-button", "n_clicks")],
    [State("config-textarea", "value")]
)
def save_config(n_clicks, value):
    if n_clicks:
        loop = asyncio.get_event_loop()
        mcp = MCPClient()
        loop.run_until_complete(mcp.send("config", ["set", value]))
    return value

@app.callback(
    Output("peer-table", "children"),
    [Input("peer-table", "n_intervals")]
)
def update_peer_table(n):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    peers = loop.run_until_complete(mcp.send("peer", ["list"]))
    
    header = [html.Tr([html.Th("ID"), html.Th("Address")])]
    if peers:
        rows = [html.Tr([html.Td(p["id"]), html.Td(p["address"])]) for p in peers]
    else:
        rows = []
    
    return header + rows

@app.callback(
    Output("log-textarea", "value"),
    [Input("log-textarea", "n_intervals")]
)
def update_log_textarea(n):
    loop = asyncio.get_event_loop()
    mcp = MCPClient()
    logs = loop.run_until_complete(mcp.send("log", []))
    
    if logs:
        return "\n".join(logs)
    else:
        return ""

if __name__ == "__main__":
    app.run_server(debug=True)

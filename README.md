# inspirational-app

A small PyQt6 desktop app that displays a hyper-graph.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Data

`data/pod_graph.json` is the dataset. The app tries Pod-OS first and falls
back to that file, showing which source won in the window subtitle. Set
`POD_GRAPH_SOURCE=file` to skip Pod-OS entirely, or `POD_GRAPH_FILE` to point
at a different dataset.

To load the dataset into Pod-OS:

```bash
export POD_OS_HOST=localhost POD_OS_PORT=62312
export POD_OS_USER=... POD_OS_PASSCODE=...
python -m app.data.buildData --file data/pod_graph.json
```

One event per vertex and per edge-node, plus an index event listing them.

## Layout

```
main.py                  entry point
app/core/config.py       constants, stylesheet
app/core/graph.py        graph model + force-directed layout
app/ui/main_window.py    MainWindow
app/ui/graph_view.py     canvas, node and incidence items
app/data/pod_schema.py   Pod-OS event schema (ids, payloads, file loader)
app/data/pod_client.py   connection settings from the environment
app/data/buildData.py    load a JSON file into Pod-OS
app/data/queryPOD.py     read the graph back out
data/pod_graph.json      mock dataset
assets/                  icons, images - future use
```

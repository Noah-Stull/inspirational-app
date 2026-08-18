"""App-wide constants and content."""

APP_NAME = "Inspirational App"
WINDOW_SIZE = (960, 640)

# --- Graph rendering -------------------------------------------------------

CANVAS_BG = "#0f1115"
EDGE_COLOR = "#4a5468"
NODE_BORDER = "#0f1115"
NODE_RADIUS = 22
LABEL_COLOR = "#d8dee9"
LAYOUT_SCALE = 620    # minimum pixels the unit-square layout is stretched across
LAYOUT_SPACING = 225  # per-node breathing room: scale grows with sqrt(node count)

# Edge-nodes: edges promoted to nodes, drawn as squares to distinguish them
# from vertices at a glance.
EDGE_NODE_SIZE = 20
EDGE_NODE_COLOR = "#8b93a1"
EDGE_NODE_LABEL_COLOR = "#8b93a1"

GROUP_COLORS = {
    "europe": "#2f6df6",
    "africa": "#f0b429",
    "asia": "#26a17b",
    "americas": "#b45cf0",
    "oceania": "#d85a30",
}
DEFAULT_NODE_COLOR = "#6b7684"

# --- Theme -----------------------------------------------------------------

STYLESHEET = """
QMainWindow, QWidget#Root {
    background-color: #14161a;
}
QLabel#Title {
    color: #f2f4f8;
    font-size: 18px;
    font-weight: 600;
}
QLabel#Subtitle {
    color: #8b93a1;
    font-size: 13px;
}
QPushButton {
    background-color: #2f6df6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #4880f8;
}
QPushButton:pressed {
    background-color: #2559cc;
}
QPushButton#Secondary {
    background-color: #262b33;
    color: #d8dee9;
}
QPushButton#Secondary:hover {
    background-color: #323945;
}
QGraphicsView {
    border: 1px solid #262b33;
    border-radius: 8px;
}
"""

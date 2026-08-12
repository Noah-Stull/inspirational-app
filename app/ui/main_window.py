"""Main application window."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import APP_NAME, STYLESHEET, WINDOW_SIZE
from app.core.graph import Graph, spring_layout
from app.data.queryPOD import fetch_graph
from app.ui.graph_view import GraphView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(*WINDOW_SIZE)
        self.setStyleSheet(STYLESHEET)

        self.graph: Graph = Graph()

        root = QWidget(objectName="Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self.title = QLabel("POD graph", objectName="Title")
        self.subtitle = QLabel(objectName="Subtitle")

        self.view = GraphView()

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.reload_button = QPushButton("Reload query")
        self.reload_button.clicked.connect(self.reload_graph)
        self.relayout_button = QPushButton("Re-layout", objectName="Secondary")
        self.relayout_button.clicked.connect(self.relayout)
        self.fit_button = QPushButton("Fit", objectName="Secondary")
        self.fit_button.clicked.connect(self.view.fit_to_contents)
        buttons.addWidget(self.reload_button)
        buttons.addWidget(self.relayout_button)
        buttons.addWidget(self.fit_button)
        buttons.addStretch(1)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.view, stretch=1)
        layout.addLayout(buttons)

        self.setCentralWidget(root)
        self.reload_graph()

    # --- actions -----------------------------------------------------------

    def reload_graph(self) -> None:
        """Fetch the graph from the data layer and draw it."""
        self.graph = fetch_graph()
        self.view.set_graph(self.graph)
        self._update_subtitle()

    def relayout(self) -> None:
        """Recompute node positions with a different random arrangement."""
        self.view.set_graph(self.graph, spring_layout(self.graph, seed=None))

    # --- helpers -----------------------------------------------------------

    def _update_subtitle(self) -> None:
        self.subtitle.setText(
            f"{len(self.graph.vertices)} vertices · "
            f"{len(self.graph.valid_edges())} edges · "
            "drag nodes, scroll to zoom, drag canvas to pan"
        )

"""Qt widgets that draw a Graph: pannable, zoomable, with draggable nodes."""

from __future__ import annotations

import math

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from app.core.config import (
    CANVAS_BG,
    DEFAULT_NODE_COLOR,
    EDGE_COLOR,
    GROUP_COLORS,
    LABEL_COLOR,
    LAYOUT_SCALE,
    NODE_BORDER,
    NODE_RADIUS,
)
from app.core.graph import Graph, Vertex, spring_layout

ARROW_SIZE = 9.0


class NodeItem(QGraphicsEllipseItem):
    """A single vertex. Drag it and its edges follow."""

    def __init__(self, vertex: Vertex, radius: float = NODE_RADIUS) -> None:
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.vertex = vertex
        self.radius = radius
        self.edges: list["EdgeItem"] = []

        color = QColor(GROUP_COLORS.get(vertex.group or "", DEFAULT_NODE_COLOR))
        self._pen = QPen(QColor(NODE_BORDER), 2)
        self._hover_pen = QPen(QColor("#f2f4f8"), 2)
        self.setBrush(QBrush(color))
        self.setPen(self._pen)
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(
            QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"{vertex.display}  ({vertex.id})")

        self.label = QGraphicsSimpleTextItem(vertex.display, self)
        self.label.setBrush(QBrush(QColor(LABEL_COLOR)))
        rect = self.label.boundingRect()
        self.label.setPos(-rect.width() / 2, radius + 5)

    def add_edge(self, edge: "EdgeItem") -> None:
        self.edges.append(edge)

    def itemChange(self, change, value):  # noqa: N802 (Qt naming)
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.adjust()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):  # noqa: N802
        self.setPen(self._hover_pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802
        self.setPen(self._pen)
        super().hoverLeaveEvent(event)


class EdgeItem(QGraphicsPathItem):
    """A line between two NodeItems, with an arrowhead at each end."""

    def __init__(self, source: NodeItem, target: NodeItem, directed: bool = True) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.directed = directed

        color = QColor(EDGE_COLOR)
        self.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        self.setBrush(QBrush(color))
        self.setZValue(-1)

        source.add_edge(self)
        target.add_edge(self)
        self.adjust()

    def adjust(self) -> None:
        line = QLineF(self.source.pos(), self.target.pos())
        length = line.length()
        if length < 1e-3:
            self.setPath(QPainterPath())
            return

        ux, uy = line.dx() / length, line.dy() / length
        start = self.source.pos() + QPointF(ux * self.source.radius, uy * self.source.radius)
        end = self.target.pos() - QPointF(ux * self.target.radius, uy * self.target.radius)

        path = QPainterPath(start)
        path.lineTo(end)

        if self.directed:
            # Bidirectional: an arrowhead pointing outward at each endpoint.
            angle = math.atan2(-(end.y() - start.y()), end.x() - start.x())
            path.addPolygon(self._arrow_head(end, angle))
            path.addPolygon(self._arrow_head(start, angle + math.pi))

        self.setPath(path)

    @staticmethod
    def _arrow_head(tip: QPointF, angle: float) -> QPolygonF:
        """Triangle whose point sits at `tip`, opening back along `angle`."""
        p1 = tip + QPointF(
            math.sin(angle - math.pi / 3) * ARROW_SIZE,
            math.cos(angle - math.pi / 3) * ARROW_SIZE,
        )
        p2 = tip + QPointF(
            math.sin(angle - math.pi + math.pi / 3) * ARROW_SIZE,
            math.cos(angle - math.pi + math.pi / 3) * ARROW_SIZE,
        )
        return QPolygonF([tip, p1, p2])


class GraphView(QGraphicsView):
    """Scrollable canvas holding the rendered graph."""

    MIN_SCALE = 0.15
    MAX_SCALE = 6.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor(CANVAS_BG)))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.nodes: dict[str, NodeItem] = {}
        self._auto_fit = True

    def set_graph(
        self,
        graph: Graph,
        positions: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        """Render `graph`. Positions default to a fresh spring layout."""
        if positions is None:
            positions = spring_layout(graph)

        self._scene.clear()
        self.nodes = {}

        for vertex in graph.vertices:
            node = NodeItem(vertex)
            x, y = positions.get(vertex.id, (0.5, 0.5))
            node.setPos(x * LAYOUT_SCALE, y * LAYOUT_SCALE)
            self._scene.addItem(node)
            self.nodes[vertex.id] = node

        for edge in graph.valid_edges():
            self._scene.addItem(
                EdgeItem(
                    self.nodes[edge.source],
                    self.nodes[edge.target],
                    directed=graph.directed,
                )
            )

        self._auto_fit = True
        self.fit_to_contents()

    def fit_to_contents(self) -> None:
        rect: QRectF = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self._scene.setSceneRect(rect.adjusted(-80, -80, 80, 80))
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._auto_fit = True

    def wheelEvent(self, event):  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current = self.transform().m11()
        if self.MIN_SCALE <= current * factor <= self.MAX_SCALE:
            self.scale(factor, factor)
            self._auto_fit = False

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if self._auto_fit:
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

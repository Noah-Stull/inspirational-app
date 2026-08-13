"""Qt widgets that draw a bipartite Graph.

Vertices are circles, edge-nodes are squares, and every line on screen is an
incidence joining one of each. Nothing connects two circles directly.
"""

from __future__ import annotations

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from app.core.config import (
    CANVAS_BG,
    DEFAULT_NODE_COLOR,
    EDGE_COLOR,
    EDGE_NODE_COLOR,
    EDGE_NODE_LABEL_COLOR,
    EDGE_NODE_SIZE,
    GROUP_COLORS,
    LABEL_COLOR,
    LAYOUT_SCALE,
    NODE_BORDER,
    NODE_RADIUS,
)
from app.core.graph import EdgeNode, Graph, Vertex, spring_layout


class _Anchored:
    """Drag behaviour shared by anything an incidence line attaches to."""

    def add_incidence(self, item: "IncidenceItem") -> None:
        self.incidences.append(item)

    def edge_offset(self, ux: float, uy: float) -> float:
        """Distance from this item's center to its outline along (ux, uy)."""
        raise NotImplementedError

    def itemChange(self, change, value):  # noqa: N802 (Qt naming)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for incidence in self.incidences:
                incidence.adjust()
        return super().itemChange(change, value)


class NodeItem(_Anchored, QGraphicsEllipseItem):
    """A vertex. Drag it and its incidence lines follow."""

    def __init__(self, vertex: Vertex, radius: float = NODE_RADIUS) -> None:
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.vertex = vertex
        self.radius = radius
        self.incidences: list["IncidenceItem"] = []

        color = QColor(GROUP_COLORS.get(vertex.group or "", DEFAULT_NODE_COLOR))
        self._pen = QPen(QColor(NODE_BORDER), 2)
        self._hover_pen = QPen(QColor("#f2f4f8"), 2)
        self.setBrush(QBrush(color))
        self.setPen(self._pen)
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"{vertex.display}  ({vertex.id})")

        self.label = QGraphicsSimpleTextItem(vertex.display, self)
        self.label.setBrush(QBrush(QColor(LABEL_COLOR)))
        rect = self.label.boundingRect()
        self.label.setPos(-rect.width() / 2, radius + 5)

    def edge_offset(self, ux: float, uy: float) -> float:
        return self.radius

    def hoverEnterEvent(self, event):  # noqa: N802
        self.setPen(self._hover_pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802
        self.setPen(self._pen)
        super().hoverLeaveEvent(event)


class EdgeNodeItem(_Anchored, QGraphicsRectItem):
    """An edge promoted to a node, drawn as a square."""

    def __init__(self, edge: EdgeNode, size: float = EDGE_NODE_SIZE) -> None:
        super().__init__(-size / 2, -size / 2, size, size)
        self.edge = edge
        self.size = size
        self.incidences: list["IncidenceItem"] = []

        self._pen = QPen(QColor(NODE_BORDER), 2)
        self._hover_pen = QPen(QColor("#f2f4f8"), 2)
        self.setBrush(QBrush(QColor(EDGE_NODE_COLOR)))
        self.setPen(self._pen)
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(
            f"{edge.display}  ({edge.arity} members)\n"
            + "\n".join(f"· {m}" for m in sorted(edge.members))
        )

        self.label = QGraphicsSimpleTextItem(edge.display, self)
        self.label.setBrush(QBrush(QColor(EDGE_NODE_LABEL_COLOR)))
        rect = self.label.boundingRect()
        self.label.setPos(-rect.width() / 2, size / 2 + 4)

    def edge_offset(self, ux: float, uy: float) -> float:
        """Exact ray/square intersection, so lines stop on the outline."""
        half = self.size / 2
        ax, ay = abs(ux), abs(uy)
        if ax < 1e-9 or ay < 1e-9:
            return half
        return min(half / ax, half / ay)


class IncidenceItem(QGraphicsPathItem):
    """A line joining an edge-node to one of its member vertices.

    Undirected: membership runs both ways, so the line carries no arrowheads.
    """

    def __init__(self, edge_item: EdgeNodeItem, vertex_item: NodeItem) -> None:
        super().__init__()
        self.source = edge_item
        self.target = vertex_item

        color = QColor(EDGE_COLOR)
        self.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        self.setBrush(QBrush(color))
        self.setZValue(-1)

        edge_item.add_incidence(self)
        vertex_item.add_incidence(self)
        self.adjust()

    def adjust(self) -> None:
        line = QLineF(self.source.pos(), self.target.pos())
        length = line.length()
        if length < 1e-3:
            self.setPath(QPainterPath())
            return

        ux, uy = line.dx() / length, line.dy() / length
        start_off = self.source.edge_offset(ux, uy)
        end_off = self.target.edge_offset(-ux, -uy)
        if start_off + end_off >= length:
            self.setPath(QPainterPath())
            return

        start = self.source.pos() + QPointF(ux * start_off, uy * start_off)
        end = self.target.pos() - QPointF(ux * end_off, uy * end_off)

        path = QPainterPath(start)
        path.lineTo(end)
        self.setPath(path)


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
        self.edge_nodes: dict[str, EdgeNodeItem] = {}
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
        self.edge_nodes = {}

        for vertex in graph.vertices:
            item = NodeItem(vertex)
            x, y = positions.get(vertex.id, (0.5, 0.5))
            item.setPos(x * LAYOUT_SCALE, y * LAYOUT_SCALE)
            self._scene.addItem(item)
            self.nodes[vertex.id] = item

        for edge in graph.valid_edges():
            item = EdgeNodeItem(edge)
            x, y = positions.get(edge.id, (0.5, 0.5))
            item.setPos(x * LAYOUT_SCALE, y * LAYOUT_SCALE)
            self._scene.addItem(item)
            self.edge_nodes[edge.id] = item

        for edge_id, vertex_id, _weight in graph.incidences():
            edge_item = self.edge_nodes.get(edge_id)
            vertex_item = self.nodes.get(vertex_id)
            if edge_item is None or vertex_item is None:
                continue
            self._scene.addItem(IncidenceItem(edge_item, vertex_item))

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

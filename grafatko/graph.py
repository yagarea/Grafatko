"""A wrapper for working with graphs that can be drawn."""

from __future__ import annotations

from abc import *
from ast import literal_eval
from collections import defaultdict
from math import radians, pi

from grafatko.color import *
from grafatko.utilities import *


class Node:
    """A class for working with nodes of a graph."""

    def __init__(self, label=None):
        self.adjacent: Set[Vertex] = set()
        self.label = label

    def get_label(self):
        """Return the label of the node."""
        return self.label

    def get_adjacent_vertices(self) -> Set[Vertex]:
        """Returns a set of vertices adjacent to this one."""
        return self.adjacent

    def get_adjacent_nodes(self) -> List[Node]:
        """Returns a list of nodes adjacent to this one."""
        return [v[1] for v in self.adjacent]

    def is_adjacent_to(self, node: Node) -> bool:
        """Return True if this node is adjacent to the specified node."""
        return node in self.get_adjacent_nodes()

    def _remove_adjacent_node(self, node: Node):
        """Remove an adjacent node (if it's there). Package-private."""
        self.adjacent = {v for v in self.adjacent if v[1] is not node}

    def _add_adjacent(self, vertex: Vertex):
        """Add an adjacent vertex. Package-private."""
        self.adjacent.add(vertex)


class Vertex:
    """A class for representing a vertex."""

    def __init__(self, node_from: Node, node_to: Node, weight=1):
        self.node_from = node_from
        self.node_to = node_to
        self.weight = weight

    def __setitem__(self, i: int, value: Node):
        if i == 0:
            self.node_from = value
        elif i == 1:
            self.node_to = value
        else:
            raise IndexError("Only indexes 0 and 1 are supported.")

    def __getitem__(self, i: int):
        if i == 0:
            return self.node_from
        elif i == 1:
            return self.node_to
        else:
            raise IndexError("Only indexes 0 and 1 are supported.")

    def get_weight(self) -> float:
        """Return the weight of the vertex."""
        return self.weight

    def set_weight(self, value: float):
        """Set the weight of the vertex."""
        self.weight = value


@dataclass
class Graph:
    """A class for working with graphs."""

    directed: bool = False
    weighted: bool = False

    nodes: List[Node] = field(default_factory=list)
    vertices: List[Vertex] = field(default_factory=list)

    # a component array that gets recalculated on each destructive graph operation
    # takes O(n^2) to rebuild, but O(1) to check components, so it's better for us
    components: List[Set[Node]] = None

    # to know which kind of vertices and nodes to create
    vertex_class = Vertex
    node_class = Node

    def recalculate_components(function):
        """A decorator for rebuilding the components of the graph."""

        def wrapper(self, *args, **kwargs):
            # first add/remove vertex/node/...
            function(self, *args, **kwargs)

            self.components = []

            for node in self.get_nodes():
                # the current set of nodes that we know are reachable from one another
                component = set([node] + node.get_adjacent_nodes())

                i = 0
                while i < len(self.components):
                    if len(self.components[i].intersection(component)) != 0:
                        component |= self.components.pop(i)
                    else:
                        i += 1

                self.components.append(component)

        return wrapper

    def get_weakly_connected(self, *args: Sequence[Node]) -> Set[Node]:
        """Return a set of all nodes that are weakly connected to any node from the
        given sequence."""
        nodes = set()

        for node in args:
            for component in self.components:
                if node in component:
                    nodes |= component

        return nodes

    def weakly_connected(self, n1: Node, n2: Node) -> bool:
        """Return True if the nodes are weakly connected, else False."""
        for component in self.components:
            a = n1 in component
            b = n2 in component

            if a and b:
                return True
            elif a or b:
                return False

    def is_directed(self) -> bool:
        """Return True if the graph is directed, else False."""
        return self.directed

    def set_directed(self, directed: bool):
        """Set, whether the graph is directed or not."""
        # if we're converting to undirected, make all current vertices go both ways
        if self.is_directed():
            for node in self.get_nodes():
                for neighbour in node.get_adjacent_nodes():
                    if node is neighbour:
                        self.remove_vertex(node, neighbour)  # no loops allowed >:C
                    else:
                        self.add_vertex(neighbour, node)

        self.directed = directed

    def is_weighted(self) -> bool:
        """Return True if the graph is weighted and False otherwise."""
        return self.weighted

    def set_weighted(self, value: bool):
        """Set, whether the graph is weighted or not."""
        self.weighted = value

    def get_weight(self, n1: Node, n2: Node) -> Optional[Union[int, float]]:
        """Return the weight of the specified vertex (and None if they're not connected)."""
        for vertex in self.get_vertices():
            if n1 is vertex[0] and n2 is vertex[1]:
                return vertex.get_weight()

    def get_nodes(self) -> List[Node]:
        """Return a list of nodes of the graph."""
        return self.nodes

    def get_vertices(self) -> List[Vertex]:
        """Return a list of vertices of the graph."""
        return self.vertices

    @recalculate_components
    def add_node(self, node: Node):
        """Add a new node to the graph."""
        self.nodes.append(node)

    def reorient(self):
        """Change the orientation of all vertices."""
        # for each pair of nodes
        for i, n1 in enumerate(self.get_nodes()):
            for n2 in self.get_nodes()[i:]:
                # change the direction, if there is only one
                if bool(n1.is_adjacent_to(n2)) != bool(n2.is_adjacent_to(n1)):  # xor
                    self.toggle_vertex(n1, n2)
                    self.toggle_vertex(n2, n1)

    def complement(self):
        """Complement the graph."""
        # for each pair of nodes
        for i, n1 in enumerate(self.get_nodes()):
            for n2 in self.get_nodes()[i:]:
                self.toggle_vertex(n1, n2)

                # also toggle the other way, if it's directed
                # node that I didn't deliberately put 'and n1 is not n2' here, since
                # they're special and we usually don't want them
                if self.is_directed():
                    self.toggle_vertex(n2, n1)

    @recalculate_components
    def remove_node(self, node: Node):
        """Removes the node from the graph."""
        # remove it from the list of nodes
        self.nodes.remove(node)

        # remove all vertices that contain it
        i = 0
        while i < len(self.vertices):
            v = self.vertices[i]
            if node is v[0] or node is v[1]:
                del self.vertices[i]
            else:
                i += 1

        # remove this node from all nodes' adjacent
        for other in self.get_nodes():
            other._remove_adjacent_node(node)

    @recalculate_components
    def add_vertex(self, n1: Node, n2: Node, weight: Optional[float] = 1):
        """Adds a vertex from node n1 to node n2 (and vice versa, if it's not directed).
        Only does so if the given vertex doesn't already exist and can be added (if, for
        example the graph is not directed and the node wants to point to itself)."""
        # prevent loops in undirected graphs and duplication
        if (n1 is n2 and not self.is_directed()) or n1.is_adjacent_to(n2):
            return

        # create the object, adding it to vertices
        vertex = self.vertex_class(n1, n2, weight)
        self.vertices.append(vertex)
        n1._add_adjacent(vertex)

        # add it one/both ways, depending on whether the graph is directed or not
        if not self.is_directed():
            vertex = self.vertex_class(n2, n1, weight)
            self.vertices.append(vertex)
            n2._add_adjacent(vertex)

    @recalculate_components
    def remove_vertex(self, n1: Node, n2: Node):
        """Removes a vertex from node n1 to node n2 (and vice versa, if it's not 
        directed). Only does so if the given vertex exists."""
        # remove it one-way if the graph is directed and both if it's not
        self.vertices = [
            v
            for v in self.vertices
            if not (
                (n1 is v[0] and n2 is v[1])
                or (not self.is_directed() and n2 is v[0] and n1 is v[1])
            )
        ]

        # see above comment
        n1._remove_adjacent_node(n2)
        if not self.is_directed():
            n2._remove_adjacent_node(n1)

    def toggle_vertex(self, n1: Node, n2: Node):
        """Toggles a connection between two nodes."""
        if n1.is_adjacent_to(n2):
            self.remove_vertex(n1, n2)
        else:
            self.add_vertex(n1, n2)

    @classmethod
    def from_string(cls, string: str) -> type(cls):
        """Generates the graph from a given string."""
        graph = None
        node_dictionary = {}

        # add each of the nodes of the given line to the graph
        for line in filter(lambda x: len(x) != 0 or x[0] != "#", string.splitlines()):
            parts = line.strip().split()

            # initialize the graph from the first line, if it hasn't been done yet
            if graph is None:
                directed = parts[1] in ("->", "<-")
                weighted = len(parts) == 3 + directed

                graph = cls(directed=directed, weighted=weighted)

            # the formats are either 'A B' or 'A <something> B'
            node_names = (parts[0], parts[1 + directed])

            # if weight is present, the formats are:
            # - 'A B num' for undirected graphs
            # - 'A <something> B num' for directed graphs
            weight = 0 if not weighted else literal_eval(parts[2 + directed])

            # create node objects for each of the names (if it hasn't been done yet)
            for name in node_names:
                if name not in node_dictionary:
                    # add it to graph with default values
                    node_dictionary[name] = cls.node_class(label=name)
                    graph.add_node(node_dictionary[name])

            # get the node objects from the names
            n1, n2 = node_dictionary[node_names[0]], node_dictionary[node_names[1]]

            # possibly switch places for a reverse arrow
            if parts[1] == "<-":
                n1, n2 = n2, n1

            # add the vertex
            graph.add_vertex(n1, n2, weight)

        return graph

    def to_string(self) -> str:
        """Exports the graph, returning the string."""
        string = ""

        counter = 0  # for naming nodes that don't have a label
        added = {}

        for i, n1 in enumerate(self.get_nodes()):
            for n2 in self.get_nodes()[i + 1 :]:
                # only add a vertex from an undirected graph once
                if not self.is_directed() and id(n1) > id(n2):
                    continue

                # TODO make this the code less shitty
                n1_label = n1.get_label()
                if n1_label is None:
                    if n1 not in added:
                        added[n1] = str(counter := counter + 1)
                    n1_label = added[n1]

                n2_label = n2.get_label()
                if n2_label is None:
                    if n2 not in added:
                        added[n2] = str(counter := counter + 1)
                    n2_label = added[n2]

                # TODO: simplify this code
                print(":ahoj")
                if n1.is_adjacent_to(n2):
                    print(self.get_weight(n1, n2))
                    string += (
                        n1_label
                        + (" -> " if self.is_directed() else " ")
                        + n2_label
                        + (
                            (" " + str(self.get_weight(n1, n2)))
                            if self.is_weighted()
                            else ""
                        )
                        + "\n"
                    )

                if n2.is_adjacent_to(n1) and self.is_directed():
                    string += (
                        n1_label
                        + (" <- " if self.is_directed() else " ")
                        + n2_label
                        + (
                            (" " + str(self.get_weight(n2, n1)))
                            if self.is_weighted()
                            else ""
                        )
                        + "\n"
                    )

            return string


class Drawable(ABC):
    """Something that can be drawn on the PyQt5 canvas."""

    def __init__(self, pen: Pen = None, brush: Brush = None):
        if pen is None:
            pen = Pen(DEFAULT, Qt.SolidLine)
        if brush is None:
            brush = Brush(DEFAULT, Qt.SolidPattern)

        self.pen = pen
        self.brush = brush

    @abstractmethod
    def draw(self, painter: QPainter, palette: QPalette, *args, **kwargs):
        """A method that draws the object on the canvas. Takes the painter to paint on
        and the palette to generate relative colors from."""


class DrawableNode(Drawable, Node):
    def __init__(self, position=Vector(0, 0), *args, **kwargs):
        self.position: Vector = position

        Drawable.__init__(self)
        Node.__init__(self, *args, **kwargs)

        self.forces: List[Vector] = []

        # for information about being dragged
        # at that point, no forces act on it
        # it's the offset from the mouse when the drag started
        self.drag: Optional[Vector] = None

        # whether it's currently selected or not
        self.selected = False

    def get_position(self) -> Vector:
        """Return the position of the node."""
        return self.position

    def set_position(self, position: Vector, override_drag: bool = False):
        """Set the position of the node (accounted for drag). The override_drag option
        moves the node to the position even if it's currently being dragged."""
        if override_drag and self.is_dragged():
            self.drag += self.position - position
        else:
            self.position = position - (self.drag or Vector(0, 0))

    def start_drag(self, mouse_position: Vector):
        """Start dragging the node, setting its drag offset from the mouse."""
        self.drag = mouse_position - self.get_position()

    def stop_drag(self) -> Vector:
        """Stop dragging the node."""
        self.drag = None

    def is_dragged(self) -> bool:
        """Return true if the node is currently in a dragged state."""
        return self.drag is not None

    def select(self):
        """Mark the node as selected."""
        self.brush.color = SELECTED
        self.__set_selected(True)

    def deselect(self):
        """Mark the node as not selected."""
        self.brush.color = DEFAULT
        self.__set_selected(False)

    def __set_selected(self, value: bool):
        """Set the selected status of the node."""
        self.selected = value

    def is_selected(self) -> bool:
        """Return, whether the node is selected or not."""
        return self.selected

    def add_force(self, force: Vector):
        """Adds a force that is acting upon the node to the force list."""
        self.forces.append(force)

    def evaluate_forces(self):
        """Evaluates all of the forces acting upon the node and moves it accordingly.
        Node that they are only applied if the note is not being dragged."""
        while len(self.forces) != 0:
            force = self.forces.pop()

            if not self.is_dragged():
                self.position += force

    def clear_forces(self):
        """Clear all of the forces from the node."""
        self.forces = []

    def draw(self, painter: QPainter, palette: QPalette, draw_label=False):
        painter.setBrush(self.brush(palette))
        painter.setPen(self.pen(palette))

        # the radius is 1
        painter.drawEllipse(QPointF(*self.position), 1, 1)

        # possibly draw the label of the node
        if draw_label and self.get_label() is not None:
            label = self.get_label()
            mid = self.get_position()

            # get the rectangle that surrounds the label
            r = QFontMetrics(painter.font()).boundingRect(label)
            scale = 1.9 / Vector(r.width(), r.height()).magnitude()

            # draw it on the screen
            size = Vector(r.width(), r.height()) * scale
            rect = QRectF(*(mid - size / 2), *size)

            painter.save()

            painter.setBrush(Brush(BACKGROUND)(palette))
            painter.setPen(Pen(BACKGROUND)(palette))

            # translate to top left and scale down to draw the actual text
            painter.translate(rect.topLeft())
            painter.scale(scale, scale)

            painter.drawText(
                QRectF(0, 0, rect.width() / scale, rect.height() / scale),
                Qt.AlignCenter,
                label,
            )

            painter.restore()


class DrawableVertex(Drawable, Vertex):
    font: QFont = None  # the font that is used to draw the weights

    arrowhead_size: Final[float] = 0.5  # how big is the head triangle
    arrow_separation: Final[float] = pi / 7  # how far apart are two-way vertices
    loop_arrowhead_angle: Final[float] = -30.0  # an angle for the head in a loop

    # possible TODO: compute this programatically
    text_scale: Final[float] = 0.04  # the constant by which to scale down the font

    def __init__(self, *args, **kwargs):
        Drawable.__init__(self)
        Vertex.__init__(self, *args, **kwargs)

        self.brush = Brush.empty()

    def draw(
        self, painter: QPainter, palette: QPalette, directed: bool, weighted: bool
    ):
        """Also takes, whether the graph is directed or not."""
        self.font = painter.font()

        painter.setPen(self.pen(palette))
        painter.setBrush(self.brush(palette))

        # special case for a loop
        if self[0] is self[1]:
            # draw the ellipse that symbolizes a loop
            center = self[0].get_position() - Vector(0.5, 1)
            painter.drawEllipse(QPointF(*center), 0.5, 0.5)

            # draw the head of the loop arrow
            head_direction = Vector(0, 1).rotated(radians(self.loop_arrowhead_angle))
            self.__draw_arrow_tip(center + Vector(0.5, 0), head_direction, painter)
        else:
            start, end = self.__get_position(directed)

            # draw the line
            painter.drawLine(QPointF(*start), QPointF(*end))

            # draw the head of a directed arrow, which is an equilateral triangle
            if directed:
                self.__draw_arrow_tip(end, end - start, painter)

        # draw the weight
        if weighted:
            # set the color to be the same as the vertex
            color = self.pen.color(palette)
            painter.setBrush(QBrush(color, Qt.SolidPattern))

            painter.save()

            # draw the bounding box
            rect = self.__get_weight_box(directed)
            painter.drawRect(rect)

            scale = self.text_scale

            # translate to top left and scale down to draw the actual text
            painter.translate(rect.topLeft())
            painter.scale(scale, scale)

            painter.setPen(Pen(color=BACKGROUND)(palette))

            painter.drawText(
                QRectF(0, 0, rect.width() / scale, rect.height() / scale),
                Qt.AlignCenter,
                str(self.get_weight()),
            )

            painter.restore()

    def __get_weight_box(self, directed) -> QRectF:
        """Get the rectangle that the weight of n1->n2 vertex will be drawn in."""
        # get the rectangle that bounds the text (according to the current font metric)
        metrics = QFontMetrics(self.font)
        r = metrics.boundingRect(str(self.get_weight()))

        # get the mid point of the weight box, depending on whether it's a loop or not
        if self[0] is self[1]:
            # the distance from the center of the node to the side of the ellipse that
            # is drawn to symbolize the loop
            offset = Vector(0.5, 1) + Vector(0.5, 0).rotated(radians(45))
            mid = self[0].get_position() - offset
        else:
            mid = Vector.average(self.__get_position(directed))

        # scale it down by text_scale before returning it
        # if width is smaller then height, set it to height
        height = r.height()
        width = r.width() if r.width() >= height else height

        size = Vector(width, height) * self.text_scale
        return QRectF(*(mid - size / 2), *size)

    def __draw_arrow_tip(self, pos: Vector, direction: Vector, painter: QPainter):
        """Draw the tip of the vertex (as a triangle)."""
        uv = direction.unit()

        # the brush color is given by the current pen
        painter.setBrush(QBrush(painter.pen().color(), Qt.SolidPattern))
        painter.drawPolygon(
            QPointF(*pos),
            QPointF(*(pos + (-uv).rotated(radians(30)) * self.arrowhead_size)),
            QPointF(*(pos + (-uv).rotated(radians(-30)) * self.arrowhead_size)),
        )

    def __get_position(self, directed: bool) -> Tuple[Vector, Vector]:
        """Return the starting and ending position of the vertex on the screen."""
        # positions of the nodes
        from_pos = Vector(*self[0].get_position())
        to_pos = Vector(*self[1].get_position())

        # unit vector from n1 to n2
        uv = (to_pos - from_pos).unit()

        # start and end of the vertex to be drawn
        start = from_pos + uv
        end = to_pos - uv

        # if the graph is directed and a vertex exists that goes the other way, we
        # have to move the start end end so the vertexes don't overlap
        if directed and self[1].is_adjacent_to(self[0]):
            start = start.rotated(self.arrow_separation, from_pos)
            end = end.rotated(-self.arrow_separation, to_pos)

        return start, end


class DrawableGraph(Drawable, Graph):
    show_labels: bool = False  # whether or not to show the labels of nodes

    # a dictionary for calculating the distance from a root node
    # used in displaying the graph as a tree
    distance_from_root = {}
    root = None

    vertex_class = DrawableVertex
    node_class = DrawableNode

    def __init__(self, *args, **kwargs):
        Drawable.__init__(self)
        Graph.__init__(self, *args, **kwargs)

    def draw(self, painter: QPainter, palette: QPalette):
        """Draw the entire graph."""
        for vertex in self.get_vertices():
            vertex.draw(painter, palette, self.is_directed(), self.is_weighted())

        # then, draw all nodes
        for node in self.get_nodes():
            node.draw(painter, palette, self.show_labels)

    def get_selected(self) -> List[DrawableNode]:
        """Yield all currently selected nodes."""
        return [node for node in self.get_nodes() if node.is_selected()]

    def set_show_labels(self, value: bool):
        """Whether to show the node labels or not."""
        self.show_labels = value

    def recalculate_distance_to_root(function):
        """A decorator for recalculating the distance from the root node to the rest of
        the graph."""

        def wrapper(self, *args, **kwargs):
            # first add/remove vertex/node/whatever
            function(self, *args, **kwargs)

            self.distance_from_root = {}

            # don't do anything if the root
            if self.get_root() is None:
                return

            # else run the BFS to calculate the distances
            queue = [(self.root, 1)]
            closed = set()
            self.distance_from_root[0] = [self.root]

            while len(queue) != 0:
                current, distance = queue.pop(0)

                for adjacent in current.get_adjacent_nodes():
                    if adjacent not in closed:
                        if distance not in self.distance_from_root:
                            self.distance_from_root[distance] = []

                        queue.append((adjacent, distance + 1))
                        self.distance_from_root[distance].append(adjacent)

                closed.add(current)

        return wrapper

    @recalculate_distance_to_root
    def set_root(self, node: DrawableNode):
        """Set a node as the root of the tree."""
        self.root = node

    def get_root(self) -> Optional[DrawableNode]:
        """Return the root of the tree (or None if there is none)."""
        return self.root

    @recalculate_distance_to_root
    def add_vertex(self, *args, **kwargs):
        super().add_vertex(*args, **kwargs)

    @recalculate_distance_to_root
    def remove_vertex(self, *args, **kwargs):
        super().remove_vertex(*args, **kwargs)

    @recalculate_distance_to_root
    def add_node(self, *args, **kwargs):
        super().add_node(*args, **kwargs)

    @recalculate_distance_to_root
    def remove_node(self, node, **kwargs):
        # check, if we're not removing the root; if we are, act accordingly
        if node is self.root:
            self.set_root(None)

        super().remove_node(node, **kwargs)

    def select_all(self):
        """Select all nodes."""
        for node in self.get_nodes():
            node.select()

    def deselect_all(self):
        """Deselect all nodes."""
        for node in self.get_nodes():
            node.deselect()

    def node_at_position(self, position: Vector) -> Optional[DrawableNode]:
        """Returns a Node if there is one at the given position, else None."""
        for node in self.get_nodes():
            if position.distance(node.get_position()) <= 1:
                return node

    def get_distance_from_root(self) -> Dict[int, List[DrawableNode]]:
        """Return the resulting dictionary of a BFS ran from the root node."""
        return self.distance_from_root

    def vertex_at_position(self, position: Vector) -> Optional[Vertex]:
        """Returns a vertex if there is one at the given position, else None."""
        for vertex in self.get_vertices():
            if vertex.__get_weight_box(self.is_directed()).contains(*position):
                return vertex

    def to_asymptote(self) -> str:
        # TODO possible export option
        pass

    def to_tikz(self) -> str:
        # TODO possible export option
        pass

    def to_svg(self) -> str:
        # TODO possible export option
        pass
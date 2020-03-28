import sys

# CLEAN CODE :)
from typing import *


# QT
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from qtmodern import styles  # themes


# UTILITIES
from functools import partial
from random import random
from math import radians

from graph import *
from utilities import *
import webbrowser  # opening the browser


@dataclass
class CanvasTransformation:
    """A class for working with the current transformation of the canvas."""

    # initial scale and transformation
    scale: float = 20
    translation: float = Vector(0, 0)

    def transform_painter(self, painter: QPainter):
        """Translate the painter according to the current canvas state."""
        painter.translate(*self.translation)
        painter.scale(self.scale, self.scale)

    def apply(self, point: Vector):
        """Apply the current canvas transformation on the point."""
        return (point - self.translation) / self.scale

    def zoom(self, position: Vector, delta: float):
        """Zoom in/out."""
        # adjust the scale
        previous_scale = self.scale
        self.scale *= 2 ** delta  # a little ad-hoc way to smoothly scale

        # adjust translation so the x and y of the mouse stay in the same spot
        self.translation -= position * (self.scale - previous_scale)


@dataclass
class Mouse:
    """A small class for storing information about the mouse."""

    transformation: CanvasTransformation

    position: Union[Vector, None] = None  # it position on canvas

    # for storing where the last left click occurred
    left_pressed: bool = None
    right_pressed: bool = None

    def move(self, event):
        """Update the mouse coordinates."""
        self.position = Vector(event.pos().x(), event.pos().y())

    def get_position(self):
        """Get the current mouse position."""
        return self.transformation.apply(self.position)

    def left(self):
        """Return True if the left mouse button is pressed."""
        return self.left_pressed is not None

    def right(self):
        """Return True if the right mouse button is pressed."""
        return self.right_pressed is not None

    def press(self, event):
        """Update mouse status when mouse is pressed."""
        self.move(event)
        if event.button() == Qt.LeftButton:
            self.left_pressed = self.get_position()
        elif event.button() == Qt.RightButton:
            self.right_pressed = self.get_position()

    def release(self, event):
        """Update mouse status when mouse is released."""
        self.move(event)
        if event.button() == Qt.LeftButton:
            self.left_pressed = None
        elif event.button() == Qt.RightButton:
            self.right_pressed = None


class Canvas(QWidget):
    # WIDGET OPTIONS
    lighten_coefficient = 10  # how much lighter/darker the canvas is (to background)

    # whether the forces are enabled/disabled
    forces: bool = True

    # _ because self.repulsion gets self as the first argument
    repulsion = lambda _, distance: (1 / distance) ** 2
    attraction = lambda _, distance: -(distance - 8) / 10

    def __init__(self, parent=None):
        super().__init__(parent)

        # GRAPH
        self.graph = DrawableGraph()
        self.selected_nodes = []

        # CANVAS STUFF
        self.transformation = CanvasTransformation()

        # MOUSE
        self.mouse = Mouse(self.transformation)
        self.setMouseTracking(True)

        # timer that runs the simulation (60 times a second... once every ~= 17ms)
        QTimer(self, interval=17, timeout=self.update).start()

    def update(self, *args):
        """A function that gets periodically called to update the canvas."""
        # only move the nodes when forces are enabled
        if self.forces:
            for i, n1 in enumerate(self.graph.get_nodes()):
                for n2 in self.graph.get_nodes()[i + 1 :]:
                    # only apply force, if n1 and n2 are weakly connected
                    if not self.graph.weakly_connected(n1, n2):
                        continue

                    d = n1.get_position().distance(n2.get_position())

                    # if they are on top of each other, nudge one of them slightly
                    if d == 0:
                        n1.add_force(Vector(random(), random()))
                        continue

                    # unit vector from n1 to n2
                    uv = (n2.get_position() - n1.get_position()).unit()

                    # the size of the repel force between the two nodes
                    fr = self.repulsion(d)

                    # add a repel force to each of the nodes, in the opposite directions
                    n1.add_force(-uv * fr)
                    n2.add_force(uv * fr)

                    # if they are also connected, add the attraction force
                    # the direction does not matter -- it would look weird for directed
                    if self.graph.is_vertex(n1, n2) or self.graph.is_vertex(n2, n1):
                        fa = self.attraction(d)

                        n1.add_force(-uv * fa)
                        n2.add_force(uv * fa)

                n1.evaluate_forces()

        super().update(*args)

    def paintEvent(self, event):
        """Paints the board."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # clip
        painter.setClipRect(0, 0, self.width(), self.height())

        # paint the background
        self.paint_background(painter)

        # transform the coordinates according to the current state of the canvas
        self.transformation.transform_painter(painter)

        # paint the graph
        self.graph.draw(painter, self.palette())

    def paint_background(self, painter: QPainter):
        """Paint the background of the widget."""
        # color shenanigans
        default_background = self.palette().color(QPalette.Background)

        background_color = default_background.lighter(100 + self.lighten_coefficient)
        border_color = default_background.darker(100 + self.lighten_coefficient)

        painter.setBrush(QBrush(background_color, Qt.SolidPattern))
        painter.setPen(QPen(border_color, Qt.SolidLine))

        # draw background
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

    def mouseMoveEvent(self, event):
        """Is called when the mouse is moved across the canvas."""
        self.mouse.move(event)

        # update dragged nodes
        for node in self.graph.get_nodes():
            if node.is_dragged():
                # TODO also drag weakly connected nodes on shift press
                node.set_position(self.mouse.get_position())

    def mouseReleaseEvent(self, event):
        """Is called when a mouse button is released."""
        self.mouse.release(event)

        # stop dragging the nodes
        for node in self.selected_nodes:
            node.stop_drag()

    def wheelEvent(self, event):
        """Is called when the mouse wheel is turned."""
        delta = radians(event.angleDelta().y() / 8)

        if self.shift_pressed():
            if len(self.selected_nodes) != 0:
                self.rotate_about_selected(delta)
        else:
            self.transformation.zoom(self.mouse.get_position(), delta)

    def rotate_about_selected(self, angle: float):
        """Rotate about the average of selected nodes by the angle."""
        nodes = self.selected_nodes

        pivot = sum([n.get_position() for n in nodes], Vector(0, 0)) / len(nodes)

        # rotate the nodes that are weakly connected to any of the selected nodes
        for node in self.graph.get_nodes():
            for selected_node in nodes:
                if self.graph.weakly_connected(node, selected_node):
                    node.set_position(node.get_position().rotated(angle, pivot))

    def mousePressEvent(self, event):
        """Called when a left click is registered."""
        self.mouse.press(event)

        pressed = self.graph.node_at_position(self.mouse.get_position())

        if self.mouse.left():
            # if we hit a node, start dragging the nodes
            if pressed is not None:
                self.select(pressed)

                # start dragging the nodes
                for node in self.selected_nodes:
                    node.start_drag(self.mouse.get_position())
            else:
                self.deselect()

        elif self.mouse.right():
            # if there isn't a node at the position, create a new one
            if pressed is None:
                pressed = DrawableNode(self.mouse.get_position())

                self.graph.add_node(pressed)
                self.select(pressed)

            # if some nodes are selected, connect them to the pressed node
            for selected_node in self.selected_nodes:
                self.graph.toggle_vertex(selected_node, pressed)

    def select(self, node: DrawableNode):
        """Select the given node."""
        # only select one when shift is not pressed
        if not self.shift_pressed():
            self.deselect()

        self.selected_nodes.append(node)

    def deselect(self):
        """Deselect all nodes."""
        self.selected_nodes = []

    def shift_pressed(self):
        """Return True if shift is currently being pressed."""
        return QApplication.keyboardModifiers() == Qt.ShiftModifier

    def get_graph(self):
        """Get the current graph."""
        return self.graph

    def set_forces(self, value: bool):
        """Enable/disable the forces that act on the nodes."""
        self.forces = value


class GraphVisualizer(QMainWindow):
    def __init__(self):
        # TODO: command line argument parsing (--dark and stuff)
        # TODO: hide toolbar with f-10 or something

        super().__init__()

        # Widgets
        ## Canvas (main widget)
        self.canvas = Canvas(parent=self)
        self.canvas.setMinimumSize(100, 200)  # reasonable minimum size
        self.setCentralWidget(self.canvas)

        ## Top menu bar
        self.menubar = self.menuBar()

        self.file_menu = self.menubar.addMenu("&File")
        self.file_menu.addAction(QAction("&Import", self))
        self.file_menu.addAction(QAction("&Export", self))
        self.file_menu.addSeparator()
        self.file_menu.addAction(QAction("&Quit", self, triggered=exit))

        self.preferences_menu = self.menubar.addMenu("&Preferences")
        self.preferences_menu.addAction(
            QAction(
                "&Dark Theme",
                self,
                checkable=True,
                triggered=partial(
                    lambda x, y: styles.dark(x) if y else styles.light(x),
                    QApplication.instance(),
                ),
            )
        )

        self.help_menu = self.menubar.addMenu("&Help")
        self.help_menu.addAction(QAction("&Manual", self))
        self.help_menu.addAction(QAction("&About", self))
        self.help_menu.addAction(
            QAction(
                "&Source Code",
                self,
                triggered=partial(
                    # TODO: make non-blocking
                    webbrowser.open,
                    "https://github.com/xiaoxiae/GraphVisualizer",
                ),
            )
        )

        ## Dock
        # TODO: shrink after leaving the dock
        # TODO: disable vertical resizing
        self.dock_menu = QDockWidget("Settings", self)
        self.dock_menu.setAllowedAreas(Qt.BottomDockWidgetArea)  # float bottom
        self.dock_menu.setFeatures(QDockWidget.DockWidgetFloatable)  # hide close button

        self.dock_widget = QWidget()
        layout = QGridLayout()

        ### Graph options
        layout.addWidget(QLabel(self, text="Graph"), 0, 0)

        layout.addWidget(
            QCheckBox(
                "directed",
                self,
                toggled=lambda value: self.canvas.get_graph().set_directed(value),
            ),
            1,
            0,
        )

        layout.addWidget(
            QCheckBox(
                "weighted",
                self,
                toggled=lambda value: self.canvas.get_graph().set_weighted(value),
            ),
            2,
            0,
        )
        layout.addWidget(QCheckBox("multi", self), 3, 0)

        ### Visual options
        layout.addWidget(QLabel(self, text="Visual"), 0, 1)

        layout.addWidget(QCheckBox("labels", self), 1, 1)

        layout.addWidget(
            QCheckBox(
                "gravity", self, toggled=lambda value: self.canvas.set_forces(value),
            ),
            2,
            1,
        )

        ### Graph actions
        layout.addWidget(QLabel(self, text="Actions"), 0, 2)
        layout.addWidget(QPushButton("complement", self), 1, 2)
        layout.addWidget(QPushButton("reorient", self), 2, 2)

        self.dock_widget.setLayout(layout)

        ### Set the dock menu as the dock widget for the app
        self.dock_menu.setWidget(self.dock_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_menu)

        # WINDOW SETTINGS
        self.show()


app = QApplication(sys.argv)
ex = GraphVisualizer()
sys.exit(app.exec_())

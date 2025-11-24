"""
gui/window.py
-------------

PyQt5 GUI layer for the Delivery Route Optimizer.

- Tab 1: "Optimizer"
    - Algorithm selection (NN / NN + 2-opt / BF)
    - Run button
    - Manage Locations (with address/postcode search)
    - Text output (route, distance, execution time)
    - Embedded map (folium HTML inside QWebEngineView)

- Tab 2: "Algorithm Evaluation"
    - Button to generate performance graph
    - Graph image (execution_time.png) comparing algorithms

The GUI does NOT implement algorithms itself.
It talks to a RouteOptimizerApp controller instance (from main.py).
"""

import os
import sys
from typing import Dict

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTextEdit,
    QMessageBox,
    QSplitter,
    QSizePolicy,
    QTabWidget,
    QDialog,
    QListWidget,
    QLineEdit,
    QFormLayout,
    QDialogButtonBox,
)




from PyQt5.QtWidgets import QHBoxLayout, QLabel
from PyQt5.QtGui import QPixmap, QFont




from geopy.geocoders import Nominatim

from src.models.location import Location
from src.utils.benchmark import benchmark_algorithms



# =====================================================================
# Location Manager Dialog
# =====================================================================

class LocationManagerDialog(QDialog):
    """
    Popup dialog for viewing / adding / removing locations.

    Features:
    - Shows existing locations in a list.
    - Allows deletion of non-depot locations.
    - Allows adding a new location using:
        - Address/postcode search (via geopy Nominatim)
        - Name, latitude, longitude fields

    The dialog directly modifies the locations dict passed in.
    """

    def __init__(self, locations: Dict[str, Location], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Locations")
        self.locations = locations  # shared with controller

        # Widgets we need later
        self.list_widget = None
        self.search_edit = None
        self.name_edit = None
        self.lat_edit = None
        self.lon_edit = None

        self._build_ui()      # all the layout / widgets go here
        self.refresh_list()   # populate the list once

    def _build_ui(self):
        # Create and lay out all widgets for the dialog
        main_layout = QVBoxLayout(self)

        # --- List of existing locations --------------------------------
        main_layout.addWidget(QLabel("Existing locations:"))

        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)

        # --- Form for adding a new location ----------------------------
        form_layout = QFormLayout()

        self.search_edit = QLineEdit()
        form_layout.addRow("Address / Postcode:", self.search_edit)

        search_button = QPushButton("Search address/postcode")
        search_button.clicked.connect(self.lookup_address)
        form_layout.addRow("", search_button)

        self.name_edit = QLineEdit()
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Latitude:", self.lat_edit)
        form_layout.addRow("Longitude:", self.lon_edit)

        main_layout.addLayout(form_layout)

        # --- Delete button ---------------------------------------------
        delete_button = QPushButton("Delete selected (non-Depot)")
        delete_button.clicked.connect(self.delete_selected)
        main_layout.addWidget(delete_button)

        # --- OK / Cancel buttons ---------------------------------------
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        self.refresh_list()

    # ------------------------------------------------------------------
    def refresh_list(self):
        """Refresh the list widget from current locations dict."""
        self.list_widget.clear()
        for name in self.locations.keys():
            self.list_widget.addItem(name)

    # ------------------------------------------------------------------
    def delete_selected(self):
        """Delete the currently selected location (but not Depot)."""
        item = self.list_widget.currentItem()
        if not item:
            return

        name = item.text()
        if name == "Depot":
            QMessageBox.warning(self, "Not allowed", "You cannot delete the Depot.")
            return

        del self.locations[name]
        self.refresh_list()

    # ------------------------------------------------------------------
    def lookup_address(self):
        """
        Use geopy Nominatim to convert an address/postcode into
        latitude/longitude. This makes the dialog user-friendly.
        """
        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "No query", "Please enter an address or postcode.")
            return

        geolocator = Nominatim(user_agent="delivery_route_optimizer")
        try:
            location = geolocator.geocode(query, timeout=10)
        except Exception as e:
            QMessageBox.critical(self, "Geocoding error", str(e))
            return

        if location is None:
            QMessageBox.warning(self, "Not found", "Could not find that location.")
            return

        # Auto-fill lat/lon
        self.lat_edit.setText(str(location.latitude))
        self.lon_edit.setText(str(location.longitude))

        # Suggest a name if empty
        if not self.name_edit.text().strip():
            self.name_edit.setText(location.address.split(",")[0])

    # ------------------------------------------------------------------
    def accept(self):
        """
        When OK is pressed:
        - If a new location is entered, validate and add it.
        - Deletions have already been applied.
        """
        name = self.name_edit.text().strip()
        lat_text = self.lat_edit.text().strip()
        lon_text = self.lon_edit.text().strip()

        if name:
            if name in self.locations:
                QMessageBox.warning(self, "Name exists", "That name already exists.")
                return
            try:
                lat = float(lat_text)
                lon = float(lon_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid", "Latitude and Longitude must be numbers.")
                return

            self.locations[name] = Location(name, lat, lon)

        super().accept()


# =====================================================================
# MainWindow – two-tab dashboard
# =====================================================================

class MainWindow(QMainWindow):
    """
    Main PyQt5 window.

    It receives a RouteOptimizerApp instance (from main.py) which
    handles algorithm execution and stores the current locations.

    The GUI is responsible only for:
    - showing controls
    - triggering app.run(mode)
    - displaying results and maps
    - running benchmark_algorithms for evaluation
    """

    def __init__(self, app_controller):
        super().__init__()
        # Simple professional light theme
        self.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f7;
        }

        QTabBar::tab {
            padding: 6px 16px;
            font-weight: 500;
        }

        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom: 2px solid #3f51b5;
        }

        QLabel#MainTitle {
            font-size: 22px;
            font-weight: 700;
        }

        QPushButton {
            background-color: #3f51b5;
            color: white;
            border-radius: 4px;
            padding: 6px;
        }

        QPushButton:hover {
            background-color: #5c6bc0;
        }

        QPushButton:disabled {
            background-color: #b0bec5;
        }

        QTextEdit {
            background-color: #ffffff;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
        }
        """)
        self.app = app_controller  # RouteOptimizerApp instance

        self.setWindowTitle("Delivery Route Optimizer — PyQt5 GUI")
        self.setMinimumSize(1500, 1000)
        self.setStyleSheet("QMainWindow { background-color: #eeeeee; }")

        # Widgets that we need to access from multiple methods
        self.output_box: QTextEdit | None = None
        self.map_view: QWebEngineView | None = None
        self.eval_graph_label: QLabel | None = None
        self.matrics_label: QLabel | None = None

        self._setup_ui()
        self._clear_previous_map()
        self.load_map()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        """
        Builds the full UI:

        - A QTabWidget with two tabs:
          1. Optimizer
          2. Algorithm Evaluation
        """
        tabs = QTabWidget()

        optimizer_tab = self._create_optimizer_tab()
        evaluation_tab = self._create_evaluation_tab()

        tabs.addTab(optimizer_tab, "Optimizer")
        tabs.addTab(evaluation_tab, "Algorithm Evaluation")

        self.setCentralWidget(tabs)

    # ------------------------------------------------------------------
    def _create_optimizer_tab(self) -> QWidget:
        """
        Creates the first tab: main optimizer dashboard.

        NEW layout:
            Left:  Title + controls + ROUTE MAP (big area)
            Right: Algorithm metrics + detailed text output (smaller area)
        """
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        tab.setLayout(layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # -------- LEFT PANEL (map side) ----------------------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(12)
        left_widget.setLayout(left_layout)

########################################################################################

        icon = QLabel()
        icon.setPixmap(QPixmap("logo.png").scaled(200, 180))

        title = QLabel("Delivery Route Optimizer")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #2E86C1;")

        header = QHBoxLayout()
        header.addWidget(icon)
        header.addWidget(title)
        header.setAlignment(Qt.AlignLeft)
        header.totalMinimumSize()

        left_layout.addLayout(header)

#######################################################################################

        # Controls container
        controls_box = QWidget()
        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)
        controls_box.setLayout(controls_layout)

        algo_label = QLabel("Select Algorithm:")
        algo_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        controls_layout.addWidget(algo_label)

        self.algo_select = QComboBox()
        self.algo_select.addItem("Nearest Neighbour", "nn")
        self.algo_select.addItem("Nearest Neighbour + 2-opt", "nn_2opt")
        self.algo_select.addItem("Brute Force TSP", "bf")
        self.algo_select.setStyleSheet("background-color: #f5f5f7; height: 25px;")
        controls_layout.addWidget(self.algo_select)

        # Buttons row
        buttons_row = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)
        buttons_row.setLayout(buttons_layout)

        run_button = QPushButton("Run")
        run_button.setStyleSheet("font-size: 16px;")
        run_button.clicked.connect(self.run_selected_algorithm)

        manage_button = QPushButton("Manage Locations")
        manage_button.setStyleSheet("font-size: 16px;")
        manage_button.clicked.connect(self.manage_locations)

        buttons_layout.addWidget(run_button)
        buttons_layout.addWidget(manage_button)

        controls_layout.addWidget(buttons_row)
        left_layout.addWidget(controls_box)

        # Route map underneath controls (BIG panel)
        map_label = QLabel("Route Map:")
        map_label.setStyleSheet("font-weight: bold; margin-top: 4px; font-size: 18px;")
        map_label.setMaximumHeight(25)
        left_layout.addWidget(map_label)

        self.map_view = QWebEngineView()
        self.map_view.setStyleSheet(
            "border: 1px solid #cccccc; background-color: white;"
        )
        left_layout.addWidget(self.map_view)

        splitter.addWidget(left_widget)

        # -------- RIGHT PANEL (metrics + output) -------------------------
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(10)
        right_widget.setLayout(right_layout)

        # Metrics box
        metrics_title = QLabel("Algorithm Metrics:")
        metrics_title.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(metrics_title)

        self.metrics_label = QLabel()
        self.metrics_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setStyleSheet(
            "background-color: #fafafa; border: 1px solid #cccccc; "
            "border-radius: 4px; padding: 6px;"
        )
        self.metrics_label.setMinimumHeight(150)
        self.metrics_label.setText(
            "Run an algorithm to see its metrics here "
            "(time complexity, nodes visited, measured runtime, etc.)."
        )
        right_layout.addWidget(self.metrics_label)

        # Detailed text output
        output_label = QLabel("Detailed Output:")
        output_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        right_layout.addWidget(output_label)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumHeight(200)
        self.output_box.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #d0d0d0; border-radius: 4px;"
        )
        right_layout.addWidget(self.output_box)

        splitter.addWidget(right_widget)

        # Keep the same proportions as before:
        # left (= map) wide, right (= output + metrics) narrower
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)
        return tab

    # ------------------------------------------------------------------
    def _create_evaluation_tab(self) -> QWidget:
        """
        Creates the second tab: algorithm evaluation.

        Contains:
        - A button to generate the time-vs-nodes graph using the current
          set of locations.
        - An image area to display execution_time.png.
        """
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        tab.setLayout(layout)

        title = QLabel("Algorithm Evaluation")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "This section compares the performance of all three algorithms:\n"
            "Nearest Neighbour, Nearest Neighbour + 2-opt, and Brute Force.\n"
            "Click 'Generate Evaluation Graph' to run timed experiments on\n"
            "increasing problem sizes and update the chart."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        button = QPushButton("Generate Evaluation Graph")
        button.clicked.connect(self.generate_evaluation_graph)
        layout.addWidget(button)

        self.eval_graph_label = QLabel()
        self.eval_graph_label.setAlignment(Qt.AlignCenter)
        self.eval_graph_label.setStyleSheet(
            "background-color: #f5f5f5; border: 1px solid #dddddd;"
        )
        self.eval_graph_label.setMinimumHeight(300)
        layout.addWidget(self.eval_graph_label)

        # Try to load an existing graph if it exists
        self._load_evaluation_graph()

        return tab

    # ------------------------------------------------------------------
    def _clear_previous_map(self):
        """
        Remove any old nearest_delivery.html so the app starts with
        a blank map message instead of a stale route.
        """
        map_path = os.path.abspath("nearest_delivery.html")
        if os.path.exists(map_path):
            os.remove(map_path)

    # ------------------------------------------------------------------
    def load_map(self):
        """
        Load the folium-generated map HTML into the QWebEngineView.
        If no map exists yet, show an instructional message.
        """
        if self.map_view is None:
            return

        map_path = os.path.abspath("nearest_delivery.html")
        if not os.path.exists(map_path):
            self.map_view.setHtml("<h3>No map generated yet. Run an algorithm first.</h3>")
        else:
            self.map_view.load(QUrl.fromLocalFile(map_path))

    # ------------------------------------------------------------------
    def run_selected_algorithm(self):
        """
        Called when the user presses "Run" on the Optimizer tab.

        - Reads the selected algorithm mode.
        - Asks the RouteOptimizerApp controller to run it.
        - Displays route, distance, and execution time in the output box.
        - Updates the Algorithm Metrics panel.
        - Reloads the map to show the new route.
        """
        mode = self.algo_select.currentData()  # "nn", "nn_2opt", "bf"

        result = self.app.run(mode)  # controller in main.py

        if result.get("error"):
            QMessageBox.critical(self, "Error", result["error"])
            return

        route_list = result.get("route") or []
        route_str = " → ".join(route_list) if route_list else "(no route)"
        distance = result.get("distance")
        exec_time = result.get("exec_time")

        # ---------- Detailed text output (right-hand text area) ----------
        text_lines = [
            f"Algorithm Mode: {mode}",
            f"Route: {route_str}",
        ]
        if distance is not None:
            text_lines.append(f"Total Distance (geodesic): {distance:.3f} km")
        if exec_time is not None:
            text_lines.append(f"Execution Time (measured): {exec_time * 1000:.2f} ms")

        self.output_box.setText("\n".join(text_lines))

        # ---------- Algorithm metrics panel (right-hand metrics box) -----
        if self.metrics_label is not None:
            # Pretty algorithm names for display
            friendly_names = {
                "nn": "Nearest Neighbour",
                "nn_2opt": "Nearest Neighbour + 2-opt",
                "bf": "Brute Force TSP",
            }
            # Theoretical time/space complexities for your report
            complexities = {
                "nn": "Time: O(n²), Space: O(n)",
                "nn_2opt": "Time: O(n²) + local search (~O(n²·k)), Space: O(n)",
                "bf": "Time: O(n! · n), Space: O(n)",
            }

            friendly = friendly_names.get(mode, mode)
            complexity = complexities.get(mode, "Unknown complexity")
            node_count = len(route_list) - 1 if route_list else 0  # minus duplicate depot

            metrics_lines = [
                f"Selected algorithm: {friendly}",
                f"Theoretical complexity: {complexity}",
                f"Nodes in route (including depot): {len(route_list)}",
                f"Unique locations visited: {node_count}",
            ]
            if exec_time is not None:
                metrics_lines.append(f"Measured runtime: {exec_time * 1000:.2f} ms")
            if distance is not None:
                metrics_lines.append(f"Route length (geodesic): {distance:.3f} km")

            self.metrics_label.setText("\n".join(metrics_lines))

        # ---------- Reload map for the new route -------------------------
        self.load_map()

    # ------------------------------------------------------------------
    def manage_locations(self):
        """
        Open the Manage Locations dialog.

        After the dialog closes with OK, update the controller's locations.

        Note: The locations dict is shared by reference with the dialog,
        so changes are already applied; we just tell the controller to use
        the updated dict.
        """
        locations = self.app.get_locations()
        dlg = LocationManagerDialog(locations, self)
        if dlg.exec_():
            # Apply updated locations to controller
            self.app.update_locations(locations)
            self.output_box.append("\n[Locations updated]")
            # Clear previous map because route is now outdated
            self._clear_previous_map()
            self.load_map()

    # ------------------------------------------------------------------
    def _load_evaluation_graph(self):
        """Load execution_time.png into the evaluation tab label, if it exists."""
        if self.eval_graph_label is None:
            return

        graph_path = os.path.join("gui", "execution_time.png")
        abs_path = os.path.abspath(graph_path)

        if os.path.exists(abs_path):
            pixmap = QPixmap(abs_path)
            self.eval_graph_label.setPixmap(
                pixmap.scaledToWidth(600, Qt.SmoothTransformation)
            )
        else:
            self.eval_graph_label.setText(
                "No evaluation graph yet.\nClick 'Generate Evaluation Graph' to create one."
            )

    # ------------------------------------------------------------------
    def generate_evaluation_graph(self):
        """
        Called from the Evaluation tab.

        Uses the current locations in the controller to run timed
        experiments and generates gui/execution_time.png via
        src.utils.benchmark.benchmark_algorithms().
        """
        locations = self.app.get_locations()
        try:
            path = benchmark_algorithms(locations)
        except Exception as e:
            QMessageBox.critical(self, "Benchmark Error", str(e))
            return

        if os.path.exists(path):
            pixmap = QPixmap(path)
            self.eval_graph_label.setPixmap(
                pixmap.scaledToWidth(600, Qt.SmoothTransformation)
            )
        else:
            QMessageBox.warning(self, "Graph Error", "Graph file could not be found.")


# =====================================================================
# Application bootstrap
# =====================================================================

def start_gui(app_controller):
    """
    Create the QApplication and launch the MainWindow.

    Parameters
    ----------
    app_controller : RouteOptimizerApp
        Controller instance from main.py, responsible for
        algorithm execution and storing locations.
    """
    qt_app = QApplication(sys.argv)
    window = MainWindow(app_controller)
    window.show()
    sys.exit(qt_app.exec_())


if __name__ == "__main__":
    # For manual testing (runs without going through main.py)
    from main import RouteOptimizerApp

    app = RouteOptimizerApp()
    start_gui(app)
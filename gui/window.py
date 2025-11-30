# PyQt5 GUI layer for the Delivery Route Optimizer.
#
# - Tab 1: "Optimizer"
#     - Algorithm selection (NN / NN + 2-opt / BF)
#     - Run button
#     - Manage Locations (with address/postcode search)
#     - Text output (route, distance, execution time)
#     - Embedded map (folium HTML inside QWebEngineView)
#
# - Tab 2: "Algorithm Evaluation"
#     - Button to generate performance graph
#     - Graph image (execution_time.png) comparing algorithms
#
# The GUI does NOT implement algorithms itself.
# It talks to a RouteOptimizerApp controller instance (from main.py).


import os
import sys
from typing import Dict

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QPixmap, QFont
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
    QTabWidget,
    QDialog,
    QListWidget,
    QLineEdit,
    QFormLayout,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QSizePolicy,
)

from src.models.location import Location
from src.utils.benchmark import benchmark_algorithms
from src.utils.geocoding import Geocoder
from geopy.distance import geodesic
import matplotlib.pyplot as plt


# =====================================================================
# Location Manager Dialog
# =====================================================================

class LocationManagerDialog(QDialog):
    # Popup dialog for viewing / adding / removing locations.
    #
    # Features:
    # - Shows existing locations in a list.
    # - Allows deletion of non-depot locations.
    # - Allows adding a new location using:
    #     - Address/postcode search (via geopy Nominatim)
    #     - Name, latitude, longitude fields
    #
    # The dialog directly modifies the locations dict passed in.

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
        # Refresh the list widget from current locations dict.
        self.list_widget.clear()
        for name in self.locations.keys():
            self.list_widget.addItem(name)

    # ------------------------------------------------------------------
    def delete_selected(self):
        # Delete the currently selected location (but not Depot).
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
    # Use geopy Nominatim to convert an address/postcode into latitude/longitude. Makes the dialog user-friendly.

        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "No input", "Please enter a postcode or location.")
            return

        # ORS key
        ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjE5YzI4NjBkYWEzMDQwZmRhODkyYmIzNGM2N2IzMDJjIiwiaCI6Im11cm11cjY0In0="

        geocoder = Geocoder(ORS_KEY)
        try:
            result = geocoder.geocode(query)
        except RuntimeError as e:
            QMessageBox.critical(self, "ORS Error", str(e))
            return

        if result is None:
            QMessageBox.warning(self, "Not found",
                                "ORS could not find a match for that text.\n"
                                "Try a more specific address or postcode.")
            return

        lat, lon = result
        self.lat_edit.setText(str(lat))
        self.lon_edit.setText(str(lon))

        # Autofill name if empty
        if not self.name_edit.text().strip():
            self.name_edit.setText(query)

    # ------------------------------------------------------------------
    def accept(self):
        # When OK is pressed:
        # - If a new location is entered, validate and add it.
        # - Deletions have already been applied.
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
    # Main PyQt5 window.
    # Receives a RouteOptimizerApp instance from main.py->handles algorithm execution & stores current locations.
    # GUI is responsible only for showing controls, triggering app.run(mode), displaying results and maps, running benchmark_algorithms for evaluation

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
        self.eval_distance_label: QLabel | None = None
        self.metrics_label: QLabel | None = None
        self.progress_bar: QProgressBar | None = None
        self.current_comparison_label: QLabel | None = None
        self.matrix_table: QTableWidget | None = None
        self.matrix_map_view: QWebEngineView | None = None

        self._setup_ui()
        self._clear_previous_map()
        self.load_map()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        # Builds the full UI: A QTabWidget with two tabs: 1. Optimizer 2. Algorithm Evaluation
        tabs = QTabWidget()

        optimizer_tab = self._create_optimizer_tab()
        evaluation_tab = self._create_evaluation_tab()
        matrix_tab = self._create_matrix_tab()

        tabs.addTab(optimizer_tab, "Optimizer")
        tabs.addTab(evaluation_tab, "Algorithm Evaluation")
        tabs.addTab(matrix_tab, "Distance Matrix")

        self.setCentralWidget(tabs)

    # ------------------------------------------------------------------
    def _create_optimizer_tab(self) -> QWidget:
        # Creates the first tab: main optimizer dashboard.
        # NEW layout:
        #     Left:  Title + controls + ROUTE MAP (big area)
        #     Right: Algorithm metrics + detailed text output (smaller area)
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        tab.setLayout(layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # -------- LEFT PANEL (map side) ----------------------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(15, 0, 15, 5)
        left_layout.setSpacing(8)
        left_widget.setLayout(left_layout)

        # Design header
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "logo.png")

        icon = QLabel()
        pixmap = QPixmap(logo_path)

        if pixmap.isNull():
            print("WARNING: Could not load logo from", logo_path)
        else:
            icon.setPixmap(
                pixmap.scaled(200, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        title = QLabel("Delivery Route Optimizer")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #2E86C1;")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(icon)
        header.addWidget(title)
        header.setAlignment(Qt.AlignLeft)

        left_layout.addLayout(header)

        # Controls container
        controls_box = QWidget()
        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)
        controls_box.setLayout(controls_layout)

        algo_label = QLabel("Select Algorithm:")
        algo_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        controls_layout.addWidget(algo_label)

        self.algo_select = QComboBox()
        self.algo_select.addItem("Nearest Neighbour", "nn")
        self.algo_select.addItem("Nearest Neighbour + 2-opt", "nn_2opt")
        self.algo_select.addItem("Brute Force TSP", "bf")
        self.algo_select.setStyleSheet("background-color: lightgray; height: 25px;")
        controls_layout.addWidget(self.algo_select)

        # Buttons row
        buttons_row = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)
        buttons_row.setLayout(buttons_layout)

        run_button = QPushButton("Run")
        run_button.setStyleSheet("font-size: 18px; background-color: steelblue;")
        run_button.clicked.connect(self.run_selected_algorithm)

        manage_button = QPushButton("Manage Locations")
        manage_button.setStyleSheet("font-size: 18px; background-color: steelblue;")
        manage_button.clicked.connect(self.manage_locations)

        compare_button = QPushButton("Compare All Algorithms")
        compare_button.setStyleSheet("font-size: 18px; background-color: steelblue;")
        compare_button.clicked.connect(self.compare_all_algorithms)

        buttons_layout.addWidget(run_button)
        buttons_layout.addWidget(manage_button)
        buttons_layout.addWidget(compare_button)

        controls_layout.addWidget(buttons_row)
        left_layout.addWidget(controls_box)

        # Header row: "Route Map:" label + progress bar on the right
        map_header = QWidget()
        map_header_layout = QHBoxLayout()
        map_header_layout.setContentsMargins(0, 0, 0, 0)
        map_header_layout.setSpacing(6)
        map_header.setLayout(map_header_layout)

        map_label = QLabel("Route Map:")
        map_label.setStyleSheet("font-weight: bold; font-size: 18px; margin: opx; padding: 0px;")
        map_label.setMaximumHeight(25)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(18)
        self.progress_bar.setMinimumHeight(10)
        self.progress_bar.setStyleSheet("margin: 0px; padding: 0px;")
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # put label left, bar right
        map_header_layout.addWidget(map_label)
        map_header_layout.addWidget(self.progress_bar)
        map_header_layout.setStretch(0, 0)  # label minimal
        map_header_layout.setStretch(1, 1)  # bar fills remaining space
        map_header.setMaximumHeight(18)

        left_layout.addWidget(map_header)

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
            "background-color: #E8F1FA; border: 1px solid #cccccc; "
            "border-radius: 4px; padding: 6px; font-size: 18px;"
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
        self.output_box.setFontPointSize(9)
        self.output_box.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #d0d0d0; border-radius: 4px;"
        )
        right_layout.addWidget(self.output_box)

        # Mini comparison graph
        comparison_title = QLabel("Current Algorithm Comparison:")
        comparison_title.setStyleSheet("font-weight: bold; margin-top: 8px;")
        right_layout.addWidget(comparison_title)

        self.current_comparison_label = QLabel(
            "Click 'Compare All Algorithms' to see a bar chart of time and distance."
        )
        self.current_comparison_label.setAlignment(Qt.AlignCenter)
        self.current_comparison_label.setMinimumHeight(200)
        self.current_comparison_label.setStyleSheet(
            "background-color: #fafafa; border: 1px solid #cccccc; border-radius: 0px;"
        )
        right_layout.addWidget(self.current_comparison_label)

        splitter.addWidget(right_widget)

        # Keep the same proportions as before:
        # left (= map) wide, right (= output + metrics) narrower
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)
        return tab

    # ------------------------------------------------------------------
    def _create_evaluation_tab(self) -> QWidget:
        # Creates the 'Algorithm Evaluation' tab.
        # Now shows TWO graphs: Execution time vs nodes & Route distance vs nodes
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        tab.setLayout(layout)

        title = QLabel("Algorithm Evaluation")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "This section compares the performance of all three algorithms: Nearest Neighbour, Nearest Neighbour + 2-opt, and Brute Force.\n"
            "Click 'Generate Evaluation Graph' to run timed experiments on increasing problem sizes and update the charts."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:18px;")
        layout.addWidget(desc)

        generate_button = QPushButton("Generate Evaluation Graph")
        generate_button.setStyleSheet("background-color: lightblue; font-size: 18px; font-color: white;")
        generate_button.clicked.connect(self.generate_evaluation_graph)
        layout.addWidget(generate_button)

        # --- Side-by-side graph layout ------------------------------------

        graphs_container = QWidget()
        graphs_layout = QHBoxLayout()
        graphs_layout.setContentsMargins(0, 0, 0, 0)
        graphs_layout.setSpacing(20)
        graphs_container.setLayout(graphs_layout)

        # Left graph (Execution Time)
        left_graph_box = QVBoxLayout()
        left_graph_box.setSpacing(6)

        time_title = QLabel("Execution Time vs Nodes:")
        time_title.setStyleSheet("font-weight: bold; font-size: 18px;")
        left_graph_box.addWidget(time_title)

        self.eval_graph_label = QLabel("No graph yet.\n Click 'Generate Evaluation Graph' above")
        self.eval_graph_label.setAlignment(Qt.AlignCenter)
        self.eval_graph_label.setMinimumHeight(700)
        left_graph_box.addWidget(self.eval_graph_label)

        # Right graph (Route Distance)
        right_graph_box = QVBoxLayout()
        right_graph_box.setSpacing(6)

        dist_title = QLabel("Route Distance vs Nodes:")
        dist_title.setStyleSheet("font-weight: bold; font-size: 18px;")
        right_graph_box.addWidget(dist_title)

        self.eval_distance_label = QLabel("No graph yet.\n Click 'Generate Evaluation Graph' above")
        self.eval_distance_label.setAlignment(Qt.AlignCenter)
        self.eval_distance_label.setMinimumHeight(700)
        right_graph_box.addWidget(self.eval_distance_label)

        # Add both
        graphs_layout.addLayout(left_graph_box)
        graphs_layout.addLayout(right_graph_box)

        layout.addWidget(graphs_container)

        return tab

    # ------------------------------------------------------------------------------------
    def _create_matrix_tab(self) -> QWidget:
        # Creates the Distance Matrix tab showing geodesic distances between all locations.
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        tab.setLayout(layout)

        title = QLabel("Distance Matrix (Geodesic)")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "This table shows straight-line (geodesic) distances between all locations currently defined in the problem.\n"
            "It matches the weights used by the algorithms. (Note: customer 1-4 are default customers)"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:18px;")
        layout.addWidget(desc)

        refresh_button = QPushButton("Refresh Matrix")
        refresh_button.setStyleSheet("background-color: lightblue; font-size: 18px;")
        refresh_button.clicked.connect(self.refresh_distance_matrix)
        layout.addWidget(refresh_button)

        # --- Matrix on top, map below -----------------------------------
        container = QWidget()
        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 5, 0, 0)
        v_layout.setSpacing(10)
        container.setLayout(v_layout)

        # Top: distance matrix table
        self.matrix_table = QTableWidget()
        self.matrix_table.setMinimumHeight(250)
        v_layout.addWidget(self.matrix_table)

        # Bottom: map view (same HTML as main map)
        self.matrix_map_view = QWebEngineView()
        self.matrix_map_view.setStyleSheet(
            "border: 1px solid #cccccc; background-color: white;"
        )
        self.matrix_map_view.setMinimumHeight(350)
        v_layout.addWidget(self.matrix_map_view)

        layout.addWidget(container)

        # Populate once initially
        self.refresh_distance_matrix()
        # Load current map (if any) into both maps
        self.load_map()

        return tab

    def refresh_distance_matrix(self):
        # Rebuild the distance matrix table from current locations.
        if self.matrix_table is None:
            return

        locations = self.app.get_locations()
        names = list(locations.keys())

        n = len(names)
        self.matrix_table.clear()
        self.matrix_table.setRowCount(n)
        self.matrix_table.setColumnCount(n)
        self.matrix_table.setHorizontalHeaderLabels(names)
        self.matrix_table.setVerticalHeaderLabels(names)

        for i, name_i in enumerate(names):
            for j, name_j in enumerate(names):
                if i == j:
                    text = "0.000"
                else:
                    loc_i = locations[name_i].as_tuple
                    loc_j = locations[name_j].as_tuple
                    d_km = geodesic(loc_i, loc_j).km
                    text = f"{d_km:.3f}"
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.matrix_table.setItem(i, j, item)

    # ------------------------------------------------------------------
    def _clear_previous_map(self):
    # Remove any old nearest_delivery.html so the app starts with a blank map message instead of a stale route.
        map_path = os.path.abspath("nearest_delivery.html")
        if os.path.exists(map_path):
            os.remove(map_path)

    # ------------------------------------------------------------------
    def load_map(self):
        # Load the folium-generated map HTML into the QWebEngineView.
        # If no map exists yet, show an instructional message.
        map_path = os.path.abspath("nearest_delivery.html")
        no_map_html = "<h3>No map generated yet. Run an algorithm first.</h3>"

        views = [self.map_view, self.matrix_map_view]

        for view in views:
            if view is None:
                continue

            if not os.path.exists(map_path):
                view.setHtml(no_map_html)
            else:
                view.load(QUrl.fromLocalFile(map_path))

    # ------------------------------------------------------------------
    def run_selected_algorithm(self):
        # Called when the user presses "Run" on the Optimizer tab.
        #
        # - Reads the selected algorithm mode.
        # - Asks the RouteOptimizerApp controller to run it.
        # - Displays route, distance, and execution time in the output box.
        # - Updates the Algorithm Metrics panel.
        # - Reloads the map to show the new route.

        mode = self.algo_select.currentData()  # "nn", "nn_2opt", "bf"

        # Start progress bar at 25% when the user clicks Run
        if self.progress_bar:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(25)
            self.progress_bar.show()
            QApplication.processEvents()

        result = self.app.run(mode)  # controller in main.py

        if result.get("error"):
            QMessageBox.critical(self, "Error", result["error"])
            if self.progress_bar:
                self.progress_bar.setValue(0)
            return

        route_list = result.get("route") or []
        route_str = " → ".join(route_list) if route_list else "(no route)"
        distance = result.get("distance")
        exec_time = result.get("exec_time")
        stats = result.get("stats") or {}

        # ---------- Detailed text output (right-hand text area) ----------
        text_lines = [
            f"Algorithm Mode: {mode}",
            f"Route: {route_str}",
        ]
        if distance is not None:
            text_lines.append(f"Total Distance (geodesic): {distance:.3f} km")
        if exec_time is not None:
            text_lines.append(f"Execution Time (measured): {exec_time * 1000:.2f} ms")

        # ---------- NEW: edge-by-edge distances along the route ----------
        if route_list and len(route_list) > 1:
            locations = self.app.get_locations()
            text_lines.append("")  # blank line
            text_lines.append("Edge distances (geodesic):")

            for i in range(len(route_list) - 1):
                a = route_list[i]
                b = route_list[i + 1]

                # Get (lat, lon) for each location
                loc_a = locations[a].as_tuple
                loc_b = locations[b].as_tuple

                d_km = geodesic(loc_a, loc_b).km
                text_lines.append(f"{a} → {b}: {d_km:.3f} km")

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

            # Algorithm specific stats
            if mode in ("nn", "nn_2opt"):
                metrics_lines.append(
                    f"Distance evaluations: {stats.get('distance_calls', 0)}"
                )
                if mode == "nn_2opt":
                    metrics_lines.append(
                        f"2-opt swaps considered: {stats.get('two_opt_swaps_considered', 0)}"
                    )
                    metrics_lines.append(
                        f"2-opt improvements kept: {stats.get('two_opt_improvements', 0)}"
                    )

                    nn_initial = stats.get("nn_initial_distance")
                    imp = stats.get("improvement_pct")

                    if nn_initial is not None:
                        metrics_lines.append(
                            f"Initial NN distance: {nn_initial:.3f} km"
                        )
                    if imp is not None:
                        metrics_lines.append(
                            f"Improvement over using only NN: {imp:.2f} %"
                        )

            elif mode == "bf":
                metrics_lines.append(
                    f"Distance evaluations: {stats.get('distance_calls', 0)}"
                )
                metrics_lines.append(
                    f"Permutations tested: {stats.get('permutations_tested', 0)}"
                )

            self.metrics_label.setText("\n".join(metrics_lines))

        if self.progress_bar:
            self.progress_bar.setValue(100)

        # ---------- Reload map for the new route -------------------------
        self.load_map()

    # ------------------------------------------------------------------
    def manage_locations(self):
        # Open the Manage Locations dialog.
        # After the dialog closes with OK, update the controller's locations.
        #
        # Note: The locations dict is shared by reference with the dialog, so changes are already applied;
        # we just tell the controller to use the updated dict.
        locations = self.app.get_locations()
        dlg = LocationManagerDialog(locations, self)
        if dlg.exec_():
            # Apply updated locations to controller
            self.app.update_locations(locations)
            self.output_box.append("\n[Locations updated]")
            # Clear previous map because route is now outdated
            self._clear_previous_map()
            self.load_map()

            self.refresh_distance_matrix()

    # ------------------------------------------------------------------
    def compare_all_algorithms(self):
        # Run NN, NN+2opt, and BF on the current locations and show
        # a textual summary + a mini comparison graph.
        if self.progress_bar:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.show()
            QApplication.processEvents()

        try:
            results = self.app.run_all()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            if self.progress_bar:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(0)
            return

        # Reset / clear the metrics box because this view is about comparison,
        # not a single algorithm's detailed stats.
        if self.metrics_label:
            self.metrics_label.setText(
                "Metrics box is cleared for comparison mode.\n"
                "Run a single algorithm to see its detailed metrics again."
            )

        # Build a summary in the output box
        lines = ["Algorithm comparison on current locations:"]

        order = [("nn", "Nearest Neighbour"),
                 ("nn_2opt", "Nearest Neighbour + 2-opt"),
                 ("bf", "Brute Force TSP")]

        for mode, name in order:
            res = results.get(mode, {})
            route = res.get("route") or []
            dist = res.get("distance")
            t = res.get("exec_time")
            stats = res.get("stats") or {}

            lines.append("")
            lines.append(f"{name} ({mode}):")
            lines.append(f"  Nodes in route: {len(route)}")
            if dist is not None:
                lines.append(f"  Total distance: {dist:.3f} km")
            if t is not None:
                lines.append(f"  Execution time: {t * 1000:.2f} ms")

            if mode in ("nn", "nn_2opt"):
                lines.append(f"  Distance evaluations: {stats.get('distance_calls', 0)}")
                if mode == "nn_2opt":
                    imp = stats.get("improvement_pct")
                    if imp is not None:
                        lines.append(f"  Improvement over NN: {imp:.2f}%")
            elif mode == "bf":
                lines.append(f"  Distance evaluations: {stats.get('distance_calls', 0)}")
                lines.append(f"  Permutations tested: {stats.get('permutations_tested', 0)}")

        if self.output_box:
            self.output_box.setText("\n".join(lines))

        if self.progress_bar:
            self.progress_bar.setValue(60)

        # Generate the mini comparison graph
        try:
            img_path = self._generate_current_comparison_graph(results)
            if self.current_comparison_label and os.path.exists(img_path):
                from PyQt5.QtGui import QPixmap
                self.current_comparison_label.setPixmap(
                    QPixmap(img_path).scaledToWidth(400, Qt.SmoothTransformation)
                )
        except Exception as e:
            # If graph generation fails, don't crash the app
            if self.current_comparison_label:
                self.current_comparison_label.setText(
                    f"Could not generate comparison graph:\n{e}"
                )

        if self.progress_bar:
            self.progress_bar.setValue(100)

    # ------------------------------------------------------------------
    def _generate_current_comparison_graph(self, results: dict) -> str:
        """
        Create a bar chart comparing execution time and distance for
        NN, NN+2opt, and BF on the current locations.

        Returns the absolute path to the saved PNG.
        """
        # Prepare data
        modes = ["nn", "nn_2opt", "bf"]
        labels = ["NN", "NN+2opt", "BF"]
        times = []
        dists = []

        for mode in modes:
            res = results.get(mode, {})
            t = res.get("exec_time") or 0.0
            d = res.get("distance") or 0.0
            times.append(t)
            dists.append(d)

        # Avoid zero-division if times are all 0
        # (will just plot zeros - fine for small instances)
        import numpy as np

        x = np.arange(len(labels))  # 0,1,2
        width = 0.35

        plt.figure(figsize=(6, 4))

        # Time bars on left, distance on right (scaled)
        plt.subplot(2, 1, 1)
        plt.bar(labels, [t * 1000 for t in times])
        plt.ylabel("Time (ms)")
        plt.title("Execution Time by Algorithm")

        plt.subplot(2, 1, 2)
        plt.bar(labels, dists)
        plt.ylabel("Distance (km)")
        plt.title("Route Distance by Algorithm")

        plt.tight_layout()

        # Save into gui folder
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gui_dir = os.path.join(root_dir, "gui")
        os.makedirs(gui_dir, exist_ok=True)
        img_path = os.path.join(gui_dir, "current_comparison.png")

        plt.savefig(img_path)
        plt.close()

        return img_path

    # -------------------------------------------------------------------------------
    def _load_evaluation_graph(self):
        # Try to load existing benchmark graphs when the Evaluation tab opens.
        #
        # This is helpful if the user has already run the benchmark in a
        # previous session or earlier in this session.

        # Project root
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gui_dir = os.path.join(root_dir, "gui")

        time_path = os.path.join(gui_dir, "execution_time.png")
        dist_path = os.path.join(gui_dir, "execution_distance.png")

        if self.eval_graph_label and os.path.exists(time_path):
            self.eval_graph_label.setPixmap(
                QPixmap(time_path).scaledToWidth(450, Qt.SmoothTransformation)
            )

        if self.eval_distance_label and os.path.exists(dist_path):
            self.eval_distance_label.setPixmap(
                QPixmap(dist_path).scaledToWidth(450, Qt.SmoothTransformation)
            )

    # ------------------------------------------------------------------
    def generate_evaluation_graph(self):
        # Called when the user presses the 'Generate Evaluation Graph' button.
        #
        # Runs the benchmarking routine and updates BOTH graphs:
        #     - time graph
        #     - distance graph
        locations = self.app.get_locations()
        try:
            paths = benchmark_algorithms(locations)  # now returns dict
        except Exception as e:
            QMessageBox.critical(self, "Benchmark error", str(e))
            return

        time_path = paths.get("time")
        dist_path = paths.get("distance")

        if self.eval_graph_label and time_path and os.path.exists(time_path):
            self.eval_graph_label.setPixmap(
                QPixmap(time_path).scaledToWidth(600, Qt.SmoothTransformation)
            )

        if self.eval_distance_label and dist_path and os.path.exists(dist_path):
            self.eval_distance_label.setPixmap(
                QPixmap(dist_path).scaledToWidth(600, Qt.SmoothTransformation)
            )


# =====================================================================
# Application bootstrap
# =====================================================================

def start_gui(app_controller):
    # Create the QApplication and launch the MainWindow.
    #
    # Parameters
    # ----------
    # app_controller : RouteOptimizerApp
    #     Controller instance from main.py, responsible for
    #     algorithm execution and storing locations.
    qt_app = QApplication(sys.argv)
    window = MainWindow(app_controller)
    window.show()
    sys.exit(qt_app.exec_())
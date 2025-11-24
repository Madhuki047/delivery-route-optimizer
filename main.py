"""
main.py
-------

Application controller for the Delivery Route Optimizer.

This version puts ALL behaviour inside the RouteOptimizerApp class
(except the tiny entrypoint), so it is easy to represent in UML.

Classes:
    - RouteOptimizerApp: holds locations and runs algorithms.

The GUI (gui/window.py) receives a RouteOptimizerApp instance and
uses its methods instead of calling free functions.
"""

from typing import Dict

from src.models.location import Location
from src.algorithms.nearest_neighbour import NearestNeighbourTSP
from src.algorithms.brute_force_tsp import brute_force_tsp
from src.utils.map_renderer import render_map_with_fallback


class RouteOptimizerApp:
    """
    High-level controller for the route optimizer.

    Responsibilities:
    - Maintain the current set of locations (depot + customers).
    - Provide a simple .run(mode) API for the GUI.
    - Provide accessors to get / update locations (for Manage Locations).
    """

    def __init__(self) -> None:
        # Initialise with a default scenario
        self.locations: Dict[str, Location] = self._build_default_locations()

    # ------------------------------------------------------------------
    # 1. Location management
    # ------------------------------------------------------------------
    def _build_default_locations(self) -> Dict[str, Location]:
        """
        Creates the default set of locations.

        This is private because the outside world should not care HOW
        we build the initial set – only that we can later get / update it.
        """
        return {
            "Depot": Location("Depot", 51.8156, -0.8120),
            "Customer1": Location("Customer1", 51.8200, -0.8000),
            "Customer2": Location("Customer2", 51.8300, -0.8100),
            "Customer3": Location("Customer3", 51.8250, -0.8200),
            "Customer4": Location("Customer4", 51.8350, -0.8050),
        }

    def get_locations(self) -> Dict[str, Location]:
        """
        Returns the current location set.

        Used by the GUI (MainWindow) to show / edit locations.
        """
        return self.locations

    def update_locations(self, new_locations: Dict[str, Location]) -> None:
        """
        Replace the current locations with a new set.

        Called when the Manage Locations dialog is closed with OK.
        """
        self.locations = new_locations

    # ------------------------------------------------------------------
    # 2. Algorithm execution API (what the GUI calls)
    # ------------------------------------------------------------------
    def run(self, mode: str) -> dict:
        """
        Public method the GUI calls to run one of the algorithms.

        Parameters
        ----------
        mode : str
            "nn"      -> Nearest Neighbour
            "nn_2opt" -> Nearest Neighbour + 2-opt
            "bf"      -> Brute Force

        Returns
        -------
        dict
            {
                "mode": mode,
                "route": [...],
                "distance": float or None,
                "exec_time": float or None,
                "error": None or str
            }
        """
        return self._run_algorithm_on_current_locations(mode)

    # ------------------------------------------------------------------
    # 3. Internal algorithm method (pure logic)
    # ------------------------------------------------------------------
    def _run_algorithm_on_current_locations(self, mode: str) -> dict:
        """
        Contains the actual algorithm logic.

        This is a *private* helper used by .run(), so the GUI only sees
        one clean method in the public API.
        """
        locations = self.locations
        start = "Depot"

        result = {
            "mode": mode,
            "route": None,
            "distance": None,
            "exec_time": None,
            "error": None,
        }

        try:
            if "Depot" not in locations:
                raise ValueError("Locations must contain a 'Depot' node.")

            # ----- NEAREST NEIGHBOUR / NN + 2-opt ---------------------
            if mode in ("nn", "nn_2opt"):
                algo = NearestNeighbourTSP(locations)

                import time
                t0 = time.perf_counter()
                nn_route, nn_distance = algo.single_start_route(start)
                t1 = time.perf_counter()

                if mode == "nn":
                    final_route = nn_route
                    final_distance = nn_distance
                    exec_time = t1 - t0
                else:
                    t2 = time.perf_counter()
                    final_route, final_distance = algo.two_opt(nn_route)
                    t3 = time.perf_counter()
                    exec_time = t3 - t0  # NN + 2-opt

            # ----- BRUTE FORCE ----------------------------------------
            elif mode == "bf":
                import time
                t0 = time.perf_counter()
                final_route, final_distance = brute_force_tsp(locations, start)
                t1 = time.perf_counter()
                exec_time = t1 - t0

            else:
                raise ValueError(f"Unknown algorithm mode: {mode}")

            result["route"] = final_route
            result["distance"] = final_distance
            result["exec_time"] = exec_time

            # Draw the map with whatever route we got
            render_map_with_fallback(final_route, locations)

        except Exception as e:
            result["error"] = str(e)

        return result


# ----------------------------------------------------------------------
# 4. Entry point – minimal, perfect for a sequence diagram
# ----------------------------------------------------------------------
if __name__ == "__main__":
    from gui.window import start_gui

    app_controller = RouteOptimizerApp()
    start_gui(app_controller)

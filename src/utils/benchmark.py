"""
benchmark.py
------------

Performance benchmarking for the three algorithms:

    - Nearest Neighbour (NN)
    - Nearest Neighbour + 2-opt (NN+2opt)
    - Brute Force (BF)

Now produces TWO graphs:
    1) execution_time.png     (time vs nodes)
    2) execution_distance.png (route distance vs nodes)
"""

from typing import Dict, List
import os
import time

import matplotlib.pyplot as plt

from src.models.location import Location
from src.algorithms.nearest_neighbour import NearestNeighbourTSP
from src.algorithms.brute_force_tsp import brute_force_tsp


class AlgorithmBenchmark:
    """
    Encapsulates the logic for measuring and plotting algorithm performance.

    Attributes
    ----------
    locations : dict[str, Location]
        Set of locations to use for benchmarking.
    """

    def __init__(self, locations: Dict[str, Location]) -> None:
        if "Depot" not in locations:
            raise ValueError("Locations must contain a 'Depot' node for benchmarking.")
        self.locations = locations

    # ------------------------------------------------------------------
    def run(self) -> Dict[str, str]:
        """
        Run benchmarking for increasing problem sizes and save TWO PNG graphs.

        Strategy
        --------
        Let customers = all locations except Depot.

        For k = 1 .. len(customers):
            - Build subproblem with Depot + first k customers.
            - Time and measure:
                * NN
                * NN + 2-opt
                * BF

        Graphs
        ------
        1) Execution time vs nodes (seconds)
        2) Route distance vs nodes (km)

        Returns
        -------
        dict
            {
                "time": "<absolute path to execution_time.png>",
                "distance": "<absolute path to execution_distance.png>"
            }
        """
        depot = self.locations["Depot"]
        customers: List[Location] = [
            loc for name, loc in self.locations.items() if name != "Depot"
        ]

        if not customers:
            raise ValueError("Need at least one customer for benchmarking.")

        # X-axis: number of nodes (Depot + customers)
        node_counts: List[int] = []

        # Time results
        times_nn: List[float] = []
        times_nn_2opt: List[float] = []
        times_bf: List[float] = []

        # Distance results
        dists_nn: List[float] = []
        dists_nn_2opt: List[float] = []
        dists_bf: List[float] = []

        # Increase the number of customers in the problem
        for k in range(1, len(customers) + 1):
            subset = [depot] + customers[:k]
            locs = {loc.name: loc for loc in subset}
            total_nodes = len(locs)  # Depot + k customers

            # --- Nearest Neighbour -----------------------------------
            nn_algo = NearestNeighbourTSP(locs)
            t0 = time.perf_counter()
            nn_route, nn_dist = nn_algo.nearest_neighbour("Depot")
            t1 = time.perf_counter()
            times_nn.append(t1 - t0)
            dists_nn.append(nn_dist)

            # --- Nearest Neighbour + 2-opt ---------------------------
            t2 = time.perf_counter()
            nn2_route, nn2_dist = nn_algo.two_opt(nn_route)
            t3 = time.perf_counter()
            times_nn_2opt.append(t3 - t0)  # NN + 2-opt combined time
            dists_nn_2opt.append(nn2_dist)

            # --- Brute Force -----------------------------------------
            t4 = time.perf_counter()
            bf_route, bf_dist = brute_force_tsp(locs, "Depot")
            t5 = time.perf_counter()
            times_bf.append(t5 - t4)
            dists_bf.append(bf_dist)

            node_counts.append(total_nodes)

        # Root folder (project root, not src/utils)
        root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        gui_dir = os.path.join(root_dir, "gui")
        os.makedirs(gui_dir, exist_ok=True)

        # === 1) TIME GRAPH ===========================================
        plt.figure(figsize=(8, 5))

        plt.plot(node_counts, times_nn, marker="o", label="Nearest Neighbour (NN)")
        plt.plot(node_counts, times_nn_2opt, marker="o", label="NN + 2-opt")
        plt.plot(node_counts, times_bf, marker="o", label="Brute Force (BF)")

        xlabels = [f"Node {n}" for n in node_counts]
        plt.xticks(node_counts, xlabels)

        plt.xlabel("Problem size (Node count: Depot + customers)")
        plt.ylabel("Execution time (seconds)")
        plt.title("Execution Time vs Nodes for NN, NN+2opt, and BF")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

        time_path = os.path.join(gui_dir, "execution_time.png")
        plt.savefig(time_path)
        plt.close()

        # === 2) DISTANCE GRAPH ======================================
        plt.figure(figsize=(8, 5))

        plt.plot(node_counts, dists_nn, marker="o", label="Nearest Neighbour (NN)")
        plt.plot(node_counts, dists_nn_2opt, marker="o", label="NN + 2-opt")
        plt.plot(node_counts, dists_bf, marker="o", label="Brute Force (BF)")

        plt.xticks(node_counts, xlabels)
        plt.xlabel("Problem size (Node count: Depot + customers)")
        plt.ylabel("Route distance (km)")
        plt.title("Route Distance vs Nodes for NN, NN+2opt, and BF")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

        dist_path = os.path.join(gui_dir, "execution_distance.png")
        plt.savefig(dist_path)
        plt.close()

        print(f"Saved time graph to {time_path}")
        print(f"Saved distance graph to {dist_path}")

        return {"time": time_path, "distance": dist_path}


# ----------------------------------------------------------------------
# Helper function to preserve simple API for the GUI
# ----------------------------------------------------------------------
def benchmark_algorithms(locations: Dict[str, Location]) -> Dict[str, str]:
    """
    Called by the GUI.

    Returns a dict with absolute paths to both graphs:
        {"time": "...execution_time.png", "distance": "...execution_distance.png"}
    """
    bench = AlgorithmBenchmark(locations)
    return bench.run()

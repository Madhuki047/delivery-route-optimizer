"""
benchmark.py
------------

Performance benchmarking utilities for the delivery route optimizer.

The main function benchmark_algorithms() measures the execution time
of three algorithms:
    - Nearest Neighbour (NN)
    - Nearest Neighbour + 2-opt (NN+2opt)
    - Brute Force (BF)

for increasing problem sizes, using the *current* set of locations.

The resulting graph is saved as gui/execution_time.png and is shown
on the 'Algorithm Evaluation' tab in the GUI.
"""

from typing import Dict, List
import os
import time

import matplotlib.pyplot as plt

from src.models.location import Location
from src.algorithms.nearest_neighbour import NearestNeighbourTSP
from src.algorithms.brute_force_tsp import brute_force_tsp


def benchmark_algorithms(locations: Dict[str, Location]) -> str:
    """
    Benchmark NN, NN+2opt and BF on increasing problem sizes.

    Parameters
    ----------
    locations : dict[str, Location]
        Current set of locations from the controller / GUI.

    Assumptions
    -----------
    - Must contain a 'Depot' entry.
    - All other locations are treated as customers.

    Strategy
    --------
    For k = 1 .. number_of_customers:
        - Use a sub-problem with:
            Depot + first k customers
        - Time:
            * NN (Nearest Neighbour)
            * NN+2opt (Nearest Neighbour + 2-opt improvement)
            * BF (Brute Force TSP)
        - Record execution time for each.

    Returns
    -------
    str
        Absolute path of the saved PNG file.
    """
    if "Depot" not in locations:
        raise ValueError("Locations must contain a 'Depot' node for benchmarking.")

    # Separate depot and customers
    depot = locations["Depot"]
    customers: List[Location] = [
        loc for name, loc in locations.items() if name != "Depot"
    ]

    if not customers:
        raise ValueError("Need at least one customer for benchmarking.")

    # Lists for plotting
    node_counts: List[int] = []
    times_nn: List[float] = []
    times_nn_2opt: List[float] = []
    times_bf: List[float] = []

    # Increase k = number of customers in the problem
    for k in range(1, len(customers) + 1):
        # Build sub-problem: Depot + first k customers
        subset = [depot] + customers[:k]
        locs = {loc.name: loc for loc in subset}

        total_nodes = len(locs)  # Depot + k customers

        # --- NEAREST NEIGHBOUR ---------------------------------------
        nn_algo = NearestNeighbourTSP(locs)
        t0 = time.perf_counter()
        nn_route, nn_dist = nn_algo.single_start_route("Depot")
        t1 = time.perf_counter()
        times_nn.append(t1 - t0)

        # --- NEAREST NEIGHBOUR + 2-opt -------------------------------
        t2 = time.perf_counter()
        _, _ = nn_algo.two_opt(nn_route)
        t3 = time.perf_counter()
        # Total time from start of NN to end of 2-opt
        times_nn_2opt.append(t3 - t0)

        # --- BRUTE FORCE ---------------------------------------------
        t4 = time.perf_counter()
        _, _ = brute_force_tsp(locs, "Depot")
        t5 = time.perf_counter()
        times_bf.append(t5 - t4)

        node_counts.append(total_nodes)

    # --- Plot graph --------------------------------------------------
    plt.figure(figsize=(8, 5))

    plt.plot(node_counts, times_nn, marker="o", label="Nearest Neighbour (NN)")
    plt.plot(node_counts, times_nn_2opt, marker="o", label="NN + 2-opt")
    plt.plot(node_counts, times_bf, marker="o", label="Brute Force (BF)")

    # Custom x-axis labels: Node 2, Node 3, ...
    xlabels = [f"Node {n}" for n in node_counts]
    plt.xticks(node_counts, xlabels)

    plt.xlabel("Problem size (Node count: Depot + customers)")
    plt.ylabel("Execution time (seconds)")
    plt.title("Execution Time vs Nodes for NN, NN+2opt, and BF")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # Save into project/gui folder (not src/utils/gui)
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    save_path = os.path.join(root_dir, "gui", "execution_time.png")
    plt.savefig(save_path)
    plt.close()

    print(f"Saved evaluation graph to {save_path}")
    return save_path
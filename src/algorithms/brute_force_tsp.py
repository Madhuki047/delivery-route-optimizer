# Brute force solver for a small TSP-like delivery problem.
#
# ORGANIZED AS A CLASS:
# - BruteForceTSPSolver: encapsulates the brute-force logic.
# - brute_force_tsp(...): helper wrapper function for backwards compatibility.

from typing import Dict, List, Tuple
from itertools import permutations

from geopy.distance import geodesic
from src.models.location import Location


class BruteForceTSPSolver:
    # Brute force TSP solver.
    #
    # Tries all possible permutations of the customer nodes and finds
    # the shortest complete loop route starting and ending at the depot.

    def __init__(self, locations: Dict[str, Location]):
        self.locations = locations

        # Stats for analysis / GUI metrics
        self.distance_calls = 0
        self.permutations_texted = 0

    def _distance(self, a: str, b: str) -> float:
        self.distance_calls += 1
        # Compute straight-line distance between two nodes, in km.
        loc1 = self.locations[a].as_tuple
        loc2 = self.locations[b].as_tuple
        return geodesic(loc1, loc2).km

    def solve(self, start: str) -> Tuple[List[str], float]:
        self.reset_stats()

        # Compute the optimal TSP route by testing all permutations.
        if start not in self.locations:
            raise ValueError(f"Start node '{start}' not found.")

        others = [name for name in self.locations.keys() if name != start]

        best_route = []
        best_distance = float("inf")

        for perm in permutations(others):
            route = [start] + list(perm) + [start]
            total = 0.0

            for i in range(len(route) - 1):
                total += self._distance(route[i], route[i + 1])

            if total < best_distance:
                best_distance = total
                best_route = route

        return best_route, best_distance

    def reset_stats(self):
        # Reset all counters before a new run.
        self.distance_calls = 0
        self.permutations_tested = 0

    def get_stats(self) -> dict:
        # Return a dictionary of current statistics.
        return {
            "distance_calls": self.distance_calls,
            "permutations_tested": self.permutations_tested,
        }


# ----------------------------------------------------------------------
# Backwards-compatible wrapper
# ----------------------------------------------------------------------
def brute_force_tsp(locations: Dict[str, Location], start: str):
    # Keeps the old API alive, so existing import statements keep working.
    # Internally creates BruteForceTSPSolver and calls solve().
    solver = BruteForceTSPSolver(locations)
    return solver.solve(start)

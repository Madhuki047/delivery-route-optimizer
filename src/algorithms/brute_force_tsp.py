# src/algorithms/brute_force_tsp.py

from typing import Dict, List, Tuple
from itertools import permutations
from geopy.distance import geodesic

from src.models.location import Location


def _distance(locations: Dict[str, Location], a: str, b: str) -> float:
    """
    Straight-line distance between two named locations.
    """
    return geodesic(locations[a].as_tuple, locations[b].as_tuple).km


def brute_force_tsp(locations: Dict[str, Location],
                    start: str) -> Tuple[List[str], float]:
    """
    Brute-force TSP solver.

    Tries every possible permutation of visiting all customers starting
    and ending at 'start', and returns the shortest route.

    WARNING: factorial time – only feasible for small numbers of nodes
    (your case with 4 customers + depot is fine).
    """
    # All nodes except the starting depot
    others = [name for name in locations.keys() if name != start]

    best_route: List[str] = []
    best_distance: float = float("inf")

    # Try every possible visiting order of the other nodes
    for perm in permutations(others):
        route = [start] + list(perm) + [start]

        total = 0.0
        for i in range(len(route) - 1):
            total += _distance(locations, route[i], route[i + 1])

        if total < best_distance:
            best_distance = total
            best_route = route

    return best_route, best_distance

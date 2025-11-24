"""
nearest_neighbour.py
--------------------

Implements a greedy Nearest Neighbour heuristic for a TSP-like
delivery problem, plus a 2-opt local search improvement.

This class is used by:
    - main.RouteOptimizerApp (controller)
    - src.utils.benchmark (for timing NN and NN+2opt)

by passing in a dictionary of Location objects.
"""

from typing import Dict, List, Tuple
from geopy.distance import geodesic

from src.models.location import Location


class NearestNeighbourTSP:
    """
    Nearest Neighbour + optional 2-opt improvement for TSP-like routes.

    The algorithm itself is completely independent of maps, folium,
    and OpenRouteService – it only needs access to coordinates.
    """

    def __init__(self, locations: Dict[str, Location]):
        """
        Parameters
        ----------
        locations : dict[str, Location]
            Mapping from location name -> Location object.
            Example keys: 'Depot', 'Customer1', 'Customer2', ...
        """
        self.locations = locations

    # ------------------------------------------------------------------
    # Distance helper
    # ------------------------------------------------------------------
    def _distance(self, name1: str, name2: str) -> float:
        """
        Compute the straight-line distance between two locations.

        This is the edge weight used by the Nearest Neighbour heuristic
        and by the 2-opt improvement step.

        Currently: geodesic (great-circle) distance in kilometres.
        """
        loc1 = self.locations[name1].as_tuple   # (lat, lon)
        loc2 = self.locations[name2].as_tuple
        return geodesic(loc1, loc2).km

    # ------------------------------------------------------------------
    # 1. Basic Nearest Neighbour from a single start
    # ------------------------------------------------------------------
    def single_start_route(self, start: str) -> Tuple[List[str], float]:
        """
        Runs the Nearest Neighbour heuristic from a single starting node.

        Parameters
        ----------
        start : str
            Name of starting node, typically 'Depot'.

        Returns
        -------
        (route, total_distance)
            route is a loop including the start again at the end, e.g.
                ['Depot', 'Customer1', 'Customer3', 'Depot']
            total_distance is the sum of distances along that loop.

        This is essentially your original best_fit_search() function.
        """
        current = start
        route: List[str] = [current]
        total_distance = 0.0

        # Build the list of unvisited locations (everything except start)
        unvisited: List[str] = [
            name for name in self.locations.keys() if name != start
        ]

        # While there are still locations to visit ...
        while unvisited:
            # Assume the first unvisited is nearest for now
            nearest = unvisited[0]
            nearest_distance = self._distance(current, nearest)

            # Check all remaining unvisited locations
            for name in unvisited:
                d = self._distance(current, name)
                if d < nearest_distance:
                    nearest = name
                    nearest_distance = d

            # Move to the nearest location found
            route.append(nearest)
            total_distance += nearest_distance
            current = nearest
            unvisited.remove(nearest)

        # Return to start (Depot) to complete the loop
        route.append(start)
        total_distance += self._distance(current, start)

        return route, total_distance

    # ------------------------------------------------------------------
    # 2. Optional: try multiple starting nodes
    # ------------------------------------------------------------------
    def best_of_multiple_starts(self, starts: List[str]) -> Tuple[List[str], float]:
        """
        Convenience method to run Nearest Neighbour from several starts
        and keep the best (shortest) route.

        This is still 'Nearest Neighbour' – just with different starting
        positions, which can change the quality of the greedy solution.
        """
        best_route: List[str] = []
        best_distance: float = float("inf")

        for start in starts:
            route, dist = self.single_start_route(start)
            if dist < best_distance:
                best_distance = dist
                best_route = route

        return best_route, best_distance

    # ------------------------------------------------------------------
    # 3. 2-opt local search improvement
    # ------------------------------------------------------------------
    def two_opt(self, route: List[str]) -> Tuple[List[str], float]:
        """
        Perform 2-opt local search on an existing route.

        The input route should already be a valid loop, e.g.
            ['Depot', 'C1', 'C2', 'C3', 'Depot']

        2-opt idea:
        -----------
        - Select two edges (A-B) and (C-D).
        - Reverse the section between B and C.
        - If the new route is shorter, keep it.
        - Repeat until no further improvement is found.

        Complexity: roughly O(n^2) per pass for n nodes,
        but for small n (your assignment) it's very manageable.
        """
        if len(route) < 4:
            # Not enough nodes to improve
            return route, self._total_route_distance(route)

        best_route = route[:]
        best_distance = self._total_route_distance(best_route)
        improved = True

        while improved:
            improved = False

            # i and k are the start and end indices of the segment to reverse
            # We avoid index 0 and the last index (they are both 'Depot').
            for i in range(1, len(best_route) - 2):
                for k in range(i + 1, len(best_route) - 1):
                    new_route = self._two_opt_swap(best_route, i, k)
                    new_distance = self._total_route_distance(new_route)

                    if new_distance < best_distance:
                        best_route = new_route
                        best_distance = new_distance
                        improved = True
                        # Restart the search from the beginning of the route
                        break
                if improved:
                    break

        return best_route, best_distance

    def _two_opt_swap(self, route: List[str], i: int, k: int) -> List[str]:
        """
        Returns a new route where the segment route[i:k+1] has been reversed.

        Example:
            route = [A, B, C, D, E, F]
            i = 2 (C), k = 4 (E)
            -> [A, B, E, D, C, F]
        """
        new_route = (
            route[0:i] +
            list(reversed(route[i:k + 1])) +
            route[k + 1:]
        )
        return new_route

    def _total_route_distance(self, route: List[str]) -> float:
        """
        Compute the total distance along a particular route loop.
        """
        total = 0.0
        for idx in range(len(route) - 1):
            total += self._distance(route[idx], route[idx + 1])
        return total
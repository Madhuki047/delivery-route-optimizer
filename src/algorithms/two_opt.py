"""
Standalone implementation of the 2-opt local search improvement for TSP routes.

This file is useful for:
- Keeping the 2-opt algorithm separate for comparison in your report.
- Re-using 2-opt with different initial routes (not only nearest neighbour).

The NearestNeighbourTSP class can internally call this function, or you
can use it directly in experiments / benchmarking.
"""

from typing import List, Callable


def two_opt(route: List[str],
            distance_fn: Callable[[str, str], float]) -> (List[str], float):
    """
    Apply 2-opt local search to a given TSP route.

    Parameters
    ----------
    route : list[str]
        A *complete loop* of node names, e.g.
            ['Depot', 'C1', 'C2', 'C3', 'Depot']
        Assumes route[0] == route[-1].

    distance_fn : function(a: str, b: str) -> float
        A callback that returns the distance between two node names.
        This keeps the 2-opt code independent of how distance is computed
        (geodesic, Euclidean, road distance, etc.)

    Returns
    -------
    (new_route, total_distance)
        new_route is the locally improved route (still a loop),
        total_distance is its total length using distance_fn.

    Complexity
    ----------
    In the worst case, 2-opt is O(n^2) per pass and can run multiple
    passes until no improvement is found. For small n (like this assignment),
    it is perfectly acceptable and gives noticeably better routes than
    plain nearest neighbour.
    """
    if len(route) < 4:
        # Too small to improve (need at least 3 edges in a loop)
        return route, _route_distance(route, distance_fn)

    best_route = route[:]
    best_distance = _route_distance(best_route, distance_fn)
    improved = True

    # Continue attempting improvements until a full pass gives no gain
    while improved:
        improved = False

        # i and k are the start and end of the segment to reverse
        # We avoid index 0 and last index (they are the same depot node)
        for i in range(1, len(best_route) - 2):
            for k in range(i + 1, len(best_route) - 1):
                new_route = _two_opt_swap(best_route, i, k)
                new_distance = _route_distance(new_route, distance_fn)

                if new_distance < best_distance:
                    best_route = new_route
                    best_distance = new_distance
                    improved = True
                    # Break to restart search from beginning with new route
                    break
            if improved:
                break

    return best_route, best_distance


def _two_opt_swap(route: List[str], i: int, k: int) -> List[str]:
    """
    Returns a new route where the section route[i:k+1] has been reversed.

    This is the fundamental 2-opt operation:
      ... A - B ---- C - D ...
    becomes:
      ... A - C ---- B - D ...
    """
    new_route = (
        route[0:i] +
        list(reversed(route[i:k + 1])) +
        route[k + 1:]
    )
    return new_route


def _route_distance(route: List[str],
                    distance_fn: Callable[[str, str], float]) -> float:
    """Utility to compute total length of a route loop."""
    total = 0.0
    for idx in range(len(route) - 1):
        total += distance_fn(route[idx], route[idx + 1])
    return total

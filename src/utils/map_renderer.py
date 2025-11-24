"""
map_renderer.py
----------------

Responsible ONLY for rendering a route onto a map.

- Takes an ordered list of location names (a route loop).
- Uses the locations dict to get coordinates.
- Tries to request a road-following path from OpenRouteService (ORS).
- If ORS fails (bad key, no internet, quota exceeded), falls back to
  straight line segments between locations.
- Saves the result to 'nearest_delivery.html' which the GUI displays.

IMPORTANT:
- This file does NOT run any algorithms.
- It does NOT change the route.
- It only draws what it is given.
"""

from typing import Dict, List

import folium
import openrouteservice
from openrouteservice import exceptions as ors_exceptions

from src.models.location import Location


def render_map_with_fallback(route: List[str],
                             locations: Dict[str, Location]) -> None:
    """
    Render a route onto a folium map, using ORS if possible.

    Parameters
    ----------
    route : list[str]
        Sequence of location names representing a *complete loop*, e.g.
        ['Depot', 'Customer1', 'Customer2', 'Depot'].

    locations : dict[str, Location]
        Mapping from location names to Location objects.

    Behaviour
    ---------
    - First tries to get a realistic driving path from ORS.
    - If that fails for any reason, falls back to straight-line
      segments between the location coordinates.

    Output
    ------
    Saves the map as 'nearest_delivery.html' in the project root.
    """
    if not route:
        # Nothing to draw
        return

    # Convert route into (lat, lon) coordinate list for fallback
    coord_list = [locations[name].as_tuple for name in route]

    # Try to get road-following path from ORS
    road_path_latlon = None
    try:
        # NOTE: replace this with your real ORS key
        client = openrouteservice.Client(key="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjE5YzI4NjBkYWEzMDQwZmRhODkyYmIzNGM2N2IzMDJjIiwiaCI6Im11cm11cjY0In0=")

        # ORS expects [lon, lat] pairs
        route_coords = [
            [locations[name].longitude, locations[name].latitude]
            for name in route
        ]

        road = client.directions(
            coordinates=route_coords,
            profile="driving-car",
            format="geojson"
        )

        geometry = road["features"][0]["geometry"]["coordinates"]
        # Convert back to (lat, lon) for folium
        road_path_latlon = [(lat, lon) for lon, lat in geometry]

    except (ors_exceptions.ApiError, Exception):
        # Fallback: straight lines between our own coordinates
        road_path_latlon = coord_list

    # Create the map centred on the first point in the route
    m = folium.Map(location=coord_list[0], zoom_start=12)

    # Add markers in route order
    for name in route:
        loc = locations[name]
        folium.Marker(
            location=loc.as_tuple,
            popup=loc.name
        ).add_to(m)

    # Add polyline for the route path
    folium.PolyLine(
        locations=road_path_latlon,
        color="red",
        weight=2.5
    ).add_to(m)

    # Save HTML file for the GUI to embed
    m.save("nearest_delivery.html")

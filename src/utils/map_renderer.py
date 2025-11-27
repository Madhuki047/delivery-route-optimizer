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

from typing import Dict, List, Optional

import folium
import openrouteservice
from openrouteservice import exceptions as ors_exceptions

from src.models.location import Location


class MapRenderer:
    """
    Responsible for taking a route (list of location names) and
    drawing it onto a folium map.

    If ORS fails, falls back to straight-line segments.
    """

    def __init__(self, ors_api_key: Optional[str] = None):
        """
        Parameters
        ----------
        ors_api_key : str or None
            API key for OpenRouteService. If None, a placeholder is used and
            ORS calls will probably fail, triggering the fallback.
        """
        self.ors_api_key = ors_api_key or "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjE5YzI4NjBkYWEzMDQwZmRhODkyYmIzNGM2N2IzMDJjIiwiaCI6Im11cm11cjY0In0="

    # ------------------------------------------------------------------
    def render_route(self,
                     route: List[str],
                     locations: Dict[str, Location]) -> None:
        """
        Render the given route and save it as 'nearest_delivery.html'.

        Parameters
        ----------
        route : list[str]
            Sequence of location names representing a complete loop.
        locations : dict[str, Location]
            Mapping from name -> Location.
        """
        if not route:
            return

        coord_list = [locations[name].as_tuple for name in route]

        road_path_latlon = None

        # Try to get a road-following path from ORS
        try:
            client = openrouteservice.Client(key=self.ors_api_key)

            coords_lonlat = [
                [locations[name].longitude, locations[name].latitude]
                for name in route
            ]

            road = client.directions(
                coordinates=coords_lonlat,
                profile="driving-car",
                format="geojson"
            )
            geometry = road["features"][0]["geometry"]["coordinates"]
            road_path_latlon = [(lat, lon) for lon, lat in geometry]

        except (ors_exceptions.ApiError, Exception):
            # Fallback: connect points directly
            road_path_latlon = coord_list

        # Build folium map
        m = folium.Map(location=coord_list[0], zoom_start=12)

        for name in route:
            loc = locations[name]
            folium.Marker(
                location=loc.as_tuple,
                popup=loc.name
            ).add_to(m)

        folium.PolyLine(
            locations=road_path_latlon,
            color="red",
            weight=2.5
        ).add_to(m)

        m.save("nearest_delivery.html")

"""
geocoding.py
------------

Geocoder class that uses OpenRouteService to look up latitude/longitude
for postcodes / addresses.
"""

from typing import Optional, Tuple
import requests


class Geocoder:
    """
    Uses OpenRouteService geocoding API.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    # ------------------------------------------------------------------    
    def geocode(self, query: str) -> Optional[Tuple[float, float]]:
        """
        Return (lat, lon) for a query, or None if no result.

        Raises RuntimeError for network / API errors (bad key, quota, etc.).
        """
        url = "https://api.openrouteservice.org/geocode/search"
        params = {
            "api_key": self.api_key,
            "text": query,
            "size": 1
        }

        try:
            response = requests.get(url, params=params, timeout=10)
        except Exception as e:
            raise RuntimeError(f"Network error talking to ORS: {e}")

        if response.status_code != 200:
            try:
                data = response.json()
                msg = data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            raise RuntimeError(f"ORS geocoding error ({response.status_code}): {msg}")

        data = response.json()
        if "features" not in data or len(data["features"]) == 0:
            return None

        coords = data["features"][0]["geometry"]["coordinates"]
        lon, lat = coords[0], coords[1]
        return lat, lon

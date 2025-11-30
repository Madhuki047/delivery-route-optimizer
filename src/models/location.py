from dataclasses import dataclass
from typing import Tuple

@dataclass
class Location:
    # Represents a physical point used by the algorithms.

    name: str
    latitude: float
    longitude: float

    @property
    def as_tuple(self) -> Tuple[float, float]:
        # Returns a (lat, lon) tuple.
        # What geopy and folium expect.- Keeping it as a property avoids repeating (lat, lon) everywhere.
        return self.latitude, self.longitude

    def __str__(self) -> str:
        # Nice string representation for debugging / logging.
        return f"{self.name} ({self.latitude:.5f}, {self.longitude:.5f})"
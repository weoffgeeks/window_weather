"""Utilities for resolving a ZIP code to NWS grid metadata via api.weather.gov.
- Converts a U.S. ZIP code to latitude/longitude using Zippopotam.us
- Queries NOAA/NWS `https://api.weather.gov/points/{lat},{lon}` to discover the relevant forecast endpoints

References:
- NWS API docs: https://api.weather.gov/
- Zippopotam API: https://api.zippopotam.us/
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests



@dataclass
class Coordinates:
    latitude: float
    longitude: float


@dataclass
class PointsMetadata:
    office: str
    grid_x: int
    grid_y: int
    forecast: str
    forecast_hourly: str
    forecast_grid_data: str


class LocationHelper:
    """Helper to resolve ZIP to coordinates and NWS grid metadata."""

    def __init__(self, user_agent: Optional[str] = None) -> None:
        self.session = requests.Session()
        # NWS requires a descriptive User-Agent with contact info
        ua = user_agent or os.getenv("WINDOW_WEATHER_USER_AGENT") or "WindowWeather/1.0 (contact: you@example.com)"
        self.session.headers.update({
            "User-Agent": ua,
            "Accept": "application/geo+json, application/json"
        })

    def _get(self, url: str, *, timeout: float = 15.0) -> Dict[str, Any]:
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def zip_to_coordinates(self, zip_code: str) -> Coordinates:
        """Resolve a U.S. ZIP code to latitude/longitude
        Args:
            zip_code: 5-digit U.S. ZIP code
        Returns:
            Coordinates(latitude, longitude)
        """
        url = f"https://api.zippopotam.us/us/{zip_code}"
        data = self._get(url)

        places = data.get("places") or []
        if not places:
            raise ValueError(f"No places found for ZIP {zip_code}")

        place0 = places[0]
        try:
            lat = float(place0["latitude"])  # type: ignore[index]
            lon = float(place0["longitude"])  # type: ignore[index]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid coordinate data for ZIP {zip_code}") from exc

        return Coordinates(latitude=lat, longitude=lon)

    def points_metadata(self, coords: Coordinates) -> PointsMetadata:
        """Query NWS /points to discover forecast endpoints for given coordinates."""
        url = f"https://api.weather.gov/points/{coords.latitude:.4f},{coords.longitude:.4f}"
        data = self._get(url)

        properties: Dict[str, Any] = data.get("properties") or {}
        grid_id: Optional[str] = properties.get("gridId")
        grid_x: Optional[int] = properties.get("gridX")
        grid_y: Optional[int] = properties.get("gridY")
        forecast: Optional[str] = properties.get("forecast")
        forecast_hourly: Optional[str] = properties.get("forecastHourly")
        forecast_grid_data: Optional[str] = properties.get("forecastGridData")

        if not all([grid_id, grid_x is not None, grid_y is not None, forecast, forecast_hourly, forecast_grid_data]):
            raise ValueError("Incomplete points metadata from NWS API")

        return PointsMetadata(
            office=str(grid_id),
            grid_x=int(grid_x),
            grid_y=int(grid_y),
            forecast=str(forecast),
            forecast_hourly=str(forecast_hourly),
            forecast_grid_data=str(forecast_grid_data),
        )

    def resolve_zip_to_points(self, zip_code: str) -> PointsMetadata:
        """Convenience: ZIP -> Coordinates -> PointsMetadata."""
        coords = self.zip_to_coordinates(zip_code)
        return self.points_metadata(coords)


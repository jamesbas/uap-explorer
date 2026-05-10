"""Location normalization with confidence labels for the Phase 3 map view.

The CSV uses free-form `incident_location` strings. This module maps the known
values in the archive to lat/lon coordinates with a confidence label per the
spec:

    Exact       — specific place
    Approximate — state or region
    Broad       — country or area
    Unknown     — not mappable
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class LocationCoord:
    label: str
    lat: float
    lon: float
    confidence: str  # exact | approximate | broad | unknown


# Curated lookup covering every distinct value currently in uap-csv.csv.
# Keys are case-insensitive matches against `incident_location`.
LOCATION_LOOKUP: Dict[str, LocationCoord] = {
    # Exact / cities
    "detroit, mi": LocationCoord("Detroit, MI", 42.3314, -83.0458, "exact"),
    # Approximate (states, named seas, regions)
    "western united states": LocationCoord(
        "Western United States", 39.5, -111.0, "approximate"
    ),
    "southern united states": LocationCoord(
        "Southern United States", 33.5, -86.0, "approximate"
    ),
    "arabian gulf": LocationCoord("Arabian Gulf", 26.5, 51.5, "approximate"),
    "mediterranean sea": LocationCoord("Mediterranean Sea", 35.0, 18.0, "approximate"),
    "middle east": LocationCoord("Middle East", 30.0, 45.0, "approximate"),
    "gulf of oman": LocationCoord("Gulf of Oman", 24.5, 58.5, "approximate"),
    "aegean sea": LocationCoord("Aegean Sea", 38.5, 25.0, "approximate"),
    "arabian sea": LocationCoord("Arabian Sea", 14.0, 65.0, "approximate"),
    "gulf of aden": LocationCoord("Gulf of Aden", 12.5, 48.0, "approximate"),
    "strait of hormuz": LocationCoord("Strait of Hormuz", 26.5, 56.25, "approximate"),
    "east china sea": LocationCoord("East China Sea", 30.0, 125.0, "approximate"),
    "pacific ocean": LocationCoord("Pacific Ocean", 0.0, -160.0, "approximate"),
    "pacific time zone": LocationCoord("Pacific Time Zone", 39.0, -120.0, "approximate"),
    "indo-pacom": LocationCoord("Indo-PACOM Area", 10.0, 130.0, "approximate"),
    # Broad (countries / large regions)
    "united states": LocationCoord("United States", 39.5, -98.35, "broad"),
    "syria": LocationCoord("Syria", 35.0, 38.0, "broad"),
    "iraq": LocationCoord("Iraq", 33.0, 44.0, "broad"),
    "iran": LocationCoord("Iran", 32.0, 53.0, "broad"),
    "greece": LocationCoord("Greece", 39.0, 22.0, "broad"),
    "germany": LocationCoord("Germany", 51.0, 10.0, "broad"),
    "netherlands": LocationCoord("Netherlands", 52.1, 5.3, "broad"),
    "azerbaijan": LocationCoord("Azerbaijan", 40.4, 47.6, "broad"),
    "djibouti": LocationCoord("Djibouti", 11.6, 43.1, "broad"),
    "japan": LocationCoord("Japan", 36.0, 138.0, "broad"),
    "papua new guinea": LocationCoord("Papua New Guinea", -6.3, 143.95, "broad"),
    "kazakhstan": LocationCoord("Kazakhstan", 48.0, 68.0, "broad"),
    "georgia": LocationCoord("Georgia", 42.3, 43.4, "broad"),
    "turkmenistan": LocationCoord("Turkmenistan", 39.0, 59.0, "broad"),
    "mexico": LocationCoord("Mexico", 23.6, -102.5, "broad"),
    "united arab emirates": LocationCoord("United Arab Emirates", 24.0, 54.0, "broad"),
    "north america": LocationCoord("North America", 50.0, -100.0, "broad"),
    # Off-Earth — render with a special marker tier
    "moon": LocationCoord("Moon (lunar surface)", 0.0, 0.0, "off-earth"),
    "low earth orbit": LocationCoord("Low Earth Orbit", 0.0, 0.0, "off-earth"),
}


def lookup(raw: Optional[str]) -> Optional[LocationCoord]:
    if not raw:
        return None
    return LOCATION_LOOKUP.get(raw.strip().lower())


def confidence_for(raw: Optional[str]) -> str:
    coord = lookup(raw)
    if not coord:
        return "unknown"
    return coord.confidence


def all_known_locations() -> List[str]:
    return sorted({c.label for c in LOCATION_LOOKUP.values()})

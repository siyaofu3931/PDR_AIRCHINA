"""
GCJ-02 (China "Mars" coordinates) ↔ WGS-84 conversion.

Scenario: Phone in China reports location; our map is OpenStreetMap (WGS-84).
In mainland China, device/API often returns GCJ-02. Plotting GCJ-02 on OSM causes
~50–700 m offset. We convert GCJ-02 → WGS-84 so positions align with OSM.

Reference: https://zh.wikipedia.org/wiki/中华人民共和国地理数据限制
Algorithm: same as wandergis/coordtransform; gcj02_to_wgs84 uses iterative reverse correction.
"""

import math
from typing import Tuple

# Krasovsky 1940 ellipsoid (used in Chinese GCJ-02)
_A = 6378245.0
_EE = 0.00669342162296594323

# China bounds (approx): don't apply transform outside
_LON_MIN, _LON_MAX = 73.66, 135.05
_LAT_MIN, _LAT_MAX = 3.86, 53.55


def _out_of_china(lon: float, lat: float) -> bool:
    """True if (lon, lat) is outside mainland China bounds."""
    return not (_LON_MIN < lon < _LON_MAX and _LAT_MIN < lat < _LAT_MAX)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
    ret += 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y
    ret += 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lat: float, lon: float) -> Tuple[float, float]:
    """Convert WGS-84 (GPS) to GCJ-02 (China map). No-op outside China."""
    if _out_of_china(lon, lat):
        return (lat, lon)
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / (_A * (1 - _EE) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    return (lat + dlat, lon + dlon)


def gcj02_to_wgs84(lat: float, lon: float, iterations: int = 3) -> Tuple[float, float]:
    """Convert GCJ-02 (China device) to WGS-84 (OSM). Use for positions to plot on OpenStreetMap."""
    if _out_of_china(lon, lat):
        return (lat, lon)
    wgs_lat, wgs_lon = lat, lon
    for _ in range(iterations):
        gcj_lat, gcj_lon = wgs84_to_gcj02(wgs_lat, wgs_lon)
        wgs_lat += lat - gcj_lat
        wgs_lon += lon - gcj_lon
    return (wgs_lat, wgs_lon)

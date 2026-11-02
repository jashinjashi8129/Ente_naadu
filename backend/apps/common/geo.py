import math
from decimal import Decimal

def is_valid_coord(lat, lon):
    """
    Validates latitude and longitude ranges.
    Latitude: -90.0 to +90.0
    Longitude: -180.0 to +180.0
    """
    if lat is None or lon is None:
        return False
    try:
        f_lat = float(lat)
        f_lon = float(lon)
        return -90.0 <= f_lat <= 90.0 and -180.0 <= f_lon <= 180.0
    except (ValueError, TypeError):
        return False


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates great-circle distance between two points on the Earth
    using the Haversine formula.
    Returns distance in kilometers (rounded to 2 decimal places), or None if invalid.
    """
    if not is_valid_coord(lat1, lon1) or not is_valid_coord(lat2, lon2):
        return None

    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        # Earth's mean radius in kilometers
        R = 6371.0

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (math.sin(dlat / 2.0) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2.0) ** 2)

        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        distance_km = R * c
        return round(distance_km, 2)
    except Exception:
        return None


def get_bounding_box(lat, lon, radius_km):
    """
    Calculates a min/max latitude and longitude bounding box for a given radius in km.
    Used for efficient DB-level pre-filtering before exact Haversine sorting.
    """
    if not is_valid_coord(lat, lon) or radius_km <= 0:
        return None

    f_lat = float(lat)
    f_lon = float(lon)
    f_radius = float(radius_km)

    # 1 degree of latitude is roughly 111.0 km
    lat_delta = f_radius / 111.0
    min_lat = max(-90.0, f_lat - lat_delta)
    max_lat = min(90.0, f_lat + lat_delta)

    # 1 degree of longitude is roughly 111.0 * cos(latitude) km
    cos_lat = math.cos(math.radians(f_lat))
    if cos_lat > 0.00001:
        lon_delta = f_radius / (111.0 * cos_lat)
    else:
        lon_delta = 180.0

    min_lon = max(-180.0, f_lon - lon_delta)
    max_lon = min(180.0, f_lon + lon_delta)

    return {
        'min_lat': Decimal(str(round(min_lat, 6))),
        'max_lat': Decimal(str(round(max_lat, 6))),
        'min_lon': Decimal(str(round(min_lon, 6))),
        'max_lon': Decimal(str(round(max_lon, 6)))
    }


def approximate_coord(lat, lon, precision_decimals=2):
    """
    Fuzzes coordinates to `precision_decimals` decimal places (~1 km fuzzing at 2 decimals).
    Used to shield residential exactness for users selecting approximate sharing.
    """
    if not is_valid_coord(lat, lon):
        return None, None
    return round(float(lat), precision_decimals), round(float(lon), precision_decimals)


def bounding_box(lat, lon, radius_km):
    """
    Convenience helper returning (min_lat, max_lat, min_lon, max_lon) as floats.
    """
    bbox = get_bounding_box(lat, lon, radius_km)
    if not bbox:
        return None, None, None, None
    return float(bbox['min_lat']), float(bbox['max_lat']), float(bbox['min_lon']), float(bbox['max_lon'])


def google_maps_directions_url(dest_lat, dest_lng, origin_lat=None, origin_lng=None):
    """Generates standard Google Maps / Native Maps directions URL."""
    if not is_valid_coord(dest_lat, dest_lng):
        return ""
    url = f"https://www.google.com/maps/dir/?api=1&destination={dest_lat},{dest_lng}"
    if is_valid_coord(origin_lat, origin_lng):
        url += f"&origin={origin_lat},{origin_lng}"
    return url


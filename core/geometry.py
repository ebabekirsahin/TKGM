from shapely.geometry import shape
from shapely.validation import explain_validity

def geometry_summary(geometry):
    if not geometry:
        return None
    try:
        geom = shape(geometry)
        if geom.is_empty or geom.geom_type not in ("Polygon","MultiPolygon") or not geom.is_valid:
            return None
        point = geom.representative_point()
        # Alan yalnızca WGS84 koordinatlarından derece² olarak hesaplanmamalı.
        # Bu nedenle m² alanı burada bilinmiyor; None döndürülür.
        return (float(point.y), float(point.x), None)
    except Exception:
        return None

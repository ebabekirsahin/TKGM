"""Discover and query openly shared ArcGIS Feature Services.

Only public ArcGIS Online items are queried. A layer is accepted for automatic
matching only when it exposes cadastral identifiers AND administrative-area
attributes, so a block/parcel collision across districts cannot silently match.
"""
import re
import requests
from urllib.parse import urlparse

SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"
HEADERS = {"User-Agent": "TasinmazHarita/1.0"}
ADMIN_ALIASES = {
    "il": ["il", "il_adi", "iladi", "province", "city"],
    "ilce": ["ilce", "ilce_adi", "ilceadi", "district"],
    "mahalle": ["mahalle", "mahalle_adi", "mahalleadi", "neighborhood", "koy"],
}
ADA_ALIASES = ["ada", "ada_no", "adano", "block"]
PARSEL_ALIASES = ["parsel", "parsel_no", "parselno", "parcel"]
COMBINED_ALIASES = ["adaparsel", "ada_parsel", "ada-parsel"]

def _norm(value):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(c for c in s if c.isalnum())

def _field(fields, aliases):
    names = {_norm(f.get("name")): f.get("name") for f in fields}
    for alias in aliases:
        if _norm(alias) in names:
            return names[_norm(alias)]
    return None

def _safe_service_url(url):
    p = urlparse(url or "")
    return p.scheme == "https" and p.hostname and (p.hostname == "arcgis.com" or p.hostname.endswith(".arcgis.com") or p.hostname.endswith(".arcgisonline.com"))

def discover_public_parcel_features(rows, max_items=12, max_records_per_layer=5000):
    """Search public ArcGIS Online catalogue and return validated parcel features."""
    terms = sorted({r.get("ilce", "") for r in rows if r.get("ilce")})
    queries = ["parsel", "kadastro parsel"]
    if terms:
        queries.extend([f'"{t}" parsel' for t in terms[:5]])
    seen_items, found = set(), []
    session = requests.Session()
    for q in queries:
        try:
            sr = session.get(SEARCH_URL, params={
                "f": "json", "q": q + ' AND type:"Feature Service"',
                "num": min(max_items, 20), "sortField": "numViews",
                "sortOrder": "desc"
            }, timeout=20, headers=HEADERS)
            sr.raise_for_status()
            items = sr.json().get("results", [])
        except Exception:
            continue
        for item in items:
            item_id = item.get("id")
            if not item_id or item_id in seen_items:
                continue
            seen_items.add(item_id)
            service_url = item.get("url")
            if not _safe_service_url(service_url):
                continue
            try:
                meta = session.get(service_url.rstrip("/") + "/0", params={"f":"json"}, timeout=20, headers=HEADERS)
                meta.raise_for_status()
                layer = meta.json()
                fields = layer.get("fields", [])
                admin_fields = {k: _field(fields, v) for k,v in ADMIN_ALIASES.items()}
                ada_field = _field(fields, ADA_ALIASES)
                parcel_field = _field(fields, PARSEL_ALIASES)
                combined_field = _field(fields, COMBINED_ALIASES)
                # Reject ambiguous datasets lacking the full administrative key.
                if not all(admin_fields.values()) or not (combined_field or (ada_field and parcel_field)):
                    continue
                oid = layer.get("objectIdField") or _field(fields, ["OBJECTID", "FID"])
                if not oid:
                    continue
                ids_resp = session.get(service_url.rstrip("/") + "/0/query", params={
                    "f":"json", "where":"1=1", "returnIdsOnly":"true"
                }, timeout=30, headers=HEADERS)
                ids_resp.raise_for_status()
                ids = ids_resp.json().get("objectIds", [])[:max_records_per_layer]
                for start in range(0, len(ids), 200):
                    batch = ids[start:start+200]
                    if not batch: continue
                    data_resp = session.get(service_url.rstrip("/") + "/0/query", params={
                        "f":"json", "objectIds":",".join(map(str,batch)),
                        "outFields":"*", "returnGeometry":"true", "outSR":"4326"
                    }, timeout=40, headers=HEADERS)
                    data_resp.raise_for_status()
                    for feat in data_resp.json().get("features", []):
                        attrs = feat.get("attributes") or {}
                        props = dict(attrs)
                        if combined_field and attrs.get(combined_field) is not None:
                            combined = str(attrs[combined_field]).strip()
                            # Retain the source's original composite value as ADA-PAFTA.
                            props.setdefault("ADA-PAFTA", combined)
                            # Try common separators to expose separate keys too.
                            parts = re.split(r"[/\\-]", combined)
                            if len(parts) == 2:
                                props.setdefault("ADA", parts[0].strip())
                                props.setdefault("PARSEL", parts[1].strip())
                        geom = feat.get("geometry")
                        if not geom:
                            continue
                        # ArcGIS polygon rings -> GeoJSON Polygon/MultiPolygon.
                        rings = geom.get("rings")
                        if not rings:
                            continue
                        spatial = geom.get("spatialReference", {})
                        wkid = spatial.get("latestWkid") or spatial.get("wkid") or 4326
                        if wkid not in (4326, 4283):
                            # Query requested outSR 4326; reject unexpected CRS rather than misplot.
                            continue
                        geom_type = "Polygon" if len(rings) == 1 else "Polygon"
                        found.append({
                            "type":"Feature",
                            "geometry":{"type":geom_type,"coordinates":rings},
                            "properties":props,
                            "source":f"ArcGIS açık veri: {item.get('title','Feature Service')} ({service_url})"
                        })
            except Exception:
                # One unavailable public service must not stop other catalogue candidates.
                continue
    return found

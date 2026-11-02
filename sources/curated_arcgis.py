"""Curated, verified public ArcGIS parcel services in Turkey.

Coverage is limited to the named administrative areas. Queries are filtered
using the uploaded Excel's cadastral identifiers; no nationwide coverage is implied.
"""
import requests
from pyproj import Transformer

SERVICES = [
    {
        "name": "Kastamonu İl Özel İdaresi – TKGM_PUBLIC",
        "url": "https://e-imar.kastamonuozelidare.gov.tr/arcgis/rest/services/IDARE_PUBLIC/TKGM_PUBLIC/FeatureServer/0",
        "province": "Kastamonu", "district": None,
        "ada_field": "adano", "parcel_field": "parselno",
        "combined_field": None, "wkid": 4326,
    },
    {
        "name": "Pursaklar Belediyesi – PARSEL",
        "url": "https://cbs.pursaklar.bel.tr/webgis/rest/services/otomasyon/identify/MapServer/0",
        "province": "Ankara", "district": "Pursaklar",
        "ada_field": None, "parcel_field": None,
        "combined_field": "adaparsel", "wkid": 3857,
    },
]

def _n(value):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(c for c in s if c.isalnum())

def _sql(v):
    return "'" + str(v).replace("'", "''") + "'"

def _polygon(rings, wkid):
    if wkid == 4326:
        convert = lambda x,y: (x,y)
    else:
        transformer = Transformer.from_crs(f"EPSG:{wkid}", "EPSG:4326", always_xy=True)
        convert = transformer.transform
    converted = [[list(convert(x,y)) for x,y in ring] for ring in rings]
    # ArcGIS polygon rings use orientation to distinguish holes. Keep the
    # service rings as a Polygon; this is adequate for rendering and area tools.
    return {"type":"Polygon","coordinates":converted}

def fetch_curated_public_parcels(rows, max_features=15000):
    session = requests.Session()
    output, notes = [], []
    for cfg in SERVICES:
        province_rows = [r for r in rows if _n(r.get("il")) == _n(cfg["province"])
                         and (not cfg["district"] or _n(r.get("ilce")) == _n(cfg["district"]))]
        if not province_rows:
            continue
        pairs = {(str(r.get("ada_pafta","")).strip(), str(r.get("parsel","")).strip())
                 for r in province_rows if r.get("ada_pafta") and r.get("parsel")}
        if not pairs:
            continue
        try:
            meta = session.get(cfg["url"], params={"f":"json"}, timeout=20)
            meta.raise_for_status()
            info = meta.json()
            wkid = (info.get("extent",{}).get("spatialReference",{}).get("latestWkid")
                    or info.get("extent",{}).get("spatialReference",{}).get("wkid")
                    or cfg["wkid"])
            fields = {f.get("name") for f in info.get("fields",[])}
            if cfg["combined_field"] and cfg["combined_field"] not in fields:
                notes.append(f"{cfg['name']}: adaparsel alanı bulunamadı.")
                continue
            if cfg["ada_field"] and (cfg["ada_field"] not in fields or cfg["parcel_field"] not in fields):
                notes.append(f"{cfg['name']}: ada/parsel alanları bulunamadı.")
                continue
            where_parts = []
            if cfg["combined_field"]:
                for ada, parcel in pairs:
                    for value in (f"{ada}/{parcel}", f"{ada}-{parcel}", f"{ada} {parcel}"):
                        where_parts.append(f"{cfg['combined_field']}={_sql(value)}")
            else:
                # Bounded pair queries. Limit OR clauses to keep URL and SQL size manageable.
                for ada, parcel in list(pairs)[:1500]:
                    where_parts.append(f"({cfg['ada_field']}={_sql(ada)} AND {cfg['parcel_field']}={_sql(parcel)})")
            for start in range(0, len(where_parts), 40):
                where = " OR ".join(where_parts[start:start+40])
                resp = session.get(cfg["url"].rstrip("/") + "/query", params={
                    "f":"json", "where":where, "outFields":"*",
                    "returnGeometry":"true", "outSR":"4326",
                    "resultRecordCount":min(1000,max_features)
                }, timeout=45)
                resp.raise_for_status()
                payload = resp.json()
                if payload.get("error"):
                    raise RuntimeError(payload["error"].get("message","ArcGIS query error"))
                for feature in payload.get("features",[]):
                    attrs = feature.get("attributes") or {}
                    geom = feature.get("geometry") or {}
                    rings = geom.get("rings")
                    if not rings:
                        continue
                    spatial = geom.get("spatialReference",{})
                    source_wkid = spatial.get("latestWkid") or spatial.get("wkid") or wkid
                    # outSR=4326 should return WGS84; convert only when service ignores it.
                    geometry = _polygon(rings, source_wkid)
                    props = dict(attrs)
                    props["IL"] = cfg["province"]
                    if cfg["district"]:
                        props["ILCE"] = cfg["district"]
                    if cfg["ada_field"]:
                        props["ADA"] = attrs.get(cfg["ada_field"])
                        props["PARSEL"] = attrs.get(cfg["parcel_field"])
                    elif cfg["combined_field"]:
                        combined = str(attrs.get(cfg["combined_field"],"")).strip()
                        props["ADA-PAFTA"] = combined
                        # Preserve source composite; split common forms for the matcher.
                        import re
                        bits = re.split(r"[/\\-]", combined)
                        if len(bits)==2:
                            props["ADA"], props["PARSEL"] = bits[0].strip(), bits[1].strip()
                    output.append({
                        "type":"Feature","geometry":geometry,"properties":props,
                        "source":cfg["name"]
                    })
                    if len(output) >= max_features:
                        return output, notes
        except Exception as exc:
            notes.append(f"{cfg['name']}: {exc}")
    return output, notes
